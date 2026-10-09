#!/usr/bin/env bash
set -euo pipefail

event_name="$1"
base_sha="$2"
head_sha="$3"
head_repository="$4"
repository="$5"
pr_number="$6"
before_sha="$7"
sha="$8"

if [ "$event_name" = pull_request ]; then
  if [ "$head_repository" != "$repository" ] && ! git cat-file -e "${head_sha}^{commit}"; then
    git fetch --no-tags origin "pull/${pr_number}/head"
  fi
  git diff --name-only --no-renames "${base_sha}...${head_sha}"
  exit 0
fi

if [ -z "$before_sha" ] || [[ "$before_sha" =~ ^0+$ ]]; then
  exit 1
fi

git cat-file -e "${before_sha}^{commit}"
git merge-base --is-ancestor "$before_sha" "$sha"
git diff --name-only --no-renames "$before_sha" "$sha"
