"""Shared pytest helpers."""

from __future__ import annotations

import pytest


def require_local_embeddings() -> None:
    """Skip integration tests when the active local embedding backend is missing."""
    from app.config import get_settings

    backend = get_settings().resolved_embedding_backend()
    if backend == "fastembed":
        pytest.importorskip("fastembed")
    else:
        pytest.importorskip("sentence_transformers")
