"""The Bandit gate must fail instead of passing vacuously (#578), proven with real Bandit.

Bandit exits 0 for most of these scopes, so the first cases build a scratch tree, run Bandit
with the flags of ``make security`` and hand its JSON report to the guard. The last cases run
the real ``make security`` recipe on a scratch copy of the layout it scans, so a skip list added
to that recipe turns them red.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

import pytest

from scripts.check_bandit_report import main

_ROOT = Path(__file__).resolve().parents[1]
_SHELL_TRUE = "import subprocess\nsubprocess.call('echo', shell=True)\n"
_NEW_CALL = "import subprocess\nimport sys\n\nsubprocess.run([sys.argv[1]], check=True)\n"
_REVIEWED_CALL = (
    "import subprocess  # nosec B404 # test fixture\n"
    "import sys\n\n"
    "subprocess.run([sys.argv[1]], check=True)  # nosec B603 # test fixture\n"
)
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


@pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("make") is None,
    reason="runs the real `make security` recipe through /bin/sh",
)
@pytest.mark.parametrize(
    ("helper_source", "failing_tests"),
    [
        pytest.param("x = 1\n", set(), id="clean-helpers"),
        pytest.param(_NEW_CALL, {"B404", "B603"}, id="new-subprocess-call-without-nosec"),
        pytest.param(_SHELL_TRUE, {"B602"}, id="shell-true"),
        pytest.param(_REVIEWED_CALL, set(), id="subprocess-call-with-reasoned-nosec"),
    ],
)
def test_make_security_holds_helper_dirs_to_every_bandit_test(
    tmp_path: Path, helper_source: str, failing_tests: set[str]
) -> None:
    # Given the layout `make security` scans, with the same new code in both helper directories
    for directory in ("src", "examples", "scripts", "tools"):
        (tmp_path / directory).mkdir()
        (tmp_path / directory / "ok.py").write_text("x = 1\n", encoding="utf-8")
    for directory in ("scripts", "tools"):
        (tmp_path / directory / "new_helper.py").write_text(helper_source, encoding="utf-8")
    shutil.copy(_ROOT / "Makefile", tmp_path / "Makefile")
    shutil.copy(_ROOT / "scripts" / "check_bandit_report.py", tmp_path / "scripts")
    hatch = tmp_path / "hatch"  # `$(HATCH) run python ...` runs this interpreter, which has Bandit
    hatch.write_text(f'#!/bin/sh\nshift 2\nexec {shlex.quote(sys.executable)} "$@"\n')
    hatch.chmod(0o755)
    environment = {k: v for k, v in os.environ.items() if not k.startswith(("MAKE", "MFLAGS"))}

    # When the real recipe runs (`true` stands in for pip, so nothing is installed)
    result = subprocess.run(
        ["make", "security", f"HATCH={hatch}", "PIP=true", f"VENV_DIR={tmp_path}"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    # Then it fails exactly when the new code is unreviewed, naming the test in each helper file
    reported = set(re.findall(r"^bandit: (\S+?):\d+ (B\d+) ", result.stderr, re.MULTILINE))
    expected = {(f"{d}/new_helper.py", t) for d in ("scripts", "tools") for t in failing_tests}
    assert (result.returncode != 0) == bool(failing_tests), result.stderr
    assert expected <= reported, result.stderr
