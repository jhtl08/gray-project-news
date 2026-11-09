# Gray Project News

A news-collection and analysis pipeline built to surface news that matters to
**prediction-market** traders. It pulls global news from the GDELT Project,
scores each headline for "disruptiveness" (potential impact on unresolved
prediction markets) using a local Laya model, stores everything in PostgreSQL
with the `pgvector` extension, and exposes it through a FastAPI backend and a
React/Vite frontend.

Status: **news end-to-end is implemented and working** (collect -> ingest ->
score -> store -> browse). **Bets, Matches, and vector processing are planned
but not yet implemented** (frontend tabs are placeholders).

---

## 1. What this project is about

- **Goal**: continuously gather worldwide news, rank it by how much it could
  move prediction-market expectations, and (later) link that news to concrete
  bets/markets and matches.
- **Current scope (done)**: news ingestion from GDELT, disruptiveness scoring,
  persistent storage, REST API, and a web UI to collect + browse news.
- **Planned scope (not done)**: Polymarket bets integration, sports matches,
  vector/embedding-based semantic search and news<->market matching.

The repo name is `gray-project-news`; the app title shown in the UI is
"Gray Project News".

---

## 2. Repository layout

```
gray-project-news/
├── README.md                 # this file
├── docker-compose.yaml       # Postgres (pgvector/pg17) + pgAdmin
├── .gitignore
├── backend/
│   ├── .env                  # DATABASE_URL (present locally)
│   ├── requirements.txt
│   ├── main.py               # FastAPI app + endpoints
│   ├── gdelt_api.py          # GDELT DOC API client (fetch + save JSON)
│   ├── db_operations.py      # Postgres/psycopg operations + ingestion + scoring hook
│   ├── laya_processes.py     # Laya Router + disruptiveness prompt + score_headlines()
│   ├── polymarket_collector.py  # WIP: prints Polymarket tags (not integrated)
│   ├── temp notes.txt        # scratch notes (gitignored)
│   ├── gdelt_data/           # saved GDELT JSON snapshots
│   └── .venv/                # Python virtualenv (not committed)
└── frontend/
    ├── package.json          # React 19 + Vite 8
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx            # tab shell: News / Bets / Matches
        ├── App.css, index.css
        ├── News.jsx           # collect + query subtabs
        ├── Bets.jsx           # placeholder "Coming soon"
        └── Matches.jsx        # placeholder "Coming soon"
```

Deleted/legacy (removed from working tree vs. first commit): `backend/filter.py`
and `backend/gdelt_csv.py`. The first commit's approach downloaded GDELT 2.0
*CSV exports* and filtered by country/location; the current approach uses the
GDELT *DOC API* (JSON) via `gdelt_api.py`. Do not revive the CSV path unless
needed.

---

## 3. Tech stack

- **Backend**: Python 3.14, FastAPI 0.150, Uvicorn, Pydantic 2, psycopg 3.3.6
  (sync), python-dotenv.
- **Database**: PostgreSQL 17 via `pgvector/pgvector:pg17` Docker image
  (includes `vector` extension). Database `pgdb`, user `pguser`.
- **Scoring/ML**: `laya` 0.4.14 (Convai) `Router(default="multilingual")`,
  torch/transformers-based, runs locally; model weights downloaded on first use
  (see `~/.cache/huggingface`).
- **News source**: GDELT Project DOC API
  (`https://api.gdeltproject.org/api/v2/doc/doc`), mode `artlist`.
- **Frontend**: React 19.3, Vite 8.3, plain CSS (dark theme), no router/state
  lib. ESLint configured.
- **Bets source (planned)**: Polymarket Gamma API (`https://gamma-api.polymarket.com`).

---

## 4. Infrastructure / database setup

### 4.1 Docker

`docker-compose.yaml` defines:

- `postgres`: image `pgvector/pgvector:pg17`, container `pg-gray-project`,
  env `POSTGRES_USER=pguser`, `POSTGRES_PASSWORD=pgpassword`,
  `POSTGRES_DB=pgdb`, port `5432:5432`, named volume `pgdata`.
- `pgadmin`: `dpage/pgadmin4`, port `5050:80`, login
  `pgadmin@example.com` / `admin`.

Start: `docker compose up -d`.

### 4.2 Environment

`backend/.env`:
```
DATABASE_URL=postgresql://pguser:pgpassword@localhost:5432/pgdb
```
`db_operations.py` loads `backend/.env` by absolute path so it works regardless
of CWD.

### 4.3 Database initialization

`db_operations.init_db()`:
1. `CREATE EXTENSION IF NOT EXISTS vector;`
2. `CREATE TABLE IF NOT EXISTS news (...)` (see schema).
3. `ALTER TABLE news ADD COLUMN IF NOT EXISTS disruptiveness_score INTEGER;`
4. `ALTER TABLE news ADD CONSTRAINT news_title_key UNIQUE (title);` (best-effort,
   wrapped in try/except).

