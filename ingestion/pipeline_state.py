"""
Lock file and ingest status for Phase 7 daily pipeline (SK-01, AP-06, PH7-04).
"""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INGEST_STATE_DIR = _PROJECT_ROOT / "data" / "ingest"

LOCK_FILENAME = ".ingest.lock"
STATUS_FILENAME = ".ingest_status.json"
DEFAULT_LOCK_TTL_SEC = 7200


class IngestLockError(RuntimeError):
    """Another ingest is in progress or lock is held (SK-01)."""


@dataclass
class IngestStatus:
    ingesting: bool = False
    started_at: str = ""
    finished_at: str = ""
    last_success_at: str = ""
    last_error: str = ""
    last_chunk_count: int = 0
    schemes_fetched: int = 0
    run_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else DEFAULT_INGEST_STATE_DIR


def lock_path(state_dir: Path | str | None = None) -> Path:
    return _state_dir(state_dir) / LOCK_FILENAME


def status_path(state_dir: Path | str | None = None) -> Path:
    return _state_dir(state_dir) / STATUS_FILENAME


def read_ingest_status(state_dir: Path | str | None = None) -> IngestStatus:
    path = status_path(state_dir)
    if not path.is_file():
        return IngestStatus()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return IngestStatus(
            ingesting=bool(data.get("ingesting", False)),
            started_at=str(data.get("started_at", "")),
            finished_at=str(data.get("finished_at", "")),
            last_success_at=str(data.get("last_success_at", "")),
            last_error=str(data.get("last_error", "")),
            last_chunk_count=int(data.get("last_chunk_count", 0) or 0),
            schemes_fetched=int(data.get("schemes_fetched", 0) or 0),
            run_id=str(data.get("run_id", "")),
        )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("Invalid ingest status file: %s", exc)
        return IngestStatus()


def write_ingest_status(status: IngestStatus, state_dir: Path | str | None = None) -> None:
    path = status_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status.to_dict(), indent=2) + "\n", encoding="utf-8")


def is_ingesting(state_dir: Path | str | None = None) -> bool:
    return read_ingest_status(state_dir).ingesting


def _lock_is_stale(lock_file: Path, ttl_sec: int) -> bool:
    if not lock_file.is_file():
        return False
    age = time.time() - lock_file.stat().st_mtime
    return age > ttl_sec


def acquire_ingest_lock(
    state_dir: Path | str | None = None,
    *,
    ttl_sec: int = DEFAULT_LOCK_TTL_SEC,
) -> Path:
    """
    Create ``.ingest.lock`` under ``data/ingest/`` (SK-01). Removes stale locks.
    """
    path = lock_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.is_file():
        if _lock_is_stale(path, ttl_sec):
            logger.warning("Removing stale ingest lock (PH7-04): %s", path)
            path.unlink(missing_ok=True)
        else:
            raise IngestLockError(
                f"Ingestion already in progress (lock: {path}). "
                "Wait for the job to finish or remove a stale lock after TTL."
            )

    payload = {
        "pid": os.getpid(),
        "started_at": _utc_now_iso(),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def release_ingest_lock(state_dir: Path | str | None = None) -> None:
    lock_path(state_dir).unlink(missing_ok=True)


@contextmanager
def ingest_lock(
    state_dir: Path | str | None = None,
    *,
    ttl_sec: int = DEFAULT_LOCK_TTL_SEC,
) -> Iterator[Path]:
    path = acquire_ingest_lock(state_dir, ttl_sec=ttl_sec)
    try:
        yield path
    finally:
        release_ingest_lock(state_dir)


@contextmanager
def ingest_run_context(
    state_dir: Path | str | None = None,
    *,
    ttl_sec: int = DEFAULT_LOCK_TTL_SEC,
    run_id: str = "",
) -> Iterator[IngestStatus]:
    """Set ``ingesting=true`` for health checks; restore prior fields on exit."""
    state_root = _state_dir(state_dir)
    prior = read_ingest_status(state_root)
    active = IngestStatus(
        ingesting=True,
        started_at=_utc_now_iso(),
        run_id=run_id or _utc_now_iso(),
        last_success_at=prior.last_success_at,
        last_chunk_count=prior.last_chunk_count,
    )
    write_ingest_status(active, state_root)
    try:
        yield active
    finally:
        active.ingesting = False
        active.finished_at = _utc_now_iso()
        write_ingest_status(active, state_root)
