from __future__ import annotations

import hashlib
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.check_wheel_schemas import main

SCHEMA_PATH = "azure_functions_validation/schemas/endpoint.schema.json"
PIN_PATH = "azure_functions_validation/schemas/endpoint.schema.sha256"
SCHEMA_BYTES = b'{"type":"object"}\n'


def _write_wheel(
    path: Path,
    *,
    include_schema: bool = True,
    include_pin: bool = True,
    pinned_digest: str | None = None,
) -> Path:
    with ZipFile(path, "w") as archive:
        if include_schema:
            archive.writestr(SCHEMA_PATH, SCHEMA_BYTES)
        if include_pin:
            digest = pinned_digest or hashlib.sha256(SCHEMA_BYTES).hexdigest()
            archive.writestr(PIN_PATH, f"{digest}  endpoint.schema.json\n")
    return path


def test_valid_wheel_passes(tmp_path: Path) -> None:
    # Given a wheel containing both resources with a pin for the packaged bytes
    wheel = _write_wheel(tmp_path / "valid.whl")

    # When the wheel is checked
    result = main([str(wheel)])

    # Then the checker accepts it
    assert result == 0


@pytest.mark.parametrize(
    ("include_schema", "include_pin"),
    [(False, True), (True, False)],
    ids=["schema", "pin"],
)
def test_omitting_either_resource_fails(
    tmp_path: Path, *, include_schema: bool, include_pin: bool
) -> None:
    # Given a wheel that omits one required endpoint schema resource
    wheel = _write_wheel(
        tmp_path / "missing.whl",
        include_schema=include_schema,
        include_pin=include_pin,
    )

    # When the wheel is checked
    result = main([str(wheel)])

    # Then the checker rejects the incomplete package
    assert result != 0


def test_digest_mismatch_fails(tmp_path: Path) -> None:
    # Given a wheel whose packaged pin does not match its packaged schema bytes
    wheel = _write_wheel(tmp_path / "mismatch.whl", pinned_digest="0" * 64)

    # When the wheel is checked
    result = main([str(wheel)])

    # Then the checker rejects the drift
    assert result != 0
