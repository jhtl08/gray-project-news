"""Text embedding helpers using ``intfloat/multilingual-e5-small``.

The model is loaded lazily and cached as a singleton so importing this module
has no download or loading side effects. All public functions degrade
gracefully (return ``None``) when the required libraries/model are unavailable.
"""

from __future__ import annotations

import threading
from typing import Any

_MODEL_NAME = "intfloat/multilingual-e5-small"

_embedder = None
_embedder_lock = threading.Lock()
_UNSET = object()


def _unpack_embedder(embedder):
    """Best-effort extraction of (tokenizer, model) from various shapes."""
    if embedder is None:
        return None
    if isinstance(embedder, (tuple, list)):
        if len(embedder) >= 2:
            return embedder[0], embedder[1]
        return None
    if isinstance(embedder, dict):
        tokenizer = embedder.get("tokenizer") or embedder.get("tok")
        model = embedder.get("model")
        if tokenizer is not None and model is not None:
            return tokenizer, model
        return None
    tokenizer = getattr(embedder, "tokenizer", None)
    if tokenizer is None:
        tokenizer = getattr(embedder, "tok", None)
    model = getattr(embedder, "model", None)
    if tokenizer is not None and model is not None:
        return tokenizer, model
    return None


def get_embedder():
    """Lazy, thread-safe singleton accessor for the embedding model.

    Returns a ``(tokenizer, model)`` tuple, or ``None`` if unavailable.
    """
    global _embedder
    if _embedder is _UNSET:
        with _embedder_lock:
            if _embedder is _UNSET:
                try:
                    from transformers import AutoTokenizer, AutoModel

                    tokenizer = AutoTokenizer.from_pretrained(_MODEL_NAME)
                    model = AutoModel.from_pretrained(_MODEL_NAME)
                    try:
                        model.eval()
                    except Exception:
                        pass
                    _embedder = (tokenizer, model)
                except Exception:
                    _embedder = None
    return _embedder


# Sentinel initialization.
_embedder = _UNSET


def embed_texts(texts):
    """Embed a list of texts and return L2-normalized averaged vectors.

    Each input is prefixed with ``"passage: "``. Returns ``None`` when the
    model or required libraries are unavailable or embedding fails.
    """
    if texts is None:
        return None
    try:
        items = list(texts)
    except TypeError:
        return None
    if not items:
        return []

    unpacked = _unpack_embedder(get_embedder())
    if unpacked is None:
        return None
    tokenizer, model = unpacked

    try:
        import torch

        prefixed = ["passage: " + str(text) for text in items]
        inputs = tokenizer(
            prefixed,
            padding=True,
            truncation=True,
            return_tensors="pt",
        )
        with torch.no_grad():
            outputs = model(**inputs)
        token_embeddings = outputs.last_hidden_state
        attention_mask = inputs["attention_mask"]
        mask = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        summed = (token_embeddings * mask).sum(dim=1)
        counts = mask.sum(dim=1).clamp(min=1e-9)
        embeddings = summed / counts
        norms = torch.norm(embeddings, p=2, dim=1, keepdim=True).clamp(min=1e-9)
        embeddings = embeddings / norms
        return embeddings.detach().cpu().tolist()
    except Exception:
        return None


# Re-initialise sentinel after function definitions (module-level).
_embedder = _UNSET