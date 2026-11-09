# Plan: Resolve Priority Issues in Gray Project News

## Context

The news pipeline is functional end-to-end, but README.md documents known
issues. This plan targets high-impact correctness, robustness, and operational
issues in the current implementation. It does not implement the large roadmap
items (Bets, Matches, full vector processing), which remain tracked in
README.md section 7.

Priority issues selected:
1. Laya model import side effects and repeated cold loads; make model loading
   efficient, lazy where appropriate, and cached across runs.
2. Scoring errors are swallowed during ingestion; no visibility or backfill path.
3. Duplicate handling must be explicit and verified for both `url` and `title`.
4. Legacy GDELT JSON files without a top-level `query` key are unusable; clean
   them up rather than adding compatibility code.
5. No automated tests; reviewer needs a repeatable gate.

Out of scope for this plan: Bets/Matches features, embedding model selection and
vector search, deployment/CI, full async ingestion, frontend label changes (user
confirmed current labels are visually correct).

## Approach

Make small, focused changes behind a reviewer gate. Each worker agent works on
an isolated git worktree/branch, runs the relevant checks, and only commits
after the reviewer agent reports PASS. The main agent orchestrates task order,
reviews diffs, and merges.

Execution model (use pi-subagents extension from the global .pi folder):
- Enable pi-subagents via `subagents_enable` before launching work.
- Main agent: orchestrates only; creates tasks, launches worker subagents,
  reviews reviewer reports, merges approved branches, updates README.md.
- Worker subagents: implement one issue group per branch/worktree, run local
  checks, but do not commit until reviewer approval.
- Reviewer subagent: independently runs lint/tests/smoke checks and reports
  PASS/FAIL with evidence before any worker commit.
- Use isolated worktrees for each worker to avoid conflicts; merge only after
  reviewer PASS.

## Files to modify

- `backend/laya_processes.py` — lazy singleton router, persistent cache config,
  preload only multilingual.
- `backend/main.py` — preload model during startup (not import side effect);
  surface ingest/scoring status.
- `backend/db_operations.py` — scoring error visibility, backfill helper,
  explicit duplicate handling tests.
- `backend/gdelt_data/` — remove legacy JSON files lacking `query`.
- `backend/tests/` (new) — pytest tests for db helpers, duplicate handling,
  ingestion compatibility, Laya import side effects.
- `README.md` — update known-issues status after fixes.

## Reuse

- `backend/db_operations.py`: `get_connection`, `init_db`, `_clean`,
  `_parse_seendate`, `_article_to_row`, `ingest_json_file`, `ingest_latest_json`.
- `backend/laya_processes.py`: `score_headlines`.
- FastAPI endpoints in `backend/main.py`.
- Existing Docker Postgres on localhost:5432.
- HuggingFace cache (`HF_HOME`, default `~/.cache/huggingface`).

## Steps

- [ ] Step 1: Enable pi-subagents (`subagents_enable`), then create feature
      branches/worktrees for each issue group and assign one worker subagent per
      branch.
- [ ] Step 2: Worker A refactors Laya loading:
      - Replace import-time `router.preload(["multilingual"])` with a lazy
        singleton `get_router()` guarded by a lock.
      - Use `Router(default="multilingual", max_loaded=1)` so only the needed
        checkpoint can load.
      - Preload in FastAPI startup via `get_router()` instead of import side
        effects.
      - Document persistent cache via `HF_HOME` and a Docker volume.
- [ ] Step 3: Reviewer verifies importing `laya_processes` does not download
      or load model weights; startup preload works; scoring still returns ints.
- [ ] Step 4: Worker B surfaces scoring failures:
      - Replace broad `except Exception: pass` with logged warning and count of
        failed titles.
      - Add `backfill_disruptiveness_scores(limit=None)` to score rows where
        `disruptiveness_score IS NULL`.
- [ ] Step 5: Worker B makes duplicate handling explicit and tested:
      - Keep unique constraints on `url` and `title`.
      - Use `ON CONFLICT DO NOTHING` (or explicit target) so duplicate url or
        title is skipped.
      - Add tests proving duplicate url and duplicate title are skipped.
- [ ] Step 6: Worker C removes legacy GDELT JSON files lacking `query` and
      adds a cleanup guard/test so ingestion fails clearly if attempted.
- [ ] Step 7: Worker D adds minimal automated tests:
      - Backend pytest for `_article_to_row`, `_parse_seendate`, duplicate
        handling, Laya lazy import, backfill happy path (mocked scorer).
- [ ] Step 8: Reviewer runs full checks on each branch before commit.
- [ ] Step 9: Main agent merges approved branches and updates README known
      issues.

## Verification

- Laya: `python -c "import laya_processes; print('import ok')"` should not
  trigger model download; `HF_HOME` persists weights across runs.
- Scoring: failed scoring logs a warning; backfill populates NULL scores.
- Duplicates: inserting same url or title twice yields one row.
- Legacy cleanup: no JSON files without `query` remain in `gdelt_data/`.
- Tests: `pytest` passes.
- Frontend: `npm run lint`, `npm run build`.
- Backend smoke: `uvicorn main:app`, `GET /api/health`, ingest latest JSON.
- Reviewer gate: no commit unless checks pass.
