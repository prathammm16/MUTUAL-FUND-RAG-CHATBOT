#!/usr/bin/env python3
"""One-shot Railway bootstrap: build Chroma index then release embedding RAM."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ingestion.bootstrap import bootstrap_index_if_needed  # noqa: E402


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return 0 if bootstrap_index_if_needed(force=True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
