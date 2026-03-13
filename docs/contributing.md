# Contributing Guide

We welcome contributions to the `azure-functions-validation` project. This guide outlines the process for contributing code, documentation, and tests while maintaining the high quality standards of the project.

## Getting Started

To begin contributing, follow these steps to set up your local development environment:

1. Fork the repository on GitHub.
2. Clone your fork locally:
   ```bash
   git clone https://github.com/your-username/azure-functions-validation.git
   cd azure-functions-validation
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

Python 3.10 or higher is required for development.

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

We use the [Conventional Commits](https://www.conventionalcommits.org/) specification for all commit messages. This allows us to automatically generate the `CHANGELOG.md` via `git-cliff`.

### Prefix Types

| Type | Description |
| --- | --- |
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation only changes |
| `style` | Formatting, missing semi colons, etc; no code change |
| `refactor` | A code change that neither fixes a bug nor adds a feature |
| `test` | Adding missing tests or correcting existing tests |
| `chore` | Changes to the build process or auxiliary tools and libraries |

### Examples

```text
feat: add support for header validation
fix: handle null values in query parameters
docs: update installation instructions in README
refactor: simplify decorator logic in core.py
test: add unit tests for mock_request_factory
```

## Code Quality Standards

We maintain strict quality standards to ensure the reliability of the validation layer:

- **Formatting**: Code must be formatted with `ruff` (v0.15.5).
- **Linting**: We use `ruff` (v0.15.5) for linting and import sorting.
- **Type Checking**: All public APIs must be fully typed. We use `mypy` (v1.19.1) for static type analysis.
- **Security**: `bandit` (1.9.4) is used to scan for common security issues.
- **Coverage**: We require 98% or higher test coverage for all changes.

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

1. Pass all CI checks, including linting, type checking, security scans, and tests.
2. Maintain or improve the overall project test coverage.
3. Receive at least one approval from a maintainer.
4. We prefer to squash and merge PRs to maintain a clean commit history.

## Version Management

The project version is defined in `src/azure_functions_validation/__init__.py`. We follow [Semantic Versioning (SemVer)](https://semver.org/):

- **Major**: Breaking changes.
- **Minor**: New features (backwards compatible).
- **Patch**: Bug fixes (backwards compatible).

The `CHANGELOG.md` is updated automatically via `git-cliff` during the release process.

## Code of Conduct

All contributors are expected to adhere to our [Code of Conduct](https://github.com/yeongseon/azure-functions-validation/blob/main/CODE_OF_CONDUCT.md). We strive to maintain a respectful and inclusive environment for everyone.
