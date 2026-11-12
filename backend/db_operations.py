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
import gc
import logging
import os

logger = logging.getLogger(__name__)
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

try:
    from laya_processes import score_bet_emotionality_and_status_quo
except Exception:
    def score_bet_emotionality_and_status_quo(markets: list[str]) -> list[tuple]:
        return [(None, None) for _ in markets]

BASE_DIR = Path(__file__).resolve().parent
# Load backend/.env regardless of the directory the script is run from.
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set (expected in backend/.env)")

DATA_DIR = BASE_DIR / "gdelt_data"
POLYMARKET_DATA_DIR = BASE_DIR / "polymarket_data"
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

CREATE_BETS_TABLE = """
CREATE TABLE IF NOT EXISTS bets (
    id                  BIGSERIAL PRIMARY KEY,
    polymarket_id       TEXT NOT NULL UNIQUE,
    question            TEXT,
    slug                TEXT,
    condition_id        TEXT,
    outcomes            TEXT,
    outcome_prices      TEXT,
    price               DOUBLE PRECISION,
    one_hour_price_change DOUBLE PRECISION,
    one_day_price_change DOUBLE PRECISION,
    one_week_price_change DOUBLE PRECISION,
    one_month_price_change DOUBLE PRECISION,
    one_year_price_change DOUBLE PRECISION,
    volume              DOUBLE PRECISION,
    volume_24hr         DOUBLE PRECISION,
    volume_1wk          DOUBLE PRECISION,
    volume_1mo          DOUBLE PRECISION,
    volume_1yr          DOUBLE PRECISION,
    liquidity           DOUBLE PRECISION,
    best_bid            DOUBLE PRECISION,
    best_ask            DOUBLE PRECISION,
    spread              DOUBLE PRECISION,
    active              BOOLEAN,
    closed              BOOLEAN,
    archived            BOOLEAN,
    is_new              BOOLEAN,
    featured            BOOLEAN,
    category            TEXT,
    tags                TEXT,
    event_id            TEXT,
    event_title         TEXT,
    clob_token_ids      TEXT,
    start_date          TIMESTAMPTZ,
    end_date            TIMESTAMPTZ,
    polymarket_created_at TIMESTAMPTZ,
    polymarket_updated_at TIMESTAMPTZ,
    emotionality_score  INTEGER,
    status_quo_deviation INTEGER,
    scored_at           TIMESTAMPTZ,
    collected_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    url                 TEXT
);
"""

