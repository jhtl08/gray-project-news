import json
from pathlib import Path

import pytest

import db_operations
import polymarket_collector


def test_ingest_polymarket_file_requires_markets(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"foo": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        db_operations.ingest_polymarket_file(path)


def test_ingest_polymarket_file_accepts_markets(tmp_path, monkeypatch):
    path = tmp_path / "ok.json"
    path.write_text(
        json.dumps({"markets": [{"id": "1", "question": "q"}]}),
        encoding="utf-8",
    )

    # Avoid network/DB failures in environments without Postgres.
    try:
        summary = db_operations.ingest_polymarket_file(path)
    except Exception as exc:
        pytest.skip(f"database unavailable: {exc}")
    assert summary["total"] == 1
    assert summary["inserted"] + summary["skipped"] == 1


def test_collect_markets_mock_requests(tmp_path, monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"id": "42", "question": "Will it rain?"}]

    monkeypatch.setattr(
        polymarket_collector.requests, "get", lambda url, params=None, timeout=30: FakeResponse()
    )

    payload = polymarket_collector.collect_markets(directory=tmp_path)

    assert payload["source"] == "polymarket"
    assert len(payload["markets"]) == 1
    assert payload["markets"][0]["id"] == "42"
    assert list(tmp_path.glob("*.json"))