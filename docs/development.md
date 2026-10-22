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
| `make install-ci` | Install extras into CI's explicitly selected interpreter |
| `make format` | Format code (ruff) |
| `make lint` | Run linter (ruff + mypy) |
| `make typecheck` | Run mypy type checking |
| `make security` | Run Bandit security scan |
| `make test` | Offline unit/mock pytest, coverage >=95%, saved JUnit/coverage/summary |
| `make cov` | Run tests with coverage |
| `make check` | Non-mutating Ruff lint/format, mypy once, Bandit, workflow and pinned schema/metadata contracts |
| `make integration` | Required worker signatures plus managed real host/private Azurite |
| `make verify` | Check + test + integration + wheel/schema install smoke + strict docs |
| `make check-all` | Exact backward-compatible alias of verify |
| `make e2e-azure` | Real Azure suite against explicit E2E_BASE_URL, no provisioning |
| `make report` | Render saved evidence, never rerun tests |
| `make build` | Build package |
| `make publish-test` | Publish to TestPyPI |
| `make precommit` | Run all pre-commit hooks |
| `make precommit-install` | Install pre-commit hooks |
| `make doctor` | Read-only prerequisites; missing required tools fail non-zero |
| `make clean` | Generated artifacts only, preserve environments/shared storage |
| `make clean-all` | Deep clean (caches, coverage, venv) |

Install Hatch once in an isolated tool environment. Routine commands never upgrade
pip or reinstall Hatch. Local commands use Hatch's Python 3.11; CI runs on its
selected Python directly, preserving Python/SDK variants. Full local verification
requires `func` and `azurite` on PATH; offline tests require neither.

The canonical contract is `install`, `install-ci`, `doctor`, `format`, `format-check`,
`check`, `test`, `integration`, `verify`, `e2e-azure`, `report`, `clean`. Other targets
are focused/partial or maintenance. `sdk-compat` requires `AZFUNC_2X_SPIKE=1` and an
installed wheel; neither it nor `e2e-local` is Azure certification.

Evidence lives in gitignored `test-results/`: `test/` has JUnit and coverage XML;
`worker-compat/` and `host-smoke/` each have their own summary, JUnit and logs;
`integration/` aggregates those lanes; `verify/` adds lane results/environment;
`azure-e2e/` has separate live evidence. Each summary includes schema version,
command, selected/passed/failed/skipped counts, status and supporting paths.
Actual interpreter/SDK versions are captured and secrets are redacted.
Console and Actions Job Summary render the same fields; uploads run even on failure.

PASS requires execution; failed checks/timeouts are FAIL; zero/all-skipped/missing
prerequisites are INCOMPLETE and non-zero. NOT_APPLICABLE is only for explicitly
unsupported lanes. Required live/worker skips cannot pass. Integration owns temporary
storage and processes on ephemeral ports and never uses shared emulator volumes.
Schema/metadata checks never rewrite pins. Wheel imports/schema resources are checked
outside the source tree. Azure certification retains its exact-ref/version record,
not an inferred result from local success. See the root CONTRIBUTING.md for details.

---

## Tips

- Ensure you're using Python 3.11-3.14.
- Use `make check-all` before committing to validate your changes.
- Prefer `make` commands to ensure consistent dev experience across platforms.
- Follow Conventional Commits for proper changelog generation.
