# Contributing Guide

We welcome contributions to the `azure-functions-validation` project.

## How to Contribute

1. Fork the repository.
2. Create a new branch.
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. Write code and tests.
4. Run the local quality gate.
   ```bash
   make check-all
   ```
5. Commit your changes with an English Conventional Commit message.
   ```bash
   git commit -m "feat: describe your feature"
   ```
6. Push and create a pull request.

## Project Commands

```bash
make format      # Format code with black
make lint        # Lint with ruff
make typecheck   # Type check with mypy
make test        # Run tests
make cov         # Run tests with coverage
make check-all   # Run the full local gate
```

## Example Coverage Policy

Examples are part of the supported developer experience and should stay runnable.

- Keep one representative example for the minimal supported workflow.
- Keep one complex example for combined validation scenarios.
- Add or update smoke tests whenever an example changes.
- Prefer lightweight smoke coverage over infrastructure-heavy end-to-end tests.

## Commit Message Guidelines

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification.

### Prefix Types

| Type | Description |
| --- | --- |
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation changes only |
| `style:` | Code formatting, no logic changes |
| `refactor:` | Code refactoring without behavior changes |
| `test:` | Adding or modifying tests |
| `chore:` | Tooling, dependencies, CI/CD, versioning |

### Examples

```bash
git commit -m "feat: add request body validation"
git commit -m "fix: handle empty JSON payload"
git commit -m "docs: improve quickstart"
git commit -m "refactor: extract response serializer"
git commit -m "chore: update dev dependencies"
```

## Version Management

Update the version number in `src/azure_functions_validation/__init__.py` when:

1. New features are added -> increment the minor version.
2. Bug fixes are added -> increment the patch version.
3. Breaking changes are added -> increment the major version.

When updating the version, also:

- Update `PRD.md` if scope or goals changed.
- Update `CHANGELOG.md`.
- Run `make check-all`.
- Ensure CI passes.

## Pre-commit Hook

Install pre-commit hooks with:

```bash
pre-commit install
```

## Code of Conduct

Be respectful and inclusive. See our [Code of Conduct](CODE_OF_CONDUCT.md) for details.
