"""Verified wheel identity and exact installed dependency inventory."""

from email.parser import BytesParser
from importlib.metadata import distributions
from pathlib import Path
import re
from zipfile import ZipFile

from tools.security_report import EvidenceError, identifier


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", identifier(name).lower())


def wheel_identity(path: Path) -> tuple[str, str]:
    with ZipFile(path) as wheel:
        metadata = [n for n in wheel.namelist() if n.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise EvidenceError("candidate wheel metadata missing or ambiguous")
        parsed = BytesParser().parsebytes(wheel.read(metadata[0]))
    return normalize(str(parsed["Name"])), identifier(str(parsed["Version"]))


def installed_inventory(site: Path, candidate: tuple[str, str]) -> dict[str, str]:
    inventory: dict[str, str] = {}
    for distribution in distributions(path=[str(site)]):
        name = normalize(distribution.metadata["Name"])
        resolved = identifier(distribution.version)
        if name in inventory:
            raise EvidenceError("duplicate installed distribution")
        inventory[name] = resolved
    name, expected = candidate
    if inventory.pop(normalize(name), None) != expected or not inventory:
        raise EvidenceError("candidate mismatch or empty third-party inventory")
    return inventory
