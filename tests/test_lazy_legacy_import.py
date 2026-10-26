import subprocess
import sys


def test_v2_decoration_does_not_import_legacy_pydantic() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from pydantic import BaseModel; "
            "from azure_functions_validation import validate_http; "
            "Model = type('Model', (BaseModel,), {'__annotations__': {'name': str}}); "
            "validate_http(body=Model)(lambda req, body: body); "
            "assert 'pydantic.v1' not in sys.modules",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
