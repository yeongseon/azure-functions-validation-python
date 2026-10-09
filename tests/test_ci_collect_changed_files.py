from __future__ import annotations

from pathlib import Path
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


def test_push_force_update_fails_closed(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    git(repository, "init", "--initial-branch=main")
    first = commit_file(repository, "README.md", "first\n")
    second = commit_file(repository, "README.md", "second\n")
    git(repository, "checkout", "--orphan", "replacement")
    git(repository, "rm", "-rf", ".")
    replacement = commit_file(repository, "source.py", "replacement\n")

    command = (
        f'if ! bash "{SCRIPT}" push "" "" "" "" "" "{first}" '
        f'"{replacement}" > changed-files.txt; then '
        "printf 'docs_only=false\\ndocs_changed=true\\nfull_required=true\\n'; fi"
    )
    result = subprocess.run(
        ["bash", "-c", command],
        cwd=repository,
        capture_output=True,
        text=True,
        check=False,
    )

    assert second != replacement
    assert result.stdout.splitlines() == [
        "docs_only=false",
        "docs_changed=true",
        "full_required=true",
    ]
