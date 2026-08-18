#!/usr/bin/env bash
# PreToolUse (Edit|Write|MultiEdit): deny writes to real secrets files and to
# vendored/generated trees. The tracked *.example templates stay editable.
set -euo pipefail

input="$(cat)"
file="$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')"
[ -z "$file" ] && exit 0

base="$(basename "$file")"
deny() { echo "BLOCKED: $1" >&2; exit 2; }

# Allow the tracked example templates explicitly.
case "$base" in
  *.example) exit 0 ;;
esac

# Real secrets: any .env / .env.<env> file (e.g. .env, .env.production, .env.bak).
case "$base" in
  .env|.env.*) deny "'$base' is a real secrets file. Edit a tracked '.env.*.example' template instead." ;;
esac
case "$file" in
  *.env) deny "'$file' looks like a secrets/env file. Edit a tracked '.env.*.example' template instead." ;;
esac

# Vendored / generated trees that must not be hand-edited.
case "$file" in
  */.agents/skills/*|.agents/skills/*|*/.claude/skills/*|.claude/skills/*)
    deny "the skills tree is vendored from mattpocock/skills and pinned by skills-lock.json — re-run skills.sh instead of editing it by hand." ;;
  */.venv/*|.venv/*)
    deny "the .venv virtualenv is generated — change pyproject.toml and run 'uv sync' instead." ;;
esac

exit 0
