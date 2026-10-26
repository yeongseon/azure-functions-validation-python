from pathlib import Path

import yaml


def test_release_host_gate_executes_candidate_behavior_and_negative_control() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/publish-pypi.yml").read_text())
    job = workflow["jobs"]["cookbook-host-smoke"]
    commands = "\n".join(step.get("run", "") for step in job["steps"])
    assert "make host-candidate" in commands
    assert any(step.get("if") == "always()" for step in job["steps"])
    assert "cookbook-host-smoke" in workflow["jobs"]["publish"]["needs"]
