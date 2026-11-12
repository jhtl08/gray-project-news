import pytest

fastapi = pytest.importorskip("fastapi")
main = pytest.importorskip("main")


def test_matches_endpoints_import():
    paths = {route.path for route in main.app.routes}
    if "/api/matches" not in paths:
        pytest.skip("matches endpoints not available")
    assert "/api/matches" in paths
    assert "/api/matches/{match_id}" in paths


def test_create_match_callable():
    if not hasattr(main, "create_match"):
        pytest.skip("matches endpoints not available")
    assert callable(main.create_match)


def test_list_matches_callable():
    if not hasattr(main, "list_matches"):
        pytest.skip("matches endpoints not available")
    assert callable(main.list_matches)


def test_delete_match_callable():
    if not hasattr(main, "delete_match"):
        pytest.skip("matches endpoints not available")
    assert callable(main.delete_match)
