from fastapi import FastAPI, HTTPException, Query
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
def collect_news(req: GDELTCollectRequest):
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

            ingested = ingest_latest_json()
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


@app.post("/api/bets/collect")
def collect_bets(limit: Optional[int] = Query(None)):
    try:
        from polymarket_collector import collect_markets
        from db_operations import ingest_latest_polymarket_file

        payload = collect_markets()
        ingested = ingest_latest_polymarket_file()
        return {
            "success": True,
            "collected": len(payload.get("markets", [])),
            "collected_at": payload.get("collected_at"),
            "ingested": ingested,
            "scoring": None,
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
