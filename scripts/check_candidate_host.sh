#!/usr/bin/env bash
set -euo pipefail
wheel=$(realpath "${1:?candidate wheel required}")
root=$(pwd)
output="$root/test-results/candidate-host"
mkdir -p "$output"
command -v func >/dev/null
command -v curl >/dev/null
scratch=$(mktemp -d)
host_pid=""
cleanup() {
  if [ -n "$host_pid" ]; then kill -KILL -- "-$host_pid" 2>/dev/null || true; wait "$host_pid" 2>/dev/null || true; fi
  rm -rf "$scratch"
}
trap cleanup EXIT
"${HOST_PYTHON:-python3.11}" -m venv "$scratch/venv"
"$scratch/venv/bin/python" -m pip install --disable-pip-version-check "$wheel"
cp tests/host_smoke/function_app.py "$scratch/function_app.py"
printf '{"version":"2.0"}\n' > "$scratch/host.json"
"$scratch/venv/bin/python" -I - "$wheel" > "$output/identity.txt" <<'PY'
import importlib.metadata
from pathlib import Path
import sys
import zipfile
import azure_functions_validation as package
with zipfile.ZipFile(sys.argv[1]) as archive:
    metadata = archive.read(next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA'))).decode()
expected = next(line.removeprefix('Version: ') for line in metadata.splitlines() if line.startswith('Version: '))
assert importlib.metadata.version('azure-functions-validation') == expected
assert Path(package.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
print(expected, package.__file__)
PY
run_host() {
  local mode="$1"
  port=$("$scratch/venv/bin/python" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')
  (cd "$scratch"; exec env PATH="$scratch/venv/bin:$PATH" VIRTUAL_ENV="$scratch/venv" \
    FUNCTIONS_WORKER_RUNTIME=python AzureWebJobsStorage="" BROKEN_VALIDATION_WRAPPER="$mode" \
    setsid func start --python --port "$port") > "$output/host-$mode.log" 2>&1 &
  host_pid=$!
}
probe() {
  local attempt status
  for attempt in {1..45}; do
    if ! kill -0 "$host_pid" 2>/dev/null; then return 1; fi
    if curl --max-time 3 --silent --fail "http://127.0.0.1:$port/api/smoke" > "$output/smoke.json"; then break; fi
    sleep 1
  done
  [ "$(< "$output/smoke.json")" = '{"function_name":"smoke"}' ] || return 1
  status=$(curl --silent -o "$output/valid.json" -w '%{http_code}' \
    -H 'Content-Type: application/json' -d '{"name":"candidate"}' "http://127.0.0.1:$port/api/validated")
  [ "$status" = 200 ] && [ "$(< "$output/valid.json")" = '{"function_name":"candidate"}' ] || return 1
  status=$(curl --silent -o "$output/malformed.json" -w '%{http_code}' \
    -H 'Content-Type: application/json' -d 'broken' "http://127.0.0.1:$port/api/validated")
  [ "$status" = 400 ] || return 1
  status=$(curl --silent -o "$output/invalid.json" -w '%{http_code}' \
    -H 'Content-Type: application/json' -d '{}' "http://127.0.0.1:$port/api/validated")
  [ "$status" = 422 ] || return 1
  status=$(curl --silent -o "$output/response.json" -w '%{http_code}' "http://127.0.0.1:$port/api/invalid-response")
  [ "$status" = 500 ] || return 1
  ! grep -q 'must not leak' "$output/response.json" || return 1
  status=$(curl --silent -o "$output/scalar-default.json" -w '%{http_code}' "http://127.0.0.1:$port/api/scalar-sync")
  [ "$status" = 200 ] || return 1
  status=$(curl --silent -D "$output/envelope.headers" -o "$output/envelope.json" -w '%{http_code}' \
    -H 'Content-Type: application/json' -d '{"name":"created"}' "http://127.0.0.1:$port/api/envelope")
  [ "$status" = 201 ] || return 1
  grep -qi 'Location: /api/envelope/1' "$output/envelope.headers" || return 1
  ! grep -qi 'secret\|envelope-private' "$output/envelope.json" || return 1
  status=$(curl --silent -D "$output/envelope-async.headers" -o "$output/envelope-async.json" -w '%{http_code}' \
    "http://127.0.0.1:$port/api/envelope-async")
  [ "$status" = 201 ] || return 1
  grep -qi 'Location: /api/envelope/2' "$output/envelope-async.headers" || return 1
  [ "$(grep -ic '^Set-Cookie:' "$output/envelope-async.headers")" = 2 ] || return 1
  grep -qi '^Set-Cookie: first=1' "$output/envelope-async.headers" || return 1
  grep -qi '^Set-Cookie: second=2' "$output/envelope-async.headers" || return 1
  ! grep -qi 'secret\|envelope-private' "$output/envelope-async.json" || return 1
  status=$(curl --silent -D "$output/envelope-empty.headers" -o "$output/envelope-empty.body" -w '%{http_code}' \
    "http://127.0.0.1:$port/api/envelope-empty")
  [ "$status" = 204 ] && [ ! -s "$output/envelope-empty.body" ] || return 1
  grep -qi 'X-Empty: yes' "$output/envelope-empty.headers" || return 1
  status=$(curl --silent -D "$output/problem.headers" -o "$output/problem.json" -w '%{http_code}' \
    -H 'Content-Type: application/json' -d '{}' "http://127.0.0.1:$port/api/problem")
  [ "$status" = 400 ] || return 1
  grep -qi 'Content-Type: application/problem+json' "$output/problem.headers" || return 1
  grep -qi 'X-Error-Contract: fixed' "$output/problem.headers" || return 1
  status=$(curl --silent -o "$output/problem-valid.json" -w '%{http_code}' \
    -H 'Content-Type: application/json' -d '{"name":"candidate"}' "http://127.0.0.1:$port/api/problem")
  [ "$status" = 200 ] || return 1
  status=$(curl --silent -D "$output/invalid-error.headers" -o "$output/invalid-error.json" -w '%{http_code}' \
    -H 'Content-Type: application/json' -d '{}' "http://127.0.0.1:$port/api/invalid-error")
  [ "$status" = 500 ] || return 1
  ! grep -qi 'secret' "$output/invalid-error.json" || return 1
  grep -qi 'Content-Type: application/json' "$output/invalid-error.headers" || return 1
  status=$(curl --silent -o "$output/scalar-invalid.json" -w '%{http_code}' "http://127.0.0.1:$port/api/scalar-sync?page=0")
  [ "$status" = 422 ] || return 1
  status=$(curl --silent -o "$output/scalar-list.json" -w '%{http_code}' "http://127.0.0.1:$port/api/scalar-async?tags=a&tags=b")
  [ "$status" = 200 ] || return 1
  "$scratch/venv/bin/python" - "$output" <<'PY'
import json
from pathlib import Path
import sys
output = Path(sys.argv[1])
assert json.loads((output / 'envelope.json').read_text()) == {'function_name': 'created'}
assert json.loads((output / 'envelope-async.json').read_text()) == {'function_name': 'envelope_async'}
assert json.loads((output / 'problem.json').read_text()) == {'title': 'Invalid request', 'status': 400}
assert json.loads((output / 'problem-valid.json').read_text()) == {'function_name': 'problem', 'name': 'candidate'}
assert json.loads((output / 'invalid-error.json').read_text()) == {'detail': [{'loc': [], 'msg': 'Internal Server Error', 'type': 'server_error'}], 'error_format_version': 1}
assert json.loads((output / 'scalar-default.json').read_text()) == {'page': 1, 'function_name': 'scalar_sync'}
assert json.loads((output / 'scalar-invalid.json').read_text())['detail'][0]['loc'] == ['query', 'page']
assert json.loads((output / 'scalar-list.json').read_text()) == {'tags': ['a', 'b'], 'function_name': 'scalar_async'}
PY
}
run_host 0
probe
kill -KILL -- "-$host_pid"; wait "$host_pid" || true
host_pid=""
run_host 1
if probe; then
  echo 'Broken wrapper unexpectedly passed the host behavior proof' >&2
  exit 1
fi
grep -q 'Worker failed to index functions' "$output/host-1.log"
grep -q 'InternalResponse.*does not match binding type' "$output/host-1.log"
echo 'Candidate host behavior passed; broken-wrapper negative control failed as required.'
