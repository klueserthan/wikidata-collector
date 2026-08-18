# `.claude/` — Claude Code project configuration

Everything an agent session needs, checked into the repo.

| Path                  | Purpose                                                              |
| --------------------- | -------------------------------------------------------------------- |
| `settings.json`       | Shared hooks and the permission allowlist. Committed.                 |
| `settings.local.json` | Personal overrides. Gitignored — never commit.                        |
| `hooks/`              | Guardrail scripts wired up from `settings.json`.                      |
| `skills/`             | Symlinks onto `.agents/skills/`, installed by `skills.sh`.            |

Repo-level conventions the skills read — issue tracker, triage labels, domain
doc layout — live in `docs/agents/`.

## Hooks

| Hook                     | Fires on                    | Behaviour                                                              |
| ------------------------ | --------------------------- | ---------------------------------------------------------------------- |
| `hooks/guard-merge.sh`   | `PreToolUse` (Bash)         | Blocks `gh pr merge`, `git merge`, pushes to `main`, and forced pushes. |
| `hooks/guard-paths.sh`   | `PreToolUse` (Edit\|Write)  | Blocks writes to `.env*` secrets, `.venv/`, and the vendored skills.    |
| `hooks/ruff-fix.sh`      | `PostToolUse` (Edit\|Write) | Formats and lint-fixes the edited Python file; blocks on leftovers.     |
| `hooks/unit-tests.sh`    | `Stop`                      | Runs `pytest tests/unit` when Python changed, so a turn never ends red. |

## Skills

Skills are vendored from `mattpocock/skills`, not authored here. The real files
live in `.agents/skills/`; `.claude/skills/<name>` symlinks onto them and
`skills-lock.json` at the repo root pins each one by content hash. Refresh them
by re-running `skills.sh` — `guard-paths.sh` blocks manual edits so the lockfile
cannot drift from the tree.

## MCP servers

This repo defines none. If one is added later, put it in a committed `.mcp.json`
at the repo root (`{"mcpServers": {...}}`) and allowlist its tools under
`permissions.allow` in `settings.json`.
