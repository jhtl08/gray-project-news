from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Any, List
import sys
from pathlib import Path

# Add backend dir to path
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from gdelt_api import get_gdelt_json, DEFAULT_QUERY
from db_operations import get_connection, init_db, ingest_json_file
from laya_processes import get_router
import os

app = FastAPI(title="Gray Project News API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GDELTCollectRequest(BaseModel):
    query: Optional[str] = None
    maxrecords: Optional[int] = None
    timespan: Optional[str] = None
    sort: Optional[str] = "datedesc"


class MatchSeedRequest(BaseModel):
    source_type: str
    source_id: int


@app.on_event("startup")
def startup_event():
    try:
        init_db()
    except Exception as e:
        print(f"Warning: init_db failed: {e}")
    try:
        get_router()
    except Exception as e:
        print(f"Warning: model preload failed: {e}")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/news/collect")
def collect_news(req: GDELTCollectRequest, background_tasks: BackgroundTasks):
    try:
        query = req.query if req.query and req.query.strip() else DEFAULT_QUERY
        data = get_gdelt_json(
            query=query,
            maxrecords=req.maxrecords,
            timespan=req.timespan,
            sort=req.sort or "datedesc",
        )
        ingested = None
        ingest_error = None
        try:
            from db_operations import ingest_latest_json

            ingested = ingest_latest_json(score=False)
            from db_operations import backfill_disruptiveness_scores

            background_tasks.add_task(backfill_disruptiveness_scores)
        except Exception as e:
            ingest_error = str(e)

        return {
            "success": True,
            "articles": len(data.get("articles", [])),
            "query_used": query,
            "maxrecords": req.maxrecords if req.maxrecords is not None else 200,
            "timespan": req.timespan if req.timespan is not None else "1h",
            "sort": req.sort or "datedesc",
            "ingested": ingested,
            "ingest_error": ingest_error,
            "data": data,
        }
    except Exception as e:
        import traceback

        error_detail = f"{type(e).__name__}: {str(e)}"
        traceback_str = traceback.format_exc()
        raise HTTPException(status_code=500, detail={"error": error_detail, "traceback": traceback_str})


@app.get("/api/news")
def get_news(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    order_by: str = Query("seendate", regex="^(seendate|created_at|id|disruptiveness_score)$"),
    order_dir: str = Query("desc", regex="^(asc|desc)$"),
):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                order_clause = f"{order_by} {'DESC' if order_dir == 'desc' else 'ASC'} NULLS LAST"
                cur.execute(
                    f"""
                    SELECT id, query, url, title, seendate, language, sourcecountry, created_at, disruptiveness_score
                    FROM news
                    ORDER BY {order_clause}
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                rows = cur.fetchall()
                cur.execute("SELECT COUNT(*) FROM news")
                total = cur.fetchone()[0]
        news = []
        for row in rows:
            news.append(
                {
                    "id": row[0],
                    "query": row[1],
                    "url": row[2],
                    "title": row[3],
                    "seendate": row[4].isoformat() if row[4] else None,
                    "language": row[5],
                    "sourcecountry": row[6],
                    "created_at": row[7].isoformat() if row[7] else None,
                    "disruptiveness_score": row[8],
                }
            )
        return {"news": news, "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.delete("/api/news")
def delete_news(start: Optional[str] = Query(None), end: Optional[str] = Query(None)):
    try:
        from db_operations import delete_news_by_date_range

        deleted = delete_news_by_date_range(start=start, end=end)
        return {"deleted": deleted, "start": start, "end": end}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bets/collect")
def collect_bets(limit: Optional[int] = Query(None), background_tasks: BackgroundTasks = None):
    try:
        from polymarket_collector import collect_markets
        from db_operations import ingest_latest_polymarket_file, backfill_bet_scores

        payload = collect_markets()
        ingested = ingest_latest_polymarket_file(score=False)
        if background_tasks is not None:
            background_tasks.add_task(backfill_bet_scores)
        return {
            "success": True,
            "collected": len(payload.get("markets", [])),
            "collected_at": payload.get("collected_at"),
            "ingested": ingested,
            "scoring": "scheduled",
        }
    except Exception as e:
        import traceback

        error_detail = f"{type(e).__name__}: {str(e)}"
        traceback_str = traceback.format_exc()
        raise HTTPException(status_code=500, detail={"error": error_detail, "traceback": traceback_str})


@app.get("/api/bets")
def get_bets(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    order_by: str = Query(
        "collected_at",
        regex="^(collected_at|volume|one_day_price_change|one_week_price_change|one_month_price_change|emotionality_score|status_quo_deviation|end_date|question)$",
    ),
    order_dir: str = Query("desc", regex="^(asc|desc)$"),
    active: Optional[bool] = Query(None),
    is_new: Optional[bool] = Query(None),
    tag: Optional[str] = Query(None),
    min_abs_change: Optional[float] = Query(None),
    has_score: Optional[bool] = Query(None),
):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                where = []
                params: List[Any] = []
                if active is not None:
                    where.append("active = %s")
                    params.append(active)
                if is_new is not None:
                    where.append("is_new = %s")
                    params.append(is_new)
                if tag is not None:
                    where.append("tags ILIKE %s")
                    params.append(f"%{tag}%")
                if min_abs_change is not None:
                    where.append(
                        "(ABS(one_day_price_change) >= %s OR "
                        "ABS(one_week_price_change) >= %s OR "
                        "ABS(one_month_price_change) >= %s)"
                    )
                    params.extend([min_abs_change, min_abs_change, min_abs_change])
                if has_score is not None:
                    if has_score:
                        where.append("emotionality_score IS NOT NULL")
                    else:
                        where.append("emotionality_score IS NULL")
                where_clause = ("WHERE " + " AND ".join(where)) if where else ""

                order_clause = f"{order_by} {'DESC' if order_dir == 'desc' else 'ASC'} NULLS LAST"

                cur.execute(f"SELECT COUNT(*) FROM bets {where_clause}", params)
                total = cur.fetchone()[0]

                cur.execute(
                    f"""
                    SELECT id, polymarket_id, question, slug, condition_id, outcomes, outcome_prices,
                           price, one_hour_price_change, one_day_price_change, one_week_price_change,
                           one_month_price_change, one_year_price_change, volume, volume_24hr, volume_1wk,
                           volume_1mo, volume_1yr, liquidity, best_bid, best_ask, spread, active, closed,
                           archived, is_new, featured, category, tags, event_id, event_title, clob_token_ids,
                           start_date, end_date, polymarket_created_at, polymarket_updated_at,
                           emotionality_score, status_quo_deviation, scored_at, collected_at, url
                    FROM bets
                    {where_clause}
                    ORDER BY {order_clause}
                    LIMIT %s OFFSET %s
                    """,
                    params + [limit, offset],
                )
                rows = cur.fetchall()

        bets = []
        for row in rows:
            bets.append(
                {
                    "id": row[0],
                    "polymarket_id": row[1],
                    "question": row[2],
                    "slug": row[3],
                    "condition_id": row[4],
                    "outcomes": row[5],
                    "outcome_prices": row[6],
                    "price": row[7],
                    "one_hour_price_change": row[8],
                    "one_day_price_change": row[9],
                    "one_week_price_change": row[10],
                    "one_month_price_change": row[11],
                    "one_year_price_change": row[12],
                    "volume": row[13],
                    "volume_24hr": row[14],
                    "volume_1wk": row[15],
                    "volume_1mo": row[16],
                    "volume_1yr": row[17],
                    "liquidity": row[18],
                    "best_bid": row[19],
                    "best_ask": row[20],
                    "spread": row[21],
                    "active": row[22],
                    "closed": row[23],
                    "archived": row[24],
                    "is_new": row[25],
                    "featured": row[26],
                    "category": row[27],
                    "tags": row[28],
                    "event_id": row[29],
                    "event_title": row[30],
                    "clob_token_ids": row[31],
                    "start_date": row[32].isoformat() if row[32] else None,
                    "end_date": row[33].isoformat() if row[33] else None,
                    "polymarket_created_at": row[34].isoformat() if row[34] else None,
                    "polymarket_updated_at": row[35].isoformat() if row[35] else None,
                    "emotionality_score": row[36],
                    "status_quo_deviation": row[37],
                    "scored_at": row[38].isoformat() if row[38] else None,
                    "collected_at": row[39].isoformat() if row[39] else None,
                    "url": row[40],
                }
            )
        return {"bets": bets, "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bets/backfill-scores")
def backfill_bets_scores(limit: Optional[int] = Query(None)):
    try:
        from db_operations import backfill_bet_scores

        return backfill_bet_scores(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




@app.delete("/api/bets")
def delete_bets(start: Optional[str] = Query(None), end: Optional[str] = Query(None)):
    try:
        from db_operations import delete_bets_by_date_range

        deleted = delete_bets_by_date_range(start=start, end=end)
        return {"deleted": deleted, "start": start, "end": end}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _coerce_vector_local(vector):
    try:
        from db_operations import _coerce_vector

        return _coerce_vector(vector)
    except Exception:
        if vector is None:
            return None
        if isinstance(vector, str):
            text = vector.strip()
            return text or None
        try:
            return "[" + ",".join(str(float(x)) for x in vector) + "]"
        except (TypeError, ValueError):
            return None


def _parse_vector_local(value):
    try:
        from db_operations import _parse_vector

        return _parse_vector(value)
    except Exception:
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return [float(x) for x in value]
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("[") and text.endswith("]"):
                text = text[1:-1].strip()
            if not text:
                return []
            try:
                return [float(part.strip()) for part in text.split(",") if part.strip() != ""]
            except ValueError:
                return None
        return None


def _get_embed_fn():
    try:
        import embedding

        fn = getattr(embedding, "embed_texts", None)
        if callable(fn):
            return fn
    except Exception:
        pass
    try:
        from db_operations import _get_embed_texts

        fn = _get_embed_texts()
        if callable(fn):
            return fn
    except Exception:
        pass
    return None


@app.post("/api/matches")
def create_match(req: MatchSeedRequest):
    try:
        source_type = (req.source_type or "").strip().lower()
        if source_type not in ("news", "bet"):
            raise HTTPException(status_code=400, detail="source_type must be 'news' or 'bet'")
        source_id = int(req.source_id)

        from db_operations import get_connection

        if source_type == "news":
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT title, content_vector FROM news WHERE id = %s",
                        (source_id,),
                    )
                    row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="news not found")
            title, content_vector = row[0], row[1]
            text = title
            table = "news"
            vector_col_update = "content_vector"
        else:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT question, content_vector FROM bets WHERE id = %s",
                        (source_id,),
                    )
                    row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="bet not found")
            title, content_vector = row[0], row[1]
            text = title
            table = "bets"
            vector_col_update = "content_vector"

        vector = _parse_vector_local(content_vector)
        if vector is None:
            embed_fn = _get_embed_fn()
            if embed_fn is not None and text:
                try:
                    vectors = embed_fn([str(text)])
                    if vectors:
                        vector = vectors[0]
                        # persist back to source row when possible
                        try:
                            if source_type == "news":
                                from db_operations import store_news_vector

                                store_news_vector(source_id, vector)
                            else:
                                from db_operations import store_bet_vector

                                store_bet_vector(source_id, vector)
                        except Exception:
                            try:
                                with get_connection() as conn:
                                    with conn.cursor() as cur:
                                        cur.execute(
                                            f"UPDATE {table} SET {vector_col_update} = %s WHERE id = %s",
                                            (_coerce_vector_local(vector), source_id),
                                        )
                            except Exception:
                                pass
                except Exception:
                    vector = None

        import json as _json

        metadata = {"source_type": source_type, "source_id": source_id}
        try:
            from db_operations import insert_match_seed

            new_id = insert_match_seed(text=text, vector=vector, metadata=metadata)
        except Exception:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO match_seeds (text, metadata, content_vector) VALUES (%s, %s, %s) RETURNING id",
                        (text, _json.dumps(metadata), _coerce_vector_local(vector)),
                    )
                    new_id = cur.fetchone()[0]

        return {"id": new_id, "source_type": source_type, "source_id": source_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/matches")
def list_matches():
    try:
        from db_operations import get_connection

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, text, metadata, content_vector, created_at FROM match_seeds ORDER BY id DESC"
                )
                rows = cur.fetchall()
        items = []
        for row in rows:
            meta = row[2]
            if isinstance(meta, str):
                try:
                    import json as _json

                    meta = _json.loads(meta)
                except Exception:
                    pass
            source_type = None
            source_id = None
            if isinstance(meta, dict):
                source_type = meta.get("source_type")
                source_id = meta.get("source_id")
            items.append(
                {
                    "id": row[0],
                    "text": row[1],
                    "metadata": meta,
                    "source_type": source_type,
                    "source_id": source_id,
                    "content_vector": _parse_vector_local(row[3]),
                    "created_at": row[4].isoformat() if hasattr(row[4], "isoformat") else row[4],
                }
            )
        return {"matches": items, "total": len(items)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/matches/{match_id}")
def delete_match(match_id: int):
    try:
        from db_operations import get_connection

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM match_seeds WHERE id = %s", (match_id,))
                deleted = cur.rowcount
        if deleted == 0:
            raise HTTPException(status_code=404, detail="match not found")
        return {"deleted": deleted, "id": match_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/matches/{match_id}/related")
def match_related(match_id: int):
    try:
        from db_operations import get_connection

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT text, metadata, content_vector FROM match_seeds WHERE id = %s",
                    (match_id,),
                )
                row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="match not found")
        text, metadata, content_vector = row[0], row[1], row[2]
        if isinstance(metadata, str):
            try:
                import json as _json

                metadata = _json.loads(metadata)
            except Exception:
                metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        source_type = metadata.get("source_type")
        vector = _parse_vector_local(content_vector)
        if vector is None and text:
            embed_fn = _get_embed_fn()
            if embed_fn is not None:
                try:
                    vectors = embed_fn([str(text)])
                    if vectors:
                        vector = vectors[0]
                except Exception:
                    vector = None
        if vector is None:
            return {"items": [], "total": 0}

        vector_literal = _coerce_vector_local(vector)
        if source_type == "news":
            # related bets
            sql = (
                "SELECT id, question, url, 1 - (content_vector <=> %s::vector) AS similarity "
                "FROM bets WHERE content_vector IS NOT NULL "
                "AND 1 - (content_vector <=> %s::vector) >= 0.7 "
                "ORDER BY content_vector <=> %s::vector LIMIT 5"
            )
            params = (vector_literal, vector_literal, vector_literal)
        else:
            sql = (
                "SELECT id, title, url, 1 - (content_vector <=> %s::vector) AS similarity "
                "FROM news WHERE content_vector IS NOT NULL "
                "AND 1 - (content_vector <=> %s::vector) >= 0.7 "
                "ORDER BY content_vector <=> %s::vector LIMIT 5"
            )
            params = (vector_literal, vector_literal, vector_literal)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        items = []
        for r in rows:
            item = {"id": r[0], "similarity": float(r[3]) if r[3] is not None else None}
            if source_type == "news":
                item["question"] = r[1]
                item["url"] = r[2]
            else:
                item["title"] = r[1]
                item["url"] = r[2]
            items.append(item)
        return {"items": items, "total": len(items)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/news/backfill-embeddings")
def backfill_news_embeddings_endpoint(limit: Optional[int] = Query(None)):
    try:
        from db_operations import backfill_news_embeddings

        return backfill_news_embeddings(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bets/backfill-embeddings")
def backfill_bets_embeddings_endpoint(limit: Optional[int] = Query(None)):
    try:
        from db_operations import backfill_bet_embeddings

        return backfill_bet_embeddings(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
