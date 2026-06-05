"""Phase 1 — parse and import loader tests."""

from pathlib import Path

import pytest

from app.config import resolve_scheme_id_from_import_stem
from ingestion.load import (
    discover_import_files,
    load_raw_document,
    parse_import_file,
)
from ingestion.parse import (
    SECTION_IDS,
    ParsedScheme,
    extract_nav_date,
    extract_source_url,
    map_sections,
    parse_document,
    strip_noise,
)

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_MID_CAP = FIXTURES / "sample_mid_cap.md"
EXPECTED_URL = "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"


class TestStripNoise:
    """IG-05 — nav/calculator/footer stripped."""

    def test_removes_nav_and_calculator_lines(self) -> None:
        text = SAMPLE_MID_CAP.read_text(encoding="utf-8")
        cleaned = strip_noise(text)
        assert "Home" not in cleaned
        assert "Mutual Funds" not in cleaned
        assert "SIP Calculator" not in cleaned
        assert "If you invested" not in cleaned
        assert "Privacy Policy" not in cleaned
        assert "Similar funds" not in cleaned
        assert "Download Groww" not in cleaned

    def test_keeps_factual_sections(self) -> None:
        cleaned = strip_noise(SAMPLE_MID_CAP.read_text(encoding="utf-8"))
        assert "Expense ratio" in cleaned
        assert "Exit load" in cleaned
        assert "Fund manager" in cleaned


class TestSectionMapper:
    def test_maps_required_sections(self) -> None:
        cleaned = strip_noise(SAMPLE_MID_CAP.read_text(encoding="utf-8"))
        sections = map_sections(cleaned)
        for key in (
            "costs",
            "exit_load",
            "tax",
            "minimum_investment",
            "risk",
            "benchmark",
            "fund_management",
            "objective",
        ):
            assert key in sections, f"missing section {key}"
        assert all(s in SECTION_IDS for s in sections)

    def test_single_canonical_exit_load(self) -> None:
        cleaned = strip_noise(SAMPLE_MID_CAP.read_text(encoding="utf-8"))
        sections = map_sections(cleaned)
        assert "Historical exit load" not in sections["exit_load"]
        assert "1%" in sections["exit_load"]


class TestParseDocument:
    def test_full_parse_mid_cap_fixture(self) -> None:
        raw = SAMPLE_MID_CAP.read_text(encoding="utf-8")
        parsed = parse_document(raw, scheme_id="hdfc-mid-cap")
        assert isinstance(parsed, ParsedScheme)
        assert parsed.scheme_id == "hdfc-mid-cap"
        assert parsed.source_url == EXPECTED_URL
        assert parsed.sections["fund_management"]
        assert parsed.last_updated == "2025-01-15"

    def test_extract_source_url(self) -> None:
        raw = SAMPLE_MID_CAP.read_text(encoding="utf-8")
        assert extract_source_url(raw) == EXPECTED_URL

    def test_extract_nav_date(self) -> None:
        raw = SAMPLE_MID_CAP.read_text(encoding="utf-8")
        assert extract_nav_date(raw) == "2025-01-15"


class TestImportLoader:
    def test_filename_stem_resolution(self) -> None:
        assert resolve_scheme_id_from_import_stem("hdfc-mid-cap") == "hdfc-mid-cap"
        assert (
            resolve_scheme_id_from_import_stem("hdfc-mid-cap-fund-direct-growth")
            == "hdfc-mid-cap"
        )

    def test_load_raw_document_from_fixture(self) -> None:
        doc = load_raw_document(SAMPLE_MID_CAP)
        assert doc is not None
        assert doc.scheme_id == "hdfc-mid-cap"
        assert doc.source_url == EXPECTED_URL

    def test_parse_import_file(self, tmp_path: Path) -> None:
        uploads = tmp_path / "uploads"
        uploads.mkdir()
        target = uploads / "hdfc-mid-cap.md"
        target.write_text(SAMPLE_MID_CAP.read_text(encoding="utf-8"), encoding="utf-8")
        paths = discover_import_files(uploads_dir=uploads, raw_dir=tmp_path / "raw")
        assert len(paths) == 1
        parsed = parse_import_file(target)
        assert parsed is not None
        assert parsed.scheme_id == "hdfc-mid-cap"
        assert "costs" in parsed.sections

    def test_uploads_override_raw(self, tmp_path: Path) -> None:
        uploads = tmp_path / "uploads"
        raw = tmp_path / "raw"
        uploads.mkdir()
        raw.mkdir()
        (raw / "hdfc-mid-cap.md").write_text("raw version", encoding="utf-8")
        (uploads / "hdfc-mid-cap.md").write_text(
            SAMPLE_MID_CAP.read_text(encoding="utf-8"), encoding="utf-8"
        )
        paths = discover_import_files(uploads_dir=uploads, raw_dir=raw)
        assert paths[0].parent == uploads

    def test_unmapped_filename_skipped(self, tmp_path: Path) -> None:
        uploads = tmp_path / "uploads"
        uploads.mkdir()
        (uploads / "unknown-fund.md").write_text("no mapping", encoding="utf-8")
        assert discover_import_files(uploads_dir=uploads, raw_dir=tmp_path / "raw") == []

    def test_missing_scheme_raises(self) -> None:
        with pytest.raises(ValueError, match="scheme"):
            parse_document("no header", scheme_id="not-a-scheme")
