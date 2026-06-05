"""
Phase 1 exit gate — parsed corpus + chunk store for all five schemes.
"""

from pathlib import Path

import pytest

from app.config import get_all_schemes
from ingestion.chunk_store import (
    DEFAULT_CHUNKS_DIR,
    EXPECTED_CHUNKS_PER_SCHEME,
    load_all_chunks,
    validate_chunks_store,
)
from ingestion.corpus import DEFAULT_CORPUS_DIR, load_corpus
from ingestion.parse import SECTION_IDS
from ingestion.validate import validate_corpus_dir

REQUIRED_SECTIONS = frozenset({"costs", "fund_management"})


class TestPhase1ExitGate:
    """PH1-01, FM-10, PH1-02, PH1-04 — full Phase 1 gate."""

    def test_five_corpus_json_files_exist(self) -> None:
        corpus_dir = DEFAULT_CORPUS_DIR
        if not corpus_dir.is_dir() or not any(corpus_dir.glob("*.json")):
            pytest.skip("data/corpus not built; run scripts/build_corpus.py")
        ids = {s.scheme_id for s in get_all_schemes()}
        on_disk = {p.stem for p in corpus_dir.glob("*.json")}
        missing = ids - on_disk
        assert not missing, f"Missing corpus JSON: {sorted(missing)}"

    def test_load_corpus_five_schemes(self) -> None:
        corpus = load_corpus()
        if not corpus:
            pytest.skip("data/corpus empty")
        assert len(corpus) == 5

    def test_validate_corpus_dir_passes(self) -> None:
        if not DEFAULT_CORPUS_DIR.is_dir() or not any(DEFAULT_CORPUS_DIR.glob("*.json")):
            pytest.skip("data/corpus not built")
        report = validate_corpus_dir(DEFAULT_CORPUS_DIR, require_all_schemes=True)
        assert report.ok, report.errors

    def test_every_scheme_has_eight_sections(self) -> None:
        corpus = load_corpus()
        if not corpus:
            pytest.skip("data/corpus empty")
        for scheme_id, parsed in corpus.items():
            for section in SECTION_IDS:
                assert section in parsed.sections, f"{scheme_id} missing {section}"
                assert parsed.sections[section].strip(), f"{scheme_id} empty {section}"

    def test_corpus_triple_artifacts_per_scheme(self) -> None:
        corpus_dir = DEFAULT_CORPUS_DIR
        if not corpus_dir.is_dir() or not any(corpus_dir.glob("*.json")):
            pytest.skip("data/corpus not built")
        for scheme in get_all_schemes():
            assert (corpus_dir / f"{scheme.scheme_id}.json").is_file()
            assert (corpus_dir / f"{scheme.scheme_id}.md").is_file()

    def test_raw_triple_artifacts_per_scheme(self) -> None:
        raw_dir = Path(__file__).resolve().parents[1] / "data" / "raw"
        if not raw_dir.is_dir() or not any(raw_dir.glob("*.md")):
            pytest.skip("data/raw md not present")
        for scheme in get_all_schemes():
            assert (raw_dir / f"{scheme.scheme_id}.md").is_file()

    def test_chunks_store_five_schemes(self) -> None:
        if not DEFAULT_CHUNKS_DIR.is_dir():
            pytest.skip("data/chunks not built")
        chunks = load_all_chunks()
        assert len(chunks) == EXPECTED_CHUNKS_PER_SCHEME * 5
        by_scheme = {s.scheme_id for s in get_all_schemes()}
        found = {c.scheme_id for c in chunks}
        assert by_scheme == found

    def test_nine_chunks_per_scheme(self) -> None:
        if not DEFAULT_CHUNKS_DIR.is_dir():
            pytest.skip("data/chunks not built")
        chunks = load_all_chunks()
        by_scheme: dict[str, list] = {}
        for c in chunks:
            by_scheme.setdefault(c.scheme_id, []).append(c)
        for scheme_id, scheme_chunks in by_scheme.items():
            assert len(scheme_chunks) == EXPECTED_CHUNKS_PER_SCHEME, (
                f"{scheme_id}: expected {EXPECTED_CHUNKS_PER_SCHEME} chunks, "
                f"got {len(scheme_chunks)}"
            )
            assert sum(1 for c in scheme_chunks if c.section == "fund_management") == 2
            assert sum(1 for c in scheme_chunks if c.section == "costs") == 1

    def test_validate_chunks_store_passes(self) -> None:
        if not DEFAULT_CHUNKS_DIR.is_dir():
            pytest.skip("data/chunks not built")
        errors = validate_chunks_store(require_all_schemes=True)
        assert not errors, errors

    def test_chunk_artifacts_per_scheme(self) -> None:
        chunks_dir = DEFAULT_CHUNKS_DIR
        if not chunks_dir.is_dir():
            pytest.skip("data/chunks not built")
        assert (chunks_dir / "all_chunks.json").is_file()
        for scheme in get_all_schemes():
            assert (chunks_dir / f"{scheme.scheme_id}.json").is_file()
            assert (chunks_dir / f"{scheme.scheme_id}.md").is_file()