INSERT_BETS = """
INSERT INTO bets (polymarket_id, question, slug, condition_id, outcomes, outcome_prices,
                  price, one_hour_price_change, one_day_price_change, one_week_price_change,
                  one_month_price_change, one_year_price_change, volume, volume_24hr,
                  volume_1wk, volume_1mo, volume_1yr, liquidity, best_bid, best_ask,
                  spread, active, closed, archived, is_new, featured, category, tags,
                  event_id, event_title, clob_token_ids, start_date, end_date,
                  polymarket_created_at, polymarket_updated_at, url)
VALUES (%(polymarket_id)s, %(question)s, %(slug)s, %(condition_id)s, %(outcomes)s,
        %(outcome_prices)s, %(price)s, %(one_hour_price_change)s, %(one_day_price_change)s,
        %(one_week_price_change)s, %(one_month_price_change)s, %(one_year_price_change)s,
        %(volume)s, %(volume_24hr)s, %(volume_1wk)s, %(volume_1mo)s, %(volume_1yr)s,
        %(liquidity)s, %(best_bid)s, %(best_ask)s, %(spread)s, %(active)s, %(closed)s,
        %(archived)s, %(is_new)s, %(featured)s, %(category)s, %(tags)s, %(event_id)s,
        %(event_title)s, %(clob_token_ids)s, %(start_date)s, %(end_date)s,
        %(polymarket_created_at)s, %(polymarket_updated_at)s, %(url)s)
ON CONFLICT (polymarket_id) DO NOTHING
RETURNING id, question;
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
        conn.execute(CREATE_BETS_TABLE)
        # Ensure columns/constraints exist for upgrades
        try:
            conn.execute("ALTER TABLE news ADD COLUMN IF NOT EXISTS disruptiveness_score INTEGER;")
        except Exception:
            conn.rollback()
        try:
            conn.execute("ALTER TABLE news ADD CONSTRAINT news_title_key UNIQUE (title);")
        except Exception:
            conn.rollback()
        # Indexes for bets.
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS bets_end_date_idx ON bets (end_date);")
        except Exception:
            conn.rollback()
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS bets_active_idx ON bets (active);")
        except Exception:
            conn.rollback()

        for col_sql in (
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS condition_id TEXT;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS price DOUBLE PRECISION;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS one_hour_price_change DOUBLE PRECISION;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS one_day_price_change DOUBLE PRECISION;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS one_week_price_change DOUBLE PRECISION;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS one_month_price_change DOUBLE PRECISION;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS one_year_price_change DOUBLE PRECISION;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS volume_24hr DOUBLE PRECISION;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS volume_1wk DOUBLE PRECISION;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS volume_1mo DOUBLE PRECISION;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS volume_1yr DOUBLE PRECISION;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS best_bid DOUBLE PRECISION;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS best_ask DOUBLE PRECISION;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS spread DOUBLE PRECISION;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS archived BOOLEAN;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS is_new BOOLEAN;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS featured BOOLEAN;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS category TEXT;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS event_id TEXT;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS event_title TEXT;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS clob_token_ids TEXT;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS start_date TIMESTAMPTZ;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS polymarket_created_at TIMESTAMPTZ;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS polymarket_updated_at TIMESTAMPTZ;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS emotionality_score INTEGER;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS status_quo_deviation INTEGER;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS scored_at TIMESTAMPTZ;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS url TEXT;",
            "ALTER TABLE bets ADD COLUMN IF NOT EXISTS collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW();",
        ):
            try:
                conn.execute(col_sql)
            except Exception:
                conn.rollback()


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




def _parse_iso_datetime(value: Any) -> datetime | None:
    """Parse an ISO-8601 datetime string into an aware UTC datetime."""
    text = _clean(value)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

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




def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _market_to_row(market: dict[str, Any]) -> dict[str, Any] | None:
    """Map one Polymarket market to INSERT_BETS params; None if no id."""
    polymarket_id = _clean(
        market.get("polymarket_id") if isinstance(market, dict) else None
    )
    if polymarket_id is None and isinstance(market, dict):
        polymarket_id = _clean(market.get("id"))
    if polymarket_id is None:
        return None
    if not isinstance(market, dict):
        return None
    prices = market.get("outcomePrices", market.get("outcome_prices", market.get("prices")))
    tags = market.get("tags")
    clob_tokens = market.get("clobTokenIds", market.get("clob_token_ids"))
    if isinstance(clob_tokens, str):
        try:
            clob_tokens = json.loads(clob_tokens)
        except Exception:
            pass
    if isinstance(clob_tokens, list):
        clob_tokens = json.dumps(clob_tokens, ensure_ascii=False)
    outcomes = market.get("outcomes")
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except Exception:
            pass
    if isinstance(outcomes, list):
        outcomes = json.dumps(outcomes, ensure_ascii=False)
    events = market.get("events") or []
    event = events[0] if isinstance(events, list) and events else {}
    return {
        "polymarket_id": polymarket_id,
        "question": _clean(market.get("question")),
        "slug": _clean(market.get("slug")),
        "condition_id": _clean(market.get("conditionId", market.get("condition_id"))),
        "outcomes": outcomes,
        "outcome_prices": json.dumps(prices, ensure_ascii=False) if isinstance(prices, (list, dict)) else prices,
        "prices": json.dumps(prices, ensure_ascii=False) if isinstance(prices, (list, dict)) else prices,
        "price": _to_float(market.get("lastTradePrice", market.get("price"))),
        "one_hour_price_change": _to_float(market.get("oneHourPriceChange", market.get("one_hour_price_change"))),
        "one_day_price_change": _to_float(market.get("oneDayPriceChange", market.get("one_day_price_change"))),
        "one_week_price_change": _to_float(market.get("oneWeekPriceChange", market.get("one_week_price_change"))),
        "one_month_price_change": _to_float(market.get("oneMonthPriceChange", market.get("one_month_price_change"))),
        "one_year_price_change": _to_float(market.get("oneYearPriceChange", market.get("one_year_price_change"))),
        "volume": market.get("volume", market.get("volumeNum")),
        "volume_24hr": _to_float(market.get("volume24hr", market.get("volume24hrClob"))),
        "volume_1wk": _to_float(market.get("volume1wk", market.get("volume1wkClob"))),
        "volume_1mo": _to_float(market.get("volume1mo", market.get("volume1moClob"))),
        "volume_1yr": _to_float(market.get("volume1yr", market.get("volume1yrClob"))),
        "liquidity": market.get("liquidity", market.get("liquidityNum", market.get("liquidityClob"))),
        "best_bid": _to_float(market.get("bestBid")),
        "best_ask": _to_float(market.get("bestAsk")),
        "spread": _to_float(market.get("spread")),
        "active": market.get("active"),
        "closed": market.get("closed"),
        "archived": market.get("archived"),
        "is_new": market.get("new"),
        "featured": market.get("featured"),
        "category": _clean(market.get("category")),
        "tags": tags,
        "event_id": _clean(event.get("id") if isinstance(event, dict) else None),
        "event_title": _clean(event.get("title") if isinstance(event, dict) else None),
        "clob_token_ids": clob_tokens,
        "start_date": market.get("startDate", market.get("startDateIso")),
        "end_date": market.get("endDate", market.get("endDateIso", market.get("end_date"))),
        "polymarket_created_at": market.get("createdAt"),
        "polymarket_updated_at": market.get("updatedAt"),
        "url": _clean(market.get("slug")) and f"https://polymarket.com/market/{market.get('slug')}",
    }



def _bet_row_value(row, key, default=None):
    """Best-effort accessor for dict-like or sequence rows."""
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    # mapping-like
    try:
        return row[key]
    except Exception:
        pass
    # attribute
    if hasattr(row, key):
        return getattr(row, key)
    return default


def bet_meets_scoring_threshold(market_row) -> bool:
    """Moderate threshold for scoring a bet market."""
    def _abs(v):
        try:
            return abs(float(v))
        except (TypeError, ValueError):
            return 0.0

    return (
        _abs(_bet_row_value(market_row, "one_day_price_change")) >= 0.05
        or _abs(_bet_row_value(market_row, "one_week_price_change")) >= 0.10
        or _abs(_bet_row_value(market_row, "one_month_price_change")) >= 0.15
    )


def bet_needs_scoring(row) -> bool:
    """Whether a bet row still needs scoring and meets threshold."""
    score = _bet_row_value(row, "emotionality_score", None)
    if score is not None:
        return False
    return bet_meets_scoring_threshold(row)

def validate_json_file(path: Path | str) -> dict[str, Any]:
    """Validate that a GDELT JSON file has a non-empty top-level ``query``.

    Returns the parsed payload on success; raises ``ValueError`` (with a
    clear message) when the file is missing or has an empty ``query`` key,
    so legacy files without ``query`` fail loudly during ingestion.
    """
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    query = _clean(payload.get("query"))
    if query is None:
        raise ValueError(f"{path} has no 'query' key")
    return payload


def find_invalid_json_files(directory: Path | str = DATA_DIR) -> list[Path]:
    """Return JSON files in ``directory`` that lack a usable top-level query."""
    directory = Path(directory)
    invalid: list[Path] = []
    for path in sorted(directory.glob("*.json")):
        try:
            validate_json_file(path)
        except (ValueError, OSError, json.JSONDecodeError):
            invalid.append(path)
    return invalid


# Backwards/alias-friendly names for the cleanup guard.
json_files_without_query = find_invalid_json_files
find_json_files_without_query = find_invalid_json_files
find_legacy_json_files = find_invalid_json_files
list_invalid_json_files = find_invalid_json_files


def ingest_json_file(path: Path | str, score: bool = True) -> dict[str, Any]:
    """Insert the articles of one GDELT JSON file, skipping existing urls.

    The query is read from the file's top-level "query" key and stored on
    every row. Returns a summary dict with the file, query and row counts.
    """
    path = Path(path)
    payload = validate_json_file(path)

    query = _clean(payload.get("query"))
    if query is None:  # defensive; validate_json_file already checks
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

        # Score newly inserted rows by title. Scoring failures must not fail
        # ingestion, but they are logged and recorded in the summary.
        scoring_error = None
        scoring_failed = 0
        scoring_scored = 0
        if score and inserted_rows:
            titles_to_score = []
            ids_to_score = []
            for row_res in inserted_rows:
                inserted_id = row_res[0]
                inserted_title = row_res[1]
                if inserted_title and str(inserted_title).strip():
                    titles_to_score.append(inserted_title)
                    ids_to_score.append(inserted_id)
            if titles_to_score:
                try:
                    scores = score_headlines(titles_to_score)
                    if len(scores) != len(titles_to_score):
                        raise ValueError(
                            f"scorer returned {len(scores)} scores for "
                            f"{len(titles_to_score)} titles"
                        )
                    with conn.cursor() as cur:
                        for inserted_id, score in zip(ids_to_score, scores):
                            cur.execute(
                                "UPDATE news SET disruptiveness_score = %s WHERE id = %s",
                                (int(score), inserted_id),
                            )
                    scoring_scored = len(titles_to_score)
                except Exception as exc:  # noqa: BLE001
                    scoring_failed = len(titles_to_score)
                    scoring_error = str(exc)
                    logger.warning(
                        "scoring failed for %d titles: %s", scoring_failed, exc
                    )
                    print(
                        f"WARNING: scoring failed for {scoring_failed} titles: {exc}",
                        flush=True,
                    )

    return {
        "file": str(path),
        "query": query,
        "total": len(articles),
        "inserted": inserted,
        "skipped": len(articles) - inserted,
        "scoring_error": scoring_error,
        "scoring_failed": scoring_failed,
        "scoring_scored": scoring_scored,
    }


def backfill_disruptiveness_scores(limit: int | None = None) -> dict[str, Any]:
    """Score rows whose ``disruptiveness_score`` is NULL and store results.

    Returns a summary with ``considered``, ``scored``, ``failed`` and
    ``errors`` keys. Empty titles are skipped (not scored, not failed).
    """
    considered = 0
    scored = 0
    failed = 0
    errors: list[str] = []

    with get_connection() as conn:
        with conn.cursor() as cur:
            if limit is None:
                cur.execute(
                    "SELECT id, title FROM news WHERE disruptiveness_score IS NULL"
                )
            else:
                cur.execute(
                    "SELECT id, title FROM news WHERE disruptiveness_score IS NULL LIMIT %s",
                    (limit,),
                )
            rows = cur.fetchall()

    considered = len(rows)

    # Only non-empty titles are scored; empty titles are skipped.
    items = [
        (row_id, str(title))
        for row_id, title in rows
        if title is not None and str(title).strip()
    ]

    batch_size = 16
    for start in range(0, len(items), batch_size):
        chunk = items[start : start + batch_size]
        chunk_ids = [item[0] for item in chunk]
        chunk_titles = [item[1] for item in chunk]
        try:
            scores = score_headlines(chunk_titles)
            if not isinstance(scores, (list, tuple)) or len(scores) != len(chunk_titles):
                raise ValueError(
                    f"scorer returned {len(scores) if hasattr(scores, '__len__') else scores!r} "
                    f"scores for {len(chunk_titles)} titles"
                )
            with get_connection() as conn:
                with conn.cursor() as cur:
                    for row_id, score in zip(chunk_ids, scores):
                        cur.execute(
                            "UPDATE news SET disruptiveness_score = %s WHERE id = %s",
                            (int(score), row_id),
                        )
            scored += len(chunk_titles)
        except Exception as exc:  # noqa: BLE001
            failed += len(chunk_titles)
            message = f"scoring failed for {len(chunk_titles)} titles: {exc}"
            errors.append(str(exc))
            logger.warning(message)
            print(f"WARNING: {message}", flush=True)

    return {
        "considered": considered,
        "scored": scored,
        "failed": failed,
        "errors": errors,
    }


def ingest_latest_json(directory: Path | str = DATA_DIR, score: bool = True) -> dict[str, Any]:
    """Ingest the most recent JSON file in `directory`."""
    return ingest_json_file(latest_json_file(directory), score=score)


def ingest_polymarket_file(path: Path | str, score: bool = True) -> dict[str, Any]:
    """Insert markets of one Polymarket JSON file, skipping existing ids.

    Validates that the file contains a top-level ``markets`` list. Returns a
    summary dict with ``file``, ``total``, ``inserted`` and ``skipped``.
    """
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    markets = payload.get("markets")
    if not isinstance(markets, list):
        raise ValueError(f"{path} has no 'markets' list")

    rows = []
    for market in markets:
        if not isinstance(market, dict):
            continue
        row = _market_to_row(market)
        if row is None:
            continue
        # Normalize values for database columns.
        row["volume"] = _to_float(row.get("volume"))
        row["liquidity"] = _to_float(row.get("liquidity"))
        for key in ("outcomes", "outcome_prices", "prices", "tags", "clob_token_ids"):
            if isinstance(row.get(key), (list, dict)):
                row[key] = json.dumps(row[key], ensure_ascii=False)
        rows.append(row)

    inserted_rows = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            if rows:
                cur.executemany(INSERT_BETS, rows, returning=True)
                while True:
                    result = cur.fetchone()
                    if result is not None:
                        inserted_rows.append(result)
                    if not cur.nextset():
                        break
    inserted = len(inserted_rows)

    # Score newly inserted threshold markets. Failures are logged, not fatal.
    scoring_error = None
    scoring_failed = 0
    scoring_scored = 0
    if score and inserted_rows:
        ids_to_score = []
        markets_to_score = []
        for row_res in inserted_rows:
            inserted_id = row_res[0]
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT question, one_day_price_change, one_week_price_change, one_month_price_change, "
                        "emotionality_score FROM bets WHERE id = %s",
                        (inserted_id,),
                    )
                    record = cur.fetchone()
            if record is None:
                continue
            question, one_day_price_change, one_week_price_change, one_month_price_change, emo_score = record
            market_row = {
                "one_day_price_change": one_day_price_change,
                "one_week_price_change": one_week_price_change,
                "one_month_price_change": one_month_price_change,
                "emotionality_score": emo_score,
            }
            if emo_score is not None:
                continue
            if not bet_meets_scoring_threshold(market_row):
                continue
            if question and str(question).strip():
                ids_to_score.append(inserted_id)
                markets_to_score.append(str(question))

        batch_size = 16
        for start in range(0, len(markets_to_score), batch_size):
            chunk_ids = ids_to_score[start:start + batch_size]
            chunk_markets = markets_to_score[start:start + batch_size]
            if not chunk_markets:
                continue
            try:
                scores = score_bet_emotionality_and_status_quo(chunk_markets)
                if not isinstance(scores, (list, tuple)) or len(scores) != len(chunk_markets):
                    raise ValueError(
                        f"scorer returned {len(scores) if hasattr(scores, '__len__') else scores!r} "
                        f"scores for {len(chunk_markets)} markets"
                    )
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        for inserted_id, (emo, sq) in zip(chunk_ids, scores):
                            if emo is None or sq is None:
                                raise ValueError("scorer returned None scores")
                            cur.execute(
                                "UPDATE bets SET emotionality_score = %s, "
                                "status_quo_deviation = %s, scored_at = NOW() WHERE id = %s",
                                (int(emo), int(sq), inserted_id),
                            )
                scoring_scored += len(chunk_markets)
                gc.collect()
            except Exception as exc:  # noqa: BLE001
                scoring_failed += len(chunk_markets)
                scoring_error = str(exc)
                logger.warning(
                    "bet scoring failed for %d markets: %s", len(chunk_markets), exc
                )
                print(
                    f"WARNING: bet scoring failed for {len(chunk_markets)} markets: {exc}",
                    flush=True,
                )

    return {
        "file": str(path),
        "total": len(markets),
        "inserted": inserted,
        "skipped": len(markets) - inserted,
        "scoring_error": scoring_error,
        "scoring_failed": scoring_failed,
        "scoring_scored": scoring_scored,
    }



def backfill_bet_scores(limit: int | None = None) -> dict[str, Any]:
    """Score bets whose ``emotionality_score`` is NULL and meet threshold.

    Processes the database in small batches to avoid loading all rows or
    exhausting memory during Laya inference.
    """
    considered = 0
    scored = 0
    failed = 0
    errors: list[str] = []

    outer_batch = 250 if limit is None else min(limit, 250)
    remaining_limit = limit

    while True:
        fetch_size = outer_batch
        if remaining_limit is not None:
            fetch_size = min(fetch_size, remaining_limit)
        if fetch_size <= 0:
            break

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, question, one_day_price_change, one_week_price_change, "
                    "one_month_price_change, emotionality_score FROM bets "
                    "WHERE emotionality_score IS NULL AND ("
                    "ABS(one_day_price_change) >= 0.05 OR "
                    "ABS(one_week_price_change) >= 0.10 OR "
                    "ABS(one_month_price_change) >= 0.15) "
                    "ORDER BY id LIMIT %s",
                    (fetch_size,),
                )
                rows = cur.fetchall()

        if not rows:
            break

        items = []
        for row in rows:
            row_id, question, one_day_price_change, one_week_price_change, one_month_price_change, emo_score = row
            if question is None or not str(question).strip():
                continue
            items.append((row_id, str(question)))

        considered += len(items)

        batch_size = 16
        for start in range(0, len(items), batch_size):
            chunk = items[start : start + batch_size]
            chunk_ids = [item[0] for item in chunk]
            chunk_markets = [item[1] for item in chunk]
            try:
                results = score_bet_emotionality_and_status_quo(chunk_markets)
                if not isinstance(results, (list, tuple)) or len(results) != len(chunk_markets):
                    raise ValueError(
                        f"scorer returned {len(results) if hasattr(results, '__len__') else results!r} "
                        f"scores for {len(chunk_markets)} markets"
                    )
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        for row_id, (emo, sq) in zip(chunk_ids, results):
                            if emo is None or sq is None:
                                raise ValueError("scorer returned None scores")
                            cur.execute(
                                "UPDATE bets SET emotionality_score = %s, "
                                "status_quo_deviation = %s, scored_at = NOW() WHERE id = %s",
                                (int(emo), int(sq), row_id),
                            )
                scored += len(chunk_markets)
                gc.collect()
            except Exception as exc:  # noqa: BLE001
                failed += len(chunk_markets)
                errors.append(str(exc))
                logger.warning("bet scoring failed for %d markets: %s", len(chunk_markets), exc)
                print(f"WARNING: bet scoring failed for {len(chunk_markets)} markets: {exc}", flush=True)

        if remaining_limit is not None:
            remaining_limit -= len(rows)
        if limit is not None and remaining_limit is not None and remaining_limit <= 0:
            break
        if len(rows) < fetch_size:
            break

    return {
        "considered": considered,
        "scored": scored,
        "failed": failed,
        "errors": errors,
    }


def ingest_latest_polymarket_file(directory: Path | str = POLYMARKET_DATA_DIR, score: bool = True) -> dict[str, Any]:
    """Ingest the most recent Polymarket JSON file in `directory`."""
    return ingest_polymarket_file(latest_json_file(directory), score=score)


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


def delete_news_by_date_range(start: Any = None, end: Any = None) -> int:
    """Delete news rows whose ``seendate`` falls within [start, end].

    Returns the number of deleted rows. Raises ValueError if both bounds are
    missing, to avoid accidental full-table deletes.
    """
    start_dt = _parse_iso_datetime(start) if start is not None else None
    end_dt = _parse_iso_datetime(end) if end is not None else None
    if start_dt is None and end_dt is None and start is None and end is None:
        raise ValueError("at least one of start or end is required")
    conditions = []
    params = []
    if start_dt is not None:
        conditions.append("seendate >= %s")
        params.append(start_dt)
    if end_dt is not None:
        conditions.append("seendate <= %s")
        params.append(end_dt)
    if not conditions:
        # Fall back to raw string bounds if ISO parsing failed.
        if start is not None:
            conditions.append("seendate >= %s")
            params.append(start)
        if end is not None:
            conditions.append("seendate <= %s")
            params.append(end)
    if not conditions:
        raise ValueError("at least one valid date bound is required")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM news WHERE {' AND '.join(conditions)}",
                params,
            )
            deleted = cur.rowcount
    return deleted


def delete_bets_by_date_range(start: Any = None, end: Any = None) -> int:
    """Delete bets rows whose ``collected_at`` falls within [start, end].

    Returns the number of deleted rows. Raises ValueError if no valid bound
    is provided.
    """
    start_dt = _parse_iso_datetime(start) if start is not None else None
    end_dt = _parse_iso_datetime(end) if end is not None else None
    conditions = []
    params = []
    if start_dt is not None:
        conditions.append("collected_at >= %s")
        params.append(start_dt)
    if end_dt is not None:
        conditions.append("collected_at <= %s")
        params.append(end_dt)
    if not conditions:
        if start is not None:
            conditions.append("collected_at >= %s")
            params.append(start)
        if end is not None:
            conditions.append("collected_at <= %s")
            params.append(end)
    if not conditions:
        raise ValueError("at least one valid date bound is required")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM bets WHERE {' AND '.join(conditions)}",
                params,
            )
            deleted = cur.rowcount
    return deleted
