#!/usr/bin/env python3
"""Fetch five Groww scheme pages into data/raw/*.md."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ingestion.fetch import DEFAULT_RAW_DIR, fetch_all_schemes, fetch_scheme_to_raw  # noqa: E402
from app.config import get_scheme  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch Groww pages to data/raw/")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--scheme-id", help="Fetch one scheme only")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    try:
        if args.scheme_id:
            scheme = get_scheme(args.scheme_id)
            if not scheme:
                logging.error("Unknown scheme_id: %s", args.scheme_id)
                return 1
            artifacts = fetch_scheme_to_raw(scheme, raw_dir=args.raw_dir)
            logging.info("Wrote %s", artifacts.html.name)
            logging.info("Fetched 1 scheme into %s", args.raw_dir)
        else:
            paths = fetch_all_schemes(raw_dir=args.raw_dir)
            logging.info(
                "Fetched %d schemes (html+json+md each) into %s",
                len(paths),
                args.raw_dir,
            )
        return 0
    except Exception as exc:
        logging.error("Fetch failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
