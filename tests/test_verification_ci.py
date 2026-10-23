from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_ci_uses_canonical_runners_and_failure_artifacts() -> None:
    workflows = ROOT / ".github/workflows"
    ci = (workflows / "ci-test.yml").read_text()
    assert 'python-version: ["3.11", "3.12", "3.13", "3.14"]' in ci
    assert "python -m tools.verification test --no-cov" in ci
    assert "python -m tools.verification integration" in ci
    assert "python -m tools.verification sdk-compat" in ci
    assert "make install-ci" in ci
    for name in ("ci-test.yml", "e2e-azure.yml", "publish-pypi.yml", "worker-nightly.yml"):
        text = (workflows / name).read_text()
        assert "path: test-results/**" in text
        blocks = text.split("      - name:")
        evidence = [block for block in blocks if "path: test-results/**" in block]
        assert evidence
        assert all("if: always()" in block for block in evidence)


def test_check_all_is_exact_verify_alias() -> None:
    text = (ROOT / "Makefile").read_text()
    assert "check-all: verify\n\n" in text
    result = subprocess.run(
        ["make", "--no-print-directory", "-n", "test", "CI=true", "PYTHON=matrix-python"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "matrix-python -m tools.verification test"


def test_clean_all_retains_deep_cleanup_contract() -> None:
    result = subprocess.run(
        ["make", "-n", "clean-all"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    assert "-m tools.verification clean" in result.stdout
    assert "__pycache__" in result.stdout
    assert "rm -rf .DS_Store .venv" in result.stdout


def test_schema_and_wheel_commands_are_non_mutating() -> None:
    result = subprocess.run(
        ["make", "-n", "check-schema-hash", "wheel-smoke"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    assert "--update" not in result.stdout
    assert "tools.verification_contracts schema-hash" in result.stdout
    assert "tools.verification_wheel" in result.stdout