Called automatically on FastAPI startup (`@app.on_event("startup")`).

### 4.4 `news` table schema (current DB)

Columns (DB retains old columns because `CREATE TABLE IF NOT EXISTS`):

| Column                | Type        | Notes                                                  |
|-----------------------|-------------|--------------------------------------------------------|
| id                    | BIGSERIAL   | PK                                                     |
| query                 | TEXT        | NOT NULL; the GDELT query string stored on every row    |
| url                   | TEXT        | NOT NULL, UNIQUE (dedupe key)                          |
| title                 | TEXT        | UNIQUE (added later)                                   |
| seendate              | TIMESTAMPTZ | GDELT stamp parsed from `YYYYMMDDTHHMMSSZ`             |
| language              | TEXT        |                                                        |
| sourcecountry         | TEXT        |                                                        |
| content_vector        | VECTOR      | **unpinned, no dimension** (leftover from first commit; unused) |
| disruptiveness_score  | INTEGER     | 0-100 from Laya                                        |
| created_at            | TIMESTAMPTZ | DEFAULT NOW()                                          |

Indexes: none beyond PK/unique constraints. No HNSW/IVFFlat index yet (blocked
on pinning a vector dimension).

Current data: ~325 rows, 3 distinct queries
(`(iran OR hormuz)`, `(openai OR anthropic OR spacex)`,
`(israel OR iran OR netanyahu)`), 0 rows with a non-null `content_vector`,
325 rows with a score.

---

## 5. News functionality (done)

### 5.1 Collection from GDELT (`backend/gdelt_api.py`)

`get_gdelt_json(query, maxrecords, timespan, sort)`:
- Builds params for GDELT DOC API (`mode=artlist`, `format=json`).
- Defaults: `maxrecords=200`, `timespan="1h"`, `sort="datedesc"`.
  - Note: GDELT rejects windows shorter than ~1h; "15min" fails.
- `DEFAULT_QUERY = "(the OR and OR of OR to)"` (a broad default; earlier
  default was `(iran OR hormuz)`).
- Retry/backoff for `429, 500, 502, 503, 504` and transient failures:
  `MAX_RETRIES=5`, base 5s, exponential, capped 60s, jitter 0-2s, honors
  `Retry-After`. Timeouts: connect 30s, read 60s.
- Rejects other 4xx immediately with `RuntimeError`.
- Treats empty/non-JSON 200 responses as transient.
- Saves the response to `backend/gdelt_data/<UTC YYYYMMDD_HHMMSS>.json`
  (collision-safe suffix) with the query injected as top-level `"query"` key:
  `{"query": ..., **data}`.
- Returns the parsed GDELT dict (`{"articles": [...]}`).

Article fields used downstream: `url`, `title`, `seendate`, `language`,
`sourcecountry`.

### 5.2 Ingestion into Postgres (`backend/db_operations.py`)

- `latest_json_file(directory)` picks newest `.json` by filename sort.
- `_article_to_row(article, query)` maps an article to INSERT params; returns
  `None` (skipped) if no url.
- `_parse_seendate` parses `YYYYMMDDTHHMMSSZ` -> aware UTC datetime.
- `INSERT_NEWS` inserts `(query, url, title, seendate, language, sourcecountry)`
  with `ON CONFLICT DO NOTHING RETURNING id, title`.
  - Note: conflict can trigger on either `url` (unique) or `title` (unique).
- `ingest_json_file(path)`:
  1. Reads JSON, requires top-level `"query"`.
  2. Maps articles -> rows.
  3. `executemany(..., returning=True)` and collects returned `(id, title)`.
  4. For newly inserted rows with a non-empty title, calls
     `score_headlines(titles)` and `UPDATE news SET disruptiveness_score`
     for each id. Scoring failures are swallowed (`except Exception: pass`).
  5. Returns `{file, query, total, inserted, skipped}`.
- `ingest_latest_json(directory)` = ingest the newest JSON file.
- `main()` runs `init_db()` + `ingest_latest_json()` and prints a summary.

Important: only **newly inserted** rows get scored. Rows inserted before the
scoring feature (or via old code) keep `NULL` scores. Re-scoring existing rows
is not implemented yet.

### 5.3 Disruptiveness scoring (`backend/laya_processes.py`)

- Imports `from laya import Router`.
- `router = Router(default="multilingual")`; `router.preload(["multilingual"])`
  at import time (so importing this module downloads/loads weights).
- Defines a `questions` dict with one scored question `"disruptiveness"`:
  - type `"score"`, criteria `0..100`.
  - A long prompt evaluating headlines for prediction-market usefulness:
    Market Relevance 40% + Potential Market Impact 60%, with detailed rules.
