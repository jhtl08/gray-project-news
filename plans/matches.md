# Plan: Matches Section with pgvector Embeddings

## Context

The Matches tab is still a placeholder. This plan adds semantic embeddings to news
and bets, lets users mark a news or bet as a match seed, and shows the top 5
semantically related items from the opposite type in the Matches tab.

Embedding model: `intfloat/multilingual-e5-small` via `transformers`
(average pooling, 384 dimensions, multilingual). Similarity threshold: 0.7
cosine similarity. A news seed matches bets; a bet seed matches news.

## Approach

Reuse the existing pipeline patterns:
- Add `content_vector VECTOR(384)` to `news` and `bets`.
- Add an `embedding.py` module with a lazy singleton embedder.
- Add embedding generation during ingestion and a backfill function.
- Add a `match_seeds` table storing selected seeds.
- Add API endpoints to create/list/delete seeds and fetch related items.
- Add "Make match" buttons to News and Bets tables.
- Implement Matches tab UI.

Use pi-subagents for implementation, with reviewer gates. Each subagent must
return Result, Output, Evidence, and Learnings.

## Database changes

- `news.content_vector VECTOR(384)` (pin dimension; create HNSW index).
- `bets.content_vector VECTOR(384)` (add column + index).
- `match_seeds`:
  - id BIGSERIAL PK
  - source_type TEXT NOT NULL ('news' or 'bet')
  - source_id BIGINT NOT NULL
  - title TEXT NOT NULL
  - content_vector VECTOR(384) NOT NULL
  - created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  - UNIQUE(source_type, source_id)

Indexes: HNSW on all vector columns for cosine distance.

## Embedding generation

`backend/embedding.py`:
- Lazy singleton `get_embedder()` loading `intfloat/multilingual-e5-small`.
- `embed_texts(texts: list[str]) -> list[list[float]]` using average pooling
  and L2 normalization.
- Prefix text with "query: " per E5 usage.
- Fallback to None if model unavailable.

Backfill functions:
- `backfill_news_embeddings(limit=None)`
- `backfill_bet_embeddings(limit=None)`

Ingestion:
- Generate embedding for newly inserted news/bets when title/question present.
- Store in `content_vector`.
- Failures logged, not fatal.

## Matching logic

For a seed:
- If source_type='news', query `bets` where `content_vector` is not null,
  order by `content_vector <=> seed_vector`, limit 5, filter similarity >= 0.7.
- If source_type='bet', query `news` similarly.
- Cosine similarity = 1 - cosine distance.

## API endpoints

- `POST /api/matches` body `{source_type, source_id}` creates a seed.
- `GET /api/matches` lists seeds.
- `DELETE /api/matches/{id}` removes a seed.
- `GET /api/matches/{id}/related` returns top 5 related items.

Also add embedding backfill endpoints:
- `POST /api/news/backfill-embeddings`
- `POST /api/bets/backfill-embeddings`

## Frontend changes

- News table: add "Match" button per row.
- Bets table: add "Match" button per row.
- Matches tab: list seeds; selecting a seed shows related items with similarity.

## Files to modify

- `backend/db_operations.py` — schema, migrations, ingest embeddings, backfill, match seeds, queries.
- `backend/embedding.py` (new) — embedder singleton.
- `backend/laya_processes.py` — no change (embeddings separate).
- `backend/main.py` — match endpoints + embedding backfill.
- `frontend/src/News.jsx` — Match button.
- `frontend/src/Bets.jsx` — Match button.
- `frontend/src/Matches.jsx` — seeds + related items UI.
- `backend/tests/` — embedding/matching tests.
- `README.md` — document matches.

## Reuse

- `get_connection`, `init_db`, ingest patterns.
- FastAPI endpoint patterns.
- Frontend table/pagination patterns.

## Steps

- [x] Step 1: Enable pi-subagents and create worktrees.
- [x] Step 2: Worker A implements embedding module + DB vector schema/migrations.
- [x] Step 3: Reviewer verifies embedding module and schema.
- [x] Step 4: Worker B updates ingestion + backfill for news/bets embeddings.
- [x] Step 5: Reviewer verifies embeddings.
- [x] Step 6: Worker C implements match seed endpoints + related query.
- [x] Step 7: Reviewer verifies API.
- [x] Step 8: Worker D implements frontend Match buttons and Matches tab.
- [x] Step 9: Reviewer verifies frontend.
- [x] Step 10: Worker E adds tests.
- [x] Step 11: Reviewer runs full checks.
- [x] Step 12: Main agent merges and updates README.

## Verification

- Embeddings generated for news/bets.
- Creating a seed returns related items with similarity >= 0.7.
- Matches tab displays seeds and related items.
- `pytest` passes.
- Frontend lint/build pass.
- Reviewer gate before commits.
