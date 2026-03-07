from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from typing import Any

import azure.functions as func

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_example_module(example_name: str) -> Any:
    module_path = REPO_ROOT / "examples" / example_name / "function_app.py"
    spec = spec_from_file_location(f"validation_demo_{example_name}", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load example module from {module_path}")

    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _format_response(response: func.HttpResponse) -> str:
    body = response.get_body().decode("utf-8")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body

    if isinstance(payload, dict) and isinstance(payload.get("detail"), list) and payload["detail"]:
        first_error = payload["detail"][0]
        if isinstance(first_error, dict):
            payload = {
                "detail": [
                    {
                        "loc": first_error.get("loc"),
                        "msg": first_error.get("msg"),
                        "type": first_error.get("type"),
                    }
                ]
            }

    return json.dumps(payload, separators=(",", ": "))


def _print_case(title: str, request_line: str, response: func.HttpResponse) -> None:
    print(title)
    print(request_line)
    print(f"Status: {response.status_code}")
    print("Body:")
    print(_format_response(response))
    print()


def main() -> None:
    hello_module = _load_example_module("hello_validation")
    success_request = func.HttpRequest(
        method="POST",
        url="/api/hello_validation",
        body=json.dumps({"name": "Azure"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    success_response = hello_module.hello_validation(success_request)
    _print_case(
        "Validated success response",
        'POST /api/hello_validation {"name":"Azure"}',
        success_response,
    )

    invalid_request = func.HttpRequest(
        method="POST",
        url="/api/hello_validation",
        body=json.dumps({}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    invalid_response = hello_module.hello_validation(invalid_request)
    _print_case(
        "Structured validation error",
        "POST /api/hello_validation {}",
        invalid_response,
    )


if __name__ == "__main__":
    main()
