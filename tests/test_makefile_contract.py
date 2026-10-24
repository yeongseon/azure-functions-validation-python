"""Contract of the Makefile targets that set up and check a checkout (#581).

``make -n`` prints recipes without running them, so the expansion cases need no network, Hatch or
virtual environment. The behaviour cases run the real recipes in a scratch directory whose ``PATH``
holds only stub programs that log their arguments: nothing is installed, no network is used and no
real tool can run.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tomllib

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("make") is None,
    reason="runs the real Makefile recipes through /bin/sh",
)

_ROOT = Path(__file__).resolve().parents[1]
_MAKE = shutil.which("make") or "make"
_PYPROJECT = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
_DEFAULT_ENV = _PYPROJECT["tool"]["hatch"]["envs"]["default"]
HATCH_SCRIPTS: dict[str, str] = {name: str(cmd) for name, cmd in _DEFAULT_ENV["scripts"].items()}
HATCH_PYTHON = f"python{_DEFAULT_ENV['python']}"  # the interpreter `make doctor` must find
REQUIRED = ("hatch", HATCH_PYTHON, "git")
OPTIONAL = ("func", "azurite")
_INLINE_CHECKS = {  # the commands of `check` that `make -n` prints verbatim
    "schema hash": "endpoint.schema.json digest matches pin.",
    "release workflow lint": "tools/lint_release_workflows.py",
    "workflow pin lint": "tools/lint_workflow_pins.py",
    "hatch matrix lint": "tools/lint_hatch_matrix.py",
    "bandit": "-m bandit",
    "bandit report guard": "scripts/check_bandit_report.py",
}


def script_runs(commands: str, name: str) -> int:
    """Count the runs of Hatch script ``name``, following scripts that run other scripts.

    Hatch's ``lint`` script runs ``style`` and ``typecheck``, so a second type check can hide
    inside a target that ``make -n`` shows as one ``hatch run lint``.
    """
    called = re.findall(r"\bhatch run ([\w-]+)", commands)
    return sum((s == name) + script_runs(HATCH_SCRIPTS.get(s, ""), name) for s in called)


def check_runs(commands: str) -> dict[str, int]:
    """Count how often each static check appears in ``commands``."""
    runs = {name: commands.count(text) for name, text in _INLINE_CHECKS.items()}
    return runs | {name: script_runs(commands, name) for name in ("style", "typecheck")}


EVERY_CHECK_ONCE = dict.fromkeys(check_runs(""), 1)


def plan(*arguments: str) -> str:
    """Return the commands ``make -n`` prints for this repository's own Makefile."""
    result = subprocess.run(
        [_MAKE, "--no-print-directory", "-n", *arguments],
        cwd=_ROOT,
        env={"PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def installs_hatch(call: str) -> bool:
    words = call.split()
    return words[:2] == ["pip", "install"] and words[-1] == "hatch" and "--upgrade" not in words


@dataclass(frozen=True)
class Sandbox:
    """A scratch copy of the Makefile, run with ``PATH`` limited to logging stub programs."""

    root: Path

    @property
    def venv(self) -> Path:
        return self.root / "venv"

    @property
    def hatch(self) -> Path:
        return self.venv / "bin" / "hatch"

    @property
    def calls(self) -> list[str]:
        log = self.root / "calls.log"
        return log.read_text(encoding="utf-8").splitlines() if log.exists() else []

    def tool(self, name: str, directory: Path | None = None, body: str = "") -> Path:
        """Create a stub that logs ``<name> <arguments>`` and then runs ``body``."""
        path = (directory or self.root / "bin") / name
        path.parent.mkdir(parents=True, exist_ok=True)
        log = shlex.quote(str(self.root / "calls.log"))
        line = f'printf "%s\\n" "{name} $*" >> {log}\n'  # printf: `echo` would expand "\\n"
        path.write_text(f"#!/bin/sh\n{line}{body}exit 0\n", encoding="utf-8")
        path.chmod(0o755)
        return path

    def pip(self, directory: Path) -> None:
        """Add a ``pip`` whose ``install ... hatch`` puts a logging ``hatch`` beside it."""
        template = self.tool("hatch", self.root / "templates")  # `cp` keeps its executable bit
        install = f'for last; do :; done\n[ "$last" = hatch ] && cp {template} "${{0%/*}}/hatch"\n'
        self.tool("pip", directory, install)

    def interpreter(self, name: str) -> Path:
        """Add an interpreter whose ``-m venv DIR`` creates ``DIR`` holding that stub pip."""
        self.pip(self.root / "templates")
        pip = self.root / "templates" / "pip"
        make_venv = f'[ "$1 $2" = "-m venv" ] && mkdir -p "$3/bin" && cp {pip} "$3/bin/pip"\n'
        return self.tool(name, body=make_venv)

    def doctor_tools(self, missing: Iterable[str] = ()) -> None:
        """Provide every tool ``make doctor`` looks for except the ``missing`` ones."""
        for name in set(REQUIRED + OPTIONAL) - set(missing):
            self.tool(name, self.hatch.parent if name == "hatch" else None)

    def make(self, *arguments: str, **environment: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [_MAKE, "--no-print-directory", f"VENV_DIR={self.venv}", *arguments],
            cwd=self.root,
            env={"PATH": str(self.root / "bin"), **environment},
            capture_output=True,
            text=True,
            check=False,
        )


@pytest.fixture
def sandbox(tmp_path: Path) -> Sandbox:
    shutil.copy(_ROOT / "Makefile", tmp_path / "Makefile")
    (tmp_path / "bin").mkdir()
    for program in ("cp", "mkdir", "rm"):  # the only real programs the stubs and `clean` run
        (tmp_path / "bin" / program).symlink_to(shutil.which(program) or program)
    return Sandbox(tmp_path)


def test_check_runs_each_static_check_once_and_no_tests() -> None:
    commands = plan("check")

    assert check_runs(commands) == EVERY_CHECK_ONCE
    assert script_runs(commands, "test") == 0


def test_check_all_is_check_plus_the_tests() -> None:
    commands = plan("check-all")

    assert check_runs(commands) == EVERY_CHECK_ONCE
    assert script_runs(commands, "test") == 1


@pytest.mark.parametrize("target", ["check", "check-all", "test", "security"])
def test_routine_targets_never_upgrade_pip(target: str) -> None:
    assert "upgrade" not in plan(target)


def test_makefile_never_upgrades_pip() -> None:
    # Also covers `docs`: its recipe line contains $(MAKE), so `make -n` would run it for real.
    assert "--upgrade" not in (_ROOT / "Makefile").read_text(encoding="utf-8")


def test_bootstrap_runs_once_per_make_invocation() -> None:
    assert plan("check-all").count("-m venv") == 1


def test_the_selected_interpreter_builds_the_virtual_environment() -> None:
    assert "sentinel -m venv" in plan("test", "PYTHON=sentinel")
    assert "python3 -m venv" in plan("test")


def test_bootstrap_leaves_an_installed_hatch_alone(sandbox: Sandbox) -> None:
    sandbox.pip(sandbox.venv / "bin")
    sandbox.tool("hatch", sandbox.venv / "bin")

    result = sandbox.make("bootstrap")

    assert result.returncode == 0, result.stderr
    assert sandbox.calls == []


def test_bootstrap_installs_hatch_once_and_only_while_it_is_missing(sandbox: Sandbox) -> None:
    sandbox.pip(sandbox.venv / "bin")

    for _ in range(2):
        assert sandbox.make("bootstrap").returncode == 0

    (call,) = sandbox.calls  # one call across both runs
    assert installs_hatch(call)


def test_a_fresh_checkout_gets_one_venv_from_the_selected_interpreter(sandbox: Sandbox) -> None:
    python = sandbox.interpreter("sentinel")

    result = sandbox.make("check-all", f"PYTHON={python}")

    assert result.returncode == 0, result.stderr
    venv_call, pip_call, *hatch_calls = sandbox.calls
    assert venv_call == f"sentinel -m venv {sandbox.venv}"
    assert installs_hatch(pip_call)
    assert [call for call in hatch_calls if not call.startswith("hatch run")] == []
    assert hatch_calls.count("hatch run typecheck") == 1
    assert hatch_calls.count("hatch run test") == 1


@pytest.mark.parametrize("kind", ["directory", "non-executable file"])
def test_only_an_executable_regular_file_counts_as_hatch(sandbox: Sandbox, kind: str) -> None:
    sandbox.doctor_tools(missing={"hatch"})
    sandbox.pip(sandbox.venv / "bin")
    if kind == "directory":
        sandbox.hatch.mkdir()
    else:
        sandbox.hatch.write_text("#!/bin/sh\n", encoding="utf-8")  # created without the x bit

    doctor = sandbox.make("doctor")
    bootstrap = sandbox.make("bootstrap")

    assert doctor.returncode != 0
    assert f"MISSING  {sandbox.hatch} (required)" in doctor.stdout
    assert bootstrap.returncode == 0, bootstrap.stderr
    (call,) = sandbox.calls
    assert installs_hatch(call)


@pytest.mark.parametrize("absent", [(), OPTIONAL], ids=["all tools", "optional tools absent"])
def test_doctor_passes_when_every_required_tool_exists(
    sandbox: Sandbox, absent: tuple[str, ...]
) -> None:
    sandbox.doctor_tools(missing=absent)

    result = sandbox.make("doctor")

    assert result.returncode == 0, result.stdout
    assert "MISSING" not in result.stdout
    for tool in absent:
        assert f"missing  {tool} (optional" in result.stdout


@pytest.mark.parametrize("tool", REQUIRED)
def test_doctor_fails_when_a_required_tool_is_missing(sandbox: Sandbox, tool: str) -> None:
    sandbox.doctor_tools(missing={tool})

    result = sandbox.make("doctor")

    name = str(sandbox.hatch) if tool == "hatch" else tool
    assert result.returncode != 0
    assert f"MISSING  {name} (required)" in result.stdout
    assert result.stdout.count("MISSING  ") == 1


def test_doctor_neither_installs_nor_writes(sandbox: Sandbox) -> None:
    sandbox.pip(sandbox.venv / "bin")  # a stub pip and no Hatch: `bootstrap` would install here
    before = sorted(sandbox.root.rglob("*"))

    result = sandbox.make("doctor")

    assert result.returncode != 0
    assert sandbox.calls == []
    assert sorted(sandbox.root.rglob("*")) == before


@pytest.mark.parametrize(
    ("environment", "build"),
    [({}, "hatch run mkdocs build --strict"), ({"CI": "1"}, "mkdocs build --strict")],
    ids=["local", "ci"],
)
def test_docs_builds_strictly(sandbox: Sandbox, environment: dict[str, str], build: str) -> None:
    sandbox.tool("hatch", sandbox.venv / "bin")
    sandbox.tool("pip")
    sandbox.tool("mkdocs")

    result = sandbox.make("docs", **environment)

    assert result.returncode == 0, result.stderr
    assert build in sandbox.calls
    assert not [call for call in sandbox.calls if "--upgrade" in call]


@pytest.mark.parametrize("environment", [{}, {"CI": "1"}], ids=["local", "ci"])
def test_docs_fails_when_the_build_fails(sandbox: Sandbox, environment: dict[str, str]) -> None:
    sandbox.tool("hatch", sandbox.venv / "bin", "exit 1\n")
    sandbox.tool("pip")
    sandbox.tool("mkdocs", body="exit 1\n")

    assert sandbox.make("docs", **environment).returncode != 0


def test_docs_does_not_build_after_a_failed_dependency_install(sandbox: Sandbox) -> None:
    sandbox.tool("pip", body="exit 1\n")
    sandbox.tool("mkdocs")

    result = sandbox.make("docs", CI="1")

    assert result.returncode != 0
    assert "mkdocs build --strict" not in sandbox.calls


def test_clean_removes_the_test_results(sandbox: Sandbox) -> None:
    report = sandbox.root / "test-results" / "bandit" / "bandit.json"
    report.parent.mkdir(parents=True)
    report.write_text("{}", encoding="utf-8")
    source = sandbox.root / "keep.py"
    source.write_text("", encoding="utf-8")

    result = sandbox.make("clean")

    assert result.returncode == 0, result.stderr
    assert not report.parent.parent.exists()
    assert source.exists()
