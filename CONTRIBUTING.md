# Contributing Guide

We welcome contributions to the `azure-functions-validation` project.

## Local development quickstart

The package supports Python 3.11, 3.12, 3.13, and 3.14. Local development
requires Python 3.11 because the default Hatch environment is pinned to that
interpreter. Offline tests and quality checks need no services. Full local
verification additionally requires Functions Core Tools (`func`) and Azurite.

Install Hatch once in an isolated tool environment, then clone the repository
and create the development environment. Routine checks never upgrade pip or
reinstall Hatch, and never change the global interpreter:

```bash
git clone https://github.com/yeongseon/azure-functions-validation-python.git
cd azure-functions-validation-python
make install
```

Run the standard verification commands before opening a pull request:

```bash
make test
make check
make verify
```

`make check-all` is an exact backward-compatible alias of `make verify`.
CI uses `make install-ci PYTHON=python` on the explicitly selected matrix
interpreter, not Hatch's pinned Python 3.11 environment.

## Branch Strategy

Use GitHub Flow and branch from `main`.

Recommended branch prefixes:

- `feat/` for new features
- `fix/` for bug fixes
- `docs/` for documentation-only changes
- `chore/` for tooling and maintenance
- `ci/` for workflow updates

## Development Workflow

1. Create a branch from `main`.
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feat/your-feature-name
   ```
2. Write code and tests.
3. Run the local quality gate.
   ```bash
   make check-all
   ```
4. Push and create a pull request.
   ```bash
   git push origin feat/your-feature-name
   ```

## Project Commands

| Command | Contract |
| --- | --- |
| `make install` | Create isolated Hatch dev/docs environment and install local hooks |
| `make install-ci` | Install extras into CI's selected `PYTHON`, preserving the matrix cell |
| `make doctor` | Read-only prerequisite check; fail for missing required tools |
| `make format` / `make format-check` | Mutating format action / non-mutating check |
| `make check` | Ruff lint/format, strict mypy once, Bandit, workflow policy and pinned metadata/schema contracts |
| `make test` | Offline unit/mock suite only, existing 95% coverage floor |
| `make integration` | Required worker signatures/registration plus managed real host and private Azurite |
| `make verify` | Always check + test + integration + wheel/schema install smoke + strict docs |
| `make e2e-azure` | Separate real Azure run against explicit `E2E_BASE_URL`; never provisions resources |
| `make report` | Render saved results without rerunning tests |
| `make clean` | Remove generated artifacts only; preserve environments/shared emulator storage |

`make check-all` means exactly `make verify`. `make clean-all` retains its historical
deep-clean meaning: artifacts, bytecode and the project-local `.venv`.
Focused/partial targets remain: `style`, `lint`, `typecheck`, `security`, `cov`,
`lint-workflows`, `check-schema-hash`, `contracts`, `worker-compat`, `sdk-compat`,
`build`, `wheel-smoke`, `docs`, screenshot checks and maintenance commands.
`sdk-compat` requires `AZFUNC_2X_SPIKE=1` and tests an installed wheel without source
path injection; it is a compatibility spike, never general Azure certification.
`e2e-local` targets an already-running local app and is not Azure certification.

### Verification evidence

Generated evidence is gitignored:

```text
test-results/
  test/{junit.xml,coverage.xml,summary.json,environment.json,logs/}
  worker-compat/{junit.xml,summary.json,environment.json,logs/}
  host-smoke/{junit/junit.xml,summary.json,environment.json,logs/}
  integration/{summary.json,environment.json,lanes.json}
  verify/{summary.json,environment.json,lanes.json,logs/}
  azure-e2e/{junit.xml,summary.json,environment.json,logs/}
