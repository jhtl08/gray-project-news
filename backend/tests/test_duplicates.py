import json

import pytest

import db_operations


def _write_json(path, articles):
    path.write_text(
        json.dumps({"query": "q", "articles": articles}),
        encoding="utf-8",
    )


def test_duplicate_url_skipped(tmp_path, clean_news, monkeypatch):
    monkeypatch.setattr(db_operations, "score_headlines", lambda h: [0] * len(h))

    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    _write_json(first, [{"url": "https://example.com/a", "title": "title a"}])
    _write_json(second, [{"url": "https://example.com/a", "title": "title a 2"}])

    s1 = db_operations.ingest_json_file(first)
    s2 = db_operations.ingest_json_file(second)

    assert s1["inserted"] == 1
    assert s2["inserted"] == 0


def test_duplicate_title_skipped(tmp_path, clean_news, monkeypatch):
    monkeypatch.setattr(db_operations, "score_headlines", lambda h: [0] * len(h))

    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    _write_json(first, [{"url": "https://example.com/a", "title": "same title"}])
    _write_json(second, [{"url": "https://example.com/b", "title": "same title"}])

    s1 = db_operations.ingest_json_file(first)
    s2 = db_operations.ingest_json_file(second)

    assert s1["inserted"] == 1
    assert s2["inserted"] == 0
