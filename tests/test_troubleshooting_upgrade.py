"""Execute the offline repro in ``docs/troubleshooting.md`` so it cannot drift (#628)."""

from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import Any

import pytest

_DOC = Path(__file__).resolve().parents[1] / "docs" / "troubleshooting.md"
_TEXT = _DOC.read_text(encoding="utf-8")
_BLOCK = re.compile(r"# --- upgrade-repro ---\n(.*?)# --- end upgrade-repro ---", re.DOTALL)


def _run_repro() -> dict[str, Any]:
    match = _BLOCK.search(_TEXT)
    assert match is not None, "upgrade-repro block missing from docs/troubleshooting.md"
    namespace: dict[str, Any] = {"__name__": "upgrade_repro"}
    exec(compile(match.group(1), str(_DOC), "exec"), namespace)  # nosec B102 # repo-owned doc snippet
    return namespace


def test_documented_repro_statuses(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR):
        namespace = _run_repro()
    assert namespace["statuses"] == {
        "legacy": 500,
        "wrong_shape": 500,
        "override": 201,
        "bypass": 200,
    }


def test_documented_repro_log_distinguishes_failures(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR):
        _run_repro()
    causes = [type(record.exc_info[1]).__name__ for record in caplog.records if record.exc_info]
    assert causes == ["AttributeError", "AdapterValidationError"]


def test_documented_repro_override_headers_and_bypass() -> None:
    namespace = _run_repro()
    response = namespace["call"](namespace["override"])
    assert response.headers["Location"] == "/api/items/1"
    assert response.get_body() == b'{"message":"hi"}'
    assert namespace["call"](namespace["bypass"]).get_body() == b'{"msg": "not validated"}'


def test_legacy_adapter_lacks_serialize_response() -> None:
    namespace = _run_repro()
    with pytest.raises(AttributeError):
        namespace["LegacyAdapter"]().serialize_response


@pytest.mark.parametrize(
    "needle",
    [
        "adapters.md#method-contract",
        "adapters.md#run-the-conformance-suite",
        "releases/tag/v0.17.0",
        "release_history.md#v0170-unpublished-release-candidate",
        "usage.md#per-return-status-and-headers-without-bypassing-validation",
        "**not** validated",
    ],
)
def test_documented_links_and_claims_present(needle: str) -> None:
    assert needle in _TEXT


def test_documented_anchors_exist() -> None:
    root = _DOC.parent
    assert "## Run the conformance suite" in (root / "adapters.md").read_text(encoding="utf-8")
    assert "## Method contract" in (root / "adapters.md").read_text(encoding="utf-8")
    assert "### Per-return status and headers without bypassing validation" in (
        root / "usage.md"
    ).read_text(encoding="utf-8")
    assert "## v0.17.0: unpublished release candidate" in (root / "release_history.md").read_text(
        encoding="utf-8"
    )
