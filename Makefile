VENV_DIR := .venv
# The interpreter that creates $(VENV_DIR), which only hosts Hatch. Hatch chooses the interpreter of
# its own default environment (Python 3.11, see [tool.hatch.envs.default] in pyproject.toml).
PYTHON ?= python3
PIP := $(VENV_DIR)/bin/pip
HATCH := $(VENV_DIR)/bin/hatch

# Idempotent: the virtual environment is created only while it is missing, Hatch is installed only
# while it is not an executable regular file (`-x` alone also accepts a directory), and pip is
# never upgraded.
.PHONY: bootstrap
bootstrap:
	@test -d "$(VENV_DIR)" || { echo "Creating virtual environment..."; $(PYTHON) -m venv "$(VENV_DIR)"; }
	@{ [ -f "$(HATCH)" ] && [ -x "$(HATCH)" ]; } || { echo "Installing Hatch..."; "$(PIP)" install --disable-pip-version-check --quiet hatch; }

.PHONY: ensure-hatch
ensure-hatch: bootstrap

.PHONY: install
install: ensure-hatch
	@$(HATCH) env create
	@if [ -n "$$CI" ]; then \
		echo "CI detected: skipping pre-commit hook installation"; \
	else \
		$(MAKE) precommit-install; \
	fi

.PHONY: shell
shell: ensure-hatch
	@$(HATCH) shell

.PHONY: reset
reset: clean-all install
	@echo "Project reset complete."

.PHONY: hatch-clean
hatch-clean: ensure-hatch
	@$(HATCH) env remove || echo "No hatch environment to remove"

.PHONY: format
format: ensure-hatch
	@$(HATCH) run format

.PHONY: format-check
format-check: ensure-hatch
	@$(HATCH) run format-check

.PHONY: style
style: ensure-hatch
	@$(HATCH) run style

.PHONY: typecheck
typecheck: ensure-hatch
	@$(HATCH) run typecheck

.PHONY: lint
lint: ensure-hatch
	@$(HATCH) run lint

# Bandit exits 0 for an empty, missing or unparsable scope, so scripts/check_bandit_report.py
# also reads its JSON report; the report is deleted first so a stale one can never pass.
# -q: Bandit 1.9.4 prints a progress bar to stdout above 50 files.
# Every Bandit test runs on every file: there is no skip list for any directory. Suppress a
# reviewed finding on its own line, `# nosec Bxxx # <reason>`, never here.
BANDIT_DIR := test-results/bandit
BANDIT_SCOPE := src examples scripts tools
BANDIT := $(HATCH) run python -m bandit -q -f json
BANDIT_CHECK := $(HATCH) run python scripts/check_bandit_report.py

.PHONY: security
security: ensure-hatch
	@rm -rf $(BANDIT_DIR) && mkdir -p $(BANDIT_DIR)
	@status=0; \
	$(BANDIT) -o $(BANDIT_DIR)/bandit.json -r $(BANDIT_SCOPE) || status=1; \
	$(BANDIT_CHECK) $(BANDIT_DIR)/bandit.json $(BANDIT_SCOPE) || status=1; \
	exit $$status

.PHONY: check-schema-hash
check-schema-hash: ensure-hatch
	@$(HATCH) run python -c "import hashlib, pathlib, sys; d = pathlib.Path('src/azure_functions_validation/schemas'); expected = (d / 'endpoint.schema.sha256').read_text().split()[0]; actual = hashlib.sha256((d / 'endpoint.schema.json').read_bytes()).hexdigest(); print('endpoint.schema.json digest matches pin.') if expected == actual else sys.exit('endpoint.schema.json digest drift:\n  pinned:  ' + expected + '\n  actual:  ' + actual + '\nUpdate endpoint.schema.sha256 if this change is intentional.')"

.PHONY: lint-workflows
lint-workflows: ensure-hatch
	@$(HATCH) run python tools/lint_release_workflows.py
	@$(HATCH) run python tools/lint_workflow_pins.py
	@$(HATCH) run python tools/lint_hatch_matrix.py

