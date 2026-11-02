import os
from pathlib import Path
import shlex
import subprocess
import sys

import yaml


def test_publish_requires_candidate_runtime_audit_on_all_supported_interpreters() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/publish-pypi.yml").read_text())
    assert "runtime-dependency-audit" in workflow["jobs"]["publish"]["needs"]
    job = workflow["jobs"]["runtime-dependency-audit"]
    assert job["strategy"]["matrix"]["python-version"] == ["3.11", "3.12", "3.13", "3.14"]
    assert any("make audit-candidate" in step.get("run", "") for step in job["steps"])
    assert any(step.get("if") == "always()" for step in job["steps"])


def test_publish_audit_guards_run_without_project_dependencies(tmp_path: Path) -> None:
    """PR dependencies must not hide conftest imports in the tag-only audit lane."""
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/publish-pypi.yml").read_text())
    steps = workflow["jobs"]["runtime-dependency-audit"]["steps"]
    guard = next(
        step["run"]
        for step in steps
        if step.get("name") == "Verify audit guards on the selected interpreter"
    )
    command = next(shlex.split(line) for line in guard.splitlines() if "-m pytest" in line)
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("PYTHON", "PYTEST", "COV_CORE"))
    }
    venv = tmp_path / "guard-venv"
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv)],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check", "pytest"],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Use the workflow's arguments verbatim, substituting only the selected interpreter.
    result = subprocess.run(
        [str(python), *command[1:]],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "8 passed" in result.stdout
