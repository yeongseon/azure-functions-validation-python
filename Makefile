VENV_DIR := .venv
PYTHON ?= python
HATCH ?= hatch
ifeq ($(CI),)
RUN := $(HATCH) run python
else
RUN := $(PYTHON)
endif

.PHONY: bootstrap ensure-hatch
bootstrap ensure-hatch:
	@command -v $(HATCH) >/dev/null || { echo "Install Hatch in an isolated tool environment first"; exit 1; }

.PHONY: install
install: ensure-hatch
	@$(HATCH) env create
	@if [ -z "$$CI" ]; then $(MAKE) precommit-install; fi

.PHONY: install-ci
install-ci:
	@$(PYTHON) -c 'import sys; assert (3, 11) <= sys.version_info[:2] < (3, 15), sys.version'
	@$(PYTHON) -m pip install -e ".[dev,docs]"

.PHONY: shell reset hatch-clean
shell: ensure-hatch
	@$(HATCH) shell
reset: clean-all install
hatch-clean: ensure-hatch
	@$(HATCH) env remove

.PHONY: format format-check style typecheck lint security
format:
	@$(RUN) -m ruff format src tests tools/verification*.py
format-check:
	@$(RUN) -m ruff format --check src tests tools/verification*.py
style: format-check
	@$(RUN) -m ruff check src tests tools/verification*.py
typecheck:
	@$(RUN) -m mypy src tests tools/verification*.py
lint: style typecheck
security:
	@$(RUN) -m bandit -r src

.PHONY: check-schema-hash contracts lint-workflows check check-all
check-schema-hash:
	@$(RUN) -m tools.verification_contracts schema-hash
contracts:
	@$(RUN) -m tools.verification contracts
lint-workflows:
	@$(RUN) tools/lint_release_workflows.py
	@$(RUN) tools/lint_workflow_pins.py
	@$(RUN) tools/lint_hatch_matrix.py
check: style typecheck security lint-workflows check-schema-hash contracts
check-all: verify

.PHONY: test integration worker-compat sdk-compat verify report wheel-smoke
test integration worker-compat sdk-compat verify report:
	@$(RUN) -m tools.verification $@
wheel-smoke:
	@$(RUN) -m tools.verification focused wheel-smoke -m tools.verification_wheel

.PHONY: cov e2e-local e2e-azure build docs docs-serve
cov:
	@$(RUN) -m tools.verification test --cov-report=html
e2e-local:
	@E2E_BASE_URL=$${E2E_BASE_URL:-http://localhost:7071} $(RUN) -m tools.verification local-e2e
e2e-azure:
	@$(RUN) -m tools.verification azure-e2e
build:
	@$(RUN) -m tools.verification focused build -m build --no-isolation
docs:
	@$(RUN) -m tools.verification focused docs -m mkdocs build --strict
docs-serve:
	@$(RUN) -m mkdocs serve

.PHONY: screenshots-check screenshots-update precommit precommit-install publish-test version
screenshots-check:
	@$(RUN) scripts/check_screenshots.py --strict
screenshots-update:
	@$(RUN) scripts/check_screenshots.py --update
precommit: ensure-hatch
	@$(HATCH) run precommit
precommit-install: ensure-hatch
	@$(HATCH) run precommit-install
publish-test: ensure-hatch
	@$(HATCH) publish --repo test
version: ensure-hatch
	@$(HATCH) version

.PHONY: doctor clean clean-all help
doctor:
	@$(RUN) -m tools.verification doctor
clean:
	@$(RUN) -m tools.verification clean
# Historical deep cleanup is intentionally separate from artifact-only clean.
clean-all: clean
	@find . -type d -name "__pycache__" -not -path "./.git/*" -exec rm -rf {} +
	@find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -not -path "./.git/*" -delete
	@rm -rf .DS_Store $(VENV_DIR)
help:
	@echo "Canonical: install install-ci doctor format format-check check test integration verify e2e-azure report clean"
	@echo "check-all: exact backward-compatible alias of verify (requires func and Azurite)"
	@echo "Partial/focused: style lint typecheck security check-schema-hash contracts lint-workflows cov worker-compat sdk-compat build wheel-smoke docs docs-serve screenshots-check screenshots-update"
	@echo "Local only, not Azure certification: e2e-local; SDK spike only: sdk-compat"
	@echo "Maintenance: bootstrap ensure-hatch shell reset hatch-clean clean-all precommit precommit-install publish-test version"
