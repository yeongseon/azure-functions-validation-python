from __future__ import annotations

from contextlib import nullcontext
import json
import os
from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest

from tools.verification import focused
from tools.verification_evidence import Summary, redact, save
from tools.verification_host import wait_ready


@pytest.mark.parametrize(
    "text",
    [
        '{"Authorization": "Bearer CANARY"}',
        "{'Authorization': 'Bearer CANARY'}",
        "Proxy-Authorization: Bearer CANARY",
        '{"password": "alpha CANARY beta"}',
        '{"token": "with \\"escaped\\" CANARY"}',
        "connection_string=Endpoint=sb://ns/;SharedAccessKey=CANARY",
        "InstrumentationKey=CANARY;IngestionEndpoint=https://x/",
        "https://user:CANARY@example.test/path",
        '<failure message="Authorization: Bearer CANARY">x</failure>',
    ],
)
def test_quoted_credentials_are_consumed_whole(text: str) -> None:
    # Given credential-bearing text, when redacting, then no suffix leaks.
    assert "CANARY" not in redact(text)


def test_save_keeps_structured_evidence_valid_and_binary_untouched(tmp_path: Path) -> None:
    # Given JSON, binary and a symlink outside the evidence tree.
    png = b"\x89PNG\r\n\x1a\n\xff\xfe\x00binary"
    (tmp_path / "chart.png").write_bytes(png)
    outside = tmp_path.parent / f"{tmp_path.name}-outside.log"
    outside.write_text("password=CANARY")
    (tmp_path / "link.log").symlink_to(outside)
    (tmp_path / "extra.json").write_text('{"nested": ["Authorization: Bearer CANARY"]}')
    # When saving evidence including tuple-valued command arguments.
    save(tmp_path, Summary(1, "test", ('Authorization: "Bearer CANARY"',), 1, 1, 0, 0, "PASS", 0))
    # Then JSON parses, secrets are absent, and non-text/outside assets stay intact.
    for name in ("summary.json", "extra.json"):
        assert "CANARY" not in str(json.loads((tmp_path / name).read_text()))
    assert (tmp_path / "chart.png").read_bytes() == png
    assert outside.read_text() == "password=CANARY"


def test_known_secret_is_replaced_before_partial_patterns(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given a complete secret containing separators and escaped quotes.
    monkeypatch.setenv("MY_API_TOKEN", 'pre;fix&CANARY "value"')
    # When redacting raw and JSON-escaped spellings, then the full value disappears.
    for value in (os.environ["MY_API_TOKEN"], json.dumps(os.environ["MY_API_TOKEN"])[1:-1]):
        assert "CANARY" not in redact(value)


@pytest.mark.parametrize("error", [TimeoutError(), ConnectionError(), OSError()])
def test_host_readiness_retries_transient_errors(
    error: OSError, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given a transient read failure followed by a ready host.
    request = Mock(side_effect=[error, nullcontext(Mock(status=200))])
    monkeypatch.setattr("tools.verification_host.urlopen", request)
    monkeypatch.setattr("tools.verification_host.time.sleep", lambda _: None)
    # When awaiting readiness, then the second probe succeeds.
    wait_ready(Mock(poll=Mock(return_value=None)), "http://localhost/")
    assert request.call_count == 2


def test_failed_quality_command_saves_redacted_log_and_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    # Given a failing quality command and a private evidence directory.
    monkeypatch.chdir(tmp_path)
    # When executing through the shared evidence runner.
    code = focused("check", [sys.executable, "-c", "print('password=CANARY');exit(7)"])
    # Then the exit code and failure survive, with a safe log.
    assert code == 7
    data = json.loads(Path("test-results/check/summary.json").read_text())
    assert data["status"] == "FAIL" and data["exit_code"] == 7
    assert "CANARY" not in Path("test-results/check/logs/runner.log").read_text()


@pytest.mark.parametrize("target", ["doctor", "report", "clean"])
def test_maintenance_never_bootstraps_hatch(target: str, tmp_path: Path) -> None:
    # Given an empty Hatch data directory and a Hatch command that cannot run.
    root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ, HATCH_DATA_DIR=str(tmp_path / "hatch"))
    environment.pop("CI", None)
    # When running a maintenance command, then no Hatch environment is created.
    (tmp_path / "Makefile").write_bytes((root / "Makefile").read_bytes())
    environment["PYTHONPATH"] = str(root)
    result = subprocess.run(
        ["make", target, "HATCH=false"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert "false run" not in result.stdout + result.stderr
    assert not (tmp_path / "hatch").exists()
    if target == "clean":
        assert result.returncode == 0, result.stderr
