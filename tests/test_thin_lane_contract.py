from pathlib import Path

import yaml


def test_matrix_uses_makefile_on_selected_interpreter() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/ci-test.yml").read_text())
    steps = workflow["jobs"]["test"]["steps"]
    commands = "\n".join(step.get("run", "") for step in steps)
    assert "make test-ci" in commands
    makefile = (root / "Makefile").read_text()
    assert "--junitxml=test-results/junit.xml" in makefile
    assert "FAIL_ON_SKIP=1" in makefile


def test_azure_certification_uses_fail_closed_make_entrypoint() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/e2e-azure.yml").read_text())
    steps = workflow["jobs"]["deploy_and_test"]["steps"]
    test_step = next(step for step in steps if step.get("name") == "Run e2e tests")
    assert "make test-e2e-ci" in test_step["run"]
