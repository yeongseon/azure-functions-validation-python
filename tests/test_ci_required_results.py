from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "ci_check_required_results.sh"
FULL_JOBS = (
    "quality",
    "test",
    "minimum-dependencies",
    "artifact-build",
    "artifact-python310-negative",
    "artifact-python311",
    "azure-functions-2x",
    "host-smoke",
)


def evaluate(
    *,
    changes: str = "success",
    event: str = "pull_request",
    docs_changed: str = "false",
    full_required: str = "true",
    overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    results = {
        "changes": changes,
        "format": "success" if event == "pull_request" else "skipped",
        "docs-check": "success" if docs_changed == "true" else "skipped",
        **dict.fromkeys(FULL_JOBS, "success" if full_required == "true" else "skipped"),
    }
    results.update(overrides or {})
    return subprocess.run(
        ["bash", str(SCRIPT), event, docs_changed, full_required],
        input="\n".join(f"{job}={result}" for job, result in results.items()) + "\n",
        capture_output=True,
        text=True,
        check=False,
    )


def test_docs_only_with_successful_docs_check_passes() -> None:
    assert evaluate(docs_changed="true", full_required="false").returncode == 0


@pytest.mark.parametrize(
    ("overrides", "docs_changed", "full_required"),
    [
        ({"docs-check": "failure"}, "true", "false"),
        ({"test": "skipped"}, "false", "true"),
        ({"test": "failure"}, "false", "true"),
        ({"changes": "failure"}, "true", "true"),
        ({"quality": "cancelled"}, "false", "true"),
    ],
)
def test_unexpected_results_fail(
    overrides: dict[str, str], docs_changed: str, full_required: str
) -> None:
    assert (
        evaluate(
            docs_changed=docs_changed,
            full_required=full_required,
            overrides=overrides,
        ).returncode
        == 1
    )


def test_main_docs_only_push_accepts_expected_skips() -> None:
    assert evaluate(event="push", docs_changed="true", full_required="false").returncode == 0


@pytest.mark.parametrize(
    ("docs_changed", "full_required"),
    [
        ("", "true"),
        ("invalid", "true"),
        ("false", ""),
        ("false", "invalid"),
        ("false", "false"),
    ],
)
def test_invalid_or_contradictory_classifier_outputs_fail(
    docs_changed: str, full_required: str
) -> None:
    assert evaluate(docs_changed=docs_changed, full_required=full_required).returncode == 1


@pytest.mark.parametrize("result", ["failure", "skipped"])
def test_unclassified_needs_job_must_succeed(result: str) -> None:
    assert evaluate(overrides={"new-job": result}).returncode == 1
