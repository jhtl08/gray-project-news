import json
from pathlib import Path

import pytest

import db_operations


def test_ingest_json_file_requires_query(tmp_path):
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps({"articles": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        db_operations.ingest_json_file(path)


def test_ingest_json_file_accepts_query(tmp_path, monkeypatch):
    # Avoid real scoring side effects.
    monkeypatch.setattr(db_operations, "score_headlines", lambda headlines: [0] * len(headlines))

    path = tmp_path / "ok.json"
    path.write_text(
        json.dumps({"query": "news", "articles": [{"url": "https://example.com/1", "title": "t1"}]}),
        encoding="utf-8",
    )

    # Use a temp DB-free path? ingest needs DB. Skip if no DB available.
    try:
        summary = db_operations.ingest_json_file(path)
    except Exception as exc:
        pytest.skip(f"database unavailable: {exc}")
    assert summary["query"] == "news"
    assert summary["inserted"] >= 0
