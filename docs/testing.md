# Testing

This guide describes the test suite for `azure-functions-validation`, including how to run tests, the structure of the test suite, and guidelines for contributing new tests.

## Testing your handlers with `MockHttpRequest`

The package ships a public test helper, `MockHttpRequest`, so you can unit-test
validated handlers without deploying or running the Functions host. It is a real
`azure.functions.HttpRequest` subclass, so it drives the genuine `@validate_http`
pipeline end-to-end.

```python
from azure_functions_validation import validate_http
from azure_functions_validation.testing import MockHttpRequest
from pydantic import BaseModel


class CreateUserRequest(BaseModel):
    name: str
    email: str


class CreateUserResponse(BaseModel):
    message: str


@validate_http(body=CreateUserRequest, response_model=CreateUserResponse)
def create_user(req, body: CreateUserRequest) -> CreateUserResponse:
    return CreateUserResponse(message=f"Hello {body.name}")


def test_create_user_ok():
    request = MockHttpRequest(
        method="POST",
        json={"name": "Alice", "email": "alice@example.com"},
    )
    response = create_user(request)
    assert response.status_code == 200
    assert b"Hello Alice" in response.get_body()


def test_create_user_missing_field_returns_422():
    request = MockHttpRequest(method="POST", json={"name": "Alice"})
    response = create_user(request)
    assert response.status_code == 422
```

A copyable, tested version covering a JSON body, query arguments and headers is the
[MockHttpRequest recipe](examples/mock_request_testing.md).

### Constructor options

| Argument | Purpose |
| :--- | :--- |
| `method` | HTTP method (default `"GET"`). |
| `url` | Request URL (default a local test URL). |
| `json` | JSON-serializable value encoded as the body; sets `Content-Type: application/json` unless already provided. Mutually exclusive with `body`. |
| `body` | Raw `bytes` or `str` body (a `str` is UTF-8 encoded). Mutually exclusive with `json`. |
| `params` | Query-string parameters. |
| `route_params` | Route (path) parameters. |
| `headers` | Request headers. |

Passing both `body` and `json` raises `ValueError`.


## Overview

The `azure-functions-validation` project maintains a high standard of quality through a comprehensive test suite. The suite ensures that request validation, response serialization, and decorator behavior work correctly across different Python versions and Azure Functions scenarios.

- **Coverage gate**: `fail_under = 95` in `pyproject.toml`; committed changes and pull requests must maintain at least 95% coverage under `AGENTS.md`.
- **Current coverage**: See the CI coverage report or the Codecov badge in the project README rather than a hard-coded measurement.
- **Supported Environments**: Python 3.11, 3.12, 3.13, and 3.14

The test suite covers unit tests for individual modules, integration tests with real Azure Function handlers, and smoke tests using the provided examples.

## Running Tests

The project uses `pytest` as its primary testing framework. You can run the tests using `make` targets or directly via `hatch`.

### Using Makefile

The simplest way to run tests is using the provided `Makefile` targets:

```bash
# Run all tests
make test

# Run tests and generate a coverage report
make cov
```

The `make cov` command generates a terminal report, an XML report for CI integration, and a detailed HTML report in the `htmlcov/` directory.

### Direct Commands

If you prefer to run commands manually via `hatch`:

```bash
# Run all tests with verbose output
hatch run test

# Run tests with coverage
hatch run cov
```

To pass specific arguments to `pytest` (e.g., to run a single test file):

```bash
hatch run pytest tests/test_pipeline.py
```

## Test Structure

Tests live in `tests/`. Rather than enumerating every file (the list changes often and goes stale),
this map lists the test *levels* and the directories or representative files that implement each one.
Every path below is checked against the working tree by `tests/test_testing_docs.py`.

| Level | Location | What it proves | Runs by default |
| :--- | :--- | :--- | :--- |
| Unit | `tests/test_decorator.py`, `tests/test_pipeline.py`, `tests/test_errors.py`, `tests/test_adapter.py`, `tests/test_public_api.py` | Decorator configuration errors, pipeline parsing/validation/response building, error formatting, adapter behavior, and the public export surface, using in-process request objects. | Yes (`make test`) |
| Offline integration | `tests/test_integration.py`, `tests/test_testing.py`, `tests/test_e2e_app.py`, `tests/test_examples.py` | Real decorated handlers (including the Azure E2E app handlers and the `examples/` snippets) driven in-process with request doubles. No Functions host and no network. | Yes |
| Functions host smoke | `tests/host_smoke/` | A real Azure Functions host (Core Tools) running the built wheel; run with `make host-candidate` (see [candidate-host.md](candidate-host.md)). | No (needs Core Tools) |
| Real Azure E2E | `tests/e2e/` | The deployed example app on Azure, selected with `-m e2e` and `E2E_BASE_URL`. | No (opt-in) |

`tests/_test_app/` contains a sample Azure Functions application used by the offline tests.

