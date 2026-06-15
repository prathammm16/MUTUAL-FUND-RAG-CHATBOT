"""Build Chroma index from committed chunks when the store is missing or invalid."""

from __future__ import annotations

import logging

from ingestion.embed import release_embedding_models
from ingestion.index import (
    COLLECTION_NAME,
    collection_exists,
    index_corpus,
    resolve_index_dir,
    validate_indexed_store,
)

logger = logging.getLogger(__name__)


def bootstrap_index_if_needed(*, force: bool = False) -> bool:
    """
    Ensure ``data/chunks/`` is embedded into Chroma at ``VECTOR_STORE_PATH``.

    Returns True when the index exists and passes validation after this call.
    """
    store = str(resolve_index_dir())
    exists = collection_exists(store)
    errors = validate_indexed_store(store) if exists else ["collection missing"]

    if exists and not errors and not force:
        return True

    if exists and errors:
        logger.warning("Index invalid (%s) — rebuilding", "; ".join(errors))

    try:
        total = index_corpus(reset_collection=True)
        errors = validate_indexed_store(store)
        if errors:
            logger.error("Index bootstrap validation failed: %s", "; ".join(errors))
            return False
        logger.info("Index bootstrap OK: %d chunks in %s", total, COLLECTION_NAME)
        release_embedding_models()
        return True
    except Exception:
        logger.exception("Index bootstrap failed")
        return False
