from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest

from tools import dependency_audit_policy as audit
from tools.security_report import Status

POLICY = '{"schema_version":1,"blocking":"all-known-runtime","exceptions":[]}'


def installed(root: Path, name: str, version: str) -> None:
    directory = root / f"{name}-{version}.dist-info"
    directory.mkdir()
    (directory / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
    )


@pytest.mark.parametrize(
    "raw,code,expected",
    [
        ('{"dependencies":[{"name":"idna","version":"3.20","vulns":[]}]}', 0, Status.PASS),
        (
            '{"dependencies":[{"name":"idna","version":"3.20","vulns":[{"id":"CVE-1","fix_versions":[]}]}]}',
            1,
            Status.FAIL,
        ),
        ('{"dependencies":[{"name":"idna","skip_reason":"unpublished"}]}', 0, Status.INCOMPLETE),
        ('{"dependencies":[]}', 0, Status.INCOMPLETE),
        ('{"dependencies":[{"name":"other","version":"3.20","vulns":[]}]}', 0, Status.INCOMPLETE),
        (
            '{"dependencies":[{"name":"idna","version":"3.20","vulns":[]},{"name":"azure-functions-validation","version":"9999.0.123","vulns":[]}]}',
            0,
            Status.PASS,
        ),
        (
            '{"dependencies":[{"name":"idna","version":"3.20","vulns":[]},{"name":"azure-functions-validation","version":"1","vulns":[]}]}',
            0,
            Status.TOOL_ERROR,
        ),
    ],
)
def test_unpublished_candidate_audits_exact_third_party_inventory(
    raw: str, code: int, expected: Status, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given a verified unpublished candidate and one installed dependency.
    installed(tmp_path, "azure-functions-validation", "9999.0.123")
    installed(tmp_path, "idna", "3.20")
    policy = tmp_path / "policy.json"
    policy.write_text(POLICY)

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert "--path" not in command
        assert "--no-deps" in command and "--disable-pip" in command
        requirements = Path(command[command.index("--requirement") + 1]).read_text()
        assert requirements == "idna==3.20\n"
        return subprocess.CompletedProcess(command, code, stdout=raw)

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(audit, "version", lambda _: "2.10.1")
    # When auditing, then only the verified first-party candidate is excluded.
    result = audit.run_audit(tmp_path, policy, ("azure-functions-validation", "9999.0.123"))
    assert result.status == expected


def test_candidate_identity_mismatch_blocks_before_tool_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given an installed candidate with the wrong version.
    installed(tmp_path, "azure-functions-validation", "1")
    run = Mock()
    monkeypatch.setattr(subprocess, "run", run)
    # When a different artifact identity is required, then auditing is incomplete.
    result = audit.run_audit(tmp_path, tmp_path / "policy", ("azure-functions-validation", "2"))
    assert result.status == Status.INCOMPLETE
    run.assert_not_called()


def test_wheel_identity_requires_one_metadata_record(tmp_path: Path) -> None:
    from zipfile import ZipFile

    from tools.dependency_inventory import wheel_identity
    from tools.security_report import EvidenceError

    wheel = tmp_path / "candidate.whl"
    with ZipFile(wheel, "w") as archive:
        archive.writestr(
            "candidate.dist-info/METADATA", "Name: azure_functions_validation\nVersion: 9999.0.1\n"
        )
    assert wheel_identity(wheel) == ("azure-functions-validation", "9999.0.1")
    with ZipFile(wheel, "a") as archive:
        archive.writestr("other.dist-info/METADATA", "Name: other\nVersion: 1\n")
    with pytest.raises(EvidenceError):
        wheel_identity(wheel)
