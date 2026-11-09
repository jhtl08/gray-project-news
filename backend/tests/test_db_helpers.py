from datetime import datetime, timezone

import pytest

import db_operations


def test_parse_seendate_valid():
    result = db_operations._parse_seendate("20240102T030405Z")
    assert result == datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def test_parse_seendate_none_and_invalid():
    assert db_operations._parse_seendate(None) is None
    assert db_operations._parse_seendate("") is None
    assert db_operations._parse_seendate("not-a-date") is None


def test_article_to_row_mapping():
    article = {
        "url": " https://example.com/a ",
        "title": "  Hello  ",
        "seendate": "20240102T030405Z",
        "language": "English",
        "sourcecountry": "US",
    }
    row = db_operations._article_to_row(article, "query1")
    assert row is not None
    assert row["query"] == "query1"
    assert row["url"] == "https://example.com/a"
    assert row["title"] == "Hello"
    assert row["seendate"] == datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    assert row["language"] == "English"
    assert row["sourcecountry"] == "US"


def test_article_to_row_requires_url():
    assert db_operations._article_to_row({"title": "no url"}, "q") is None
