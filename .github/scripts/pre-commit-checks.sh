#!/usr/bin/env bash
# Run everything CI runs, in CI's order, so a push cannot fail on something that
# was checkable locally. Stops at the first failure.
#
# Usage: .github/scripts/pre-commit-checks.sh [--fix]
#   --fix   format and lint-fix in place before checking, instead of only checking
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

TARGETS=(wikidata_collector tests)
FIX=0
[ "${1:-}" = "--fix" ] && FIX=1

SMOKE_DIR="$(mktemp -d)"
trap 'rm -rf "$SMOKE_DIR"' EXIT

step() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

step "Sync dependencies"
uv sync --locked --dev

if [ "$FIX" -eq 1 ]; then
  step "Format and lint-fix (ruff)"
  uv run ruff format "${TARGETS[@]}"
  uv run ruff check --fix "${TARGETS[@]}"
fi

step "Format check (ruff)"
uv run ruff format --check "${TARGETS[@]}"

step "Lint (ruff)"
uv run ruff check "${TARGETS[@]}"

step "Type check (pyright)"
uv run pyright "${TARGETS[@]}"

step "Unit tests + coverage gate"
uv run pytest tests/unit -p no:randomly --cov=wikidata_collector --cov-report=term

step "Unit tests (shuffled)"
uv run pytest tests/unit --no-cov -q

step "Integration tests"
uv run pytest tests/integration --no-cov

step "Lockfile check"
uv lock --check

# Mirrors the `package` job: a library that builds but does not import is broken
# for every consumer, and no other check here would notice.
step "Package builds, installs, and imports"
uv build --out-dir "$SMOKE_DIR/dist"
uv venv "$SMOKE_DIR/venv"
uv pip install --quiet --python "$SMOKE_DIR/venv/bin/python" "$SMOKE_DIR"/dist/*.whl
"$SMOKE_DIR/venv/bin/python" -c "
import wikidata_collector as wc
missing = [name for name in wc.__all__ if not hasattr(wc, name)]
assert not missing, f'exported but missing: {missing}'
print('imported', wc.__name__, wc.__version__, '-', len(wc.__all__), 'exports')
"

printf '\n\033[32mAll checks passed.\033[0m\n'
