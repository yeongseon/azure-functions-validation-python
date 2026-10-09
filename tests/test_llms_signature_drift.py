from __future__ import annotations

import inspect
from pathlib import Path
import re

from azure_functions_validation import validate_http

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_llms_full_validate_http_parameters_match_public_signature() -> None:
    # Given the documented validate_http signature
    reference = (PROJECT_ROOT / "llms-full.txt").read_text(encoding="utf-8")
    signature_block = re.search(
        r"^def validate_http\(\n(?P<parameters>.*?)^\) ->",
        reference,
        flags=re.DOTALL | re.MULTILINE,
    )
    assert signature_block is not None, "llms-full.txt must document validate_http"

    # When its keyword-only parameter names are parsed
    documented = set(
        re.findall(r"^    ([a-z_][a-z0-9_]*):", signature_block["parameters"], re.MULTILINE)
    )
    public = {
        name
        for name, parameter in inspect.signature(validate_http).parameters.items()
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY
    }

    # Then the reference exposes every and only public keyword-only option
    assert documented == public, (
        "llms-full.txt validate_http parameters drifted from the public signature: "
        f"missing={sorted(public - documented)}, extra={sorted(documented - public)}"
    )
