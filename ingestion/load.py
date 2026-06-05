"""
Import loader for local corpus files (Phase 1 task 1.3).

Reads markdown from ``uploads/*.md`` and ``data/raw/`` (uploads take precedence
per scheme when both exist).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.config import (
    get_scheme,
    resolve_scheme_id_from_import_stem,
    resolve_scheme_id_from_url,
)
from ingestion.parse import ParsedScheme, extract_source_url, parse_document

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UPLOADS_DIR = _PROJECT_ROOT / "uploads"
DEFAULT_RAW_DIR = _PROJECT_ROOT / "data" / "raw"

_IMPORT_GLOBS = ("*.md", "*.markdown", "*.txt")


@dataclass(frozen=True)
class RawDocument:
    """Loaded file before parsing."""

    path: Path
    text: str
    scheme_id: str | None
    source_url: str | None


def _scheme_id_from_filename(path: Path) -> str | None:
    """
    Map filename stem to scheme_id (IG-07).

    Accepts ``{scheme_id}.md`` or Groww URL slug stems.
    """
    return resolve_scheme_id_from_import_stem(path.stem)


def _read_text_file(path: Path) -> str:
    """Read UTF-8 text; normalize common corruption (IG-12)."""
    for encoding in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    logger.warning("Skipping unreadable file (encoding): %s", path)
    return ""


def discover_import_files(
    uploads_dir: Path | None = None,
    raw_dir: Path | None = None,
) -> list[Path]:
    """Collect import paths; uploads override raw for the same scheme_id."""
    uploads = uploads_dir or DEFAULT_UPLOADS_DIR
    raw = raw_dir or DEFAULT_RAW_DIR

    by_scheme: dict[str, Path] = {}

    def _register(directory: Path, *, priority: bool) -> None:
        if not directory.is_dir():
            return
        for pattern in _IMPORT_GLOBS:
            for path in sorted(directory.glob(pattern)):
                if not path.is_file() or path.name.upper().startswith("README"):
                    continue
                scheme_id = _scheme_id_from_filename(path)
                if not scheme_id:
                    logger.warning("Unmapped import filename, skipping: %s", path.name)
                    continue
                if priority or scheme_id not in by_scheme:
                    by_scheme[scheme_id] = path

    _register(raw, priority=False)
    _register(uploads, priority=True)
    return list(by_scheme.values())


def load_raw_document(path: Path) -> RawDocument | None:
    """Load one file and resolve scheme metadata from header or filename."""
    text = _read_text_file(path)
    if not text.strip():
        logger.warning("Empty import file: %s", path)
        return None

    source_url = extract_source_url(text)
    scheme_id = resolve_scheme_id_from_url(source_url or "") if source_url else None
    filename_id = _scheme_id_from_filename(path)

    if scheme_id and filename_id and scheme_id != filename_id:
        logger.warning(
            "Filename scheme_id %s disagrees with Source URL %s in %s; using URL",
            filename_id,
            scheme_id,
            path.name,
        )

    resolved_id = scheme_id or filename_id
    if not resolved_id:
        logger.warning("Cannot resolve scheme for %s", path)
        return None

    if filename_id and resolved_id != filename_id:
        # PH1-03: reject ambiguous wrong mapping when URL absent
        if not source_url:
            logger.error(
                "Filename maps to %s but content resolves to %s: %s",
                filename_id,
                resolved_id,
                path,
            )
            return None

    return RawDocument(
        path=path,
        text=text,
        scheme_id=resolved_id,
        source_url=source_url,
    )


def load_all_raw(
    uploads_dir: Path | None = None,
    raw_dir: Path | None = None,
) -> list[RawDocument]:
    """Load all discoverable import files."""
    docs: list[RawDocument] = []
    for path in discover_import_files(uploads_dir, raw_dir):
        doc = load_raw_document(path)
        if doc:
            docs.append(doc)
    return docs


def parse_import_file(path: Path) -> ParsedScheme | None:
    """Load and parse a single import file."""
    raw = load_raw_document(path)
    if raw is None:
        return None
    scheme = get_scheme(raw.scheme_id)
    if scheme is None:
        return None
    return parse_document(
        raw.text,
        scheme=scheme,
        source_url=raw.source_url,
    )


def parse_all_imports(
    uploads_dir: Path | None = None,
    raw_dir: Path | None = None,
) -> dict[str, ParsedScheme]:
    """
    Parse every import file keyed by scheme_id.

    Returns one ParsedScheme per scheme found; missing schemes are omitted.
    """
    result: dict[str, ParsedScheme] = {}
    for doc in load_all_raw(uploads_dir, raw_dir):
        scheme = get_scheme(doc.scheme_id)
        if scheme is None:
            continue
        parsed = parse_document(doc.text, scheme=scheme, source_url=doc.source_url)
        result[parsed.scheme_id] = parsed
    return result
