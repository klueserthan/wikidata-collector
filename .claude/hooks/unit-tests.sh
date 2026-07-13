#!/usr/bin/env bash
# Stop: before finishing, run the unit-test suite (the CI `unit-tests` gate) when
# Python under wikidata_collector/ or tests/ changed. Blocks (exit 2) on failure
# so a turn never ends with a red suite. Non-code turns skip the run and stay cheap.
set -euo pipefail

input="$(cat)"

# Infinite-loop guard: if this stop is already the result of our hook blocking,
# let it stop rather than re-verifying forever.
active="$(printf '%s' "$input" | jq -r '.stop_hook_active // false')"
[ "$active" = "true" ] && exit 0

# Only run when Python under wikidata_collector/ or tests/ actually changed.
changed="$(git status --porcelain -- wikidata_collector tests 2>/dev/null | grep -E '\.py$' || true)"
[ -z "$changed" ] && exit 0

if ! out="$(uv run pytest tests/unit/ -q 2>&1)"; then
  {
    echo "Unit tests are failing — fix them before finishing:"
    printf '%s\n' "$out" | tail -n 40
  } >&2
  exit 2
fi

exit 0
