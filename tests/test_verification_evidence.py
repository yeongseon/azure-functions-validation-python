from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from tools.verification import execute, pytest_command
from tools.verification_environment import clean, doctor
from tools.verification_evidence import Summary, collect, redact, report, save
from tools.verification_process import child, run, terminate


@pytest.mark.parametrize(
    ("cases", "exit_code", "status"),
    [
        ("", 0, "INCOMPLETE"),
        ("", 5, "INCOMPLETE"),
        ("<testcase><skipped/></testcase>", 0, "INCOMPLETE"),
        ("<testcase/><testcase><skipped/></testcase>", 0, "INCOMPLETE"),
        ("<testcase><failure/></testcase>", 1, "FAIL"),
        ("<testcase/>", 0, "PASS"),
        ("<testcase/>", 124, "FAIL"),
    ],
)
def test_junit_classifies_execution_fail_closed(
    tmp_path: Path, cases: str, exit_code: int, status: str
) -> None:
    (tmp_path / "junit.xml").write_text(f"<testsuite>{cases}</testsuite>")
    summary = collect(tmp_path, ["pytest"], exit_code)
    assert summary.status == status
    assert (summary.exit_code == 0) == (status == "PASS")


@pytest.mark.parametrize(
    "secret",
    [
        "AccountKey=VERYSECRET;",
        "SharedAccessSignature=VERYSECRET;",
        "code=VERYSECRET&x=1",
        "x-functions-key: VERYSECRET",
        "Authorization: Bearer VERYSECRET",
        "password=VERYSECRET",
        "token=VERYSECRET",
        "AzureWebJobsStorage=VERYSECRET",
        "sas=VERYSECRET",
        "api_key=VERYSECRET",
        "DefaultEndpointsProtocol=https;AccountName=PRIVATE;AccountKey=VERYSECRET;",
    ],
)
def test_secrets_are_redacted_from_all_saved_evidence(tmp_path: Path, secret: str) -> None:
    (tmp_path / "junit.xml").write_text(
        "<testsuite><testcase><system-out>"
        + secret.replace("&", "&amp;")
        + "</system-out></testcase></testsuite>"
    )
    (tmp_path / "output.log").write_text(secret)
    save(tmp_path, collect(tmp_path, ["pytest", secret], 0))
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert "VERYSECRET" not in path.read_text()
    json.loads((tmp_path / "summary.json").read_text())


def test_environment_secrets_are_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CUSTOM_ACCESS_TOKEN", "opaque-sensitive-value")
    assert redact("diagnostic opaque-sensitive-value") == "diagnostic [REDACTED]"


def test_summary_schema_and_saved_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    directory = tmp_path / "test"
    directory.mkdir()
    (directory / "junit.xml").write_text("<testsuite><testcase/></testsuite>")
    (directory / "coverage.xml").write_text('<coverage line-rate="0.99"/>')
    save(directory, collect(directory, ["not-an-executable"], 0))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "job-summary"))
    assert report(tmp_path) == 0
    data = json.loads((directory / "summary.json").read_text())
    assert data["schema_version"] == 1
    assert (data["selected"], data["passed"], data["failed"], data["skipped"]) == (1, 1, 0, 0)
    assert data["coverage"] == 0.99
    assert str(directory / "junit.xml") in data["supporting_files"]
    assert "passed=1" in (tmp_path / "job-summary").read_text()


def test_report_without_results_does_not_create_evidence(tmp_path: Path) -> None:
    assert report(tmp_path) == 1
    assert list(tmp_path.iterdir()) == []


def test_required_tools_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("tools.verification_environment.shutil.which", lambda _: None)
    assert doctor() != 0
    assert execute("host-smoke", []) != 0
    data = json.loads((tmp_path / "test-results/host-smoke/summary.json").read_text())
    assert data["status"] == "INCOMPLETE"


def test_sdk_spike_is_opt_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AZFUNC_2X_SPIKE", raising=False)
    assert execute("sdk-compat", []) != 0
    data = json.loads((tmp_path / "test-results/sdk-compat/summary.json").read_text())
    assert data["status"] == "INCOMPLETE"


