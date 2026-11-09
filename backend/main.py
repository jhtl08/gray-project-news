from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
