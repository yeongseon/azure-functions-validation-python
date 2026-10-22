"""Non-mutating schema-pin and metadata-contract checks."""

from __future__ import annotations

import hashlib
from pathlib import Path


def schema_hash(root: Path) -> int:
    directory = root / "src/azure_functions_validation/schemas"
    expected = (directory / "endpoint.schema.sha256").read_text().split()[0]
    actual = hashlib.sha256((directory / "endpoint.schema.json").read_bytes()).hexdigest()
    if actual != expected:
        print(f"endpoint.schema.json digest drift: pinned={expected} actual={actual}")
        return 1
    print("endpoint.schema.json digest matches pin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(schema_hash(Path.cwd()))
