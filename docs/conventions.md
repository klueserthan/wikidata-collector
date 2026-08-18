# Conventions

Long-form reference for `wikidata-collector`. `CLAUDE.md` carries the rules every
agent needs on every task; this file carries the detail you look up when you are
actually editing a particular file.

## Repository map

```
wikidata_collector/
├── __init__.py              # Public API — the export list IS the contract
├── client.py                # WikidataClient: entity pipeline, retries, pagination
├── config.py                # WikidataCollectorConfig (constructor args + env vars)
├── constants.py             # COUNTRY_MAPPINGS, TYPE_MAPPINGS, PROFESSION_MAPPINGS,
│                            #   GENDER_MAPPINGS — the only label→QID translation
├── exceptions.py            # WikidataCollectorError hierarchy
├── models.py                # Pydantic record families + normalize_bindings
├── proxy.py                 # ProxyManager: rotation, cooldown, SSRF validation
├── security.py              # validate_qid, validate_pid, escape_sparql_literal
└── query_builders/
    ├── figures_query_builder.py
    └── organizations_query_builder.py

tests/
├── conftest.py              # Shared fixtures and SPARQL binding builders
├── unit/                    # Fast, no network, no real sleeping
└── integration/             # Full pipeline over mocked HTTP (@pytest.mark.integration)
                             #   @pytest.mark.live hits real Wikidata; excluded from CI
```

Domain vocabulary lives in `CONTEXT.md`; architectural decisions in `docs/adr/`.

## Types

- Python ≥ 3.13. `pyright` in `basic` mode over `wikidata_collector` and `tests`.
- Every function signature is annotated.
- Prefer modern syntax in new files (`list[str]`, `str | None`). Existing modules
  use `typing.List` / `Optional` — match the file you are editing rather than
  mixing both in one module.

## Formatting and linting

`ruff` is the only formatter and linter. Line length 100, `E501` ignored,
rules `E`, `F`, `I`, `N`, `W`, target `py313`. Imports group stdlib →
third-party → local, local imports relative (`from .config import ...`).

Adding another type checker or linter needs agreement first — ruff plus pyright
is the project standard.

## Naming

| Kind                | Convention          | Example                            |
| ------------------- | ------------------- | ---------------------------------- |
| Classes             | `PascalCase`        | `WikidataClient`                   |
| Functions / methods | `snake_case`        | `build_public_figures_query`       |
| Constants           | `UPPER_SNAKE_CASE`  | `DEFAULT_LIMIT`, `TYPE_MAPPINGS`   |
| Private             | `_prefix`           | `_parse_date`, `_fetch_page`       |
| Public iterators    | `iterate_*`         | `iterate_public_figures`           |
| Internal iterators  | `_iterate`, `iter_*`| `_paginate_sparql_results`         |

Filter names are fixed end to end — public method, pipeline, and query builder
all use the same word. The table lives in `CONTEXT.md`; do not introduce a
synonym at any layer.

## Docstrings

Google style on every public function and class, with `Args:`, `Returns:`, and
`Raises:` where they apply. Modules open with a triple-quoted docstring.

## Errors

- Every custom exception subclasses `WikidataCollectorError` and lives in
  `exceptions.py`: `InvalidQIDError`, `InvalidFilterError`, `EntityNotFoundError`,
  `QueryExecutionError`, `ProxyMisconfigurationError`, `ProxyUnavailableError`,
  `UpstreamUnavailableError`.
- Validate early and raise — no silent fallbacks, no compatibility shims, no
  broad `except Exception` that swallows.
- Never swallow: log with context and re-raise, or wrap in a project exception.
- Log with `extra={}` so fields stay machine-parseable. The vocabulary in use:
  `event`, `query_type`, `entity_kind`, `latency_ms`, `result_count`,
  `error_category`, `attempt`, `proxy`.

## Models

- Pydantic v2 `BaseModel` subclasses in `models.py`.
- Two tiers per entity kind: `*WikiRecord` parses one raw SPARQL row;
  `*NormalizedRecord` aggregates consecutive same-QID rows into list fields.
- `entity_kind` is the discriminator on every model; `qid` is the identifier,
  with `.id` kept as an alias.
- Multi-valued fields are `List[str]` (or `List[AccountEntry]`) defaulting to an
  empty list.
- `normalize_bindings` is the single entry point for row → record folding.
  Adding an entity kind means adding a record family, a query builder, and an
  `_EntitySpec` row — never a second pipeline.

## SPARQL security

Non-negotiable, and the reason `security.py` carries a 100% coverage floor:

- Every user-supplied value reaching a query passes `validate_qid()` (`^Q\d+$`),
  `validate_pid()` (`^P\d+$`), or `escape_sparql_literal()`.
- Human-readable labels resolve to QIDs only through the `constants.py` mappings.
  An unknown label raises — it is never interpolated into the query.
- Any new filter needs an injection test alongside its happy-path test.

## Testing

- TDD: the failing test lands before the implementation.
- Group with `class Test<Subject>:`; name tests `test_<what_it_does>` — spelled
  out, no abbreviations.
- Mock external calls with `pytest-mock`'s `mocker`, or the shared fixtures in
  `tests/conftest.py`.
- Unit tests never sleep and never touch the network, and both are enforced by
  autouse fixtures in `tests/unit/conftest.py`: `recorded_sleeps` swaps
  `time.sleep` for a recorder tests can assert on, and `no_network` blocks
  `socket.connect`. The integration suite records sleeps the same way, except on
  `live` tests.
- Markers: `integration` (full pipeline over mocked HTTP), `iterator`, `live`.
  `live` is deselected by default; opt in with `uv run pytest -m live`.
- Shared builders live in `tests/conftest.py`: `sparql_response`,
  `figure_binding`, `organization_binding`, `make_config`, `make_client`,
  `figure_page`, `organization_page`. Reach for those before hand-rolling a
  SPARQL envelope.
- The public surface is pinned by `tests/unit/test_public_api.py`. Changing
  `__all__`, a public signature, or the filter vocabulary means updating that
  test deliberately — which is the point.
- Warnings are errors. If a dependency emits one that cannot be fixed, add a
  narrow `filterwarnings` entry in `pyproject.toml` with a comment saying why.
