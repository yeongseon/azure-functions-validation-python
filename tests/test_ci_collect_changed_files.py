from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "ci_collect_changed_files.sh"


def git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def commit_file(repository: Path, name: str, content: str) -> str:
    (repository / name).write_text(content)
    git(repository, "add", name)
    git(
        repository,
        "-c",
        "user.name=CI Test",
        "-c",
        "user.email=ci@example.invalid",
        "commit",
        "-m",
        f"update {name}",
    )
    return git(repository, "rev-parse", "HEAD")


def _run_workflow_wrapper(
    repository: Path,
    tmp_path: Path,
    *collector_args: str,
    fail_diff: bool = True,
) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    git_path = shutil.which("git")
    assert git_path is not None
    if fail_diff:
        (bin_dir / "git").write_text(
            f'#!/usr/bin/env bash\nif [ "$1" = diff ]; then exit 42; fi\nexec "{git_path}" "$@"\n'
        )
        (bin_dir / "git").chmod(0o755)
    output = tmp_path / "github-output"
    env = os.environ | {
        "GITHUB_OUTPUT": str(output),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
    }
    result = subprocess.run(
        ["bash", str(SCRIPT.with_name("ci_classify_workflow_changes.sh")), *collector_args],
        cwd=repository,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return dict(line.split("=", 1) for line in output.read_text().splitlines())


def test_pull_request_git_diff_failure_fails_closed(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    git(repository, "init", "--initial-branch=main")
    base = commit_file(repository, "README.md", "first\n")
    head = commit_file(repository, "README.md", "second\n")

    result = _run_workflow_wrapper(
        repository,
        tmp_path,
        "pull_request",
        base,
        head,
        "owner/repo",
        "owner/repo",
        "1",
        "",
        "",
    )

    assert result == {
        "docs_only": "false",
        "docs_changed": "true",
        "full_required": "true",
    }


def test_push_force_update_fails_closed(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    git(repository, "init", "--initial-branch=main")
    first = commit_file(repository, "README.md", "first\n")
    git(repository, "checkout", "--orphan", "replacement")
    git(repository, "rm", "-rf", ".")
    replacement = commit_file(repository, "source.py", "replacement\n")

    result = _run_workflow_wrapper(
        repository,
        tmp_path,
        "push",
        "",
        "",
        "",
        "",
        "",
        first,
        replacement,
        fail_diff=False,
    )

    assert result == {
        "docs_only": "false",
        "docs_changed": "true",
        "full_required": "true",
    }


def test_push_git_diff_failure_fails_closed(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    git(repository, "init", "--initial-branch=main")
    first = commit_file(repository, "README.md", "first\n")
    second = commit_file(repository, "README.md", "second\n")

    result = _run_workflow_wrapper(
        repository,
        tmp_path,
        "push",
        "",
        "",
        "",
        "",
        "",
        first,
        second,
    )

    assert result == {
        "docs_only": "false",
        "docs_changed": "true",
        "full_required": "true",
    }
