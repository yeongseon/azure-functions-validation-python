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

    return json.dumps(payload, indent=2)


def _print_case(title: str, request_line: str, response: func.HttpResponse) -> None:
    print(title)
    print(request_line)
    print(f"Status: {response.status_code}")
    print("Body:")
    print(_format_response(response))
    print()


def main() -> None:
    hello_module = _load_example_module("hello_validation")
    hello_request = func.HttpRequest(
        method="POST",
        url="/api/hello_validation",
        body=json.dumps({"name": "Azure"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    hello_response = hello_module.hello_validation(hello_request)
    _print_case(
        "Representative example",
        'POST /api/hello_validation {"name":"Azure"}',
        hello_response,
    )

    profile_module = _load_example_module("profile_validation")
    bad_request = func.HttpRequest(
        method="GET",
        url="/api/users/7",
        body=b"",
        params={},
        headers={},
        route_params={"user_id": "7"},
    )
    bad_response = profile_module.get_profile(bad_request)
    _print_case(
        "Validation error example",
        "GET /api/users/7  # missing x-request-id header",
        bad_response,
    )


if __name__ == "__main__":
    main()
