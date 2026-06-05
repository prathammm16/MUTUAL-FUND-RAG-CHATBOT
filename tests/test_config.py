"""Phase 0 — scheme registry and configuration tests."""

import pytest

from app.config import (
    ALLOWLISTED_SOURCE_URLS,
    AMC_NAME,
    EMBEDDING_BACKEND_FASTEMBED,
    EMBEDDING_BACKEND_SENTENCE_TRANSFORMERS,
    SCHEME_ALIASES,
    SCHEMES,
    Scheme,
    get_all_schemes,
    get_scheme,
    get_settings,
    is_allowlisted_source_url,
    resolve_scheme_id_from_text,
    resolve_scheme_id_from_url,
    validate_registry,
)

EXPECTED_URLS = {
    "hdfc-silver-etf-fof": "https://groww.in/mutual-funds/hdfc-silver-etf-fof-direct-growth",
    "hdfc-mid-cap": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
    "hdfc-equity": "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth",
    "hdfc-gold-etf-fof": "https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth",
    "hdfc-nifty-50-index": "https://groww.in/mutual-funds/hdfc-nifty-50-index-fund-direct-growth",
}


class TestSchemeRegistry:
    """PH0-01: exactly five schemes with allowlisted Groww URLs."""

    def test_scheme_count_is_five(self) -> None:
        assert len(SCHEMES) == 5
        assert len(get_all_schemes()) == 5

    def test_all_source_urls_allowlisted(self) -> None:
        assert len(ALLOWLISTED_SOURCE_URLS) == 5
        for scheme in SCHEMES:
            assert scheme.source_url in ALLOWLISTED_SOURCE_URLS
            assert scheme.source_url.startswith("https://groww.in/mutual-funds/")

    def test_expected_urls_per_scheme_id(self) -> None:
        for scheme_id, url in EXPECTED_URLS.items():
            scheme = get_scheme(scheme_id)
            assert scheme is not None
            assert scheme.source_url == url

    def test_unique_scheme_ids_and_urls(self) -> None:
        ids = [s.scheme_id for s in SCHEMES]
        urls = [s.source_url for s in SCHEMES]
        assert len(ids) == len(set(ids))
        assert len(urls) == len(set(urls))

    def test_validate_registry_passes(self) -> None:
        validate_registry()

    def test_amc_name(self) -> None:
        assert AMC_NAME == "HDFC Mutual Fund"


class TestAliases:
    """SC-02, SC-03, SC-04, PH0-04 — alias map."""

    @pytest.mark.parametrize(
        "phrase,expected_id",
        [
            ("silver fund", "hdfc-silver-etf-fof"),
            ("What is the expense ratio of the silver FoF?", "hdfc-silver-etf-fof"),
            ("gold fof", "hdfc-gold-etf-fof"),
            ("gold fund of fund", "hdfc-gold-etf-fof"),
            ("mid cap", "hdfc-mid-cap"),
            ("HDFC Midcap fund", "hdfc-mid-cap"),
            ("mid-cap", "hdfc-mid-cap"),
            ("hdfc equity", "hdfc-equity"),
            ("nifty 50 index", "hdfc-nifty-50-index"),
            ("Nifty50", "hdfc-nifty-50-index"),
        ],
    )
    def test_resolve_alias(self, phrase: str, expected_id: str) -> None:
        assert resolve_scheme_id_from_text(phrase) == expected_id
        assert get_scheme(expected_id) is not None

    def test_silver_fof_not_ambiguous_with_generic_silver(self) -> None:
        # SC-11: registry targets FoF scheme slug, not stock ETF page
        scheme = get_scheme("hdfc-silver-etf-fof")
        assert scheme is not None
        assert "fof" in scheme.source_url

    def test_full_scheme_name_resolution(self) -> None:
        assert (
            resolve_scheme_id_from_text("HDFC Mid Cap Fund Direct Growth")
            == "hdfc-mid-cap"
        )


class TestUrlResolution:
    """SC-12 — Groww URL in query."""

    def test_resolve_from_full_url(self) -> None:
        url = EXPECTED_URLS["hdfc-gold-etf-fof"]
        assert resolve_scheme_id_from_url(url) == "hdfc-gold-etf-fof"
        assert resolve_scheme_id_from_text(f"Tell me about {url}") == "hdfc-gold-etf-fof"

    def test_non_allowlisted_url_returns_none(self) -> None:
        assert (
            resolve_scheme_id_from_url(
                "https://groww.in/mutual-funds/hdfc-flexi-cap-fund-direct-growth"
            )
            is None
        )


class TestCitationAllowlist:
    def test_is_allowlisted_source_url(self) -> None:
        assert is_allowlisted_source_url(EXPECTED_URLS["hdfc-equity"])
        assert not is_allowlisted_source_url("https://example.com/fund")


class TestSettings:
    """PH0-03 — compliance URLs present."""

    def test_default_compliance_urls(self) -> None:
        settings = get_settings()
        assert settings.amfi_education_url.startswith("https://")
        assert settings.sebi_investor_url.startswith("https://")
        assert "amfi" in settings.amfi_education_url.lower()
        assert "sebi" in settings.sebi_investor_url.lower()

    def test_invalid_scheme_url_rejected(self) -> None:
        with pytest.raises(ValueError, match="groww.in/mutual-funds"):
            Scheme(
                scheme_id="bad",
                scheme_name="Bad",
                source_url="https://example.com/fund",
            )


class TestEmbeddingBackend:
    def test_auto_uses_fastembed_in_production(self, monkeypatch) -> None:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("EMBEDDING_BACKEND", "auto")
        get_settings.cache_clear()
        assert get_settings().resolved_embedding_backend() == EMBEDDING_BACKEND_FASTEMBED
        get_settings.cache_clear()

    def test_auto_uses_sentence_transformers_in_dev(self, monkeypatch) -> None:
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("EMBEDDING_BACKEND", "auto")
        get_settings.cache_clear()
        assert (
            get_settings().resolved_embedding_backend()
            == EMBEDDING_BACKEND_SENTENCE_TRANSFORMERS
        )
        get_settings.cache_clear()
