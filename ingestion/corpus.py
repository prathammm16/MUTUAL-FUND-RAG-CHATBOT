"""
Write and read parsed corpus files under ``data/corpus/`` (Phase 1 task 1.4).

Per scheme writes three artifacts:
  - ``{scheme_id}.json`` — structured parsed sections
  - ``{scheme_id}.md`` — human-readable cleaned corpus
  - ``{scheme_id}.html`` — simple HTML view of the same content
"""

from __future__ import annotations

import html
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import get_all_schemes
from ingestion.load import parse_all_imports
from ingestion.parse import SECTION_IDS, ParsedScheme

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS_DIR = _PROJECT_ROOT / "data" / "corpus"

_CORPUS_VERSION = 1

_SECTION_HEADINGS: dict[str, str] = {
    "costs": "Expense ratio and costs",
    "exit_load": "Exit load",
    "tax": "Tax implications",
    "minimum_investment": "Minimum investment",
    "risk": "Risk",
    "benchmark": "Benchmark",
    "fund_management": "Fund management",
    "objective": "Investment objective",
}


@dataclass(frozen=True)
class CorpusArtifacts:
    """Paths to corpus JSON, markdown, and HTML for one scheme."""

    scheme_id: str
    json: Path
    markdown: Path
    html: Path


def corpus_paths(scheme_id: str, corpus_dir: Path | None = None) -> CorpusArtifacts:
    """Standard paths for corpus JSON / markdown / HTML."""
    base = corpus_dir or DEFAULT_CORPUS_DIR
    return CorpusArtifacts(
        scheme_id=scheme_id,
        json=base / f"{scheme_id}.json",
        markdown=base / f"{scheme_id}.md",
        html=base / f"{scheme_id}.html",
    )


def corpus_path(scheme_id: str, corpus_dir: Path | None = None) -> Path:
    """Path to ``data/corpus/{scheme_id}.json`` (primary structured store)."""
    return corpus_paths(scheme_id, corpus_dir).json


def parsed_to_dict(parsed: ParsedScheme) -> dict[str, Any]:
    """Serialize a parsed scheme for JSON corpus storage."""
    return {
        "corpus_version": _CORPUS_VERSION,
        "scheme_id": parsed.scheme_id,
        "scheme_name": parsed.scheme_name,
        "source_url": parsed.source_url,
        "last_updated": parsed.last_updated,
        "sections": parsed.sections,
    }


def parsed_from_dict(data: dict[str, Any]) -> ParsedScheme:
    """Load ``ParsedScheme`` from a corpus JSON object."""
    return ParsedScheme(
        scheme_id=data["scheme_id"],
        scheme_name=data["scheme_name"],
        source_url=data["source_url"],
        sections=dict(data.get("sections") or {}),
        last_updated=data.get("last_updated"),
    )


def parsed_to_markdown(parsed: ParsedScheme) -> str:
    """Export parsed corpus as readable markdown."""
    lines = [
        f"Source URL: {parsed.source_url}",
        "",
        f"# {parsed.scheme_name}",
        "",
    ]
    if parsed.last_updated:
        lines.append(f"Last updated: {parsed.last_updated}")
        lines.append("")

    for section_id in SECTION_IDS:
        content = (parsed.sections.get(section_id) or "").strip()
        if not content:
            continue
        heading = _SECTION_HEADINGS.get(section_id, section_id.replace("_", " ").title())
        lines.extend([f"## {heading}", "", content, ""])

    return "\n".join(lines).strip() + "\n"


def parsed_to_html(parsed: ParsedScheme) -> str:
    """Export parsed corpus as a simple HTML page."""
    sections_html = []
    for section_id in SECTION_IDS:
        content = (parsed.sections.get(section_id) or "").strip()
        if not content:
            continue
        heading = _SECTION_HEADINGS.get(section_id, section_id.replace("_", " ").title())
        escaped = html.escape(content)
        sections_html.append(
            f'<section id="{section_id}">\n'
            f"  <h2>{html.escape(heading)}</h2>\n"
            f"  <pre>{escaped}</pre>\n"
            f"</section>"
        )

    last_updated = ""
    if parsed.last_updated:
        last_updated = f"<p><strong>Last updated:</strong> {html.escape(parsed.last_updated)}</p>"

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        f"  <meta charset=\"utf-8\">\n"
        f"  <title>{html.escape(parsed.scheme_name)}</title>\n"
        "</head>\n"
        "<body>\n"
        f"  <h1>{html.escape(parsed.scheme_name)}</h1>\n"
        f'  <p>Source: <a href="{html.escape(parsed.source_url)}">'
        f"{html.escape(parsed.source_url)}</a></p>\n"
        f"  {last_updated}\n"
        + "\n".join(f"  {block}" for block in sections_html)
        + "\n</body>\n</html>\n"
    )


def write_corpus_file(
    parsed: ParsedScheme,
    corpus_dir: Path | None = None,
) -> CorpusArtifacts:
    """Write ``data/corpus/{scheme_id}.json``, ``.md``, and ``.html``."""
    paths = corpus_paths(parsed.scheme_id, corpus_dir)
    paths.json.parent.mkdir(parents=True, exist_ok=True)

    payload = parsed_to_dict(parsed)
    paths.json.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths.markdown.write_text(parsed_to_markdown(parsed), encoding="utf-8")
    paths.html.write_text(parsed_to_html(parsed), encoding="utf-8")

    logger.info("Wrote corpus artifacts for %s: json, md, html", parsed.scheme_id)
    return paths


def read_corpus_file(
    scheme_id: str,
    corpus_dir: Path | None = None,
) -> ParsedScheme | None:
    """Read a single corpus JSON file; return None if missing."""
    path = corpus_path(scheme_id, corpus_dir)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return parsed_from_dict(data)


def load_corpus(
    corpus_dir: Path | None = None,
) -> dict[str, ParsedScheme]:
    """Load all ``*.json`` corpus files (ignores ``.md`` / ``.html`` siblings)."""
    base = corpus_dir or DEFAULT_CORPUS_DIR
    if not base.is_dir():
        return {}
    result: dict[str, ParsedScheme] = {}
    for path in sorted(base.glob("*.json")):
        if path.name.upper().startswith("README"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            parsed = parsed_from_dict(data)
            result[parsed.scheme_id] = parsed
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Skipping invalid corpus file %s: %s", path.name, exc)
    return result


def build_corpus_from_imports(
    uploads_dir: Path | None = None,
    raw_dir: Path | None = None,
    corpus_dir: Path | None = None,
    *,
    build_chunks: bool = True,
    chunks_dir: Path | None = None,
) -> dict[str, ParsedScheme]:
    """
    Parse imports and write corpus JSON, markdown, and HTML per scheme.

    When ``build_chunks`` is True (default), also writes ``data/chunks/`` (Phase 1.7).
    """
    parsed = parse_all_imports(uploads_dir, raw_dir)
    out_dir = corpus_dir or DEFAULT_CORPUS_DIR
    for scheme in parsed.values():
        write_corpus_file(scheme, out_dir)
    if build_chunks and parsed:
        from ingestion.chunk_store import build_chunks_from_corpus, write_all_chunks

        chunks = build_chunks_from_corpus(parsed)
        write_all_chunks(chunks, chunks_dir)
    return parsed


def expected_scheme_ids() -> list[str]:
    """All scheme_ids from the Phase 0 registry."""
    return [s.scheme_id for s in get_all_schemes()]
