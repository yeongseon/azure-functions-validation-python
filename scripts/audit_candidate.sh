#!/usr/bin/env bash
set -euo pipefail
wheel=$(realpath "${1:?candidate wheel required}")
output="$(pwd)/test-results/runtime-audit"
mkdir -p "$output"
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
python -m venv "$scratch/runtime"
"$scratch/runtime/bin/python" -m pip install --disable-pip-version-check "$wheel"
"$scratch/runtime/bin/python" -m pip check
"$scratch/runtime/bin/python" -m pip freeze --exclude azure-functions-validation > "$output/runtime.txt"
test -s "$output/runtime.txt"
python -m venv "$scratch/auditor"
"$scratch/auditor/bin/python" -m pip install --disable-pip-version-check 'pip-audit==2.10.0'
rm -f "$output/audit.json"
status=0
"$scratch/auditor/bin/python" -m pip_audit --strict --no-deps --disable-pip \
  -r "$output/runtime.txt" --format json --output "$output/audit.json" || status=$?
python scripts/check_runtime_audit.py "$output/audit.json" "$status"
