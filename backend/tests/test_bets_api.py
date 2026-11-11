import pytest

fastapi = pytest.importorskip("fastapi")


def test_bets_endpoints_import():
    main = pytest.importorskip("main")
    paths = {route.path for route in main.app.routes}
    assert "/api/bets" in paths
    assert "/api/bets/collect" in paths
    assert "/api/bets/backfill-scores" in paths


def test_get_bets_callable():
    main = pytest.importorskip("main")
    assert callable(main.get_bets)


def test_collect_bets_callable():
    main = pytest.importorskip("main")
    assert callable(main.collect_bets)