import pytest


def test_embed_texts_empty_input():
    embedding = pytest.importorskip("embedding")
    result = embedding.embed_texts([])
    assert result == []


def test_embed_texts_returns_list_or_none():
    embedding = pytest.importorskip("embedding")
    result = embedding.embed_texts(["hello world"])
    assert result is None or (
        isinstance(result, list)
        and all(isinstance(vec, list) for vec in result)
    )
    if isinstance(result, list) and result:
        assert all(
            all(isinstance(x, float) for x in vec) for vec in result
        )


def test_embed_texts_none_input():
    embedding = pytest.importorskip("embedding")
    # Graceful degradation: None input is treated as no items -> [] or None.
    result = embedding.embed_texts(None)
    assert result is None or result == []
