#!/usr/bin/env bash
# Validate actual job results against the classifier's expected run/skip state.
set -euo pipefail

event_name="$1"
docs_changed="$2"
full_required="$3"

declare -A results=()
while IFS='=' read -r job result; do
  [ -z "$job" ] && continue
  results["$job"]="$result"
done

check_result() {
  local job="$1"
  local expected="$2"
  local actual="${results[$job]:-missing}"
  printf '%s result: %s (expected %s)\n' "$job" "$actual" "$expected"
  if [ "$actual" != "$expected" ]; then
    return 1
  fi
}

check_result changes success

if [ "$event_name" = pull_request ]; then
  check_result format success
else
  check_result format skipped
fi

if [ "$docs_changed" = true ]; then
  check_result docs-check success
else
  check_result docs-check skipped
fi

if [ "$full_required" = true ]; then
  expected_full=success
else
  expected_full=skipped
fi

for job in quality test minimum-dependencies artifact-build artifact-python310-negative \
  artifact-python311 azure-functions-2x host-smoke; do
  check_result "$job" "$expected_full"
done