```

Each summary has a schema version, lane/command, selected/passed/failed/skipped
counts, exit status and supporting paths. Actual Python/runtime/SDK versions are
recorded; credentials, connection strings, authorization headers, SAS and tokens
are redacted. Console and Actions Job Summary use the same saved fields; CI uploads
`test-results/**` with `if: always()`.

- **PASS** requires actual execution and successful required checks.
- **FAIL** means a process/check/test failed or timed out.
- **INCOMPLETE** means missing prerequisites, missing/invalid JUnit, zero tests,
  all skipped, or a skipped required live/worker test. These exit non-zero.
- **NOT_APPLICABLE** is reserved for explicitly unsupported lanes, never missing tools.

Host smoke uses temporary storage, unique ephemeral ports and bounded readiness;
it stops only processes it owns, including on interruption. Core Tools may need
its extension bundle cached. Worker signature evidence and host evidence stay
separate. Local verification never implies real Azure certification. Azure release
certification keeps the existing exact-ref/source-version record; this repository's
live endpoint does not currently expose a deployed package-version assertion.
Schema/hash checks never rewrite pinned metadata. Wheel smoke verifies packaged
schema bytes and installed imports outside the checkout, separately from source tests.

Before opening a PR, run `make format-check` to check `src`, `tests` and verification
helpers without changing files. Run `make format` to fix those trees. CI also checks every
changed Python file, including files outside `src` and `tests`.

## GitHub Actions Pinning

All external `uses:` references in `.github/workflows/` MUST pin to a
full 40-character commit SHA with a trailing comment documenting the
released version or channel. Example:

```yaml
- uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6
```

This applies to first-party (`actions/*`, `github/*`, `azure/*`) and
third-party Actions alike.

**Rationale.** Mutable tags (including immutable-looking version tags
like `@v6.0.1`) can be retroactively moved by an attacker who gains
write access to the upstream repository. The
[`tj-actions/changed-files` compromise (CVE-2025-30066, March 2025)](https://www.cisa.gov/news-events/alerts/2025/03/18/supply-chain-compromise-third-party-tj-actionschanged-files-cve-2025-30066)
demonstrated this exact failure mode: ~23,000 repositories had their CI
secrets exfiltrated, and only workflows that pinned to a commit SHA were
safe. GitHub's own guidance now identifies SHA pinning as
[the only way to use an Action as an immutable release](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions#using-third-party-actions),
and OpenSSF Scorecard's
[`Pinned-Dependencies` check](https://github.com/ossf/scorecard/blob/main/docs/checks.md#pinned-dependencies)
flags anything weaker as Medium-risk.

Dependabot updates SHA-pinned references on the configured schedule and
keeps the trailing version comment in sync, so the human-readable
context never drifts from the pinned commit.

**Approved exceptions.** The following mutable refs are the only ones
permitted in this repository and are flagged with an inline comment at
the call site:

- `pypa/gh-action-pypi-publish@release/v1` — PyPA-maintained stable
  release channel; this pinning style is explicitly recommended upstream.
- Local composite actions (`uses: ./...`) — versioned with the repo.

When adding a new external Action, resolve the SHA with
`git ls-remote <repo-url> 'refs/tags/<tag>^{}'`. The trailing `^{}`
**dereferences** the ref to its target commit; without it, an
*annotated* tag returns the tag-object SHA instead of the commit SHA,
and the tag-object SHA is **not** a valid `uses:` target.

```bash
# Annotated tag — the two forms return *different* SHAs:
git ls-remote https://github.com/Azure/login 'refs/tags/v3.0.0' 'refs/tags/v3.0.0^{}'
# 93381592...   refs/tags/v3.0.0       <- tag object, do NOT pin to this
# 532459ea...   refs/tags/v3.0.0^{}    <- commit, pin to this one

# Lightweight tag — only the non-deref form returns a row, and it is
# already the commit SHA. Always include the `^{}` form anyway so the
# same command works for both tag types:
git ls-remote https://github.com/actions/setup-python 'refs/tags/v6' 'refs/tags/v6^{}'
```

Single-quote the `refs/...^{}` argument so the `{}` and `^` are not
interpreted by your shell (notably zsh with `EXTENDED_GLOB`).

## Example Coverage Policy

Examples are part of the supported API experience and should stay verified.

- Keep one representative example for the minimal validation workflow.
- Keep one complex example for custom error handling and multi-field validation.
- Add or update smoke tests whenever an example changes.
- Prefer lightweight smoke coverage over infrastructure-heavy end-to-end tests.

## Issue Scope

Follow the [repository-scope rules in AGENTS.md](AGENTS.md#repository-scope)
when opening or editing an issue, including the checks before and after saving.
Explain this repository's problem, evidence, user impact, and completion criteria,
and state why any external project or source is relevant.

## Title Convention

This section is the single source of truth for issue, pull request, and commit titles in this repository. `AGENTS.md`, the pull request template, the issue forms, and the documentation site point here instead of restating the rules.

Issues, pull requests, and the final squash commit on the default branch all use:

```text
type: description
type(scope): description
```

- Write titles in English.
- `type` and `scope` are lowercase. Put exactly one space after the colon.
- `scope` is optional. Add it only when it narrows the area; do not add one just for uniformity.
- `description` states what changes and why, concisely. Start with a lowercase word, but keep the spelling of API names, acronyms, error codes, and proper nouns.
- No trailing period.
- No priority, size, status, or owner markers, and no bracket prefixes such as `[Bug]`, `[Feature]`, or `[WIP]`. Use labels and Draft pull requests instead.
- An issue title may describe the problem; the pull request title describes the change that resolves it. Keep them aligned when they cover the same work, without forcing identical wording when the scope differs.
- Do not put issue numbers in pull request titles. Link issues in the pull request body with `Closes #123` or `Refs #123`.

| type | use for |
|---|---|
| `feat` | a user-facing feature or capability |
| `fix` | a bug fix in product behavior |
| `docs` | documentation only |
| `test` | adding or changing tests |
| `perf` | a performance improvement |
| `refactor` | internal restructuring that keeps external behavior |
| `ci` | CI and automation workflows |
| `build` | build, packaging, and dependency changes |
| `chore` | maintenance that fits none of the above |
| `style` | formatting only, no behavior change |
| `revert` | reverting an earlier change |

A breaking change adds `!` before the colon: `type!: description` or `type(scope)!: description`. Whether a change is breaking, and how it is released, is decided by the Release Process in [AGENTS.md](AGENTS.md), not by the title alone. Release Please reads these titles from the squash commits on `main`: `fix` and `feat` drive the version bump, and the other types only shape the changelog.

Examples:

```text
fix: isolate missing-body validation errors
feat(validation): add a custom error formatter
docs(readme): clarify the local setup steps
refactor!: rename the public configuration keys
```

Not accepted: `[Bug] crash on save` (bracket prefix, no type), `Fix: crash on save` (uppercase type), `feature: add export` (type not in the table), `fix: crash on save.` (trailing period), `fix: isolate missing-body validation errors (#503)` (the pull request number belongs in the body).

Pull requests are squash-merged and the pull request title becomes the final commit title. GitHub appends the pull request number by itself, so `fix: isolate missing-body validation errors` lands on `main` as `fix: isolate missing-body validation errors (#503)`. Do not write that number into the title yourself — the check rejects a title ending in `(#123)`, because it would be doubled. Link the issue from the pull request body instead, for example `Closes #503`. The **PR title** check validates the format whenever a pull request is opened, edited, reopened, or updated. Individual commits on a branch are not checked.

Issue titles are not enforced. Anyone can open an issue without knowing this convention; maintainers adjust the title during triage.

## Releases

Merging to `main` does not publish a release.

Release Please keeps an open **Release PR** showing what the next version would
be; merging that PR is what cuts the release, and it is what creates the `v*`
tag that starts the publish workflow. Publishing happens only after the release
verification requirements have been satisfied. Contributors never need to bump a
version or tag anything in an ordinary pull request.


See `AGENTS.md` for the maintainer-only release procedure.

## Code of Conduct

Be respectful and inclusive. See our [Code of Conduct](CODE_OF_CONDUCT.md) for details.