These levels are **not equivalent evidence**. Offline mocks prove the library's logic against request
doubles; they cannot prove worker, host, or binding behavior. The host smoke lane proves behavior on a real
local Functions host, but not Azure hosting. Only the real Azure E2E lane exercises a deployed Function
App. A passing offline run is not host or Azure verification, and a local host smoke run is not Azure
certification.

## Test Organization

Tests are generally organized into classes to group related functionality and share logic. Common patterns include:

- `TestSuccessfulValidation`: Verifies that valid requests result in successful processing and correct responses.
- `TestValidationErrors`: Verifies that invalid input (body, query, path, headers) results in the expected 422 Unprocessable Entity responses.
- `TestAsyncHandlers`: Ensures that both synchronous and asynchronous Azure Function handlers are supported correctly.
- `TestCustomErrorFormatter`: Validates that users can override the default error response format.
- `TestConfigurationErrors`: Checks that improper use of the decorator (e.g., conflicting parameters) is caught at decoration time.

## Request test doubles

There are two kinds of request double. Only one is public API.

### `MockHttpRequest` (public, for consumers)

`azure_functions_validation.testing.MockHttpRequest` is the supported helper for testing your own
handlers; see the first section of this guide. Use it in consumer test suites and in new tests in this
repository that need a realistic request.

### `mock_request_factory` (internal fixture)

`mock_request_factory` is an internal pytest fixture defined in `tests/conftest.py`, so it is available to
every test module in this repository without an import. It is **not** public API and is not available to
consumers of the package. It returns a `unittest.mock.Mock` spec'd against `azure.functions.HttpRequest`
with `method`, `url`, `params`, `route_params`, and `headers` set, and `get_body()` returning the given
bytes. Because it is a mock, `get_json()` is **not** wired to the body; the pipeline reads
`get_body()`.

```python
def test_example(mock_request_factory):
    request = mock_request_factory(
        method="POST",
        body=b'{"name": "Alice"}',
        params={"debug": "true"},
    )
    # Use the mock request in your test
```

`tests/test_integration.py` also defines its own local `MockHttpRequest` class. It is a test-local helper
that shares a name with, but is unrelated to, the public `azure_functions_validation.testing.MockHttpRequest`.

## Writing New Tests

When contributing new features or fixing bugs, please follow these guidelines:

1. **Location**: Place unit tests in the file corresponding to the module being tested. If it's a new functional area, create a new `test_*.py` file.
2. **Naming**: Use descriptive names for test functions, starting with `test_`. Use class-based grouping for related tests.
3. **Mocking**: For low-level pipeline tests in this repository, the internal `mock_request_factory` fixture is fine. When a realistic `HttpRequest` is needed, prefer the public `MockHttpRequest`.
4. **Async**: If testing async functionality, mark the test with `@pytest.mark.anyio`.

Example of a new test:

```python
@pytest.mark.anyio
async def test_my_new_feature(mock_request_factory):
    @validate_http(body=MyModel)
    async def handler(req, body):
        return {"result": body.value}

    request = mock_request_factory(body=b'{"value": 42}')
    response = await handler(request)
    assert response.status_code == 200
```

## Coverage Configuration

Coverage settings are defined in `pyproject.toml`. The project tracks branch coverage to ensure all logical paths are exercised.

- **Source**: `src/azure_functions_validation`
- **Reports**: Terminal (missing lines), XML (for CI), and HTML.
- **Branch Coverage**: Enabled (`branch = true`).

You can view the coverage configuration under the `[tool.coverage.run]` and `[tool.coverage.report]` sections of `pyproject.toml`.

## CI Test Matrix

The test suite runs automatically on every pull request and push to the main branch. The CI matrix ensures compatibility across:

- **OS**: `ubuntu-latest`
- **Python Versions**: 3.11, 3.12, 3.13, 3.14

This is managed via the `.github/workflows/ci-test.yml` configuration.

The artifact gate builds the source distribution first and then builds the wheel from that sdist,
matching the release path. It runs `scripts/check_wheel_schemas.py --install-smoke` against the wheel
to require both endpoint schema resources, verify their SHA-256 pin, and load them from an isolated
installation outside the checkout.

## Troubleshooting

### Common Test Failures

- **PYTHONPATH Issues**: If tests cannot find the `src` or `examples` modules, ensure your environment is set up correctly. Running via `hatch run test` or `make test` handles this automatically via the `pythonpath` setting in `pyproject.toml`.
- **Pydantic Version**: The project supports Pydantic v2. Tests may fail if an older version of Pydantic is installed.
- **Async Setup**: Ensure `pytest-anyio` is installed and tests are correctly marked with `@pytest.mark.anyio`.
- **Missing Dependencies**: If you see import errors for `azure.functions`, ensure you have installed the development dependencies using `pip install -e .[dev]`.

## Real Azure E2E Tests

The project includes a real Azure end-to-end test workflow that deploys an actual Function App to Azure and validates HTTP endpoints.

### Workflow

