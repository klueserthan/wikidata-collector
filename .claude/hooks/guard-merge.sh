#!/usr/bin/env bash
# PreToolUse (Bash): block Claude-initiated merges and direct pushes to main.
# Merging a PR is a human-control gate — the user merges manually, after the
# GitHub Copilot review comments land. This hook exits 2 so the merge tool call
# never runs and control returns to the user.
set -euo pipefail

input="$(cat)"
cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // empty')"
[ -z "$cmd" ] && exit 0

deny() {
  echo "BLOCKED: $1" >&2
  echo "Do not merge. Report the PR as ready and let the user merge it themselves once the GitHub Copilot review comments have landed." >&2
  exit 2
}

# `gh pr merge` — the primary offender.
if printf '%s' "$cmd" | grep -Eq '(^|[^[:alnum:]_-])gh[[:space:]]+pr[[:space:]]+merge([^[:alnum:]_-]|$)'; then
  deny "'gh pr merge' merges a PR — that's a human-only action."
fi

# `git merge` as a standalone verb — but NOT `git merge-base`.
if printf '%s' "$cmd" | grep -Eq '(^|[^[:alnum:]_-])git[[:space:]]+merge([[:space:]]|$)'; then
  deny "'git merge' integrates branches — that's a human-only action."
fi

# `git push` to main/master, or any forced push.
if printf '%s' "$cmd" | grep -Eq '(^|[^[:alnum:]_-])git[[:space:]]+push([[:space:]].*)?'; then
  if printf '%s' "$cmd" | grep -Eq '(^|[^[:alnum:]_-])git[[:space:]]+push([[:space:]].*)?([[:space:]]|:)(main|master)([^[:alnum:]_/-]|$)'; then
    deny "direct 'git push' to main/master — that's a human-only action."
  fi
  if printf '%s' "$cmd" | grep -Eq '(^|[^[:alnum:]_-])git[[:space:]]+push([[:space:]].*)?[[:space:]](-f|--force|--force-with-lease)([[:space:]=]|$)'; then
    deny "forced 'git push' — that's a human-only action."
  fi
fi

exit 0