- `score_headlines(headlines: list[str]) -> list[int]`:
  - Builds one request per headline with `state={"headline": headline}`.
  - `router.predict_batch(requests, batch_size=64)`.
  - Returns `round(result["answers"]["disruptiveness"]["score"])`.

Scoring happens inline during ingestion. The Laya model is multilingual, which
matters because GDELT articles are in many languages.

### 5.4 REST API (`backend/main.py`)

FastAPI app "Gray Project News API", CORS for
`http://localhost:5173`, `http://localhost:3000`, `http://127.0.0.1:5173`.

Endpoints:
- `GET /api/health` -> `{"status": "ok"}`.
- `POST /api/news/collect` body `GDELTCollectRequest`
  `{query?, maxrecords?, timespan?, sort?="datedesc"}`:
  1. Resolves query (default if blank).
  2. Calls `get_gdelt_json(...)` (fetches + saves JSON).
  3. Calls `ingest_latest_json()` to ingest the just-saved file.
  4. Returns `{success, articles, query_used, maxrecords, timespan, sort,
     ingested, ingest_error, data}`. Ingest errors are returned, not raised.
- `GET /api/news?limit&offset&order_by&order_dir`:
  - `limit` 1..1000 (default 100), `offset` >=0.
  - `order_by` in {seendate, created_at, id, disruptiveness_score}.
  - `order_dir` in {asc, desc}.
  - SQL: `ORDER BY <col> <dir> NULLS LAST LIMIT/OFFSET`, plus `COUNT(*)`.
  - Returns `{news: [...], total, limit, offset}`. Dates ISO-formatted.

Run: `uvicorn main:app --reload --host 0.0.0.0 --port 8000` from `backend/`.

### 5.5 Frontend (`frontend/src`)

- `App.jsx`: tab shell with News / Bets / Matches tabs (state `activeTab`).
- `News.jsx`: two subtabs.
  - **Collect New Data**: form (query, maxrecords, timespan, sort) POSTs to
    `/api/news/collect`, shows success/error feedback including ingest counts.
  - **Query Local News Database**: table of news with columns ID, Title,
    Disruptiveness, Query, Seendate, Language, Source Country, URL. Controls:
    order-by select, direction select, Refresh, pagination (Previous/Next,
    100 per page). Fetches on tab entry and when order params change.
  - `API_BASE = "http://localhost:8000"`.
- `Bets.jsx`, `Matches.jsx`: placeholders ("Coming soon").
- Dark theme CSS in `index.css`/`App.css`.

Run: `npm install` then `npm run dev` (Vite, default port 5173).

### 5.6 Frontend <-> Backend <-> DB integration

Flow (collect):
```
Browser (News.jsx Collect form)
  -> POST /api/news/collect
     -> gdelt_api.get_gdelt_json()  (GDELT DOC API -> gdelt_data/*.json)
     -> db_operations.ingest_latest_json()
        -> ingest_json_file() -> INSERT into news (dedupe)
        -> score_headlines() (Laya) -> UPDATE disruptiveness_score
  -> JSON response with counts
```

Flow (query):
```
Browser (News.jsx Query tab)
  -> GET /api/news?...
     -> SELECT ... FROM news ORDER BY ... LIMIT/OFFSET
  -> render table
```

CORS is configured for the Vite dev origin. No auth, no proxy in Vite config
(`vite.config.js` has no proxy; frontend calls absolute `localhost:8000`).

---

## 6. What is NOT done / known issues

1. **Bets tab** (`Bets.jsx`) is a placeholder. `polymarket_collector.py` only
   fetches and prints Polymarket tags; no persistence, no endpoints, no UI.
2. **Matches tab** (`Matches.jsx`) is a placeholder. No match data source or
   schema.
3. **Vector processing is not implemented**:
   - `content_vector VECTOR` column exists (from first commit) but is never
     populated (0 non-null rows).
   - No dimension pinned, no embedding model chosen, no HNSW/IVFFlat index,
     no similarity search endpoint.
   - Comment in code explicitly notes this is deferred until the title-embedding
     model is chosen.
4. **No tests** anywhere (backend or frontend).
5. **Scoring only on insert**: previously stored rows are not backfilled; if
   `score_headlines` fails during ingest, scores stay NULL silently.
6. **Frontend direction labels are swapped**: in `News.jsx`, the `desc` option
   is labeled "Ascending" and `asc` "Descending" (backwards). The backend
   semantics are correct; only labels are wrong.
7. **Old JSON files lack `query` key** (20261021_*, 20261021_030951, etc.)
   and cannot be ingested by `ingest_json_file` (raises "no 'query' key").
   Only files saved by current `get_gdelt_json` (20261023_003705 onward) have it.
