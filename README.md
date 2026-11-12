# Gray Project News

A news-collection and analysis pipeline for **prediction-market** traders. It
pulls global news from GDELT, scores headlines for disruptiveness with a local
Laya model, stores news and Polymarket bets in PostgreSQL with `pgvector`
embeddings, and exposes everything through FastAPI and a React/Vite UI. A
Matches section links related news and bets by semantic similarity.

Status: **News, Bets, and Matches are implemented end-to-end.** The Matches tab
uses pgvector embeddings and a 0.7 cosine-similarity threshold.

---

## 1. What this project is about

- **Goal**: gather worldwide news and prediction-market bets, rank news by market
  impact, and link related news/bets semantically.
- **Done**: news ingestion/scoring, bets ingestion/scoring, pgvector embeddings,
  match seeds/related items, REST APIs, web UI, deletion by date range, tests.

---

## 2. Repository layout

```
gray-project-news/
├── README.md
├── docker-compose.yaml
├── plans/                  # plannotator plans (news/bets/matches)
├── backend/
│   ├── .env
│   ├── requirements.txt
│   ├── main.py             # FastAPI app + endpoints
│   ├── gdelt_api.py        # GDELT DOC API client
│   ├── db_operations.py    # Postgres operations, ingestion, scoring, embeddings
│   ├── laya_processes.py   # Laya scoring (news + bets)
│   ├── embedding.py        # multilingual-e5-small embeddings
│   ├── polymarket_collector.py
│   ├── check_gdelt_json.py
│   ├── gdelt_data/         # GDELT JSON snapshots
│   ├── polymarket_data/    # Polymarket JSON snapshots
│   ├── tests/
│   └── .venv/
└── frontend/
    └── src/
        ├── App.jsx
        ├── News.jsx
        ├── Bets.jsx
        └── Matches.jsx
```

---

## 3. Tech stack

- **Backend**: Python 3.14/3.15, FastAPI, Uvicorn, Pydantic, psycopg 3, pgvector.
- **Database**: PostgreSQL 17 (`pgvector/pgvector:pg17`), database `pgdb`.
- **Scoring**: Laya 0.4.14 `Router(default="multilingual")` (lazy singleton).
- **Embeddings**: `intfloat/multilingual-e5-small` via `transformers` (384 dims).
- **News source**: GDELT DOC API.
- **Bets source**: Polymarket Gamma API.
- **Frontend**: React 19, Vite 8, plain CSS.

---

## 4. Infrastructure / database

### 4.1 Docker

`docker compose up -d` starts Postgres (5432) and pgAdmin (5050).

### 4.2 Environment

`backend/.env`:

```
DATABASE_URL=postgresql://pguser:pgpassword@localhost:5432/pgdb
```

### 4.3 Initialization

`init_db()` creates the `vector` extension, `news`, `bets`, and `match_seeds`
tables, migrates columns, and creates HNSW indexes. Called on FastAPI startup.

### 4.4 Schemas (summary)

**news**: id, query, url (unique), title (unique), seendate, language,
sourcecountry, disruptiveness_score, content_vector VECTOR(384), created_at.

**bets**: id, polymarket_id (unique), question, slug, condition_id, outcomes,
outcome_prices, price, one_hour/day/week/month/year_price_change, volume\*,
liquidity, best_bid/ask, spread, active, closed, archived, is_new, featured,
category, tags, event_id/title, clob_token_ids, dates, emotionality_score,
status_quo_deviation, scored_at, collected_at, url, content_vector VECTOR(384).

**match_seeds**: id, source_type, source_id, title, content_vector VECTOR(384),
created_at, unique(source_type, source_id).

---

## 5. News functionality

- Collect from GDELT with retry/backoff; saves JSON snapshots.
- Ingest dedupes by url/title; scores newly inserted rows with Laya
  (0-100 disruptiveness) but scoring is non-blocking (background backfill).
- `GET /api/news` with pagination/sort.
- `DELETE /api/news?start=&end=` by seendate range.
- `POST /api/news/backfill-embeddings`.
- Match button per row.

---

## 6. Bets functionality

- Collect active Polymarket markets (priority tags: Politics, Economics,
  Finance, Business + new markets); saves JSON snapshots.
- Store price changes, volumes, liquidity, metadata, tags.
- Laya scores emotionality (0-100) and status-quo deviation (0/1) only for
  markets crossing a moderate price-change threshold.
- `GET /api/bets` with filters/sort/pagination.
- `DELETE /api/bets?start=&end=` by collected_at range.
- `POST /api/bets/backfill-scores`, `POST /api/bets/backfill-embeddings`.
- Match button per row.

---

## 7. Matches functionality

- Embeddings for news and bets using multilingual-e5-small (384 dims).
- `POST /api/matches` creates a seed from a news or bet item.
- `GET /api/matches` lists seeds; `DELETE /api/matches/{id}` removes.
- `GET /api/matches/{id}/related` returns top 5 items from the opposite type
  with cosine similarity >= 0.7.
- Matches tab displays seeds and related items with similarity scores.

---

## 8. API summary

- News: collect, list, delete, backfill embeddings.
- Bets: collect, list, delete, backfill scores/embeddings.
- Matches: create/list/delete seeds, related items.
- Health: `GET /api/health`.

---

## 9. Frontend

- Tabs: News, Bets, Matches.
- News: collect + query subtabs, delete by date range.
- Bets: single view with inline collect, filters, sort, pagination, delete.
- Matches: seeds + related items.
- Dark theme; `npm run lint` and `npm run build` pass.

---

## 10. How to run

Prerequisites: Docker Desktop, Python 3.14+, Node 20+.

```bash
docker compose up -d

cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
# create backend/.env with DATABASE_URL=postgresql://pguser:pgpassword@localhost:5432/pgdb
uvicorn main:app --reload --host 0.0.0.0 --port 8000

cd frontend
npm install
npm run dev
```

Useful:

- pgAdmin: http://localhost:5050
- Health: http://localhost:8000/api/health
- Tests: `cd backend && python -m pytest tests/ -q`

---

## 11. Known issues / notes

- Matches tab is semantic matching, not sports data.
- Laya and embedding models download on first use; set `HF_HOME` for caching.
- Collection can be heavy; scoring/embeddings run in background.
- `requirements.txt` still has duplicates/stray entries.
- No deployment config or CI.

---

## 12. Environment variables

| Var          | Where used    | Example                                            |
| ------------ | ------------- | -------------------------------------------------- |
| DATABASE_URL | db_operations | postgresql://pguser:pgpassword@localhost:5432/pgdb |
| HF_HOME      | model cache   | C:/models/hf-cache                                 |
| USE_TF       | set by laya   | 0 (automatic)                                      |

---
