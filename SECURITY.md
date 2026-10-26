# Security Policy

## Candidate runtime advisory gate

The release `runtime-dependency-audit` matrix installs the exact built wheel in a
fresh environment on Python 3.11–3.14 and audits its resolved runtime closure.
`make audit-candidate CANDIDATE_WHEEL=/absolute/path/to/candidate.whl` reproduces
the gate on the current `python` interpreter. Scanner tools live in a different
environment, so development/scanner dependencies cannot contaminate that closure.
The unpublished candidate itself is excluded from advisory lookup; its dependencies
are not. Runtime advisories return status 1; missing, incomplete or malformed
reports and scanner failures return status 2. Both block publishing, with inventory
and JSON scanner evidence uploaded even on failure. No exception mechanism is
introduced. Development-dependency audit findings remain advisory, not a substitute
for this exact-candidate gate.

Azure host authentication belongs to the route binding, never this decorator.
`expose_internal_errors=True` is unsafe for production: it gives custom formatters
original server-side exceptions. Default 5xx responses and formatter fallback must
not echo request bodies, credentials or Pydantic input. Server-side diagnostic logs
can retain exception details and must be protected separately.

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
