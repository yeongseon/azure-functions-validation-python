# Query and Header Validation Errors

A minimal recipe for the **bad-input** side of `query=` and `headers=` validation.
It shows one accepted request and the predictable `422` error for each way a query
parameter or header can be wrong. No Azure account, credentials, or Functions host is needed.

| Request | Status | `detail[0]["loc"]` | `detail[0]["type"]` |
| --- | --- | --- | --- |
| `?limit=5` + `x-api-version: v1` | `200` | | |
| `?limit=abc` | `422` | `["query", "limit"]` | `int_parsing` |
| `?limit=0` | `422` | `["query", "limit"]` | `greater_than_equal` |
| missing `x-api-version` | `422` | `["headers", "x-api-version"]` | `missing` |
| `x-api-version: 1` | `422` | `["headers", "x-api-version"]` | `string_pattern_mismatch` |

The header `loc` uses the wire name (`x-api-version`), not the Python field name
(`x_api_version`). The tests assert only the status code, `loc`, and `type`; `msg` text
is Pydantic wording and is deliberately not asserted.

## Run it offline

From the repository root, after installing the development dependencies:

```bash
python -m pytest tests/test_query_header_errors_example.py -v --no-cov
```

(`--no-cov` only skips the repository-wide 95% coverage gate, which a single test file cannot meet.)

The test drives the real decorated handler with `azure_functions_validation.testing.MockHttpRequest`.
