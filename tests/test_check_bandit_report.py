"""The Bandit gate must fail instead of passing vacuously (#578), proven with real Bandit.

Bandit exits 0 for most of these scopes, so each case builds a scratch tree, runs Bandit with
the flags of ``make security`` and hands its JSON report to the guard.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

from scripts.check_bandit_report import main

_SHELL_TRUE = "import subprocess\nsubprocess.call('echo', shell=True)\n"
_SUPPRESSED = (
    "import subprocess  # nosec B404 # test fixture\n"
    "subprocess.call('echo', shell=True)  # nosec B602 B607 # test fixture\n"
)
_OK = "x = 1\n"


@pytest.mark.parametrize(
    ("files", "exit_code", "reason"),
    [
        pytest.param({"ok.py": _OK}, 0, "", id="clean-tree"),
        # Bandit 1.9.4 draws a progress bar on stdout above 50 files; -q keeps it out.
        pytest.param({f"m{n}.py": _OK for n in range(60)}, 0, "", id="over-50-files"),
        pytest.param({"ok.py": _SUPPRESSED}, 0, "", id="inline-nosec-with-reason"),
        pytest.param({}, 1, "no code was analysed", id="empty-dir"),
        pytest.param({"empty.py": ""}, 1, "no code was analysed", id="only-empty-files"),
        pytest.param(None, 1, "skipped", id="missing-dir"),
        pytest.param({"bad.py": "def (:\n"}, 1, "syntax error", id="unparsable-file"),
        pytest.param(
            {"a.py": _OK, "gone.py": _OK, ".bandit": "[bandit]\nexclude = gone.py\n"},
            1,
            "not scanned",
            id="narrowed-scope",
        ),
        pytest.param({"bad.py": _SHELL_TRUE}, 1, "B602", id="shell-true-finding"),
    ],
)
def test_bandit_gate_fails_unless_everything_was_analysed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    files: dict[str, str] | None,
    exit_code: int,
    reason: str,
) -> None:
    # Given a scope (``None``: a path that does not exist) scanned like `make security` does
    scope = tmp_path / "scope"
    if files is not None:
        scope.mkdir()
        for name, text in files.items():
            (scope / name).write_text(text, encoding="utf-8")
    report = tmp_path / "bandit.json"
    bandit = [sys.executable, "-m", "bandit", "-q", "-f", "json", "-o", str(report)]
    subprocess.run([*bandit, "-r", str(scope)], check=False, capture_output=True)

    # When the guard reads Bandit's report
    result = main(str(report), [str(scope)])

    # Then it passes only a complete, finding-free scan, and names why it failed otherwise
    assert result == exit_code
    assert reason in capsys.readouterr().err


def test_missing_report_fails_instead_of_reading_a_stale_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Given a scope and a report path that Bandit never wrote
    scope = tmp_path / "scope"
    scope.mkdir()
    (scope / "ok.py").write_text(_OK, encoding="utf-8")

    # When the guard looks for the report
    result = main(str(tmp_path / "bandit.json"), [str(scope)])

    # Then it fails and says it could not read it
    assert result == 1
    assert "cannot read" in capsys.readouterr().err
