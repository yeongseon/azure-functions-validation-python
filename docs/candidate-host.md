# Candidate-wheel host verification

Build and exercise the wheel locally on Python 3.11 with Functions Core Tools v4:

```bash
make build
make host-candidate CANDIDATE_WHEEL="$(realpath dist/*.whl)"
```

This supersedes the historical Cookbook HTTP host-boot instructions in the release
guide. The release job retains the ID `cookbook-host-smoke` for gate compatibility,
but checks out this repository and executes its own HTTP-only fixture. Cookbook
import smoke remains a separate downstream integration gate. Real Azure candidate
certification remains mandatory and separate; local success is not Azure evidence.

The runner installs the candidate in a fresh non-editable virtual environment,
checks distribution version against wheel metadata and import origin under that
environment, and starts a real Functions host outside the checkout. It uses a
private directory and dynamically selected loopback ports, never shared services.
It checks default request/context binding, custom `trigger_arg_name`, typed body
injection, success serialization without subclass-only fields, malformed JSON 400,
invalid-model 422 and sanitized invalid-response 500.
Envelope routes prove sync/async validated 201 plus Location, subclass-secret
exclusion, real context passthrough and None-to-204 precedence with custom headers.
Curl's raw header capture retains both separate Set-Cookie fields on the async
route; neither a mapping nor a comma-joined cookie assertion stands in for wire
evidence. The existing broken-wrapper negative control remains mandatory.
The fixed-error route proves 400 `application/problem+json`, a preserved custom
header and real `func.Context` passthrough on success. An invalid rich error
response must produce the exact sanitized 500 JSON envelope without secret data.
Sync/async scalar-query routes additionally prove custom request and real
`func.Context` binding, a validated default, constrained-query `422` locations,
and ordered repeated-list input. Native queue output binding registration and
signature-name equality are covered separately against the real SDK, without
requiring Azurite in this HTTP-only gate.

A second host uses the same installed candidate but deliberately replaces the
fixture's decorator with a no-op. The same behavior probe must fail, with the
worker reporting a return-annotation indexing error. A timeout or arbitrary
process failure alone is not accepted as the negative-control proof.

`test-results/candidate-host/` retains import identity, synthetic HTTP responses
and host logs. CI uploads these even on failure. The fixture contains no real
credentials or user payloads. The runner fails rather than skips when tools,
installation, identity, indexing or behavior checks fail.
