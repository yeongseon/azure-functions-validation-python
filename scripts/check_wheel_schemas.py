"""Verify endpoint schema resources in a built wheel."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv
from zipfile import BadZipFile, ZipFile

SCHEMA_PATH = "azure_functions_validation/schemas/endpoint.schema.json"
PIN_PATH = "azure_functions_validation/schemas/endpoint.schema.sha256"


@dataclass(frozen=True, slots=True)
class WheelSchemaError(Exception):
    detail: str

    def __str__(self) -> str:
        return self.detail


def _verify_digest(schema_bytes: bytes, pin_bytes: bytes) -> None:
    tokens = pin_bytes.decode("utf-8").split()
    if not tokens:
        raise WheelSchemaError("endpoint schema pin is empty")
    expected = tokens[0]
    actual = hashlib.sha256(schema_bytes).hexdigest()
    if expected != actual:
        raise WheelSchemaError(
            f"endpoint schema digest mismatch:\n  pinned:  {expected}\n  actual:  {actual}"
        )


def verify_wheel(wheel: Path) -> None:
    try:
        with ZipFile(wheel) as archive:
            names = set(archive.namelist())
            missing = [path for path in (SCHEMA_PATH, PIN_PATH) if path not in names]
            if missing:
                raise WheelSchemaError(f"wheel is missing required resource: {', '.join(missing)}")
            _verify_digest(archive.read(SCHEMA_PATH), archive.read(PIN_PATH))
    except (BadZipFile, OSError) as error:
        raise WheelSchemaError(f"cannot read wheel {wheel}: {error}") from error


def _install_smoke(wheel: Path) -> None:
    smoke_code = """
from importlib import resources
import hashlib

package = resources.files("azure_functions_validation.schemas")
schema_bytes = package.joinpath("endpoint.schema.json").read_bytes()
pin = package.joinpath("endpoint.schema.sha256").read_text(encoding="utf-8").split()[0]
actual = hashlib.sha256(schema_bytes).hexdigest()
if pin != actual:
    raise SystemExit(f"installed endpoint schema digest mismatch: {pin} != {actual}")
print("Installed endpoint schema resources load and match their pin.")
"""
    with tempfile.TemporaryDirectory(prefix="wheel-schema-smoke-") as directory:
        root = Path(directory)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run([python, "-m", "pip", "install", str(wheel)], cwd=root, check=True)
        process_environment = os.environ.copy()
        process_environment.pop("PYTHONPATH", None)
        subprocess.run(
            [python, "-I", "-c", smoke_code],
            cwd=root,
            env=process_environment,
            check=True,
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Check the wheel selected by ``argv``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument(
        "--install-smoke",
        action="store_true",
        help="install the wheel in a temporary venv and load its schema resources",
    )
    arguments = parser.parse_args(argv)
    wheel = arguments.wheel.resolve()
    try:
        verify_wheel(wheel)
        if arguments.install_smoke:
            _install_smoke(wheel)
    except (WheelSchemaError, subprocess.CalledProcessError) as error:
        print(f"wheel schema check failed: {error}", file=sys.stderr)
        return 1
    print(f"Wheel endpoint schema resources verified: {wheel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
