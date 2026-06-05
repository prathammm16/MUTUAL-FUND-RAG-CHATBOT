#!/usr/bin/env python3
"""One-shot Railway bootstrap: build Chroma index then release embedding RAM."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ingestion.embed import release_embedding_models  # noqa: E402
from ingestion.index import COLLECTION_NAME, index_corpus, validate_indexed_store  # noqa: E402


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        total = index_corpus(reset_collection=True)
        errors = validate_indexed_store()
        if errors:
            logging.error("Index validation failed: %s", "; ".join(errors))
            return 1
        logging.info("Railway bootstrap OK: %d chunks in %s", total, COLLECTION_NAME)
        release_embedding_models()
        return 0
    except Exception as exc:
        logging.error("Bootstrap failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
