from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools import dependency_audit_policy, security_evidence
from tools.security_evidence import apply_bandit_policy, classify_bandit, semgrep_evidence
from tools.security_report import Check, Status, write_report


def payload() -> str:
    return json.dumps(
        {
            "errors": [],
            "metrics": {
                "_totals": {"loc": 10, "nosec": 0, "skipped_tests": 0},
                "src/x.py": {"loc": 10},
            },
            "results": [],
        }
    )


@pytest.mark.parametrize(
    "raw,code,status",
    [
        ("", 2, Status.TOOL_ERROR),
        ("invalid", 0, Status.TOOL_ERROR),
        ('{"errors":[],"metrics":{"_totals":{}},"results":[]}', 0, Status.INCOMPLETE),
    ],
)
def test_missing_evidence_fails_closed(raw: str, code: int, status: Status) -> None:
    assert classify_bandit(raw, code, floor=1).status == status


def test_complete_scan_has_real_counts() -> None:
    result = classify_bandit(payload(), 0, floor=1)
    assert result.status == Status.PASS
    assert result.counts == {"files": 1, "loc": 10, "errors": 0}


@pytest.mark.parametrize("severity", ["LOW", "MEDIUM", "HIGH"])
def test_findings_block_without_disclosing_raw_diagnostics(severity: str, tmp_path: Path) -> None:
    # Given secret-bearing source diagnostics; When classified; Then only metadata survives.
    data = json.loads(payload())
    data["results"] = [
        {
            "test_id": "B105",
            "filename": "src/x.py",
            "line_number": 3,
            "issue_severity": severity,
            "issue_confidence": "HIGH",
            "code": "Bearer CANARY_SECRET_token",
            "issue_text": "AccountKey=CANARY_SECRET",
        }
    ]
    result = classify_bandit(json.dumps(data), 1, floor=1)
    assert result.status == Status.FAIL
    assert result.counts[f"severity.{severity}"] == 1
    summary = tmp_path / "summary.md"
    assert write_report([result], tmp_path, summary) == 1
    assert "CANARY_SECRET" not in (tmp_path / "summary.json").read_text() + summary.read_text()


@pytest.mark.parametrize("code", [0, 2])
def test_crash_or_error_files_are_tool_errors(code: int) -> None:
    data = json.loads(payload())
    data["errors"] = [{"reason": "CANARY_SECRET"}]
    assert classify_bandit(json.dumps(data), code, floor=1).status == Status.TOOL_ERROR


def test_static_policy_matches_exact_location_and_expires() -> None:
    data = json.loads(payload())
    data["results"] = [
        {
            "test_id": "B404",
            "filename": "src/x.py",
            "line_number": 1,
            "issue_severity": "LOW",
            "issue_confidence": "HIGH",
        }
    ]
    check = classify_bandit(json.dumps(data), 1, floor=1)
    rule = {
        "id": "B404",
        "file": "src/x.py",
        "line": 1,
        "kind": "reviewed-static",
        "reason": "fixed shell-free command",
        "owner": "maintainer",
        "added": "2026-10-01",
        "expires": "2026-11-01",
    }
    policy = json.dumps({"schema_version": 1, "exceptions": [rule]})
    assert apply_bandit_policy(check, policy, date(2026, 10, 22)).status == Status.PASS
    assert apply_bandit_policy(check, policy, date(2026, 11, 2)).status == Status.FAIL
    rule["line"] = 2
    assert (
        apply_bandit_policy(
            check, json.dumps({"schema_version": 1, "exceptions": [rule]}), date(2026, 10, 22)
        ).status
        == Status.FAIL
    )
    assert apply_bandit_policy(check, "invalid", date(2026, 10, 22)).status == Status.TOOL_ERROR


@pytest.mark.parametrize(
    "outcome,status",
    [
        ("success", Status.PASS),
        ("failure", Status.TOOL_ERROR),
        ("skipped", Status.INCOMPLETE),
    ],
)
def test_semgrep_outcome_is_not_misreported_as_vulnerability(outcome: str, status: Status) -> None:
    assert semgrep_evidence(outcome).status == status


def test_bandit_runner_compares_full_inventory(monkeypatch: pytest.MonkeyPatch) -> None:
    metrics = {
        p.as_posix(): {"loc": 1}
        for surface in security_evidence.SCOPE
        for p in Path(surface).rglob("*.py")
    }
    metrics["_totals"] = {"loc": len(metrics)}
    raw = json.dumps({"errors": [], "metrics": metrics, "results": []})

    def complete(command: list[str], **kwargs: str) -> subprocess.CompletedProcess[str]:
        assert "--ignore-nosec" in command
        return subprocess.CompletedProcess(command, 0, stdout=raw, stderr="CANARY_SECRET")

    monkeypatch.setattr(subprocess, "run", complete)
    assert security_evidence.run_bandit().status == Status.PASS
    del metrics[next(iter(metrics))]
    raw = json.dumps({"errors": [], "metrics": metrics, "results": []})
    assert security_evidence.run_bandit().status == Status.INCOMPLETE


@pytest.mark.parametrize("failure", [OSError(), subprocess.TimeoutExpired("scanner", 1)])
def test_tool_execution_failures_never_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: OSError | subprocess.TimeoutExpired
) -> None:
    (tmp_path / "example.dist-info").mkdir()

    def fail(*args: str, **kwargs: str) -> subprocess.CompletedProcess[str]:
        raise failure

    monkeypatch.setattr(subprocess, "run", fail)
    assert security_evidence.run_bandit().status == Status.TOOL_ERROR
    assert dependency_audit_policy.run_audit(tmp_path, tmp_path).status == Status.TOOL_ERROR


def test_evidence_cli_runs_without_runtime_dependencies(tmp_path: Path) -> None:
    # Given the real stdlib-only CLI; When invoked; Then it writes machine-readable evidence.
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.security_evidence",
            "semgrep",
            "--outcome",
            "success",
            "--output",
            str(tmp_path),
        ],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert json.loads((tmp_path / "summary.json").read_text())["schema_version"] == 1


@pytest.mark.parametrize("marker", ["# nosec", "# nosec B999"])
def test_unlisted_inline_suppression_is_incomplete(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, marker: str
) -> None:
    # Given an unlisted inline skip in a scanned file; When scanned; Then it cannot pass.
    root = tmp_path / "src"
    root.mkdir()
    (root / "example.py").write_text(f"value = 1  {marker}\n")
    policy = tmp_path / "security"
    policy.mkdir()
    (policy / "bandit-policy.json").write_text('{"schema_version":1,"exceptions":[]}')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(security_evidence, "SCOPE", ("src",))
    raw = json.dumps(
        {
            "errors": [],
            "metrics": {"_totals": {"loc": 30}, **{f"src/{i}.py": {} for i in range(30)}},
            "results": [],
        }
    )

    def complete(*args: str, **kwargs: str) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, stdout=raw, stderr="")

    monkeypatch.setattr(subprocess, "run", complete)
    result = security_evidence.run_bandit()
    assert result.status == Status.INCOMPLETE
    assert "Unlisted inline suppression" in result.message


@pytest.mark.parametrize("development", [False, True])
def test_audit_cli_preserves_failure_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, development: bool
) -> None:
    args = ["audit", "--site-packages", str(tmp_path), "--output", str(tmp_path)]
    if development:
        args.append("--development")
    monkeypatch.setattr(sys, "argv", args)
    monkeypatch.setattr(
        dependency_audit_policy,
        "run_audit",
        lambda path, policy: Check("pip-audit", (), Status.INCOMPLETE, None),
    )
    assert dependency_audit_policy.main() == 3
