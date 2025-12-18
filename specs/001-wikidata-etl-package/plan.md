# Implementation Plan: Wikidata Public Entities ETL Package

**Branch**: `001-wikidata-etl-package` | **Date**: 2025-12-18 | **Spec**: specs/001-wikidata-etl-package/spec.md
**Input**: Feature specification from `specs/001-wikidata-etl-package/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Implement a pure-Python ETL library that streams public figures and public institutions from the
Wikidata SPARQL endpoint via iterator-based APIs, normalizes results into Pydantic v2 models, and
handles internal SPARQL pagination, logging, and error handling. As part of this plan, we will
also define live, non-proxy integration tests that verify direct connectivity to the official
Wikidata SPARQL endpoint, validate that our query templates execute successfully, and confirm that
typical queries return data within an acceptable time budget.

## Technical Context

**Language/Version**: Python ≥ 3.13 (CPython)
**Primary Dependencies**: Pydantic v2, requests, python-dotenv, pytest (+ pytest-mock, pytest-cov),
ruff, pyright
**Storage**: N/A (reads from Wikidata SPARQL endpoint only; no persistent storage)
**Testing**: pytest test suite (`tests/unit`, `tests/integration`) with type checking via pyright
and coverage via pytest-cov; live SPARQL connectivity tests marked separately as `live`
**Target Platform**: Linux (CI: ubuntu-latest) and macOS for local development
**Project Type**: Python library package (`wikidata_collector`) consumed by ETL jobs
**Performance Goals**: Small-scale ETL workloads; iterator APIs should sustain typical Wikidata
queries with internal page size ≈15 entities per page and end-to-end query times generally under
~3 seconds per live query in the connectivity tests
**Constraints**: Must be robust to upstream latency and intermittent failures, avoid excessive
memory use by streaming results, and keep live endpoint tests optional (non-blocking for CI) due
to network variability
**Scale/Scope**: Library-scope project with one main package (`wikidata_collector`) and a focused
test suite; intended for low-concurrency ETL pipelines rather than high-throughput services

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

For Wikidata Collector, every feature plan MUST explicitly state how it complies with the
constitution in .specify/memory/constitution.md:

- **Library-first, ETL-oriented usage**: The public APIs (`WikidataClient` iterator methods) are
  pure library calls with no long-running background processes. Live SPARQL tests drive these APIs
  end-to-end but do not introduce new services or side-effects beyond read-only queries against
  Wikidata.
- **TDD workflow**: New behavior, including live connectivity checks, will be introduced by first
  defining tests in `specs/001-wikidata-etl-package/tasks.md` and the pytest suite, then
  implementing any required configuration or helper code. Each discovered defect must gain a
  regression test.
- **Stable public API & semantic versioning**: Live SPARQL tests exercise existing public APIs and
  query builders; they do not add or change public signatures. Any future API changes must follow
  semantic versioning rules and be documented in the spec and README.
- **Reliability & observability**: Connectivity and template tests will validate that iterator
  flows behave correctly with and without proxies, that errors are surfaced as documented
  exceptions, and that structured logging fields (event, entity_kind, filters, result_count,
  duration_ms, status) are populated for real queries.
- **Pythonic quality & simplicity**: Test code will follow the same standards as library code
  (type hints where appropriate, clear names, minimal abstractions) and reuse existing helpers in
  `wikidata_collector/client.py` and the query builders rather than introducing bespoke HTTP
  clients.
- **CI gates**: Static type checking (pyright) and non-live pytest suites (unit + integration with
  `-m "not live"`) remain mandatory CI gates. Live SPARQL tests will be marked (e.g.,
  `@pytest.mark.live`) and excluded from default CI runs to avoid flakes, but can be invoked
  manually or via a dedicated workflow when needed.

## Project Structure

### Documentation (this feature)

```text
specs/001-wikidata-etl-package/
├── plan.md              # Implementation plan (this file)
├── research.md          # Design decisions and rationales
├── data-model.md        # Pydantic models for figures and institutions
├── quickstart.md        # Usage examples for iterator APIs
├── contracts/
│   └── python-api.md    # Public Python API contracts
└── tasks.md             # Task breakdown and test plan
```

### Source Code (repository root)

```text
wikidata_collector/
├── client.py                 # WikidataClient, iterator APIs, pagination, logging
├── config.py                 # Configuration, including timeouts and proxy settings
├── constants.py              # Shared constants (e.g., endpoint URLs)
├── exceptions.py             # Library-specific exception types
├── models.py                 # PublicFigure, PublicInstitution, and supporting models
├── proxy.py                  # Optional proxy integration (not used in live connectivity tests)
├── query_builders/
│   ├── figures_query_builder.py
│   └── institutions_query_builder.py
└── normalizers/
    ├── figure_normalizer.py
    └── institution_normalizer.py

tests/
├── unit/                     # Pure unit tests (models, normalizers, query builders)
└── integration/              # Integration tests for iterator APIs and, later,
    ├── test_iterate_public_figures.py
    ├── test_iterate_public_institutions.py
    └── test_live_sparql_endpoints.py   # New live connectivity + template tests (marked "live")
```

**Structure Decision**: Single Python package (`wikidata_collector`) with a separate `tests/`
tree split into `unit` and `integration`. Live Wikidata SPARQL tests will live under
`tests/integration/test_live_sparql_endpoints.py` and be controlled via pytest markers so that
they are opt-in and do not become hard CI gates.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
