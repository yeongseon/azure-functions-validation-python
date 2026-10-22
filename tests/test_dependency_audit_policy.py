from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import subprocess

import pytest

from tools import dependency_audit_policy
from tools.dependency_audit_policy import classify_audit
from tools.security_exceptions import parse_exceptions
from tools.security_report import EvidenceError, Status, load

TODAY = date(2026, 10, 22)
POLICY = '{"schema_version":1,"blocking":"all-known-runtime","exceptions":[]}'


def payload(vulnerable: bool = False) -> str:
    return json.dumps(
        {
            "dependencies": [
                {
                    "name": "pydantic",
                    "version": "2.0",
                    "vulns": [
                        {"id": "CVE-2026-12345", "fix_versions": [], "description": "CANARY_SECRET"}
                    ]
                    if vulnerable
                    else [],
                }
            ]
        }
    )


@pytest.mark.parametrize("vulnerable,expected", [(False, Status.PASS), (True, Status.FAIL)])
def test_any_known_runtime_advisory_blocks(vulnerable: bool, expected: Status) -> None:
    result = classify_audit(payload(vulnerable), int(vulnerable), policy_raw=POLICY, today=TODAY)
    assert result.status == expected
    assert "CANARY_SECRET" not in repr(result)


@pytest.mark.parametrize("raw", ["", "invalid", "{}"])
def test_invalid_audit_is_tool_error(raw: str) -> None:
    assert classify_audit(raw, 1, policy_raw=POLICY, today=TODAY).status == Status.TOOL_ERROR


@pytest.mark.parametrize(
    "raw",
    [
        '{"dependencies":[]}',
        '{"dependencies":[{"name":"x","version":"1","skip_reason":"CANARY_SECRET"}]}',
    ],
)
def test_empty_or_skipped_audit_is_incomplete(raw: str) -> None:
    assert classify_audit(raw, 0, policy_raw=POLICY, today=TODAY).status == Status.INCOMPLETE


@pytest.mark.parametrize(
    "expires,expected", [("2026-10-21", Status.FAIL), ("2026-11-21", Status.PASS)]
)
def test_exception_expiry_and_affectedness(expires: str, expected: Status) -> None:
    policy = json.loads(POLICY)
    policy["exceptions"] = [
        {
            "id": "CVE-2026-12345",
            "package": "pydantic",
            "kind": "fix-not-available",
            "reason": "no patched release",
            "owner": "maintainer",
            "added": "2026-10-01",
            "expires": expires,
        }
    ]
    result = classify_audit(payload(True), 1, policy_raw=json.dumps(policy), today=TODAY)
    assert result.status == expected
    raw = json.loads(payload(True))
    raw["dependencies"][0]["vulns"][0]["fix_versions"] = ["3"]
    assert (
        classify_audit(json.dumps(raw), 1, policy_raw=json.dumps(policy), today=TODAY).status
        == Status.FAIL
    )


@pytest.mark.parametrize(
    "patch",
    [
        {"expires": "2027-10-22"},
        {"added": "2026-11-01"},
        {"kind": "ignore-all"},
        {"line": -1},
        {"line": True},
        {"owner": ""},
        {"reason": ""},
    ],
)
def test_invalid_exception_policy_fails(patch: dict[str, str | int]) -> None:
    rule = {
        "id": "CVE-1",
        "package": "example",
        "kind": "not-affected",
        "reason": "reviewed",
        "owner": "maintainer",
        "added": "2026-10-01",
        "expires": "2026-11-01",
        **patch,
    }
    with pytest.raises((EvidenceError, ValueError)):
        parse_exceptions(load(json.dumps({"exceptions": [rule]}))["exceptions"], TODAY)


@pytest.mark.parametrize("code", [0, 2])
def test_inconsistent_exit_status_fails(code: int) -> None:
    assert (
        classify_audit(payload(True), code, policy_raw=POLICY, today=TODAY).status
        == Status.TOOL_ERROR
    )


def test_audit_runner_targets_only_candidate_installation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given an isolated installed inventory; When audited; Then tools use only its path.
    (tmp_path / "example.dist-info").mkdir()
    policy = tmp_path / "policy.json"
    policy.write_text(POLICY)

    def complete(command: list[str], **kwargs: str) -> subprocess.CompletedProcess[str]:
        assert command[command.index("--path") + 1] == str(tmp_path)
        return subprocess.CompletedProcess(command, 0, stdout=payload(), stderr="CANARY_SECRET")

    monkeypatch.setattr(subprocess, "run", complete)
    monkeypatch.setattr(dependency_audit_policy, "version", lambda name: "2.10.1")
    assert dependency_audit_policy.run_audit(tmp_path, policy).status == Status.PASS
