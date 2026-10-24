# Development Guide

This guide covers how to set up a local development environment, run tests, and manage code quality for **azure-functions-validation**, using Hatch and a Makefile for workflow automation.

---

## Prerequisites

- **Python 3.11-3.14**
- **Git**
- **Hatch** (`pip install hatch`)
- **Make**

---

## Project Structure

```text
azure-functions-validation/
├── src/
│   └── azure_functions_validation/
├── tests/
├── docs/
├── .github/
│   └── workflows/
├── release-please-config.json
├── .release-please-manifest.json
├── .pre-commit-config.yaml
├── Makefile
├── pyproject.toml
├── CHANGELOG.md
└── README.md
```

- **`Makefile`** — common commands for environment setup, testing, linting, releasing, and publishing.
- **`pyproject.toml`** — Hatch environments, project metadata, and tool configuration.
- **`release-please-config.json`** / **`.release-please-manifest.json`** — Release Please configuration and the tracked version; these drive version bumps, `CHANGELOG.md`, and release tags.
- **`src/azure_functions_validation/`** — core library code.
- **`tests/`** — unit and integration tests.
- **`docs/`** — documentation files served by MkDocs.

---

## Initial Setup

1. **Clone the repository**:
    ```bash
    git clone https://github.com/yeongseon/azure-functions-validation-python.git
    cd azure-functions-validation-python
    ```

2. **Create environment and install dependencies**:
    ```bash
    make install
    ```

3. **Install pre-commit hooks**:
    ```bash
    make precommit-install
    ```

---

## Pre-commit Hooks

This project uses pre-commit to ensure consistent code quality across formatting, linting, typing, and security.

| Tool   | Purpose                             |
|--------|-------------------------------------|
| ruff   | Formatter + linter + import sorter  |
| mypy   | Static type checker                 |
| bandit | Security checker on `src/` only     |

Exact versions are pinned in the `dev` dependency group of `pyproject.toml`
(and in `.pre-commit-config.yaml` for the hook revisions). Those files are the
single source of truth, so this table does not restate the numbers.

### Bandit Configuration

- Only scans `src/` directory
- Skips `tests/`
- This is the pre-commit hook; `make security` scans more (see [Security](security.md))

### Run Hooks Manually

```bash
make precommit
```

---

## Development Workflow

1. **Create a feature branch**:
    ```bash
    git checkout -b feature/your-description
    ```

2. **Implement changes** in `src/azure_functions_validation/` and add tests in `tests/`.

3. **Run quality checks** locally:
    ```bash
    make check-all
    ```

4. **Commit changes** with [Conventional Commits](https://www.conventionalcommits.org/) format:
    ```bash
    git commit -m "feat: add new validator"
    ```

5. **Push and open a Pull Request** to `main`.

---

## Makefile Targets

Use these as the **golden commands** for local validation and CI parity. Prefer `make` targets over direct tool commands.

| Target | Description |
|--------|-------------|
| `make install` | Create Hatch env and install pre-commit hooks |
| `make format` | Format code (ruff) |
| `make lint` | Run linter (ruff + mypy) on `src`, `tests`, `tools` and `scripts` |
| `make typecheck` | Run mypy type checking |
| `make security` | Run Bandit on `src`, `examples`, `scripts` and `tools`; fail on an empty or partial scan |
| `make test` | Run pytest |
| `make cov` | Run tests with coverage |
| `make check` | Run style, type check, schema-hash pin, workflow lints and Bandit, each once |
| `make check-all` | Run `make check`, then the tests |
| `make docs` | Build the documentation with `mkdocs build --strict` |
| `make build` | Build package |
| `make publish-test` | Publish to TestPyPI |
| `make precommit` | Run all pre-commit hooks |
| `make precommit-install` | Install pre-commit hooks |
| `make doctor` | Check the prerequisites (read-only); fails when a required tool is missing |
| `make clean` | Remove build artifacts and `test-results/` |
| `make clean-all` | Deep clean (caches, coverage, venv) |

`make install` creates `.venv` only while it is missing and installs Hatch only while `.venv/bin/hatch`
is missing. No target upgrades pip. `PYTHON` selects the interpreter that creates `.venv` (default
`python3`, for example `make install PYTHON=python3.12`); Hatch still chooses the interpreter of its
default environment, Python 3.11.

`make doctor` checks this repository's prerequisites and installs or writes nothing. `.venv/bin/hatch`
(created by `make install`), `python3.11` on `PATH` and `git` are required: each prints `ok` or
`MISSING <tool> (required)`, and a missing one makes the target fail. `func` and `azurite` are
optional, because only a local Functions host needs them. A Python 3.11 that only Hatch manages is not
on `PATH`, so `doctor` reports it as missing.

---

## Tips

- Ensure you're using Python 3.11-3.14.
- Use `make check-all` before committing to validate your changes.
- Prefer `make` commands to ensure consistent dev experience across platforms.
- Follow Conventional Commits for proper changelog generation.
