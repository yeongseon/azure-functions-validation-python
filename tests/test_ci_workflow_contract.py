"""Contract: the required SDK 2.x lane in ci-test.yml must fail closed (#580).

The spike module skips itself unless ``AZFUNC_2X_SPIKE=1``, so a lane that loses its
environment would report ``6 skipped`` and exit 0. Parse the workflow instead of grepping it.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci-test.yml"


def test_sdk_2x_spike_lane_sets_both_fail_closed_variables() -> None:
    workflow = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    job = workflow["jobs"]["azure-functions-2x"]
    spike_steps = [step for step in job["steps"] if "-m compat2x" in step.get("run", "")]
    assert spike_steps, "azure-functions-2x no longer runs `pytest -m compat2x`"
    for step in spike_steps:
        env = {**workflow.get("env", {}), **job.get("env", {}), **step.get("env", {})}
        name = step.get("name")
        assert env.get("AZFUNC_2X_SPIKE") == "1", f"{name!r} must set AZFUNC_2X_SPIKE: '1'"
        assert env.get("FAIL_ON_SKIP") == "1", f"{name!r} must set FAIL_ON_SKIP: '1'"
