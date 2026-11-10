"""The committed historical exceptions, exercised against the audit with fixtures (#641).

The generic behaviour is covered by ``test_release_audit.py``. These cases use this repository's
own history: a valid release, the ``v0.17.0`` candidate whose certification failed before publish,
a PyPI release without a GitHub Release, and an intentionally tag-only version.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from tools import release_audit as ra

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
OLD = NOW - timedelta(days=30)
CFG = ra.Config.load(ROOT / ra.CONFIG_PATH)


def tag(version: str, declared: str | None = None, on_mainline: bool = True) -> ra.TagFact:
    return ra.TagFact(f"v{version}", "a" * 40, OLD, declared or version, on_mainline)


def release(version: str) -> ra.ReleaseFact:
    return ra.ReleaseFact(f"v{version}", False, OLD)


def pypi(version: str) -> ra.PyPIFact:
    return ra.PyPIFact(version, False, OLD)


def facts(
    tags: list[ra.TagFact],
    releases: list[ra.ReleaseFact],
    published: list[ra.PyPIFact],
    changelog: set[str],
) -> ra.Facts:
    return ra.Facts(
        tags={t.name.removeprefix("v"): t for t in tags},
        releases={r.tag.removeprefix("v"): r for r in releases},
        pypi={p.version: p for p in published},
        changelog_versions=frozenset(changelog),
    )


def only(*versions: str) -> ra.Config:
    """The committed exceptions for just these versions, so a one-version fixture is not stale."""
    return ra.Config(
        repo=CFG.repo,
        package=CFG.package,
        mainline=CFG.mainline,
        approved={v: CFG.approved[v] for v in versions},
    )


def test_the_committed_exceptions_are_exactly_the_documented_cases() -> None:
    assert set(CFG.approved) == {"0.5.0", "0.5.1", "0.7.2", "0.9.0", "0.17.0"}
    assert CFG.approved["0.17.0"].codes == {ra.RELEASE_WITHOUT_PYPI}
    assert CFG.approved["0.5.1"].codes == {ra.TAG_ONLY}


def test_a_valid_release_is_clean() -> None:
    clean = facts([tag("0.16.1")], [release("0.16.1")], [pypi("0.16.1")], {"0.16.1"})
    report = ra.audit(only(), clean, NOW)
    assert report.ok
    assert report.findings == ()


def test_the_failed_candidate_v0_17_0_is_a_documented_exception_not_a_new_defect() -> None:
    candidate = facts([tag("0.17.0")], [release("0.17.0")], [], {"0.17.0"})
    assert not ra.audit(only(), candidate, NOW).ok
    report = ra.audit(only("0.17.0"), candidate, NOW)
    assert report.ok
    assert report.findings[0].approved == (ra.RELEASE_WITHOUT_PYPI,)


def test_a_new_unpublished_release_is_still_reported_next_to_the_exceptions() -> None:
    both = facts(
        [tag("0.17.0"), tag("0.18.0")],
        [release("0.17.0"), release("0.18.0")],
        [],
        {"0.17.0", "0.18.0"},
    )
    report = ra.audit(only("0.17.0"), both, NOW)
    assert not report.ok
    assert [f.version for f in report.findings if f.failing] == ["0.18.0"]


def test_a_pypi_release_without_a_github_release_is_reported() -> None:
    missing = facts([tag("0.5.3")], [], [pypi("0.5.3")], {"0.5.3"})
    report = ra.audit(only(), missing, NOW)
    assert not report.ok
    assert report.findings[0].unapproved == (ra.PYPI_WITHOUT_RELEASE,)


def test_the_tag_only_v0_5_1_is_allowed_only_because_it_is_documented() -> None:
    tag_only = facts([tag("0.5.1")], [], [], {"0.5.1"})
    assert not ra.audit(only(), tag_only, NOW).ok
    assert ra.audit(only("0.5.1"), tag_only, NOW).ok


def test_the_invalid_v0_7_2_tag_is_recognised_in_full() -> None:
    invalid = facts(
        [tag("0.7.2", declared="0.6.0", on_mainline=False)], [release("0.7.2")], [], set()
    )
    codes = {
        ra.TAG_VERSION_MISMATCH,
        ra.TAG_NOT_ON_MAINLINE,
        ra.RELEASE_WITHOUT_PYPI,
        ra.CHANGELOG_MISSING,
    }
    assert ra.audit(only(), invalid, NOW).findings[0].unapproved == tuple(sorted(codes))
    assert ra.audit(only("0.7.2"), invalid, NOW).ok