8. **`ON CONFLICT DO NOTHING`** (no target) catches any unique violation
   (url or title), which can hide which constraint fired. Also title uniqueness
   can drop legitimate articles that share a title.
9. `total` counts all rows.
10. **Laya import side effects**: importing `laya_processes` loads the model;
    first run downloads weights and can be slow. `laya` sets `USE_TF=0`.
11. **No deployment config** (no Dockerfile for app, no CI).
12. **`requirements.txt`** has duplicates and a stray `python-multipart`.

---

## 7. What's next (planned work)

### 7.1 Bets functionality
- Finish `polymarket_collector.py`: paginate `gamma-api.polymarket.com/events`
  (or markets), filter active/open, extract id, title, outcomes, prices,
  volume, end date, tags.
- Design DB tables: `bets`/`markets` (and maybe `events`), with columns for
  polymarket id, question, slug, outcomes, prices, volume, liquidity, end_date,
  active/closed, tags, created_at, and possibly an embedding vector.
- Add ingestion endpoint (manual + scheduled) and `/api/bets` CRUD/list endpoints
  with filtering/pagination.
- Frontend: implement `Bets.jsx` table + filters, mirroring `News.jsx`.
- Link news to bets: match headlines to markets (keyword + vector similarity)
  and show related news on a bet and related bets on a news row.

### 7.2 Matches functionality
- Choose a sports data source (e.g., a football/sports API) and define what
  "match" means in this app (teams, league, kickoff, outcome, odds).
- DB table `matches` with teams, competition, start time, status, result.
- Ingestion + endpoints + frontend table in `Matches.jsx`.
- Optionally connect matches to bets (prediction markets on match outcomes).

### 7.3 Vector processing
- Choose an embedding model for titles (and possibly full text). This unblocks
  pinning `content_vector` dimension.
- Populate vectors during ingestion (title embedding at least).
- Migration: `ALTER TABLE news ALTER COLUMN content_vector TYPE VECTOR(<dim>)`,
  add HNSW/IVFFlat index.
- Add semantic search endpoint (`/api/news/search?q=...`) and similarity-based
  "related news/bets" features.
- Use vectors for news<->bet matching and for deduplication beyond url/title.
- Consider backfilling vectors and scores for existing rows (batch job).

### 7.4 General improvements
- Backfill scoring/vectors for existing rows.
- Fix swapped asc/desc labels in `News.jsx`.
- Add tests (pytest for backend, vitest for frontend).
- Handle Laya scoring errors visibly instead of swallowing.
- Make ingestion async or backgrounded (FastAPI BackgroundTasks) for large
  collects; current collect blocks the request.
- Add Vite proxy to avoid absolute `localhost:8000` URLs.
- Clean up `requirements.txt`.
- Add Dockerfile / compose for the app itself.

---

## 8. How to run (local dev)

Prerequisites: Docker Desktop, Python 3.14 (or compatible), Node 20+.

```bash
# 1. Database
docker compose up -d

# 2. Backend
cd backend
python -m venv .venv
# Windows:
.venv/Scripts/activate
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
# create backend/.env with DATABASE_URL=postgresql://pguser:pgpassword@localhost:5432/pgdb
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 3. Frontend
cd frontend
npm install
npm run dev   # http://localhost:5173
```

Useful:
- pgAdmin: http://localhost:5050
- Health check: http://localhost:8000/api/health
- Ingest newest saved JSON manually: `cd backend && python db_operations.py`
- Score model smoke test: `cd backend && python laya_processes.py`

---

## 9. Key entry points for an agent

- Backend entry: `backend/main.py` (`app`).
- DB layer: `backend/db_operations.py` (`get_connection`, `init_db`,
  `ingest_json_file`, `ingest_latest_json`).
- News fetch: `backend/gdelt_api.py` (`get_gdelt_json`).
- Scoring: `backend/laya_processes.py` (`score_headlines`).
- Frontend entry: `frontend/src/main.jsx` -> `App.jsx` -> `News.jsx`.
- Planned integrations: `backend/polymarket_collector.py`.

Invariants to respect:
- `news.url` is the dedupe key; `news.title` is also unique.
- `ingest_json_file` requires a top-level `"query"` key in the JSON.
- Scoring only runs for newly inserted rows.
- `content_vector` has no fixed dimension yet; do not assume one.
- CORS origins are hardcoded in `main.py`.

---

## 10. Environment variables

| Var           | Where used      | Example                                                  |
|---------------|-----------------|----------------------------------------------------------|
| DATABASE_URL  | db_operations   | postgresql://pguser:pgpassword@localhost:5432/pgdb        |
| USE_TF        | set by laya     | 0 (set automatically)                                    |

No other env vars are currently required.
