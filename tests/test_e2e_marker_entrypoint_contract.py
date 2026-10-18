"""Regression tests for the E2E marker / entry-point contract (#545).

These exercise the real pytest CLI contract via subprocess -- no Azure
resources or E2E_BASE_URL are required for any of them.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_pytest(args: list[str], *, base_url: str | None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if base_url is None:
        env.pop("E2E_BASE_URL", None)
    else:
        env["E2E_BASE_URL"] = base_url
    return subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


class TestDedicatedE2eSelector:
    def test_collects_all_intended_e2e_tests(self) -> None:
        # Given no Azure deployment and no base URL -- collection only
        # When the dedicated certification selector is used
        result = _run_pytest(
            ["--collect-only", "-m", "e2e", "tests/e2e/", "--no-cov", "-q"],
            base_url=None,
        )

        # Then it collects the intended 21 real-host tests, not zero (#545)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "test_pipeline_branches_e2e.py: 15" in result.stdout
        assert "test_validation_e2e.py: 6" in result.stdout

    def test_without_base_url_fails_clearly_instead_of_silently_skipping(self) -> None:
        # Given E2E_BASE_URL is unset
        # When the dedicated certification selector actually runs (not
        # collect-only)
        result = _run_pytest(["-m", "e2e", "tests/e2e/", "--no-cov", "-q"], base_url=None)

        # Then it fails loudly with a clear configuration error -- an
        # entirely skipped suite must never look like a passing live run
        assert result.returncode != 0
        assert "E2E_BASE_URL is required" in (result.stdout + result.stderr)
        assert "21 skipped" not in result.stdout


class TestDefaultUnitSelector:
    def test_default_suite_still_excludes_e2e_tests(self) -> None:
        # Given the default marker exclusions (no explicit -m override)
        # When tests/e2e/ is collected without the dedicated selector
        result = _run_pytest(["--collect-only", "tests/e2e/", "--no-cov", "-q"], base_url=None)

        # Then nothing is selected -- e2e tests stay opt-in only (#545)
        assert result.returncode == 5
