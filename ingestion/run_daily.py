"""
Daily ingestion pipeline (Phase 7): fetch → parse → chunk → index with lock + atomic swap.

Usage::

    python -m ingestion.run_daily
    python -m ingestion.run_daily --skip-fetch   # use existing data/raw/
    python -m ingestion.run_daily --offline      # alias for --skip-fetch
"""

from __future__ import annotations

import argparse
import gc
import logging
import os
import shutil
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_all_schemes, get_settings
from ingestion.chunk_store import MIN_TOTAL_CHUNKS, validate_chunks_store
from ingestion.corpus import DEFAULT_CORPUS_DIR, build_corpus_from_imports
from ingestion.fetch import DEFAULT_RAW_DIR, FetchError, fetch_all_schemes
from ingestion.index import (
    close_chroma_clients,
    collection_exists,
    get_indexed_chunk_count,
    resolve_index_dir,
)
from ingestion.pipeline_state import (
    DEFAULT_INGEST_STATE_DIR,
    IngestLockError,
    IngestStatus,
    ingest_lock,
    ingest_run_context,
    read_ingest_status,
    write_ingest_status,
)
from ingestion.validate import validate_corpus_dir, log_validation_report

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
STAGING_SUFFIX = ".staging"
PREVIOUS_SUFFIX = ".previous"
DEFAULT_MAX_CHUNK_DROP_RATIO = 0.5


class DailyIngestError(Exception):
    """Pipeline failure; live index must remain unchanged."""


@dataclass(frozen=True)
class DailyIngestResult:
    ingested_at: str
    chunk_count: int
    schemes: int
    staging_dir: Path
    live_dir: Path


def _utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def staging_index_dir(live_dir: Path | None = None) -> Path:
    live = live_dir or resolve_index_dir()
    return live.parent / f"{live.name}{STAGING_SUFFIX}"


def previous_index_dir(live_dir: Path | None = None) -> Path:
    live = live_dir or resolve_index_dir()
    return live.parent / f"{live.name}{PREVIOUS_SUFFIX}"


def _on_rm_error(func, path: str, exc_info) -> None:
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def _remove_tree(path: Path) -> None:
    if not path.exists():
        return
    for attempt in range(6):
        try:
            shutil.rmtree(path, onerror=_on_rm_error)
            if not path.exists():
                return
        except OSError:
            pass
        time.sleep(0.25 * (attempt + 1))
        gc.collect()
    if path.exists():
        shutil.rmtree(path, onerror=_on_rm_error, ignore_errors=True)


def check_chunk_count_drop(
    new_count: int,
    old_count: int,
    *,
    max_drop_ratio: float = DEFAULT_MAX_CHUNK_DROP_RATIO,
) -> None:
    """PH7-03: fail if chunk count drops more than ``max_drop_ratio`` vs prior index."""
    if old_count <= 0:
        return
    if new_count == 0:
        raise DailyIngestError("IG-09: zero chunks after build; aborting swap")
    ratio = 1.0 - (new_count / old_count)
    if ratio > max_drop_ratio:
        raise DailyIngestError(
            f"PH7-03: chunk count dropped {ratio:.0%} ({old_count} → {new_count}); "
            f"threshold is {max_drop_ratio:.0%}"
        )


def atomic_swap_index(
    staging: Path,
    live: Path | None = None,
) -> Path:
    """
    Promote staging Chroma dir to live (SK-03, PH7-01).

    Keeps ``live.previous`` as rollback snapshot until next successful run.
    """
    live_dir = live or resolve_index_dir()
    prev_dir = previous_index_dir(live_dir)

    if not staging.is_dir():
        raise DailyIngestError(f"staging index missing: {staging}")

    _remove_tree(prev_dir)
    gc.collect()
    if live_dir.exists() and any(live_dir.iterdir()):
        try:
            shutil.copytree(live_dir, prev_dir)
        except OSError as exc:
            raise DailyIngestError(
                f"PH7-01: could not backup live index to {prev_dir}: {exc}"
            ) from exc
    _remove_tree(live_dir)
    close_chroma_clients()
    time.sleep(0.3)
    gc.collect()
    if live_dir.exists():
        raise DailyIngestError(f"PH7-01: could not clear live index at {live_dir}")
    if not staging.exists():
        raise DailyIngestError(f"staging index missing: {staging}")
    shutil.copytree(staging, live_dir)
    _remove_tree(staging)
    return live_dir


def run_fetch_step(*, raw_dir: Path | None = None) -> int:
    """Fetch all five schemes; raises on partial failure (IG-02)."""
    written = fetch_all_schemes(raw_dir=raw_dir)
    expected = len(get_all_schemes())
    if len(written) != expected:
        raise DailyIngestError(
            f"IG-02: partial fetch {len(written)}/{expected}; keeping previous index"
        )
    return len(written)


def run_parse_chunk_step(
    *,
    raw_dir: Path | None = None,
    corpus_dir: Path | None = None,
    chunks_dir: Path | None = None,
) -> int:
    """Build corpus + chunks from raw/uploads."""
    built = build_corpus_from_imports(
        raw_dir=raw_dir,
        corpus_dir=corpus_dir,
        build_chunks=True,
        chunks_dir=chunks_dir,
    )
    if len(built) != len(get_all_schemes()):
        raise DailyIngestError(
            f"Expected {len(get_all_schemes())} parsed schemes, got {len(built)}"
        )

    report = validate_corpus_dir(corpus_dir or DEFAULT_CORPUS_DIR)
    log_validation_report(report)
    if not report.ok:
        raise DailyIngestError("Corpus validation failed")

    chunk_errors = validate_chunks_store(chunks_dir)
    if chunk_errors:
        raise DailyIngestError("; ".join(chunk_errors))

    from ingestion.chunk_store import load_all_chunks

    return len(load_all_chunks(chunks_dir))


