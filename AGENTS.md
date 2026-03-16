# AGENTS.md

## Purpose
`azure-functions-validation` provides request and response validation for Azure Functions Python v2 applications using Pydantic.

## Read First
- `README.md`
- `CONTRIBUTING.md`
- `docs/agent-playbook.md`

## Working Rules
- Runtime code must remain compatible with Python 3.10+.
- Public APIs must be fully typed.
- No runtime dependency on `azure-functions` beyond what is required for type hints — keep imports optional where possible.
- Keep documentation examples, decorator behaviour, and tests synchronized.
- When bumping version, update `tests/test_public_api.py` to match the new version string.

## Validation
- `make test`
- `make lint`
- `make typecheck`
- `make build`