- **File**: `.github/workflows/e2e-azure.yml`
- **Trigger**: `workflow_call` from `publish-pypi.yml` (certification gates every release, so it always covers the exact commit being published) or manual (`workflow_dispatch`)
- **Package under test**: the wheel built from the commit under test, pre-installed into `examples/e2e_app/.python_packages/lib/site-packages` and published with `--no-build`. `examples/e2e_app/requirements.txt` is not resolved during certification.
- **Infrastructure**: classic Linux Consumption plan (`Y1`/Dynamic, see `infra/main.bicep`), `koreacentral` region. Linux Consumption retires 30 September 2028; migrating this harness to [Flex Consumption](https://learn.microsoft.com/azure/azure-functions/flex-consumption-plan) is tracked separately.
- **Cleanup**: Resource group deleted immediately after tests (`if: always()`)

### Running E2E Tests

```bash
gh workflow run e2e-azure.yml --ref main
```

Optional inputs: `-f ref=<branch|tag|sha>` to certify a specific commit and
`-f version=<X.Y.Z>` to assert the expected package version (the run fails if it
does not match `__version__` in the source).

Without `E2E_BASE_URL`, the real-Azure modules are still collected but skipped.
`tests/test_e2e_app.py` invokes the same deployed handlers through the real
`@validate_http` decorator and `MockHttpRequest`, so their status codes and response
bodies are verified locally before Azure certification.

### Deployed Coverage

The temporary app verifies the worker-sensitive pipeline branches that unit tests
cannot prove on a deployed host:

- body validation, malformed JSON (`400`), and source-prefixed query/path/header
  validation errors (`422`);
- synchronous and asynchronous validated handlers;
- response-model enforcement with a sanitized `500` body;
- dataclass, list-model, and `None`/`204` serialization;
- sanitized fallback when a custom `error_formatter` raises;
- configured `201` success and controlled `HttpError(404)` responses;
- Azure `Context` binding passthrough alongside `@validate_http`.

This coverage is intentionally representative rather than a duplicate of the unit
suite. The `azure-e2e` job remains a required dependency of the PyPI publish job in
`.github/workflows/publish-pypi.yml`.

### Required Secrets & Variables

The `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and `AZURE_SUBSCRIPTION_ID` secrets are expected in the `azure-e2e` GitHub Environment used by `deploy_and_test` and `cleanup`. `AZURE_LOCATION` is read from the `vars` context with a fallback to `koreacentral`.

| Name | Type | Description |
| --- | --- | --- |
| `AZURE_CLIENT_ID` | Secret | App Registration Client ID (OIDC) |
| `AZURE_TENANT_ID` | Secret | Azure Tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Secret | Azure Subscription ID |
| `AZURE_LOCATION` | Variable | Azure region (default: `koreacentral`) |

### Federated Credential (OIDC) Setup

Azure login uses [GitHub OIDC](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect) to exchange a short-lived token with the Azure AD app registration referenced by `AZURE_CLIENT_ID`. The app registration must have a federated credential whose **subject claim matches exactly** the value GitHub presents.

For this workflow, the expected subject is:

```text
repo:yeongseon/azure-functions-validation-python:environment:azure-e2e
```

The subject is composed of `repo:<owner>/<repo>:environment:<environment_name>`, where:

- `<owner>/<repo>` is the GitHub repository slug (`github.repository`). Not the PyPI package name (`azure-functions-validation`) or the Python import name (`azure_functions_validation`).
- `<environment_name>` is the GitHub Environment declared on the workflow jobs (`environment: azure-e2e` in `e2e-azure.yml`).

The match is **case-sensitive** and exact. Renaming the GitHub owner, repository, or environment requires updating the federated credential in Azure to match the new subject; otherwise Azure login fails with `AADSTS700213`.

Reference:

- Workflow declares `environment: azure-e2e` on both `deploy_and_test` and `cleanup` jobs in `.github/workflows/e2e-azure.yml`.
- Azure docs: [Configure a federated identity credential on an app](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-create-trust?pivots=identity-wif-apps-methods-azp).

### Troubleshooting

#### `AADSTS700213: No matching federated identity record found`

This means the OIDC subject GitHub presented does not match any federated credential on the Azure AD app registration behind `AZURE_CLIENT_ID`. Typical causes:

1. The repository was renamed (for example, the toolkit-wide `-python` suffix migration) and the federated credential still references the old subject.
2. The `environment:` value on the workflow job changed and the federated credential references the old environment name.
3. A different app registration is configured in the `azure-e2e` environment secrets than the one carrying the federated credential.

To recover:

1. Confirm which Azure AD app registration is referenced by the `AZURE_CLIENT_ID` value stored in the `azure-e2e` GitHub Environment.
2. On that app registration, add or update a federated credential with subject `repo:yeongseon/azure-functions-validation-python:environment:azure-e2e`, issuer `https://token.actions.githubusercontent.com`, and audience `api://AzureADTokenExchange`.
3. Re-run `e2e-azure` (tag push or `workflow_dispatch`) and confirm the `Azure login (OIDC)` step succeeds.

### Test Report

HTML test report is uploaded as a GitHub Actions artifact (retained 30 days).
