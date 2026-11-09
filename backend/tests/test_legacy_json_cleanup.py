"""Guard against legacy GDELT JSON files without a top-level ``query`` key."""

import json
from pathlib import Path

import pytest

import db_operations


DATA_DIR = Path(__file__).resolve().parents[1] / "gdelt_data"


def test_no_gdelt_json_files_lack_query():
    """Every remaining GDELT JSON file must contain a non-empty ``query``."""
    offenders = db_operations.find_invalid_json_files(DATA_DIR)
    assert offenders == [], f"JSON files without a usable query: {offenders}"


def test_validate_json_file_rejects_missing_query(tmp_path):
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps({"articles": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        db_operations.validate_json_file(path)


def test_validate_json_file_accepts_query(tmp_path):
    path = tmp_path / "ok.json"
    path.write_text(json.dumps({"query": "news", "articles": []}), encoding="utf-8")
    payload = db_operations.validate_json_file(path)
    assert payload["query"] == "news"
