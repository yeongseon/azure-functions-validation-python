"""Exit 1 unless Bandit analysed every Python file in the scope and reported nothing.

Bandit exits 0 for an empty directory, a missing path and a file it cannot parse (it only
lists them as skipped), so its exit status alone can pass without analysing anything.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


def main(report: str, scopes: list[str]) -> int:
    try:
        data = json.loads(Path(report).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"bandit: cannot read {report}: {error}", file=sys.stderr)
        return 1
    scanned = {Path(name).as_posix() for name in data["metrics"]}
    loc = data["metrics"]["_totals"]["loc"]
    problems = ["no code was analysed"] if loc == 0 else []
    problems += [f"skipped {e['filename']}: {e['reason']}" for e in data["errors"]]
    problems += [
        f"not scanned: {path.as_posix()}"
        for scope in scopes
        for path in sorted(Path(scope).rglob("*.py"))
        if path.as_posix() not in scanned
    ]
    problems += [
        f"{r['filename']}:{r['line_number']} {r['test_id']} {r['issue_text']}"
        for r in data["results"]
    ]
    for problem in problems:
        print(f"bandit: {problem}", file=sys.stderr)
    if not problems:
        print(f"bandit: {' '.join(scopes)}: {loc} lines in {len(scanned) - 1} files, no findings")
    return 1 if problems else 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit("Usage: python scripts/check_bandit_report.py <report.json> <scope>...")
    raise SystemExit(main(sys.argv[1], sys.argv[2:]))
