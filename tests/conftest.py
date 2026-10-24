"""Shared pytest fixtures for the azure-functions-validation test suite.

Fixtures declared here are auto-discovered by pytest and available to every
test module without re-declaration, matching the convention used by sibling
DX Toolkit repositories (langgraph, durable-graph, db).

It also holds the guards that stop a required opt-in lane from going green by
running nothing (#580): the dedicated ``-m compat2x`` selector requires
``AZFUNC_2X_SPIKE=1``, and ``FAIL_ON_SKIP=1`` makes any skip or xfail fail the run.
"""

from __future__ import annotations

from collections.abc import Callable
import os
from unittest.mock import Mock

from azure.functions import HttpRequest
import pytest


@pytest.fixture
def mock_request_factory() -> Callable[..., HttpRequest]:
    """Return a factory that builds mock ``HttpRequest`` objects.

    The factory accepts the request attributes exercised by the pipeline
    (method, url, body, params, route_params, headers) and returns a
    ``Mock`` spec'd against ``HttpRequest`` so attribute access is validated.
    """

    def _create_request(
        method: str = "GET",
        url: str = "http://example.com",
        body: bytes = b"",
        params: dict[str, str] | None = None,
        route_params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> HttpRequest:
        mock_req = Mock(spec=HttpRequest)
        mock_req.method = method
        mock_req.url = url
        mock_req.get_body.return_value = body
        mock_req.params = params or {}
        mock_req.route_params = route_params or {}
        mock_req.headers = headers or {}

        return mock_req

    return _create_request


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Refuse the dedicated ``-m compat2x`` selector unless the spike is enabled.

    The spike module skips itself without ``AZFUNC_2X_SPIKE=1``, so the SDK 2.x lane
    would report ``6 skipped`` and exit 0 (#580). Modeled on ``tests/e2e/conftest.py``.
    """
    if config.option.collectonly:
        return
    if (config.option.markexpr or "").strip() != "compat2x":
        return
    if not any(item.get_closest_marker("compat2x") for item in items):
        return  # no spike test collected: pytest itself exits 5
    if os.environ.get("AZFUNC_2X_SPIKE") == "1":
        return
    pytest.exit(
        "AZFUNC_2X_SPIKE=1 is required to run the SDK 2.x spike with the dedicated "
        "'-m compat2x' selector. Without it every spike test skips itself and the run "
        "exits 0, indistinguishable from a passing compatibility check (#580).",
        returncode=1,
    )


class _FailOnSkip:
    """Opt-in (``FAIL_ON_SKIP=1``): any skipped, xfailed or xpassed test fails the session.

    Covers skips raised in setup, call or teardown and module-level skips at collection
    (``importorskip``). A run that selects no tests keeps pytest's exit code 5.
    """

    def __init__(self) -> None:
        self.found: list[str] = []

    def _note(self, report: pytest.TestReport | pytest.CollectReport) -> None:
        if report.skipped or hasattr(report, "wasxfail"):
            longrepr = report.longrepr
            reason = longrepr[2] if isinstance(longrepr, tuple) else getattr(report, "wasxfail", "")
            self.found.append(f"{report.nodeid} ({report.when}): {reason}")

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        self._note(report)

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        self._note(report)

    def pytest_terminal_summary(self, terminalreporter: pytest.TerminalReporter) -> None:
        if self.found:
            terminalreporter.section("FAIL_ON_SKIP=1: skipped or xfailed tests", red=True)
            for line in self.found:
                terminalreporter.write_line(line)

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        if self.found and exitstatus in (pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED):
            session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_configure(config: pytest.Config) -> None:
    if os.environ.get("FAIL_ON_SKIP") == "1" and not config.option.collectonly:
        config.pluginmanager.register(_FailOnSkip(), "fail-on-skip")