# Every check runs once. `lint` is not listed: `hatch run lint` is `style` followed by `typecheck`,
# and both are already prerequisites here.
.PHONY: check
check: style typecheck check-schema-hash lint-workflows security
	@echo "All static checks passed (style, types, schema hash, workflow lints, Bandit)."

.PHONY: check-all
check-all: check test
	@echo "All checks passed including tests and security scan."

.PHONY: screenshots-check
screenshots-check: ensure-hatch
	@$(HATCH) run python scripts/check_screenshots.py --strict

.PHONY: screenshots-update
screenshots-update: ensure-hatch
	@$(HATCH) run python scripts/check_screenshots.py --update

.PHONY: precommit
precommit: ensure-hatch
	@$(HATCH) run precommit

.PHONY: precommit-install
precommit-install: ensure-hatch
	@$(HATCH) run precommit-install

.PHONY: test
test: ensure-hatch
	@echo "Running tests..."
	@$(HATCH) run test

.PHONY: cov
cov: ensure-hatch
	@$(HATCH) run cov
	@echo "Open htmlcov/index.html in your browser to view the coverage report."
	@echo "coverage.xml generated for Codecov upload."

.PHONY: e2e-local
e2e-local: ensure-hatch
	@echo "Running e2e tests against local Azurite (E2E_BASE_URL=http://localhost:7071)..."
	@E2E_BASE_URL=http://localhost:7071 $(HATCH) run e2e-azure

.PHONY: e2e-azure
e2e-azure: ensure-hatch
	@echo "Running e2e tests against Azure (E2E_BASE_URL must be set)..."
	@$(HATCH) run e2e-azure

.PHONY: build
build: ensure-hatch
	@$(HATCH) build

.PHONY: publish-test
publish-test: ensure-hatch
	@$(HATCH) publish --repo test

.PHONY: version
version: ensure-hatch
	@echo "Current version:"
	@$(HATCH) version

# Strict, like the CI docs gate: a broken nav entry or link fails the build, and no step of the
# build may fail silently.
.PHONY: docs
docs:
	@if [ -n "$$CI" ]; then \
		echo "CI detected: running MkDocs directly"; \
		pip install --disable-pip-version-check --quiet "mkdocs<2.0" "mkdocs-material<10.0" "mkdocstrings[python]<1.0" && \
		mkdocs build --strict; \
	else \
		$(MAKE) ensure-hatch > /dev/null && \
		$(HATCH) run mkdocs build --strict; \
	fi

.PHONY: docs-serve
docs-serve: ensure-hatch
	@$(HATCH) run docs

# Read-only prerequisite check: it installs and writes nothing, and fails when a required tool is
# missing. A tool counts only if `command -v` resolves it to an executable regular file, because
# `command -v` accepts any existing path and `-x` alone also accepts a directory. Python 3.11 is
# what the default Hatch environment is pinned to, and it is looked up on PATH.
.PHONY: doctor
doctor:
	@missing=0; \
	have() { p="$$(command -v "$$1")"; [ -f "$$p" ] && [ -x "$$p" ]; }; \
	for tool in "$(HATCH)" python3.11 git; do \
		if have "$$tool"; then echo "ok       $$tool"; \
		else echo "MISSING  $$tool (required)"; missing=1; fi; \
	done; \
	for tool in func azurite; do \
		if have "$$tool"; then echo "ok       $$tool"; \
		else echo "missing  $$tool (optional: needed only to run a local Functions host)"; fi; \
	done; \
	exit $$missing

.PHONY: clean
clean:
	@rm -rf *.egg-info dist build __pycache__ .pytest_cache test-results

.PHONY: clean-all
clean-all: clean
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete
	@rm -rf .mypy_cache .ruff_cache .pytest_cache .coverage coverage.xml htmlcov .DS_Store $(VENV_DIR) site

.PHONY: help
help:
	@echo "Available commands:" && \
	grep -E '^\.PHONY: ' Makefile | cut -d ':' -f2 | xargs -n1 echo "  - make"
