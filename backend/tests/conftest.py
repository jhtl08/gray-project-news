import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest


@pytest.fixture
def clean_news():
    """Truncate the news table before and after a test."""
    import db_operations

    try:
        with db_operations.get_connection() as conn:
            conn.execute("TRUNCATE TABLE news RESTART IDENTITY CASCADE")
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"database unavailable: {exc}")
    yield
    try:
        with db_operations.get_connection() as conn:
            conn.execute("TRUNCATE TABLE news RESTART IDENTITY CASCADE")
    except Exception:
        pass
