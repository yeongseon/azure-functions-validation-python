import json
from pathlib import Path
from typing import Any

import pytest

from scripts.check_runtime_audit import check_report


@pytest.mark.parametrize(
    ("report", "status", "expected"),
    [
        ({"dependencies": [{"name": "dep", "vulns": []}]}, 0, 0),
        ({"dependencies": [{"name": "dep", "vulns": [{"id": "CVE-test"}]}]}, 1, 1),
        ({"dependencies": []}, 0, 2),
        ({"dependencies": [None]}, 0, 2),
        ({"dependencies": [{"name": "dep", "skip_reason": "unknown"}]}, 0, 2),
        ({"dependencies": [{"name": "dep", "vulns": []}]}, 1, 2),
        ({"dependencies": [{"name": "dep", "vulns": []}]}, 2, 2),
    ],
)
def test_audit_report_distinguishes_advisories_from_tool_errors(
    tmp_path: Path, report: dict[str, Any], status: int, expected: int
) -> None:
    path = tmp_path / "audit.json"
    path.write_text(json.dumps(report))
    assert check_report(path, status) == expected


def test_missing_and_unparsable_audit_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"
    assert check_report(path, 0) == 2
    path.write_text("not JSON")
    assert check_report(path, 0) == 2
