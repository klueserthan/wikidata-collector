#!/usr/bin/env bash
# PostToolUse (Edit|Write|MultiEdit): auto-format + lint-fix the edited Python
# file, then block (exit 2) only if unfixable lint issues remain — mirroring the
# CI `ruff format --check` and `ruff check` gates so they can never fail later.
set -euo pipefail

input="$(cat)"
file="$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')"

[ -z "$file" ] && exit 0
case "$file" in
  *.py) ;;
  *) exit 0 ;;
esac
[ -f "$file" ] || exit 0

uv run ruff format "$file" >/dev/null 2>&1 || true
uv run ruff check --fix "$file" >/dev/null 2>&1 || true

# Re-check; surface any remaining (unfixable) issues back to the model.
if ! out="$(uv run ruff check "$file" 2>&1)"; then
  {
    echo "ruff found issues in $file that need a manual fix before continuing:"
    echo "$out"
  } >&2
  exit 2
fi

exit 0
