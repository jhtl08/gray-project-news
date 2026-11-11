import pytest

import db_operations


def test_market_to_row_mapping():
    market = {
        "id": "  123  ",
        "question": "  Will it rain?  ",
        "slug": "will-it-rain",
        "outcomePrices": "[0.4, 0.6]",
        "volume": "1000",
        "volumeNum": "999",
        "liquidity": "500",
        "liquidityNum": "499",
        "endDate": "2025-01-02T03:04:05Z",
        "active": True,
        "closed": False,
        "tags": ["weather"],
    }
    row = db_operations._market_to_row(market)
    assert row is not None
    assert row["polymarket_id"] == "123"
    assert row["question"] == "Will it rain?"
    assert row["slug"] == "will-it-rain"
    assert row["outcome_prices"] == "[0.4, 0.6]"
    assert row["prices"] == "[0.4, 0.6]"
    assert row["volume"] == "1000"
    assert row["liquidity"] == "500"
    assert row["end_date"] == "2025-01-02T03:04:05Z"
    assert row["active"] is True
    assert row["closed"] is False
    assert row["tags"] == ["weather"]


def test_market_to_row_prefers_polymarket_id():
    row = db_operations._market_to_row({"polymarket_id": "abc", "id": "ignored"})
    assert row is not None
    assert row["polymarket_id"] == "abc"


def test_market_to_row_requires_id():
    assert db_operations._market_to_row({"question": "no id"}) is None
    assert db_operations._market_to_row({}) is None


def test_market_to_row_rejects_non_dict():
    assert db_operations._market_to_row("not a dict") is None


def test_clean_helper_trims_and_drops_empty():
    assert db_operations._clean("  hello  ") == "hello"
    assert db_operations._clean("") is None
    assert db_operations._clean(None) is None