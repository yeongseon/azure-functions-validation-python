# Contributing Guide

We welcome contributions to the `azure-functions-validation` project.

## How to Contribute

1. Fork the repository
2. Create a new branch
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. Write code and tests
   - Run `make test` to ensure everything passes.
   - Follow code style using `black`, `ruff`, and `mypy`.
4. Commit your changes
   ```bash
   git commit -m "feat: describe your feature"
   ```
5. Push and create a pull request

## Project Commands

```bash
make format      # Format code with black
make lint        # Lint with ruff
make typecheck   # Type check with mypy
make test        # Run tests
make cov         # Run tests with coverage
```

## Commit Message Guidelines

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification.

### Prefix Types

| Type        | Description                               |
|-------------|-------------------------------------------|
| `feat:`     | New feature                               |
| `fix:`      | Bug fix                                   |
| `docs:`     | Documentation changes only                |
| `style:`    | Code formatting, no logic changes         |
| `refactor:` | Code refactoring without behavior changes |
| `test:`     | Adding or modifying tests                 |
| `chore:`    | Tooling, dependencies, CI/CD, versioning  |

### Examples

```bash
git commit -m "feat: add request body validation"
git commit -m "fix: handle empty JSON payload"
git commit -m "docs: improve quickstart"
git commit -m "refactor: extract response serializer"
git commit -m "chore: update dev dependencies"
```

## Code of Conduct

Be respectful and inclusive. See our [Code of Conduct](CODE_OF_CONDUCT.md) for details.
