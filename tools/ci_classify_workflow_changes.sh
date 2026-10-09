#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
changed_files="$(mktemp)"
trap 'rm -f "$changed_files"' EXIT

fail_safe() {
  printf 'docs_only=false\ndocs_changed=true\nfull_required=true\n' >> "$GITHUB_OUTPUT"
}

fail_safe
if ! "$script_dir/ci_collect_changed_files.sh" "$@" > "$changed_files"; then
  exit 0
fi

cat "$changed_files"
if ! "$script_dir/ci_classify_changes.sh" < "$changed_files" >> "$GITHUB_OUTPUT"; then
  exit 0
fi
