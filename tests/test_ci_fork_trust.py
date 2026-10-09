from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess

TOOLS = Path(__file__).resolve().parents[1] / "tools"
TRUSTED_SCRIPTS = (
    "ci_classify_workflow_changes.sh",
    "ci_collect_changed_files.sh",
    "ci_classify_changes.sh",
)


@dataclass(frozen=True, slots=True)
class ForkRepository:
    path: Path
    base_sha: str
    head_sha: str
    sentinel: Path


def git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def commit(repository: Path, message: str) -> str:
    git(repository, "add", ".")
    git(
        repository,
        "-c",
        "user.name=CI Test",
        "-c",
        "user.email=ci@example.invalid",
        "commit",
        "-m",
        message,
    )
    return git(repository, "rev-parse", "HEAD")


def create_fork_repository(tmp_path: Path) -> ForkRepository:
    repository = tmp_path / "repository"
    scripts = repository / "tools"
    source = repository / "src"
    scripts.mkdir(parents=True)
    source.mkdir()
    git(repository, "init", "--initial-branch=main")
    for name in TRUSTED_SCRIPTS:
        shutil.copy2(TOOLS / name, scripts / name)
    (source / "application.py").write_text("TRUSTED = True\n")
    base_sha = commit(repository, "trusted base")

    git(repository, "checkout", "-b", "fork-head")
    sentinel = tmp_path / "malicious-classifier-ran"
    (scripts / "ci_classify_changes.sh").write_text(
        "#!/usr/bin/env bash\n"
        'touch "$MALICIOUS_SENTINEL"\n'
        "printf 'docs_only=true\\ndocs_changed=true\\nfull_required=false\\n'\n"
    )
    (scripts / "ci_classify_changes.sh").chmod(0o755)
    (source / "application.py").write_text("TRUSTED = False\n")
    head_sha = commit(repository, "malicious fork head")
    git(repository, "checkout", "main")
    return ForkRepository(repository, base_sha, head_sha, sentinel)


def run_workflow_wrapper(
    fork: ForkRepository,
    tmp_path: Path,
    *,
    fail_diff: bool = False,
) -> dict[str, str]:
    output = tmp_path / "github-output"
    env = os.environ | {
        "GITHUB_OUTPUT": str(output),
        "MALICIOUS_SENTINEL": str(fork.sentinel),
    }
    if fail_diff:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        git_path = shutil.which("git")
        assert git_path is not None
        (bin_dir / "git").write_text(
            f'#!/usr/bin/env bash\nif [ "$1" = diff ]; then exit 42; fi\nexec "{git_path}" "$@"\n'
        )
        (bin_dir / "git").chmod(0o755)
        env["PATH"] = f"{bin_dir}:{env['PATH']}"

    result = subprocess.run(
        [
            "bash",
            "tools/ci_classify_workflow_changes.sh",
            "pull_request",
            fork.base_sha,
            fork.head_sha,
            "fork/repo",
            "owner/repo",
            "1",
            "",
            "",
        ],
        cwd=fork.path,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return dict(line.split("=", 1) for line in output.read_text().splitlines())


def test_fork_head_classifier_is_never_executed(tmp_path: Path) -> None:
    fork = create_fork_repository(tmp_path)

    result = run_workflow_wrapper(fork, tmp_path)

    assert not fork.sentinel.exists()
    assert result == {
        "docs_only": "false",
        "docs_changed": "true",
        "full_required": "true",
    }


def test_fork_collection_failure_fails_closed(tmp_path: Path) -> None:
    fork = create_fork_repository(tmp_path)

    result = run_workflow_wrapper(fork, tmp_path, fail_diff=True)

    assert not fork.sentinel.exists()
    assert result == {
        "docs_only": "false",
        "docs_changed": "true",
        "full_required": "true",
    }
