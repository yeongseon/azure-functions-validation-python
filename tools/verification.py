"""Canonical verification CLI: python -m tools.verification, normally through Make."""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.verification_environment import clean, doctor
from tools.verification_evidence import Status, Summary, collect, publish, report, save
from tools.verification_host import host_smoke
from tools.verification_process import run

WORKER_TESTS = (
    "tests/test_decorator.py",
    "tests/test_integration.py",
    "tests/test_trigger_arg_name_worker_compat.py",
)
CONTRACT_TESTS = (
    "tests/test_endpoint_schema.py",
    "tests/test_metadata_helpers_drift.py",
    "tests/test_metadata_contract.py",
    "tests/test_toolkit_metadata.py",
    "tests/test_metadata.py",
    "tests/test_check_wheel_schemas.py",
)


def pytest_command(lane: str, extra: list[str]) -> list[str]:
    directory = Path("test-results") / lane
    command = [sys.executable, "-m", "pytest"]
    match lane:
        case "test":
            command += [
                "tests/",
                "-m",
                "not e2e and not compat2x",
                "--ignore=tests/e2e",
                "--ignore=tests/host_smoke",
                "--cov-report=xml:" + str(directory / "coverage.xml"),
            ]
        case "worker-compat":
            command += [*WORKER_TESTS, "--no-cov", "-m", "not e2e and not compat2x"]
        case "sdk-compat":
            command += [
                "tests/test_worker_compat_2x_spike.py",
                "-m",
                "compat2x",
                "-o",
                "addopts=",
                "-o",
                "pythonpath=",
            ]
        case "contracts":
            command += [*CONTRACT_TESTS, "--no-cov"]
        case _:
            command += ["tests/e2e/", "-m", "e2e", "--no-cov"]
    return command + ["--junitxml=" + str(directory / "junit.xml"), *extra]


def execute(lane: str, extra: list[str]) -> int:
    directory = Path("test-results") / lane
    if directory.exists():
        shutil.rmtree(directory)
    (directory / "logs").mkdir(parents=True)
    command = pytest_command(lane, extra)
    reason = ""
    code = 0
    blocked = False
    try:
        if lane in {"azure-e2e", "local-e2e"} and not os.environ.get("E2E_BASE_URL"):
            blocked, code, reason = True, 2, "Missing prerequisite: E2E_BASE_URL"
        if lane == "sdk-compat" and os.environ.get("AZFUNC_2X_SPIKE") != "1":
            blocked, code, reason = True, 2, "Opt-in SDK spike requires AZFUNC_2X_SPIKE=1"
        if lane == "host-smoke":
            command = ["func", "start", "(managed validation host smoke)"]
            if doctor():
                blocked, code, reason = True, 2, "Missing required integration tools"
            else:
                code = host_smoke(directory)
        elif not blocked:
            code = run(command, directory / "logs/runner.log")
    except KeyboardInterrupt:
        code, reason = 130, "Interrupted; owned child processes terminated"
    except (OSError, ET.ParseError, ValueError) as error:
        code, reason = 2, str(error)
    try:
        summary = collect(directory, command, code)
    except (ET.ParseError, ValueError) as error:
        summary = Summary(
            1,
            lane,
            tuple(command),
            0,
            0,
            0,
            0,
            "INCOMPLETE",
            2,
            reason=f"Invalid evidence: {error}",
        )
    if blocked:
        summary = replace(summary, status="INCOMPLETE")
        ET.ElementTree(ET.Element("testsuite", name=lane, tests="0")).write(
            directory / "junit.xml", encoding="unicode"
        )
    if lane == "sdk-compat":
        reason = (
            reason + "; " if reason else ""
        ) + "SDK compatibility spike, NOT Azure certification"
    summary = save(directory, replace(summary, reason=reason or summary.reason))
    publish(summary)
    return summary.exit_code


def aggregate(lane: str, outcomes: list[Summary]) -> int:
    status: Status = "FAIL" if any(item.status == "FAIL" for item in outcomes) else "PASS"
    if status == "PASS" and any(item.status != "PASS" for item in outcomes):
        status = "INCOMPLETE"
    directory = Path("test-results") / lane
    directory.mkdir(parents=True, exist_ok=True)
    summary = Summary(
        1,
        lane,
        ("make", lane),
        sum(s.selected for s in outcomes),
        sum(s.passed for s in outcomes),
        sum(s.failed for s in outcomes),
        sum(s.skipped for s in outcomes),
        status,
        int(status != "PASS"),
        reason="; ".join(f"{item.lane}={item.status}" for item in outcomes),
    )
    (directory / "lanes.json").write_text(json.dumps([asdict(s) for s in outcomes], indent=2))
    publish(save(directory, summary))
    return summary.exit_code


def integration() -> int:
    directory = Path("test-results/integration")
    if directory.exists():
        shutil.rmtree(directory)
    outcomes = []
    for lane in ("worker-compat", "host-smoke"):
        execute(lane, [])
        source = Path("test-results") / lane
        path = source / "summary.json"
        outcomes.append(Summary(**json.loads(path.read_text())))
        for pattern, destination in (("**/*junit.xml", "junit"), ("logs/*", "logs")):
            for artifact in source.glob(pattern):
                target = directory / destination / f"{lane}-{artifact.name}"
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(artifact, target)
    return aggregate("integration", outcomes)


def verify() -> int:
    directory = Path("test-results/verify")
    if directory.exists():
        shutil.rmtree(directory)
    outcomes = []
    for target in ("check", "test", "integration", "wheel-smoke", "docs"):
        path = Path("test-results") / target / "summary.json"
        path.unlink(missing_ok=True)
        code = run(["make", target], directory / "logs" / f"{target}.log", 1200)
        if path.exists():
            summary = Summary(**json.loads(path.read_text()))
            if code and summary.status == "PASS":
                summary = replace(summary, status="FAIL", exit_code=code)
        else:
            required = target != "check"
            summary = Summary(
                1,
                target,
                ("make", target),
                int(not required),
                int(not required and code == 0),
                int(code != 0),
                0,
                "INCOMPLETE" if required else ("FAIL" if code else "PASS"),
                code or int(required),
                reason="Required lane summary missing" if required else "",
            )
        outcomes.append(summary)
    return aggregate("verify", outcomes)


def focused(lane: str, command: list[str]) -> int:
    directory = Path("test-results") / lane
    if directory.exists():
        shutil.rmtree(directory)
    code = run(command, directory / "logs/runner.log", 1200)
    summary = Summary(
        1,
        lane,
        tuple(command),
        1,
        int(code == 0),
        int(code != 0),
        0,
        "PASS" if code == 0 else "FAIL",
        code,
    )
    publish(save(directory, summary))
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "lane",
        choices=(
            "test",
            "check",
            "integration",
            "worker-compat",
            "host-smoke",
            "sdk-compat",
            "contracts",
            "verify",
            "azure-e2e",
            "local-e2e",
            "report",
            "doctor",
            "clean",
            "focused",
        ),
    )
    args, extra = parser.parse_known_args()
    if not (3, 11) <= sys.version_info[:2] < (3, 15):
        parser.error("Python >=3.11,<3.15 is required")
    match args.lane:
        case "report":
            return report(Path("test-results"))
        case "doctor":
            return doctor()
        case "clean":
            clean(Path.cwd())
            return 0
        case "verify":
            return verify()
        case "check":
            return focused("check", ["make", "check-steps"])
        case "integration":
            return integration()
        case "focused":
            return focused(extra[0], [sys.executable, *extra[1:]])
        case _:
            return execute(args.lane, extra)


if __name__ == "__main__":
    raise SystemExit(main())
