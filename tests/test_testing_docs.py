"""Keep literal test paths and fixture claims in ``docs/testing.md`` honest (#647)."""

from __future__ import annotations

from pathlib import Path
import re

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_GUIDE = _ROOT / "docs" / "testing.md"
_TEXT = _GUIDE.read_text(encoding="utf-8")
_PATH_RE = re.compile(r"`((?:tests|examples|scripts|tools)/[A-Za-z0-9_./-]*)`")
# Build-time output directories (created by the Azure E2E workflow) are not in the tree.
_GENERATED = (".python_packages",)
_PATHS = sorted(p for p in set(_PATH_RE.findall(_TEXT)) if not any(g in p for g in _GENERATED))


def test_guide_documents_some_paths() -> None:
    assert _PATHS, "docs/testing.md no longer lists any literal repository paths"


@pytest.mark.parametrize("path", _PATHS)
def test_documented_path_exists(path: str) -> None:
    assert (_ROOT / path).exists(), f"docs/testing.md references missing path {path}"


def test_documented_mock_request_factory_fixture_is_defined_in_conftest() -> None:
    conftest = (_ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert "def mock_request_factory(" in conftest
    assert "`mock_request_factory`" in _TEXT
    assert "tests/conftest.py" in _TEXT
    assert "tests/test_pipeline.py`, this fixture" not in _TEXT
