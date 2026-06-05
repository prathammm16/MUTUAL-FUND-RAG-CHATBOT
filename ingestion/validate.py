"""
Parse validation for Phase 1 exit gate (task 1.5).

Logs section counts per scheme; fails on PH1-01, FM-10, and missing ``costs``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from ingestion.corpus import DEFAULT_CORPUS_DIR, expected_scheme_ids, load_corpus
from ingestion.parse import SECTION_IDS, ParsedScheme

_EXIT_LOAD_HISTORY_RE = re.compile(
    r"historical|previous(?:ly)?|earlier|was\s+applicable",
    re.IGNORECASE,
)

logger = logging.getLogger(__name__)

# Sections that must be non-empty when present on source (FM-10).
REQUIRED_SECTIONS: tuple[str, ...] = ("fund_management", "costs")

EXPECTED_SCHEME_COUNT = len(expected_scheme_ids())


@dataclass
class SchemeValidation:
    """Per-scheme validation snapshot."""

    scheme_id: str
    present_sections: list[str] = field(default_factory=list)
    missing_sections: list[str] = field(default_factory=list)
    section_char_counts: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def section_count(self) -> int:
        return len(self.present_sections)


@dataclass
class CorpusValidationReport:
    """Full corpus validation result."""

    schemes: list[SchemeValidation] = field(default_factory=list)
    missing_scheme_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors and all(s.ok for s in self.schemes)


def _char_counts(sections: dict[str, str]) -> dict[str, int]:
    return {name: len(text) for name, text in sections.items() if text.strip()}


def validate_scheme(parsed: ParsedScheme) -> SchemeValidation:
    """Validate one parsed scheme (PH1-01, PH1-02, FM-10)."""
    result = SchemeValidation(scheme_id=parsed.scheme_id)
    sections = {k: v for k, v in parsed.sections.items() if v and v.strip()}

    if not sections:
        result.errors.append("PH1-01: parsed sections empty")
        return result

    result.section_char_counts = _char_counts(sections)
    result.present_sections = sorted(sections.keys())
    result.missing_sections = sorted(set(SECTION_IDS) - set(result.present_sections))

    for req in REQUIRED_SECTIONS:
        if req not in sections:
            if req == "fund_management":
                result.errors.append("FM-10: fund_management section missing")
            elif req == "costs":
                result.errors.append("PH1-02: costs section missing")

    if "exit_load" in sections and _exit_load_has_history_noise(sections["exit_load"]):
        result.warnings.append("IG-06: exit_load may contain historical wording")

    if not parsed.source_url:
        result.errors.append("source_url missing")
    if not parsed.scheme_name:
        result.warnings.append("scheme_name missing")

    return result


def _exit_load_has_history_noise(text: str) -> bool:
    return bool(_EXIT_LOAD_HISTORY_RE.search(text))


def validate_corpus(
    corpus: dict[str, ParsedScheme],
    *,
    require_all_schemes: bool = True,
) -> CorpusValidationReport:
    """
    Validate loaded or freshly parsed corpus.

    When ``require_all_schemes`` is True (default), all five registry schemes
    must have corpus entries (Phase 1 exit gate).
    """
    report = CorpusValidationReport()
    expected = set(expected_scheme_ids())
    found = set(corpus.keys())

    if require_all_schemes:
        report.missing_scheme_ids = sorted(expected - found)
        if report.missing_scheme_ids:
            report.errors.append(
                f"Expected {EXPECTED_SCHEME_COUNT} schemes, found {len(found)}; "
                f"missing: {', '.join(report.missing_scheme_ids)}"
            )

    for scheme_id in sorted(found):
        parsed = corpus[scheme_id]
        if not parsed.sections:
            report.errors.append(f"PH1-01: {scheme_id} has empty sections")
            continue
        report.schemes.append(validate_scheme(parsed))

    for sv in report.schemes:
        report.errors.extend(f"{sv.scheme_id}: {e}" for e in sv.errors)
        report.warnings.extend(f"{sv.scheme_id}: {w}" for w in sv.warnings)

    return report


def log_validation_report(report: CorpusValidationReport) -> None:
    """Log section counts per scheme (task 1.5)."""
    logger.info("=== Parse validation ===")
    if report.missing_scheme_ids:
        logger.error("Missing schemes: %s", ", ".join(report.missing_scheme_ids))

    for sv in report.schemes:
        counts = ", ".join(
            f"{name}={sv.section_char_counts[name]}" for name in sv.present_sections
        )
        status = "OK" if sv.ok else "FAIL"
        logger.info(
            "%s | sections=%d/%d | present=[%s] | missing=[%s] | %s",
            sv.scheme_id,
            sv.section_count,
            len(SECTION_IDS),
            ", ".join(sv.present_sections),
            ", ".join(sv.missing_sections) or "(none)",
            status,
        )
        if counts:
            logger.info("  char_counts: %s", counts)
        for w in sv.warnings:
            logger.warning("  %s", w)

    if report.errors:
        logger.error("Validation FAILED (%d error(s))", len(report.errors))
        for err in report.errors:
            logger.error("  %s", err)
    else:
        logger.info("Validation PASSED")

    if report.warnings:
        logger.warning("Warnings (%d):", len(report.warnings))
        for w in report.warnings:
            logger.warning("  %s", w)


def validate_corpus_dir(
    corpus_dir: Path | None = None,
    *,
    require_all_schemes: bool = True,
) -> CorpusValidationReport:
    """Load corpus from disk and validate."""
    base = corpus_dir or DEFAULT_CORPUS_DIR
    return validate_corpus(load_corpus(base), require_all_schemes=require_all_schemes)


def log_chunk_counts(chunks: list) -> None:
    """Log chunk counts per scheme (Phase 1.8)."""
    from collections import Counter

    from ingestion.chunk import Chunk

    logger.info("=== Chunk validation ===")
    if not chunks:
        logger.error("No chunks loaded")
        return

    by_scheme: dict[str, list[Chunk]] = {}
    for c in chunks:
        if isinstance(c, Chunk):
            by_scheme.setdefault(c.scheme_id, []).append(c)

    for scheme_id in sorted(by_scheme):
        scheme_chunks = by_scheme[scheme_id]
        sections = Counter(c.section for c in scheme_chunks)
        section_summary = ", ".join(f"{k}={v}" for k, v in sorted(sections.items()))
        logger.info(
            "%s | chunks=%d | %s",
            scheme_id,
            len(scheme_chunks),
            section_summary,
        )
    logger.info("Total chunks: %d", len(chunks))