def test_offline_and_worker_selection_are_explicit() -> None:
    unit = pytest_command("test", [])
    assert "--ignore=tests/e2e" in unit
    assert "--ignore=tests/host_smoke" in unit
    assert "not e2e and not compat2x" in unit
    assert "tests/test_trigger_arg_name_worker_compat.py" in pytest_command("worker-compat", [])
    assert "pythonpath=" in pytest_command("sdk-compat", [])


def test_clean_preserves_environments_and_shared_storage(tmp_path: Path) -> None:
    for name in (".venv", "src", "shared-azurite", "test-results", "dist", "build"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "keep").touch()
    clean(tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == [".venv", "shared-azurite", "src"]


def test_clean_unlinks_artifact_symlink_without_following(tmp_path: Path) -> None:
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared/keep").touch()
    (tmp_path / "test-results").symlink_to(tmp_path / "shared", target_is_directory=True)
    clean(tmp_path)
    assert (tmp_path / "shared/keep").exists()


def test_process_failure_is_preserved(tmp_path: Path) -> None:
    assert run([sys.executable, "-c", "raise SystemExit(7)"], tmp_path / "log") == 7
    assert run(["/nonexistent/verification-command"], tmp_path / "missing") == 127


def test_owned_process_is_reaped_after_interrupt(tmp_path: Path) -> None:
    with (
        pytest.raises(KeyboardInterrupt),
        child([sys.executable, "-c", "import time; time.sleep(30)"], tmp_path / "log") as process,
    ):
        raise KeyboardInterrupt
    assert process.poll() is not None


def test_timeout_reaps_process_and_redacts_logs(tmp_path: Path) -> None:
    code = run(
        [sys.executable, "-u", "-c", "import time; print('password=VERYSECRET'); time.sleep(30)"],
        tmp_path / "log",
        1,
    )
    assert code == 124
    assert "VERYSECRET" not in (tmp_path / "log").read_text()


def test_cleanup_tolerates_process_exit_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def exited_group(pid: int, number: int) -> None:
        raise ProcessLookupError(pid)

    with child([sys.executable, "-c", "raise SystemExit(0)"], tmp_path / "log") as process:
        monkeypatch.setattr("tools.verification_process.os.killpg", exited_group)
        terminate(process)
    assert process.returncode == 0


def test_wheel_smoke_rejects_stale_dist_when_build_produces_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.verification_wheel import main

    (tmp_path / "dist").mkdir()
    (tmp_path / "dist/stale.whl").write_bytes(b"stale")

    def empty_build(command: list[str], log: Path, timeout: float = 600) -> int:
        assert "--outdir" in command
        assert str(tmp_path / "dist") not in command
        return 0

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("tools.verification_wheel.run", empty_build)
    assert main() != 0


def test_integration_preserves_separate_required_lanes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.verification import integration

    calls: list[str] = []

    def fake_execute(lane: str, extra: list[str]) -> int:
        calls.append(lane)
        save(
            Path("test-results") / lane,
            Summary(
                1,
                lane,
                ("test",),
                0,
                0,
                0,
                0,
                "INCOMPLETE",
                1,
            ),
        )
        return 1

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("tools.verification.execute", fake_execute)
    assert integration() != 0
    assert calls == ["worker-compat", "host-smoke"]
    assert (
        json.loads(Path("test-results/integration/summary.json").read_text())["status"]
        == "INCOMPLETE"
    )


def test_verify_runs_all_lanes_after_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.verification import verify

    calls: list[str] = []

    def fake_run(command: list[str], log: Path, timeout: float = 600) -> int:
        calls.append(command[1])
        return 1

    monkeypatch.chdir(tmp_path)
    save(Path("test-results/test"), Summary(1, "test", ("old",), 1, 1, 0, 0, "PASS", 0))
    monkeypatch.setattr("tools.verification.run", fake_run)
    assert verify() != 0
    assert calls == ["check", "test", "integration", "wheel-smoke", "docs"]
    lanes = json.loads(Path("test-results/verify/lanes.json").read_text())
    assert lanes[1]["status"] == "INCOMPLETE"
