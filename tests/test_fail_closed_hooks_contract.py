"""Regression tests for the fail-closed hooks in ``tests/conftest.py`` (#580).

The workflow contract only checks that the SDK 2.x lane sets its variables and a passing spike
never reaches the failure paths, so deleting either hook would leave every other check green.
Each case runs pytest in a subprocess on a throwaway module beside a verbatim copy of the real
``conftest.py``, like ``test_e2e_marker_entrypoint_contract.py``.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

_HOOK = "FAIL_ON_SKIP=1: skipped or xfailed tests"

# Test modules; the helper prepends ``import os, pytest``. _SPIKE has the real spike's self-skip
# gate, so without the guard ``-m compat2x`` would report "1 skipped" and exit 0.
_SPIKE = (
    "pytestmark = [pytest.mark.compat2x,\n"
    "    pytest.mark.skipif(os.environ.get('AZFUNC_2X_SPIKE') != '1', reason='x')]\n"
    "def test_spike(): pass\n"
)
_PASS = "def test_it(): pass\n"
_SKIP = "def test_it(): pytest.skip('x')\n"
_XFAIL = "@pytest.mark.xfail\ndef test_it(): assert False\n"
_XPASS = "@pytest.mark.xfail\ndef test_it(): pass\n"
_TEARDOWN_SKIP = "def test_it(request): request.addfinalizer(lambda: pytest.skip('x'))\n"
_IMPORTORSKIP = "pytest.importorskip('no_such_xyz')\ndef test_it(): pass\n"

# id: (module, command line, expected exit code, expected output fragment)
_CASES = {
    "opt-in": (_SPIKE, "AZFUNC_2X_SPIKE=1 -m compat2x", 0, "1 passed"),
    "lane-env": (_SPIKE, "AZFUNC_2X_SPIKE=1 FAIL_ON_SKIP=1 -m compat2x", 0, "1 passed"),
    "no-spike-selected": (_PASS, "-m compat2x", 5, "1 deselected"),
    "collect-only": (_SPIKE, "-m compat2x --collect-only", 0, "1 test collected"),
    "fail-on-skip-setup-skip": (_SPIKE, "FAIL_ON_SKIP=1", 1, _HOOK),
    "fail-on-skip-call-skip": (_SKIP, "FAIL_ON_SKIP=1", 1, _HOOK),
    "fail-on-skip-xfail": (_XFAIL, "FAIL_ON_SKIP=1", 1, _HOOK),
    "fail-on-skip-xpass": (_XPASS, "FAIL_ON_SKIP=1", 1, _HOOK),
    "fail-on-skip-teardown-skip": (_TEARDOWN_SKIP, "FAIL_ON_SKIP=1", 1, _HOOK),
    "fail-on-skip-importorskip": (_IMPORTORSKIP, "FAIL_ON_SKIP=1", 1, _HOOK),
    "fail-on-skip-unset": (_SPIKE, "", 0, "1 skipped"),
    "fail-on-skip-0": (_SPIKE, "FAIL_ON_SKIP=0", 0, "1 skipped"),
    "fail-on-skip-true": (_SPIKE, "FAIL_ON_SKIP=true", 0, "1 skipped"),
    "fail-on-skip-nothing-selected": (_SPIKE, "FAIL_ON_SKIP=1 -m nonexistent", 5, "1 deselected"),
    "fail-on-skip-collect-only": (_IMPORTORSKIP, "FAIL_ON_SKIP=1 --collect-only", 5, "no tests"),
}


def _run_pytest(tmp_path: Path, source: str, cmdline: str) -> subprocess.CompletedProcess[str]:
    """Run pytest on ``source``; ``VAR=value`` words set the environment, the rest are options."""
    (tmp_path / "test_sandbox.py").write_text("import os, pytest\n" + source, encoding="utf-8")
    (tmp_path / "pytest.ini").write_text("[pytest]\nmarkers = compat2x\n", encoding="utf-8")
    shutil.copy(Path(__file__).with_name("conftest.py"), tmp_path)  # the real hook code, verbatim
    words = cmdline.split()
    env = {k: v for k, v in os.environ.items() if k not in {"AZFUNC_2X_SPIKE", "FAIL_ON_SKIP"}}
    env |= dict(w.split("=", 1) for w in words if "=" in w)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *(w for w in words if "=" not in w)],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=60,
    )


@pytest.mark.parametrize(
    "env",
    ["", "AZFUNC_2X_SPIKE=0", "AZFUNC_2X_SPIKE=true", "AZFUNC_2X_SPIKE="],
    ids=["unset", "0", "true", "empty"],
)
def test_selector_fails_instead_of_skipping_when_opt_in_is_unset_or_not_exactly_1(
    tmp_path: Path, env: str
) -> None:
    # Given a spike module that skips itself without the opt-in, When the dedicated selector runs it
    result = _run_pytest(tmp_path, _SPIKE, f"{env} -m compat2x")

    # Then it fails loudly -- "1 skipped" with exit 0 is the #580 defect
    assert result.returncode == 1, result.stdout
    assert "AZFUNC_2X_SPIKE=1 is required" in result.stdout
    assert "1 skipped" not in result.stdout


@pytest.mark.parametrize(("source", "cmdline", "code", "text"), _CASES.values(), ids=list(_CASES))
def test_hooks_keep_the_documented_exit_codes(
    tmp_path: Path, source: str, cmdline: str, code: int, text: str
) -> None:
    # Given a throwaway module under the real conftest, When pytest runs it with this env/selection
    result = _run_pytest(tmp_path, source, cmdline)

    # Then the hooks decide the exit code, and say why
    assert result.returncode == code, result.stdout
    assert text in result.stdout
