import os
from pathlib import Path
import subprocess
import sys

import yaml

from tools.lint_release_workflows import check_pins, check_publish_needs

ROOT = Path(__file__).resolve().parents[1]


def test_release_audit_is_blocking_and_uses_candidate_artifact() -> None:
    text = (ROOT / ".github/workflows/publish-pypi.yml").read_text()
    jobs = yaml.safe_load(text)["jobs"]
    assert check_publish_needs(text, "publish-pypi.yml") == []
    assert "runtime-dependency-audit" in jobs["publish"]["needs"]
    gate = jobs["runtime-dependency-audit"]
    assert gate["permissions"] == {"contents": "read"}
    assert gate["needs"] == "build"
    assert gate["strategy"]["matrix"]["interpreter"] == ["3.11", "3.12", "3.13", "3.14"]
    assert not gate.get("continue-on-error")
    assert all(not step.get("continue-on-error") for step in gate["steps"])
    download = next(s for s in gate["steps"] if "download-artifact@" in s.get("uses", ""))
    assert download["with"]["name"] == "dist"
    commands = "\n".join(s.get("run", "") for s in gate["steps"])
    assert "pip-audit==2.10.1" in commands
    assert "--without-pip" in commands
    assert "make security-runtime-audit" in commands
    assert 'CANDIDATE_WHEEL="${wheels[0]}"' in commands


def test_evidence_uploads_run_on_failure_and_keep_permissions_narrow() -> None:
    for filename in ("security.yml", "dependency-audit.yml", "publish-pypi.yml"):
        text = (ROOT / ".github/workflows" / filename).read_text()
        workflow = yaml.safe_load(text)
        assert workflow["permissions"] == {"contents": "read"}
        assert check_pins(text, filename) == []
        uploads = [
            step
            for job in workflow["jobs"].values()
            for step in job.get("steps", [])
            if "upload-artifact@" in step.get("uses", "")
            and step.get("with", {}).get("path", "").startswith("security-results")
        ]
        assert uploads
        assert all(
            s["if"] == "always()" and s["with"]["if-no-files-found"] == "error" for s in uploads
        )


def test_worker_variants_include_offline_security_proofs() -> None:
    for filename in ("worker-nightly.yml", "ci-test.yml"):
        text = (ROOT / ".github/workflows" / filename).read_text()
        assert "tests/test_security_runtime.py" in text
        assert "tests/test_security_auth.py" in text


def test_reporting_lane_reuses_policy_without_weakening_release() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/dependency-audit.yml").read_text())
    steps = workflow["jobs"]["pip-audit"]["steps"]
    audits = [s for s in steps if "make security-audit-report" in s.get("run", "")]
    assert len(audits) == 2
    assert all(s["continue-on-error"] for s in audits)
    assert any("--development" in s["run"] for s in audits)


def test_collectors_run_even_after_scanner_failure() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/security.yml").read_text())
    for job in ("bandit", "semgrep"):
        collectors = [
            s for s in workflow["jobs"][job]["steps"] if f"make security-{job}" in s.get("run", "")
        ]
        assert len(collectors) == 1
        assert collectors[0]["if"] == "always()"


def test_semgrep_make_tolerates_only_incomplete_evidence(tmp_path: Path) -> None:
    for outcome, succeeds in (("success", True), ("failure", False)):
        result = subprocess.run(
            [
                "make",
                "security-semgrep",
                f"SECURITY_PYTHON={sys.executable}",
                f"SECURITY_OUTPUT={tmp_path / outcome}",
            ],
            cwd=ROOT,
            env=dict(os.environ, SCAN_OUTCOME=outcome),
            capture_output=True,
            text=True,
        )
        assert (result.returncode == 0) == succeeds
        assert "action outcome only" in result.stdout
