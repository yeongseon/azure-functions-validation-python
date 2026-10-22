"""Regression contracts for the canonical developer commands."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    "install",
    "install-ci",
    "doctor",
    "format",
    "format-check",
    "check",
    "test",
    "integration",
    "verify",
    "e2e-azure",
    "report",
    "clean",
)


@pytest.mark.parametrize("target", CONTRACT)
def test_make_contract_is_install_free_on_routine_runs(target: str) -> None:
    # Given the public command contract, when dry-running a command.
    result = subprocess.run(["make", "-n", target], cwd=ROOT, capture_output=True, text=True)
    # Then routine runs never upgrade pip or bootstrap Hatch.
    assert result.returncode == 0, result.stderr
    assert "install --upgrade pip" not in result.stdout
    if target not in {"install", "install-ci"}:
        assert "pip install hatch" not in result.stdout


def test_check_runs_types_once_and_read_only_contract_checks() -> None:
    # Given the complete quality command, when expanding its recipe.
    result = subprocess.run(["make", "-n", "check"], cwd=ROOT, capture_output=True, text=True)
    # Then types run once and pinned contracts are checked, never regenerated.
    assert result.returncode == 0
    assert result.stdout.count("-m mypy") == 1
    assert "schema-hash" in result.stdout
    assert "contracts" in result.stdout
    assert "--update" not in result.stdout


def test_schema_mismatch_does_not_rewrite_pin(tmp_path: Path) -> None:
    # Given a checkout-shaped directory with an intentionally stale schema pin.
    schema = tmp_path / "src/azure_functions_validation/schemas"
    schema.mkdir(parents=True)
    (schema / "endpoint.schema.json").write_text("{}\n")
    pin = schema / "endpoint.schema.sha256"
    before = b"incorrect-pin  endpoint.schema.json\n"
    pin.write_bytes(before)
    environment = dict(os.environ, PYTHONPATH=str(ROOT))
    # When invoking the same non-mutating checker used by make check.
    result = subprocess.run(
        [sys.executable, "-m", "tools.verification_contracts", "schema-hash"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    # Then drift fails without changing pinned metadata bytes.
    assert result.returncode != 0
    assert "digest drift" in result.stdout
    assert pin.read_bytes() == before


def test_unconfigured_azure_saves_incomplete(tmp_path: Path) -> None:
    # Given no Azure URL and an isolated evidence root.
    environment = dict(os.environ, PYTHONPATH=str(ROOT))
    environment.pop("E2E_BASE_URL", None)
    # When using the canonical CLI surface.
    result = subprocess.run(
        [sys.executable, "-m", "tools.verification", "azure-e2e"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    # Then configuration absence is saved as INCOMPLETE, not certification.
    assert result.returncode != 0
    data = json.loads((tmp_path / "test-results/azure-e2e/summary.json").read_text())
    assert data["status"] == "INCOMPLETE"
    assert data["selected"] == 0
