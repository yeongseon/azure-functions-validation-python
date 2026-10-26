from __future__ import annotations

import json
from pathlib import Path
import sys


def check_report(path: Path, status: int) -> int:
    try:
        report = json.loads(path.read_text())
        dependencies = report["dependencies"]
        if not dependencies or any("skip_reason" in item for item in dependencies):
            raise ValueError("incomplete runtime inventory")
        findings = any(item["vulns"] for item in dependencies)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        print("runtime audit tool error: missing, malformed or incomplete report", file=sys.stderr)
        return 2
    if status not in (0, 1) or (status == 1 and not findings):
        print("runtime audit tool error: scanner did not complete", file=sys.stderr)
        return 2
    if findings:
        print("runtime audit blocked: known runtime advisories", file=sys.stderr)
        return 1
    print(f"runtime audit clean: {len(dependencies)} dependencies")
    return 0


if __name__ == "__main__":
    raise SystemExit(check_report(Path(sys.argv[1]), int(sys.argv[2])))
