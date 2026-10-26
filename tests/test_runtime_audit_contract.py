from pathlib import Path

import yaml


def test_publish_requires_candidate_runtime_audit_on_all_supported_interpreters() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/publish-pypi.yml").read_text())
    assert "runtime-dependency-audit" in workflow["jobs"]["publish"]["needs"]
    job = workflow["jobs"]["runtime-dependency-audit"]
    assert job["strategy"]["matrix"]["python-version"] == ["3.11", "3.12", "3.13", "3.14"]
    assert any("make audit-candidate" in step.get("run", "") for step in job["steps"])
    assert any(step.get("if") == "always()" for step in job["steps"])
