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

## Version Management

### When to Update Version

You **MUST** update the version number in `src/azure_functions_validation/__init__.py` when:

1. **New features are added** → Increment minor version (e.g., 0.2.0 → 0.3.0)
2. **Bug fixes** → Increment patch version (e.g., 0.2.0 → 0.2.1)
3. **Breaking changes** → Increment major version (e.g., 0.2.0 → 1.0.0)

### Version Update Checklist

When updating the version, also:

- [ ] Update `docs/PRD.md` roadmap section
- [ ] Update `CHANGELOG.md` with detailed changes
- [ ] Run all tests: `make test`
- [ ] Ensure CI/CD checks pass

### Example Version Update Process

```bash
# 1. Update version in __init__.py
vim src/azure_functions_validation/__init__.py  # Change __version__

# 2. Update PRD roadmap
vim docs/PRD.md  # Mark completed features as done

# 3. Update CHANGELOG
vim CHANGELOG.md  # Add new version section with changes

# 4. Test everything
make check-all

# 5. Commit
git add src/azure_functions_validation/__init__.py docs/PRD.md CHANGELOG.md
git commit -m "chore: bump version to 0.3.0"
```

### Pre-commit Hook

The repository includes a pre-commit hook that will:
- ✅ Check if version file is staged when committing
- ⚠️  Warn you if PRD is changed but version is not updated

Install it:
```bash
pre-commit install
```

## Code of Conduct

Be respectful and inclusive. See our [Code of Conduct](CODE_OF_CONDUCT.md) for details.
