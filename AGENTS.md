# AGENTS.md — Wikidata Collector

> Python ETL library for streaming Wikidata entities via SPARQL. Pure library — no web framework.

## Build & Run Commands

```bash
# Install dependencies
uv sync --dev

# Type checking (required before commit)
uv run pyright wikidata_collector tests

# Lint (check only — CI mode)
uv run ruff check wikidata_collector tests

# Lint (auto-fix)
uv run ruff check --fix wikidata_collector tests

# Format (auto-fix)
uv run ruff format wikidata_collector tests

# Format (check only — CI mode)
uv run ruff format --check wikidata_collector tests

# Run ALL tests
uv run pytest

# Unit tests only
uv run pytest tests/unit -v

# Integration tests (non-live)
uv run pytest tests/integration -v -m "not live"

# Single test file
uv run pytest tests/unit/test_sparql_builders.py -v

# Single test by name
uv run pytest tests/unit/test_sparql_builders.py::TestBuildPublicFiguresQuery::test_basic_query -v

# Tests by marker
uv run pytest -m iterator -v
uv run pytest -m "not integration" -v

# Coverage
uv run pytest --cov=wikidata_collector --cov-report=term

# Full pre-commit (runs all CI checks)
.github/scripts/pre-commit-checks.sh
```

## CI Pipeline (must pass before merge)

1. `uv run pyright wikidata_collector tests` — type checking
2. `uv run ruff format --check wikidata_collector tests` — format check
3. `uv run ruff check wikidata_collector tests` — lint check
4. `uv run pytest tests/unit -v --cov=wikidata_collector` — unit tests + coverage
5. `uv run pytest tests/integration -v -m "not live"` — integration tests

## Code Style

### Python Version & Types
- **Python ≥ 3.13** (`.python-version` = 3.13)
- Modern type hints: `list[str]`, `dict[str, Any]`, `str | None` (NOT `List[str]`, `Optional[str]`)
  - NOTE: Current code uses `Optional`/`List`/`Dict` from `typing` — follow existing file style when editing, but prefer modern syntax for new files
- Type checker: **pyright** in `basic` mode
- All function signatures must have type annotations

### Formatting & Linting
- **ruff** — linter and formatter
- Line length: **100** characters
- Rules: `E`, `F`, `I` (isort), `N` (naming), `W` — `E501` (line length) is ignored
- Target: `py313`

### Imports
- Group order: stdlib → third-party → local (enforced by ruff `I`)
- Local imports use relative paths: `from .config import WikidataCollectorConfig`
- Blank line between groups

### Naming
- Classes: `PascalCase` (`WikidataClient`, `PublicFigureNormalizedRecord`)
- Functions/methods: `snake_case` (`build_public_figures_query`, `validate_qid`)
- Constants: `UPPER_SNAKE_CASE` (`DEFAULT_LIMIT`, `TYPE_MAPPINGS`)
- Private: `_prefix` (`_parse_date`, `_paginate_sparql_results`)
- Iterator methods: `iterate_` prefix for public API, `iter_` prefix for internal

### Docstrings
- Google-style docstrings on all public functions/classes
- Include `Args:`, `Returns:`, `Raises:` sections
- Module-level docstrings in triple quotes

### Error Handling
- Custom exceptions in `wikidata_collector/exceptions.py`
- Hierarchy: `WikidataCollectorError` (base) → `InvalidQIDError`, `InvalidFilterError`, `EntityNotFoundError`, `QueryExecutionError`, `ProxyMisconfigurationError`, `UpstreamUnavailableError`
- Validate inputs early (fail-fast): dates, QIDs, filter params
- Never swallow exceptions — log and re-raise or wrap
- Use structured logging with `extra={}` dict for machine-parseable fields

### Models
- **Pydantic v2** `BaseModel` subclasses in `models.py`
- Two-tier: `*WikiRecord` (raw SPARQL row) → `*NormalizedRecord` (aggregated, multi-valued)
- `entity_kind` discriminator field on all models (`Literal["public_figure"]`)
- `qid` as primary identifier; `.id` property alias for compatibility
- Multi-valued fields as `List[str]` with `default_factory=list` or `= []`

### SPARQL Security (CRITICAL)
- ALL user inputs in SPARQL must pass `validate_qid()` or `escape_sparql_literal()`
- QIDs: `^Q\d+$` — PIDs: `^P\d+$`
- Label-to-QID translation via `constants.py` mappings (reject unknown labels)

## Architecture

```
wikidata_collector/
├── __init__.py              # Public API exports
├── client.py                # WikidataClient — main entry point, iterators, pagination
├── config.py                # WikidataCollectorConfig (env vars + dotenv)
├── constants.py             # COUNTRY_MAPPINGS, TYPE_MAPPINGS, PROFESSION_MAPPINGS
├── exceptions.py            # Custom exception hierarchy
├── models.py                # Pydantic models (WikiRecord + NormalizedRecord)
├── proxy.py                 # ProxyManager — rotation, retry, cooldown
├── security.py              # validate_qid, validate_pid, escape_sparql_literal
└── query_builders/
    ├── figures_query_builder.py
    └── institutions_query_builder.py

tests/
├── conftest.py              # Shared fixtures (wikidata_client, sample_sparql_response)
├── unit/                    # Fast, no network (mock everything)
└── integration/             # Mocked HTTP but full pipeline; @pytest.mark.integration
                             # @pytest.mark.live for real Wikidata calls (excluded in CI)
```

## Testing Conventions

- **TDD workflow**: write failing test → implement → refactor
- Test classes group related tests: `class TestBuildPublicFiguresQuery:`
- Test names: `test_<what_it_does>` — descriptive, no abbreviations
- Mock external calls with `pytest-mock` (`mocker` fixture)
- Markers: `@pytest.mark.integration`, `@pytest.mark.iterator`, `@pytest.mark.live`
- Shared fixtures in `tests/conftest.py`
- Security functions need 100% coverage including injection attempts

## Key Patterns

- **Iterator API** (`iterate_public_figures`, `iterate_public_institutions`): keyword-only args, accepts human-readable labels, validates inputs, handles pagination internally, yields `NormalizedRecord` objects
- **Lower-level API** (`get_public_figures`, `get_public_institutions`): returns `Tuple[List[NormalizedRecord], str]` (records + proxy used)
- **Keyset pagination**: uses `after_qid` param, ordered by numeric QID — preferred over OFFSET
- **Structured logging**: all log calls use `extra={}` with fields like `event`, `query_type`, `latency_ms`, `result_count`, `error_category`

## Specs & Reference Docs

Before implementing features, consult `specs/001-wikidata-etl-package/`:
- `spec.md` — user stories, acceptance criteria
- `contracts/python-api.md` — exact API signatures
- `data-model.md` — Pydantic model field specs
- `research.md` — design decisions and rationales
- `tasks.md` — implementation checklist
