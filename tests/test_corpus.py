"""Phase 1.4–1.5 — corpus export and validation tests."""

import json
from pathlib import Path

import pytest

from ingestion.corpus import (
    build_corpus_from_imports,
    corpus_path,
    corpus_paths,
    load_corpus,
    parsed_from_dict,
    parsed_to_dict,
    parsed_to_html,
    parsed_to_markdown,
    read_corpus_file,
    write_corpus_file,
)
from ingestion.parse import parse_document
from ingestion.validate import (
    SchemeValidation,
    validate_corpus,
    validate_corpus_dir,
    validate_scheme,
)

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_MID_CAP = FIXTURES / "sample_mid_cap.md"


@pytest.fixture
def mid_cap_parsed():
    raw = SAMPLE_MID_CAP.read_text(encoding="utf-8")
    return parse_document(raw, scheme_id="hdfc-mid-cap")


class TestCorpusExport:
    def test_parsed_round_trip_dict(self, mid_cap_parsed) -> None:
        data = parsed_to_dict(mid_cap_parsed)
        restored = parsed_from_dict(data)
        assert restored.scheme_id == mid_cap_parsed.scheme_id
        assert restored.sections == mid_cap_parsed.sections

    def test_parsed_to_markdown_and_html(self, mid_cap_parsed) -> None:
        md = parsed_to_markdown(mid_cap_parsed)
        assert "Source URL:" in md
        assert "## Expense ratio and costs" in md
        html_out = parsed_to_html(mid_cap_parsed)
        assert "<!DOCTYPE html>" in html_out
        assert "fund_management" in html_out

    def test_write_and_read_corpus_file(self, mid_cap_parsed, tmp_path: Path) -> None:
        paths = write_corpus_file(mid_cap_parsed, tmp_path)
        assert paths == corpus_paths("hdfc-mid-cap", tmp_path)
        assert paths.json.is_file()
        assert paths.markdown.is_file()
        assert paths.html.is_file()
        on_disk = json.loads(paths.json.read_text(encoding="utf-8"))
        assert on_disk["scheme_id"] == "hdfc-mid-cap"
        assert "costs" in on_disk["sections"]
        loaded = read_corpus_file("hdfc-mid-cap", tmp_path)
        assert loaded is not None
        assert loaded.sections["fund_management"]

    def test_build_corpus_from_imports(self, tmp_path: Path) -> None:
        uploads = tmp_path / "uploads"
        corpus_dir = tmp_path / "corpus"
        uploads.mkdir()
        (uploads / "hdfc-mid-cap.md").write_text(
            SAMPLE_MID_CAP.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        empty_raw = tmp_path / "empty_raw"
        built = build_corpus_from_imports(
            uploads_dir=uploads,
            raw_dir=empty_raw,
            corpus_dir=corpus_dir,
            chunks_dir=tmp_path / "chunks",
        )
        assert len(built) == 1
        assert (corpus_dir / "hdfc-mid-cap.json").is_file()
        assert (corpus_dir / "hdfc-mid-cap.md").is_file()
        assert (corpus_dir / "hdfc-mid-cap.html").is_file()
        loaded = load_corpus(corpus_dir)
        assert "hdfc-mid-cap" in loaded


class TestCorpusValidation:
    def test_validate_scheme_ok(self, mid_cap_parsed) -> None:
        result = validate_scheme(mid_cap_parsed)
        assert isinstance(result, SchemeValidation)
        assert result.ok
        assert result.section_count == 8
        assert "fund_management" in result.present_sections
        assert "costs" in result.present_sections

    def test_validate_scheme_empty_fails(self, mid_cap_parsed) -> None:
        mid_cap_parsed.sections = {}
        result = validate_scheme(mid_cap_parsed)
        assert not result.ok
        assert any("PH1-01" in e for e in result.errors)

    def test_validate_scheme_missing_fund_management(self, mid_cap_parsed) -> None:
        del mid_cap_parsed.sections["fund_management"]
        result = validate_scheme(mid_cap_parsed)
        assert not result.ok
        assert any("FM-10" in e for e in result.errors)

    def test_validate_corpus_requires_five_by_default(self, mid_cap_parsed) -> None:
        report = validate_corpus({"hdfc-mid-cap": mid_cap_parsed})
        assert not report.ok
        assert len(report.missing_scheme_ids) == 4

    def test_validate_corpus_allow_partial(self, mid_cap_parsed) -> None:
        report = validate_corpus(
            {"hdfc-mid-cap": mid_cap_parsed},
            require_all_schemes=False,
        )
        assert report.ok

    def test_validate_corpus_dir(self, tmp_path: Path, mid_cap_parsed) -> None:
        write_corpus_file(mid_cap_parsed, tmp_path)
        report = validate_corpus_dir(tmp_path, require_all_schemes=False)
        assert report.ok
        assert len(report.schemes) == 1
