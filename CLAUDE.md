# CLAUDE.md — wikidata-collector

Python library that streams normalized Wikidata entities (public figures, public
institutions) over SPARQL. Pure library: no web framework, no database, no CLI.

## Commands

```bash
uv sync --dev                          # install
uv run pytest tests/unit               # fast suite — no network, no sleeping
uv run pytest                          # unit + integration (live tests excluded)
uv run pytest -m live                  # hits real Wikidata; opt in deliberately
.github/scripts/pre-commit-checks.sh   # everything CI runs, in CI's order
```

CI gates, in order: `ruff format --check` → `ruff check` → `pyright` → unit tests
with a coverage floor → integration tests → package build. All five must pass
before merge.

## Rules

- **TDD.** Write the failing test first. Every function gets tests and a
  Google-style docstring.
- **Fail fast.** Validate inputs and raise. No compatibility shims, no silent
  fallbacks, no broad `except`. Delete obsolete code rather than branching around
  it.
- **SPARQL is never string-concatenated from user input.** Values pass
  `validate_qid` / `validate_pid` / `escape_sparql_literal`, and human-readable
  labels resolve through `constants.py` mappings only — unknown labels raise.
- **One pipeline.** Entity retrieval is a single generic pipeline in `client.py`
  parameterized by `_EntitySpec`. A new entity kind adds a spec row, a record
  family, and a query builder — not a second pipeline.
- **One name per concept.** Filter vocabulary is fixed in `CONTEXT.md` and must
  read identically in the public method, the pipeline, and the query builder.
- **Never merge.** Do not run `gh pr merge`, `git merge` onto `main`, or push to
  `main`. Hand the PR back; the user merges. A `guard-merge` hook enforces this.
  Resolve conflicts on the PR branch.
- **Atomic commits.** One task, one commit.

## Where to look

| Question                                    | File                          |
| ------------------------------------------- | ----------------------------- |
| What does a term mean? Which filter name?   | `CONTEXT.md`                  |
| Why is it built this way?                   | `docs/adr/`                   |
| Style, naming, types, testing detail        | `docs/conventions.md`         |
| Runtime settings and defaults               | `wikidata_collector/config.py`|
| Public API surface                          | `wikidata_collector/__init__.py` |
| Install, usage, examples                    | `README.md`                   |
| Dependencies and tool config                | `pyproject.toml`              |

## Agent workflow

Issues live in GitHub (`klueserthan/wikidata-collector`) — see
`docs/agents/issue-tracker.md` for `gh` usage and
`docs/agents/triage-labels.md` for the label vocabulary. File any bug or
improvement you discover in passing as its own issue, using the matching
template and label (`bug` / `enhancement`) plus `needs-triage`. Skip filing for
work already covered by an open PR.