def run_index_staging_step(
    staging_dir: Path,
    *,
    ingested_at: str | None = None,
) -> int:
    """Build Chroma index into staging directory (subprocess releases DB locks)."""
    _remove_tree(staging_dir)
    ingested = ingested_at or _utc_date()
    cmd = [
        sys.executable,
        "-m",
        "ingestion.index_worker",
        str(staging_dir.resolve()),
        "--ingested-at",
        ingested,
    ]
    import os

    proc = subprocess.run(
        cmd,
        cwd=str(_PROJECT_ROOT),
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise DailyIngestError(f"IG-08: index worker failed: {detail}")

    total = 0
    for line in (proc.stdout or "").splitlines():
        if line.startswith("indexed="):
            total = int(line.split("=", 1)[1])
            break
    if total == 0:
        from ingestion.index import get_indexed_chunk_count

        total = get_indexed_chunk_count(str(staging_dir))

    if total < MIN_TOTAL_CHUNKS:
        raise DailyIngestError(
            f"Indexed only {total} chunks; need >={MIN_TOTAL_CHUNKS}"
        )

    gc.collect()
    time.sleep(0.5)
    return total


def run_daily_ingest(
    *,
    skip_fetch: bool = False,
    raw_dir: Path | None = None,
    corpus_dir: Path | None = None,
    chunks_dir: Path | None = None,
    live_index_dir: Path | None = None,
    max_chunk_drop_ratio: float = DEFAULT_MAX_CHUNK_DROP_RATIO,
    lock_ttl_sec: int | None = None,
) -> DailyIngestResult:
    """
    Full daily pipeline under lock with atomic index swap.

    On any failure, the live vector store is not replaced.
    """
    settings = get_settings()
    live_dir = live_index_dir or resolve_index_dir()
    staging_dir = staging_index_dir(live_dir)
    ttl = lock_ttl_sec if lock_ttl_sec is not None else settings.ingest_lock_ttl_seconds
    ingested_at = _utc_date()
    has_live_index = (
        live_dir.exists()
        and collection_exists(str(live_dir))
        and get_indexed_chunk_count(str(live_dir)) >= MIN_TOTAL_CHUNKS
    )
    prior_count = get_indexed_chunk_count(str(live_dir)) if has_live_index else 0
    close_chroma_clients()

    state_dir = DEFAULT_INGEST_STATE_DIR
    with ingest_lock(state_dir, ttl_sec=ttl):
        with ingest_run_context(state_dir, ttl_sec=ttl) as status:
            try:
                schemes_fetched = 0
                if not skip_fetch:
                    schemes_fetched = run_fetch_step(raw_dir=raw_dir)
                    status.schemes_fetched = schemes_fetched
                    write_ingest_status(status, state_dir)

                chunk_count = run_parse_chunk_step(
                    raw_dir=raw_dir,
                    corpus_dir=corpus_dir,
                    chunks_dir=chunks_dir,
                )
                check_chunk_count_drop(
                    chunk_count,
                    prior_count,
                    max_drop_ratio=max_chunk_drop_ratio,
                )

                if has_live_index:
                    indexed = run_index_staging_step(
                        live_dir,
                        ingested_at=ingested_at,
                    )
                else:
                    _remove_tree(staging_dir)
                    indexed = run_index_staging_step(
                        staging_dir,
                        ingested_at=ingested_at,
                    )
                    atomic_swap_index(staging_dir, live_dir)

                status.last_success_at = datetime.now(timezone.utc).isoformat()
                status.last_chunk_count = indexed
                status.last_error = ""
                status.schemes_fetched = schemes_fetched
                write_ingest_status(status, state_dir)

                logger.info(
                    "Daily ingest OK: %d chunks, ingested_at=%s",
                    indexed,
                    ingested_at,
                )
                return DailyIngestResult(
                    ingested_at=ingested_at,
                    chunk_count=indexed,
                    schemes=len(get_all_schemes()),
                    staging_dir=staging_dir,
                    live_dir=live_dir,
                )
            except Exception as exc:
                status.last_error = str(exc)
                write_ingest_status(status, state_dir)
                _remove_tree(staging_dir)
                logger.exception("Daily ingest failed: %s", exc)
                raise DailyIngestError(str(exc)) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Daily ingestion pipeline (Phase 7)")
    parser.add_argument(
        "--skip-fetch",
        "--offline",
        action="store_true",
        dest="skip_fetch",
        help="Skip Groww fetch; use existing data/raw/ or uploads/",
    )
    parser.add_argument(
        "--max-chunk-drop",
        type=float,
        default=DEFAULT_MAX_CHUNK_DROP_RATIO,
        help="Fail if chunk count drops more than this fraction vs live index (PH7-03)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    try:
        settings = get_settings()
        result = run_daily_ingest(
            skip_fetch=args.skip_fetch,
            max_chunk_drop_ratio=settings.max_ingest_chunk_drop_ratio
            if args.max_chunk_drop == DEFAULT_MAX_CHUNK_DROP_RATIO
            else args.max_chunk_drop,
        )
        print(
            f"OK: indexed {result.chunk_count} chunks, "
            f"ingested_at={result.ingested_at}, store={result.live_dir}"
        )
        return 0
    except IngestLockError as exc:
        logging.error("%s", exc)
        return 2
    except DailyIngestError as exc:
        logging.error("%s", exc)
        return 1
    except FetchError as exc:
        logging.error("Fetch failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
