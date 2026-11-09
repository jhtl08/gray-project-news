"""PostgreSQL operations for the gray-project news pipeline.

Uses psycopg 3 (synchronous). The functions are plain Python so they can be
called from FastAPI endpoints directly (regular `def` endpoints run in a
thread pool) or from scripts.

Typical use:
    from db_operations import init_db, ingest_latest_json

    init_db()
    summary = ingest_latest_json()
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import psycopg
from dotenv import load_dotenv

try:
    from laya_processes import score_headlines
except Exception:
    def score_headlines(headlines: list[str]) -> list[int]:
        return [0] * len(headlines)

BASE_DIR = Path(__file__).resolve().parent
# Load backend/.env regardless of the directory the script is run from.
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set (expected in backend/.env)")

DATA_DIR = BASE_DIR / "gdelt_data"
SEENDATE_FORMAT = "%Y%m%dT%H%M%SZ"

# content_vector is left without a fixed dimension because the title-embedding
# model hasn't been chosen yet. Pin it (e.g. VECTOR(768)) when that function
# is added, so an HNSW/IVFFlat index can be created.
CREATE_NEWS_TABLE = """
CREATE TABLE IF NOT EXISTS news (
    id                  BIGSERIAL PRIMARY KEY,
    query               TEXT NOT NULL,
    url                 TEXT NOT NULL UNIQUE,
    title               TEXT UNIQUE,
    seendate            TIMESTAMPTZ,
    language            TEXT,
    sourcecountry       TEXT,
    disruptiveness_score INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

INSERT_NEWS = """
INSERT INTO news (query, url, title, seendate, language, sourcecountry)
VALUES (%(query)s, %(url)s, %(title)s, %(seendate)s, %(language)s, %(sourcecountry)s)
ON CONFLICT DO NOTHING
RETURNING id, title;
"""


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    """Open a connection and commit on success / roll back on error."""
    with psycopg.connect(DATABASE_URL) as conn:
        yield conn


def init_db() -> None:
    """Create the pgvector extension and the news table if they don't exist."""
    with get_connection() as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.execute(CREATE_NEWS_TABLE)
        # Ensure columns/constraints exist for upgrades
        try:
            conn.execute("ALTER TABLE news ADD COLUMN IF NOT EXISTS disruptiveness_score INTEGER;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE news ADD CONSTRAINT news_title_key UNIQUE (title);")
        except Exception:
            pass


def latest_json_file(directory: Path | str = DATA_DIR) -> Path:
    """Return the newest .json file in `directory` (by filename)."""
    directory = Path(directory)
    files = sorted(directory.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"ALERT: No JSON files found in {str(directory)!r}.")
    return files[-1]


def _clean(value: Any) -> str | None:
    """Return a stripped string, or None for empty/missing values."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_seendate(value: Any) -> datetime | None:
    """Parse GDELT's 'YYYYMMDDTHHMMSSZ' stamp into an aware UTC datetime."""
    text = _clean(value)
    if text is None:
        return None
    try:
        return datetime.strptime(text, SEENDATE_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _article_to_row(article: dict[str, Any], query: str) -> dict[str, Any] | None:
    """Map one GDELT article to INSERT_NEWS params; None if it has no url."""
    url = _clean(article.get("url"))
    if url is None:  # url is the dedupe key, so it's required
        return None
    return {
        "query": query,
        "url": url,
        "title": _clean(article.get("title")),
        "seendate": _parse_seendate(article.get("seendate")),
        "language": _clean(article.get("language")),
        "sourcecountry": _clean(article.get("sourcecountry")),
    }


def ingest_json_file(path: Path | str) -> dict[str, Any]:
    """Insert the articles of one GDELT JSON file, skipping existing urls.

    The query is read from the file's top-level "query" key and stored on
    every row. Returns a summary dict with the file, query and row counts.
    """
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)

    query = _clean(payload.get("query"))
    if query is None:
        raise ValueError(f"{path} has no 'query' key")

    articles = payload.get("articles") or []
    rows = [
        row
        for article in articles
        if (row := _article_to_row(article, query)) is not None
    ]

    inserted_rows = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            if rows:
                cur.executemany(INSERT_NEWS, rows, returning=True)
                while True:
                    result = cur.fetchone()
                    if result is not None:
                        inserted_rows.append(result)
                    if not cur.nextset():
                        break
        inserted = len(inserted_rows)

        # Score newly inserted rows by title
        if inserted_rows:
            try:
                titles_to_score = []
                ids_to_score = []
                for row_res in inserted_rows:
                    inserted_id = row_res[0]
                    inserted_title = row_res[1]
                    if inserted_title and inserted_title.strip():
                        titles_to_score.append(inserted_title)
                        ids_to_score.append(inserted_id)
                if titles_to_score:
                    scores = score_headlines(titles_to_score)
                    with conn.cursor() as cur:
                        for inserted_id, score in zip(ids_to_score, scores):
                            cur.execute(
                                "UPDATE news SET disruptiveness_score = %s WHERE id = %s",
                                (int(score), inserted_id),
                            )
            except Exception:
                pass

    return {
        "file": str(path),
        "query": query,
        "total": len(articles),
        "inserted": inserted,
        "skipped": len(articles) - inserted,
    }


def ingest_latest_json(directory: Path | str = DATA_DIR) -> dict[str, Any]:
    """Ingest the most recent JSON file in `directory`."""
    return ingest_json_file(latest_json_file(directory))


def main() -> None:
    init_db()
    summary = ingest_latest_json()
    print(
        f"{summary['file']}: query={summary['query']!r}, "
        f"{summary['inserted']} inserted, {summary['skipped']} skipped "
        f"({summary['total']} articles)"
    )


if __name__ == "__main__":
    main()
