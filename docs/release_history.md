# Release History and Provenance

This page records how each published version of **azure-functions-validation** maps to a Git tag, a
GitHub Release and a PyPI distribution, and lists the historical cases where those records do not
line up. The data was reconciled against Git, PyPI and GitHub on 2026-11-10. For how new versions
are released, see [Release Process](release_process.md).

---

## What each record proves

| Record | Proves | Does not prove |
|---|---|---|
| PyPI distribution | The package users install exists, with its files and upload time | Which commit built it (only PyPI attestations, available from `0.5.2`, say so) |
| Git tag | A commit was labelled with a version | That the tagged source is what shipped, or that anything was published |
| GitHub Release | A release page with notes exists | That a package was published |

A GitHub Release is never evidence of publication. Check the
[PyPI release history](https://pypi.org/project/azure-functions-validation/#history).

---

## Reconciliation summary

| Evidence set | Count |
|---|---:|
| Git tags | 37 |
| PyPI versions (`0.3.0` to `0.16.0`) | 32 |
| GitHub Releases | 36 |

| Category | Versions |
|---|---|
| Published, with a matching tag and GitHub Release | 28 versions: every published version except the four below |
| Published, tag exists, GitHub Release added afterwards | `0.5.3`, `0.5.4`, `0.5.5`, `0.5.6` |
| Unpublished release candidate: tag and GitHub Release, never on PyPI | `0.5.0`, `0.9.0`, `0.17.0` |
| Failed candidate: tag only, no GitHub Release | `0.5.1` |
| Invalid tag with a GitHub Release, never published | `v0.7.2` |

For every published version the package files on PyPI are byte-identical to the tagged commit (see
[How this was verified](#how-this-was-verified)).

---

## v0.17.0: unpublished release candidate

**Facts**

- The tag `v0.17.0` is a lightweight tag on the release commit `3379eb6`, which declares
  `__version__ = "0.17.0"` and is on the history of `main`. Release Please created the GitHub
  Release at 2026-11-01 13:37:58 UTC, and
  [`Publish to PyPI` run 41312202572](https://github.com/yeongseon/azure-functions-validation-python/actions/runs/41312202572)
  started two seconds later and failed.
- In that run the build, library tests, cookbook smoke, candidate host-behavior checks and the
  real-Azure certification all succeeded. The four `Candidate runtime audit` jobs (Python 3.11 to
  3.14) failed at the step *Verify audit guards on the selected interpreter*, so the `publish` job
  was skipped.
- The retained log of every one of the four jobs shows the same sequence: the dependency audit
  reported `No known vulnerabilities found` and `runtime audit clean: 8 dependencies`, and then
  pytest failed while loading `tests/conftest.py` (`from azure.functions import HttpRequest`,
  `ModuleNotFoundError: No module named 'azure'`, exit code 4). The guard tests ran in an
  interpreter that has pytest but not the project's dependencies.
- Issue [#624](https://github.com/yeongseon/azure-functions-validation-python/issues/624) recorded
  the same cause. [#625](https://github.com/yeongseon/azure-functions-validation-python/pull/625)
  (merged 2026-11-02) runs those guard tests with `--noconftest` and adds a regression test that
  reproduces the failure.
- PyPI still ends at `0.16.0`; there is no `0.17.0` distribution.

**Decision**

- The tag and the GitHub Release are kept; nothing is moved, deleted or re-uploaded. The Release
  body now opens with a notice that the version was not published, and it keeps the
  breaking-change guidance for `ValidationAdapter.serialize_response()` (a protected statement in
  `.github/release-notes.json`, as is the notice). It is also marked as a **pre-release**, so GitHub
  no longer shows it as the Latest release: the Latest release is `v0.16.0`, the latest version on
  PyPI. The next published release becomes Latest by itself.
- Re-running the publish workflow for this tag is not a recovery: a dispatch uses the workflow file
  at the tag, which still contains the failing step.
- The supported path is fix-forward. The cause is fixed on `main`, so the next published release
  will ship the `0.17.0` changes under its own version. Release Please hides `docs`, `ci`,
  `chore`, `refactor`, `style`, `test` and `build` commits, and only `feat`, `fix`, `perf` or
  `revert` commits open a Release PR, so nothing merged since `v0.17.0` has opened one. Until a
  release ships, PyPI users stay on `0.16.0`; when to release is a maintainer decision under the
  [release cadence](release_process.md#release-cadence).
- [Custom adapters](adapters.md#compatibility-and-versioning) are affected by the `serialize_response()`
  requirement from the first published release after `0.16.0`, not from a version `0.17.0`.

---

## v0.9.0: unpublished, superseded by v0.9.1

- The annotated tag `v0.9.0` (commit `0af7b28`, 2026-08-09 05:43:59 UTC) started three workflows.
  `Create GitHub Release` succeeded and created the Release at 05:44:16 UTC, and the real-Azure
  `e2e-azure` run succeeded, but
  [`Publish to PyPI` run 31297327148](https://github.com/yeongseon/azure-functions-validation-python/actions/runs/31297327148)
  failed at the step *Build distribution packages*. The job log has expired, so the build error
  itself cannot be re-read.
- `v0.9.1` was tagged at 05:58:34 UTC and published to PyPI at 05:58:58 UTC, about 15 minutes
  later. `v0.9.0` is an ancestor of `v0.9.1`, so every change in `0.9.0` shipped in `0.9.1`.
- **Decision:** keep the tag and the Release, with a notice that `0.9.0` was not published.

---

## v0.5.0 and v0.5.1: failed publishes

- `v0.5.0` (commit `23f4f3e`, 2026-03-11 01:42:59 UTC) has a GitHub Release, but its
  [`Publish to PyPI` run 22932614727](https://github.com/yeongseon/azure-functions-validation-python/actions/runs/22932614727)
  failed (the log has expired).
- `v0.5.1` (annotated tag, commit `215e056`, 2026-03-14 13:19:41 UTC) also failed
  ([run 23088752563](https://github.com/yeongseon/azure-functions-validation-python/actions/runs/23088752563))
  and has neither a GitHub Release nor a PyPI distribution. It is classified as **tag-only**: a
  Release page would imply a package that does not exist, so none is created.
- `0.5.2` (published 2026-03-15) is the first package on PyPI after `0.3.0`. Both `v0.5.0` and
  `v0.5.1` are ancestors of `v0.5.2`, so their changes shipped in it.
- **Decision:** keep both tags. The `v0.5.0` Release carries a notice that it was not published.

---

## v0.7.2: invalid tag, never published

**Facts**

- `v0.7.2` is a lightweight tag on commit `2d7339f` ("update repo references for
  azure-functions-{feature}-python naming convention", 2026-04-17), which declares
  `__version__ = "0.6.0"`.
- The commit is not part of the history of `main`. It sits on a side branch forked from `main` at
  `b81c38b` with two commits: `66539ef` ("add automatic GitHub Release creation on tag push") and
  `2d7339f`. GitHub's
  [`v0.7.1...v0.7.2`](https://github.com/yeongseon/azure-functions-validation-python/compare/v0.7.1...v0.7.2)
  comparison reports it as *diverged* (2 commits ahead, 44 behind).
- Pushing the tag (2026-04-18 13:28:46 UTC, Actions actor `yeongseon`) started three workflows:
  [`Publish to PyPI`](https://github.com/yeongseon/azure-functions-validation-python/actions/runs/24605715586)
  (failed),
  [`e2e-azure`](https://github.com/yeongseon/azure-functions-validation-python/actions/runs/24605715589)
  (failed) and
  [`Create GitHub Release`](https://github.com/yeongseon/azure-functions-validation-python/actions/runs/24605715583)
  (succeeded). The last one created the GitHub Release four seconds later. That workflow
  (`create-release.yml`) was removed when Release Please was adopted.
- PyPI has no `0.7.2`, `CHANGELOG.md` has no `0.7.2` section, and the next release, `v0.7.3`,
  follows `v0.7.1`. The job logs have expired, so the exact failing step cannot be re-read. A
  version mismatch between the tag and `__version__` is the expected cause but is not confirmed.

**Decision:** the tag is kept unchanged as an audit record and no `0.7.2` package is created. The
GitHub Release body now begins with a notice that it is not a usable release, the notice is a
protected statement in `.github/release-notes.json`, and `v0.7.2` is listed under `not_a_release`
so that it is never used as the compare base of `v0.7.3`.

---

## GitHub Releases added for published versions

These versions were already on PyPI and already had a tag, but no GitHub Release. The Release was
added afterwards on the **existing** tag; no tag, package file or date was changed. Notes are
reconstructed from `CHANGELOG.md` and cross-checked against the commits between the tags, which
agree item for item.

| Version | PyPI upload (UTC) | Tagged commit | PyPI attestation |
|---|---|---|---|
| `0.5.3` | 2026-03-16 | `1c49426` | built from the tag at this commit |
| `0.5.4` | 2026-03-16 | `616abbf` | built from the tag at this commit |
| `0.5.5` | 2026-03-17 | `16c27b2` | built from the tag at this commit |
| `0.5.6` | 2026-03-17 | `03466ae` | built from the tag at this commit |

GitHub orders Releases by the date of their tag, so each added Release appears next to its
neighbours rather than at the top of the list; the time it was added is recorded as its
publication time. Older Release bodies link to the former repository name
`azure-functions-validation`; GitHub redirects those URLs, including compare links, to the current
repository.

---

## Checking the history automatically

`make release-audit` re-reads Git tags, GitHub Releases, `CHANGELOG.md` and PyPI and exits
non-zero for any discrepancy that is not an approved exception. It only reads: it never moves,
creates or deletes a tag, a Release or a package. Set `GH_TOKEN` to stay under GitHub's anonymous
rate limit, for example `GH_TOKEN=$(gh auth token) make release-audit`.

| Code | Meaning |
|---|---|
| `TAG_VERSION_MISMATCH` | the tagged source declares a different version than the tag |
| `TAG_NOT_ON_MAINLINE` | the tagged commit is not on the history of `main` |
| `TAG_ONLY` | a tag with neither a PyPI distribution nor a GitHub Release |
| `PYPI_WITHOUT_TAG` | published to PyPI, but no Git tag exists |
| `PYPI_WITHOUT_RELEASE` | published and tagged, but no GitHub Release exists |
| `RELEASE_WITHOUT_PYPI` | a GitHub Release exists, but nothing was published to PyPI |
| `RELEASE_WITHOUT_TAG` | a GitHub Release exists, but its tag does not |
| `CHANGELOG_MISSING` | tagged, released or published, but `CHANGELOG.md` has no section for it |

The approved exceptions are the cases documented on this page, kept in
`.github/release-audit.json` with their reason and a link to the section that explains them. An
exception must match the findings exactly, so one that no longer applies, or no longer covers
everything found for that version, fails the audit instead of going stale. A release younger than
12 hours that is still in the publish gate is reported as pending rather than as a failure. Do not
edit the file to silence a real defect: fix forward, or record the case here with its evidence.

Two narrower commands are used by the release pipeline. `python -m tools.release_audit
check-tag vX.Y.Z` checks that the tagged source declares that version, that the commit is on
`main` and that `CHANGELOG.md` has its section. `check-published vX.Y.Z --wait-minutes N` waits
until PyPI serves the version. Exit codes are 0 for clean, 1 for a discrepancy and 2 when the
audit itself could not run. The full audit also runs weekly in the `Release history audit`
workflow; see [Release verification and alerts](release_process.md#release-verification-and-alerts).

---

## How this was verified

1. **Tag, commit and version.** `git show vX.Y.Z:src/azure_functions_validation/__init__.py` gives
   the declared `__version__`, and `git merge-base --is-ancestor vX.Y.Z origin/main` tells whether
   the tag is on the history of `main`.
2. **PyPI.** The [JSON API](https://pypi.org/pypi/azure-functions-validation/json) lists each
   version's files, upload time and yanked state.
3. **PyPI files against the tagged commit.** The snippet below compares the package files in the
   sdist with the package directory at the tag, using Git blob IDs. All 32 published versions are
   identical to their tags. Run it from a clone that has the tags.
4. **PyPI attestations.** For `0.5.2` and later,
   `https://pypi.org/integrity/azure-functions-validation/<version>/<sdist file>/provenance`
   returns an attestation whose certificate records the source commit and the workflow run. For
   all 31 attested versions the attested commit equals the tagged commit.
5. **Workflow runs.** The Actions API keeps run metadata, and job logs for about 90 days.

```python
import hashlib
import io
import json
import subprocess
import tarfile
import urllib.request

version, tag = "0.5.3", "v0.5.3"
meta = json.load(
    urllib.request.urlopen(f"https://pypi.org/pypi/azure-functions-validation/{version}/json")
)
sdist = next(u["url"] for u in meta["urls"] if u["packagetype"] == "sdist")


def blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


shipped = {}
with tarfile.open(fileobj=io.BytesIO(urllib.request.urlopen(sdist).read())) as tar:
    for member in tar.getmembers():
        _, found, name = member.name.partition("/azure_functions_validation/")
        if member.isfile() and found and "__pycache__" not in name:
            shipped[name] = blob_id(tar.extractfile(member).read())

listing = subprocess.run(
    ["git", "ls-tree", "-r", f"{tag}:src/azure_functions_validation"],
    capture_output=True,
    text=True,
    check=True,
).stdout
tagged = {line.split("\t")[1]: line.split()[2] for line in listing.splitlines()}
print(
    "identical"
    if shipped == tagged
    else sorted(k for k in shipped.keys() | tagged.keys() if shipped.get(k) != tagged.get(k))
)
```

---

## Rules for the future

- Never move or delete a tag, and never re-upload or replace a published file to repair history.
  Record the case here instead.
- Do not create a tag for a commit that did not produce the published package.
- When a GitHub Release is added for an existing tag, say so in its notes. Mark a release that was
  never published as such.
- Use PyPI, not a GitHub Release, to decide whether a version was published.
