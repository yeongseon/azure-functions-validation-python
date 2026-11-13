# Testing a Validated Handler with MockHttpRequest

## Overview

A self-contained, copyable pytest recipe for a handler decorated with `@validate_http`,
driven by the public `azure_functions_validation.testing.MockHttpRequest`. It sends a JSON
body, query arguments and request headers to the **real** decorated handler (no mocked
pipeline) and checks one success and one validation failure. No Azure account, credentials,
network or Functions host is needed. For the full constructor reference and the repository's
test layout, see [Testing](../testing.md).

It is the file `tests/test_mock_request_recipe.py`; copy it into your own project as-is.

## Complete recipe

```python
"""Copyable pytest recipe: test a validated handler with ``MockHttpRequest`` (#634).

Self-contained: the handler and its tests live in one file and need only
``azure-functions-validation`` and ``pytest``. No Functions host, network or
Azure credentials are involved; the real ``@validate_http`` pipeline runs.
"""

import json

import azure.functions as func
from pydantic import BaseModel, ConfigDict, Field
import pytest

from azure_functions_validation import validate_http
from azure_functions_validation.testing import MockHttpRequest


class CreateOrder(BaseModel):
    sku: str = Field(min_length=3)


class OrderQuery(BaseModel):
    quantity: int = Field(default=1, ge=1)


class TenantHeaders(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    x_tenant_id: str = Field(alias="x-tenant-id")


class OrderOut(BaseModel):
    sku: str
    quantity: int
    tenant: str


@validate_http(
    body=CreateOrder,
    query=OrderQuery,
    headers=TenantHeaders,
    response_model=OrderOut,
)
def create_order(
    req: func.HttpRequest, body: CreateOrder, query: OrderQuery, headers: TenantHeaders
) -> OrderOut:
    return OrderOut(sku=body.sku, quantity=query.quantity, tenant=headers.x_tenant_id)


def test_success_with_json_body_query_and_headers() -> None:
    request = MockHttpRequest(
        method="POST",
        json={"sku": "abc"},
        params={"quantity": "3"},
        headers={"x-tenant-id": "t-1"},
    )

    response = create_order(request)

    assert response.status_code == 200
    assert json.loads(response.get_body()) == {"sku": "abc", "quantity": 3, "tenant": "t-1"}


def test_validation_failure_is_422_with_source_prefixed_loc() -> None:
    request = MockHttpRequest(
        method="POST",
        json={"sku": "a"},
        params={"quantity": "3"},
        headers={"x-tenant-id": "t-1"},
    )

    response = create_order(request)

    assert response.status_code == 422
    errors = json.loads(response.get_body())["detail"]
    assert [error["loc"] for error in errors] == [["body", "sku"]]


def test_json_argument_sets_content_type_automatically() -> None:
    assert MockHttpRequest(json={"a": 1}).headers["Content-Type"] == "application/json"


def test_explicit_content_type_is_preserved() -> None:
    request = MockHttpRequest(json={"a": 1}, headers={"Content-Type": "application/vnd.acme+json"})

    assert request.headers["Content-Type"] == "application/vnd.acme+json"


def test_body_argument_sends_raw_bytes_without_a_content_type() -> None:
    request = MockHttpRequest(method="POST", body='{"sku": "abc"}')

    assert request.get_body() == b'{"sku": "abc"}'
    assert "Content-Type" not in request.headers


def test_json_and_body_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError):
        MockHttpRequest(json={"a": 1}, body=b"{}")
```

## How `MockHttpRequest` builds the request

- **`json=`** encodes any JSON-serializable value as the body and adds
  `Content-Type: application/json` automatically, unless you pass a `Content-Type` header in
  any casing, in which case yours is kept untouched.
- **`body=`** sends raw `bytes` or `str` (UTF-8 encoded) and adds **no** `Content-Type`.
  Use it for malformed or non-JSON payloads.
- **`json=` and `body=` are mutually exclusive**: passing both raises `ValueError`.
  Note that `json=None` is a real value and encodes the body `null`.
- **`params=`** are query-string parameters, **`route_params=`** are path parameters and
  **`headers=`** are request headers; header models use the wire name (`x-tenant-id`).
- Because it subclasses `azure.functions.HttpRequest`, the genuine pipeline runs. Validation
  failures come back as a normal `422` response, never as a raised exception.

## Run it offline

From the repository root:

```bash
python -m pytest tests/test_mock_request_recipe.py -v --no-cov
```

`--no-cov` only skips this repository's 95% coverage gate, which one test file cannot meet;
in your own project you can omit it.
