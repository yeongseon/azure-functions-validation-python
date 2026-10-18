# Agent Playbook

## Source Of Truth
- `AGENTS.md` for repository-wide engineering and agent rules.
- `README.md` for installation, quick start, and CLI examples.
- `CONTRIBUTING.md` for branch, commit, and release workflow.
- `pyproject.toml` and `Makefile` for supported commands.

## Repository Map
- `src/azure_functions_validation/` package code.
- `tests/` validation, serialization, and error handling coverage.
- `examples/` example Azure Functions apps.
- `docs/` documentation site content.

## Issue Authoring

Follow [Repository scope](https://github.com/yeongseon/azure-functions-validation-python/blob/main/AGENTS.md#repository-scope)
before creating or editing an issue and verify the saved title, body, and labels afterwards.
This also applies when using the API or CLI.

## Change Workflow
1. Confirm whether the change affects validation API, error formatting, serialization, or docs only.
2. Update examples when they are used as public contract material.
3. Keep tests and docs in lockstep for public behavior changes.
4. Do not broaden supported Python versions or dependency ranges casually.

## Review Evidence

Follow [`docs/review-evidence-policy.md`](review-evidence-policy.md) for recording review
source/SHA, findings disposition, and R3 human-authorization notes in the PR body. This is
advisory, not a required check — it does not change the zero-native-approval merge policy or the
required CI contexts in `AGENTS.md`.

## Validation
- `make test`
- `make lint`
- `make typecheck`
- `make security`
- `make build`
