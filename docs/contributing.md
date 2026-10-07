# Contributing Guide

We welcome contributions to the `azure-functions-validation` project. This guide outlines the process for contributing code, documentation, and tests while maintaining the high quality standards of the project.

## Getting Started

To begin contributing, follow these steps to set up your local development environment:

1. Fork the repository on GitHub.
2. Clone your fork locally:
   ```bash
   git clone https://github.com/your-username/azure-functions-validation-python.git
   cd azure-functions-validation-python
   ```
3. Set up the development environment using Hatch:
   ```bash
   make install
   ```
4. Install the pre-commit hooks to ensure code quality:
   ```bash
   make precommit-install
   ```
5. Verify your setup by running the full quality gate:
   ```bash
   make check-all
   ```

Python 3.11-3.14 is required for development (`pyproject.toml` declares `requires-python = ">=3.11,<3.15"`).

## Development Workflow

We follow a standard feature branch workflow:

1. Create a new branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Implement your changes in `src/azure_functions_validation/`.
3. Add or update tests in the `tests/` directory.
4. Run the local quality gate frequently to catch issues early:
   ```bash
   make check-all
   ```
5. Commit your changes using the Conventional Commits format.
6. Push your branch to your fork and create a Pull Request (PR) against the `main` branch.

## Commit Message Convention

Titles for issues, pull requests, and commits follow the **Title Convention** in [`CONTRIBUTING.md`](https://github.com/yeongseon/azure-functions-validation-python/blob/main/CONTRIBUTING.md#title-convention), the single source of truth for the format and the allowed types.

## Code Quality Standards

We maintain strict quality standards to ensure the reliability of the validation layer:

- **Formatting**: Code must be formatted with `ruff`.
- **Linting**: We use `ruff` for linting and import sorting.
- **Type Checking**: All public APIs must be fully typed. We use `mypy` for static type analysis.
- **Security**: `bandit` is used to scan for common security issues.
- **Coverage**: The `fail_under` threshold in `pyproject.toml` is **95%**; changes must keep coverage at or above it.

Tool versions are pinned in the `dev` dependency group of `pyproject.toml` — that
file is the single source of truth, so this guide does not restate the numbers.

Run `make check-all` to execute all these tools locally before pushing your changes.

## Testing Requirements

All new features and bug fixes must include tests.

- Place tests in the appropriate file within the `tests/` directory (e.g., `test_decorator.py` for configuration, `test_pipeline.py` for runtime logic).
- Use the `mock_request_factory` fixture for unit tests to simulate Azure Functions requests.
- Use `MockHttpRequest` for integration tests that require more complex request structures.
- Ensure you test both success paths and error cases (e.g., invalid payloads, missing headers).

## Example Coverage Policy

Examples are part of the supported developer experience and must remain runnable.

- Keep examples in the `examples/` directory up to date with API changes.
- Update smoke tests whenever an example is modified.
- Prefer lightweight smoke coverage over infrastructure-heavy end-to-end tests for examples.

## Pull Request Process

Every Pull Request must meet the following criteria before being merged:

1. Pass all CI checks required by branch protection on `main` — currently
   `ci-required`, `bandit`, `semgrep`, `Analyze` (CodeQL), and `PR title`.
2. Maintain or improve the overall project test coverage.
3. Resolve every review conversation (branch protection requires this).
4. We prefer to squash and merge PRs to maintain a clean commit history.

> **Reviews.** Branch protection does not currently require an approving review,
> so a green PR with all conversations resolved is mergeable. Maintainer review
> is still encouraged for anything touching the validation pipeline or the
> public API.

## Version Management

The project version is defined in `src/azure_functions_validation/__init__.py`. We follow [Semantic Versioning (SemVer)](https://semver.org/):

- **Major**: Breaking changes.
- **Minor**: New features (backwards compatible).
- **Patch**: Bug fixes (backwards compatible).

`CHANGELOG.md` is written by Release Please in the Release PR; see [Release Process](release_process.md).

## Code of Conduct

All contributors are expected to adhere to our [Code of Conduct](https://github.com/yeongseon/azure-functions-validation-python/blob/main/CODE_OF_CONDUCT.md). We strive to maintain a respectful and inclusive environment for everyone.
