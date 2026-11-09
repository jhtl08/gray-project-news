import pytest

import db_operations


@pytest.fixture
def seeded_null_scores(clean_news):
    with db_operations.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO news (query, url, title, disruptiveness_score) VALUES (%s, %s, %s, %s)",
                ("q", "https://example.com/1", "title one", None),
            )
            cur.execute(
                "INSERT INTO news (query, url, title, disruptiveness_score) VALUES (%s, %s, %s, %s)",
                ("q", "https://example.com/2", "title two", None),
            )
    return None


def test_backfill_happy_path(seeded_null_scores, monkeypatch):
    monkeypatch.setattr(db_operations, "score_headlines", lambda headlines: [10, 20])

    summary = db_operations.backfill_disruptiveness_scores()

    assert summary["considered"] == 2
    assert summary["scored"] == 2
    assert summary["failed"] == 0

    with db_operations.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT disruptiveness_score FROM news ORDER BY id")
            scores = [r[0] for r in cur.fetchall()]
    assert scores == [10, 20]
