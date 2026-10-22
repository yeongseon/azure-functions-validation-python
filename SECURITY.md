# Security Policy

## Reporting a Vulnerability

We take security seriously. If you discover a vulnerability, please report it
responsibly and avoid public disclosure until a fix is available.

### Preferred: GitHub Security Advisory

1. Go to the [Security Advisories page](https://github.com/yeongseon/azure-functions-validation-python/security/advisories/new)
2. Click "Report a vulnerability"
3. Submit the details in the private advisory

### Alternative: Email

If you prefer email, contact: yeongseon.choe@gmail.com

### What to Include

* A clear description of the issue
* Steps to reproduce
* Impact assessment
* Suggested mitigation or fix, if available

### Response Timeline

* Initial response: within 48 hours
* Status update: within 7 days

## Supported Versions

| Version | Supported |
| ------- | --------- |
| Latest release | :white_check_mark: |
| Older releases | :x: |

## Production trust boundaries

Default 5xx responses and failed formatters contain a fixed public envelope.
Pipeline logs contain fixed diagnostics and handler/source identifiers, not original
exceptions, traceback chains, Pydantic inputs or request bodies. This covers
library-owned logs, not logs emitted by application code, adapters, formatters,
the host or Azure. Handlers returning `HttpResponse` and successful custom
formatters own their content.

`expose_internal_errors=False` is the default. Enabling it passes original 5xx
exceptions to formatters and is **unsafe for production** without application
redaction; it does not automatically recognize/redact secrets. Original 4xx
exceptions are also available to custom formatters. See
[configuration safety](docs/configuration.md#expose_internal_errors).

Authentication is host-owned. Validation preserves route auth levels, rejects the
unsupported above-route decorator order, and never authenticates direct requests.
Configure platform authentication and route auth explicitly. Body-size and JSON
content-type enforcement are opt-in. Use `max_body_bytes` and constrained models
for public input. No implicit error-count/response-size cap or JSON-depth limit
exists: nested invalid arrays can amplify errors. Duplicate JSON keys are
last-value-wins; non-finite numbers require model constraints. These are follow-up
hardening topics, not demonstrated credential leaks. Schema/wheel verification
rejects drift and never rewrites pins.

## Automated controls and permissions

| Control | Runs where | Enforcement |
| --- | --- | --- |
| Bandit 1.9.4 | PR, main, weekly, dispatch | Existing blocking job; all severities reviewed |
| SHA-pinned Semgrep `p/python` | Same workflow | Existing blocking job; execution evidence added |
| CodeQL and SBOM | Existing workflows | Unchanged scanning/reporting controls |
| Runtime pip-audit 2.10.1 | Exact candidate wheel, Python 3.11–3.14 | Blocking dependency of `publish` |
| Runtime/development audit | Weekly/dispatch | Reporting-only with shared classifier |
| Offline trust-boundary tests | Full SDK matrix, 2.x wheel lane, worker nightly | Existing lane enforcement retained |

Security workflows and the new release job use `contents: read` only. Existing
CodeQL security-events permission, Azure OIDC and PyPI OIDC are unchanged. The new
gate replaces no runtime/host/Azure certification and never rebuilds the artifact.
Browser/CDN checks do not apply: this package ships no Swagger UI/browser assets.
Branch-protection requirements remain repository settings, not workflow assertions.

## Static scope and exceptions

`hatch run python -m tools.security_evidence bandit` scans every Python file under
`src/`, `examples/` (including deployed `e2e_app`), `scripts/`, and `tools/`, with
no per-file exclusions. Tests/fixtures are excluded; shipped `conformance.py` is
included. `infra/` contains Bicep, not Python, and requires configuration review.
There is no demo directory. Bytecode/non-Python generated files are not inputs.
Scanned inventory must equal disk, include at least 30 files and have positive LOC.

Bandit uses `--ignore-nosec`: existing conformance assertion markers cannot hide
findings. Every inline marker must match exact ID/file/line policy; unlisted or
blanket skips produce INCOMPLETE. Baseline exceptions cover test-only assertions,
shell-free tooling subprocesses and the literal TOOL_ERROR enum false positive.
No blanket rule skips or new inline suppressions replace review. `make security`
retains its src-only local behavior; CI uses the expanded helper.

Both policies require exact identifiers, reason, owner, added and expiry dates,
with a positive lifetime at most 90 days. Static exceptions use `reviewed-static`
and exact file/line. Dependencies use exact package/advisory and `not-affected`
(independent affectedness evidence) or `fix-not-available` (only while no fix is
listed). Expired exceptions block even when unused; stale exceptions are counted.
Maintainers review evidence before accepting exceptions. Runtime policy starts empty.

## Runtime policy, failure semantics and recovery

Every known runtime advisory blocks, regardless of severity; missing severity is
UNKNOWN, never assumed low. Each supported interpreter is audited because markers
change dependency closures. The candidate venv is created without pip and contains
only the wheel/runtime dependencies; pip-audit runs outside it with `--path`.

Exit statuses: PASS=0; FAIL=1 (findings/expired exceptions); TOOL_ERROR=2
(crash, timeout, malformed evidence, policy/tool/DB failure); INCOMPLETE=3
(empty/missing scope, skipped dependencies, inventory gaps/unlisted suppressions).
Every non-PASS blocks release. Semgrep exposes only action outcome: success PASS,
failure conservatively TOOL_ERROR (unknown finding count), skipped/cancelled
INCOMPLETE. Its original failing step remains blocking.

Advisory DB outages can delay releases: a deliberate availability tradeoff for
fail-closed evidence. Never bypass it. Retry an unchanged tag with
`gh workflow run publish-pypi.yml --ref vX.Y.Z`; changed code/workflows must fix
forward to a new candidate. Trusted OIDC publishing and exact-wheel reuse remain.

## Evidence and deployment review

Helpers emit versioned `security-results/**/summary.json` with check/scope/status,
counts, exit status, tool versions, applied exceptions and allow-listed finding
IDs, relative paths/lines and severities. Markdown summaries go to Job Summary.
Artifact uploads run `always()` and fail on missing evidence. Raw scanner output,
source, advisory descriptions, policy reasons, request bodies, authorization headers
and connection strings are not retained. Generated local evidence is gitignored.
Findings remain code/config review findings until runtime impact is demonstrated.

Examples and anonymous host-smoke apps are local/synthetic demonstrations, not
production authentication templates. `examples/e2e_app` and `infra/main.bicep` are
ephemeral public certification infrastructure. Bicep enforces HTTPS, storage TLS
1.2 and private blobs, but retains shared-key connection strings, public ingress
and an Application Insights connection-string output. Managed identity/RBAC,
private endpoints, explicit SCM/app TLS and removing deployment outputs need
real-Azure certification. This work changes no IaC identity/auth settings.

Azure failure diagnostics print Application Insights exceptions/traces and raw
app logs. Library logs are sanitized and the settings printer hides unclassified
values/package SAS URLs, but host/app logs remain outside that guarantee. Use
synthetic data only; replace raw dumps with allow-listed diagnostics in an
Azure-verified follow-up. Never send real credentials/user data to certification.
