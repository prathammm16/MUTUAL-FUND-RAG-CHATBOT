"""Phase 8 — daily scheduler wiring (reindex.sh, cron.example, GitHub Actions)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REINDEX_SH = PROJECT_ROOT / "scripts" / "reindex.sh"
CRON_EXAMPLE = PROJECT_ROOT / "scheduler" / "cron.example"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"
GH_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "daily-ingest.yml"
SCHEDULER_README = PROJECT_ROOT / "scheduler" / "README.md"


def _parse_env_example(key: str) -> str:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    match = re.search(rf"^{key}=(.+)$", text, re.MULTILINE)
    assert match, f"{key} missing from .env.example"
    return match.group(1).strip()


class TestSchedulerArtifacts:
    def test_reindex_sh_exists_and_invokes_run_daily(self) -> None:
        assert REINDEX_SH.is_file()
        content = REINDEX_SH.read_text(encoding="utf-8")
        assert "ingestion.run_daily" in content
        assert "PROJECT_ROOT" in content or 'cd "$PROJECT_ROOT"' in content
        assert "source" in content and ".env" in content
        assert "flock" in content

    def test_cron_example_matches_env_schedule(self) -> None:
        schedule = _parse_env_example("INGEST_CRON_SCHEDULE")
        timezone = _parse_env_example("INGEST_TIMEZONE")
        cron_text = CRON_EXAMPLE.read_text(encoding="utf-8")

        assert schedule == "0 10 * * *"
        assert timezone == "Asia/Kolkata"
        assert f"CRON_TZ={timezone}" in cron_text
        assert schedule in cron_text
        assert "reindex.sh" in cron_text

    def test_config_default_schedule_matches_env_example(self) -> None:
        default_schedule = Settings.model_fields["ingest_cron_schedule"].default
        default_tz = Settings.model_fields["ingest_timezone"].default
        assert default_schedule == _parse_env_example("INGEST_CRON_SCHEDULE")
        assert default_tz == _parse_env_example("INGEST_TIMEZONE")

    def test_scheduler_readme_documents_timezone(self) -> None:
        text = SCHEDULER_README.read_text(encoding="utf-8")
        assert "10:00 AM IST" in text or "0 10 * * *" in text
        assert "Asia/Kolkata" in text
        assert "CRON_TZ" in text
        assert "SK-06" in text or "UTC" in text

    def test_github_actions_utc_matches_ist_schedule(self) -> None:
        assert GH_WORKFLOW.is_file()
        workflow = GH_WORKFLOW.read_text(encoding="utf-8")
        # 10:00 AM IST = 04:30 UTC
        assert 'cron: "30 4 * * *"' in workflow or "30 4 * * *" in workflow
        assert "reindex.sh" in workflow
        assert "Asia/Kolkata" in workflow or "INGEST_TIMEZONE" in workflow

    def test_k8s_example_uses_ist_schedule(self) -> None:
        k8s = PROJECT_ROOT / "scheduler" / "k8s-cronjob.example.yaml"
        text = k8s.read_text(encoding="utf-8")
        assert 'schedule: "0 10 * * *"' in text
        assert "timeZone: Asia/Kolkata" in text
        assert "concurrencyPolicy: Forbid" in text


@pytest.mark.skipif(
    not REINDEX_SH.exists(),
    reason="reindex.sh missing",
)
class TestReindexShSmoke:
    def test_reindex_sh_help_via_dry_parse(self) -> None:
        """Ensure script is valid bash (syntax check only; no ingest run)."""
        import shutil
        import subprocess

        bash = shutil.which("bash")
        if bash is None:
            pytest.skip("bash not available on PATH")
        proc = subprocess.run(
            [bash, "-n", str(REINDEX_SH)],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
