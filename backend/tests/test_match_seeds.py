import pytest

db_operations = pytest.importorskip("db_operations")


@pytest.fixture
def db_available():
    try:
        db_operations.init_db()
        with db_operations.get_connection() as conn:
            conn.execute("SELECT 1")
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"database unavailable: {exc}")
    yield


def test_match_seed_create_list_delete(db_available):
    insert = getattr(db_operations, "insert_match_seed", None)
    getter = getattr(db_operations, "get_match_seed", None)
    if not callable(insert):
        pytest.skip("insert_match_seed not available")

    seed_id = insert(text="seed text", metadata={"source_type": "news", "source_id": 1}, vector=None)
    assert isinstance(seed_id, int)

    try:
        # "list" via direct query (endpoint-level listing is covered elsewhere)
        with db_operations.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, text FROM match_seeds WHERE id = %s", (seed_id,))
                row = cur.fetchone()
        assert row is not None
        assert row[1] == "seed text"

        if callable(getter):
            fetched = getter(seed_id)
            assert fetched is not None
            assert fetched["text"] == "seed text"

        with db_operations.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM match_seeds WHERE id = %s", (seed_id,))
                assert cur.rowcount == 1

        if callable(getter):
            assert getter(seed_id) is None
    finally:
        # Best-effort cleanup in case of assertion failure.
        try:
            with db_operations.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM match_seeds WHERE id = %s", (seed_id,))
        except Exception:
            pass
