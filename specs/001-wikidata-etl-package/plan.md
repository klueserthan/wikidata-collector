# Implementation Plan: Wikidata Public Entities ETL Package

**Branch**: `001-wikidata-etl-package` | **Date**: 2025-12-17 | **Spec**: specs/001-wikidata-etl-package/spec.md
**Input**: Feature specification from `specs/001-wikidata-etl-package/spec.md`

**Note**: This plan is generated via the `/speckit.plan` workflow and guides implementation and
testing for the iterator-based ETL library.

## Summary

Build a small-scale production Python library that fetches public figures and public institutions
from Wikidata via SPARQL, normalizes them into Pydantic v2 models, and exposes iterator-based
APIs that yield individual entities matching a given filter set. Pagination, ordering, and
proxy usage are handled internally; consuming ETL code only sees simple, filter-driven iterators
and structured logging.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python >= 3.13 (library code and tests written to target Python 3.13+).  
**Primary Dependencies**: Pydantic v2 for data models; existing wikidata_collector SPARQL
query builders and security helpers (extended to translate human-readable filter labels such as
"US", "DE", or "public broadcaster" into appropriate SPARQL constraints); existing HTTP client
stack used by wikidata_collector (e.g., requests or equivalent); Python standard logging for
structured logs.  
**Storage**: N/A (no persistent storage; only in-memory data and any short-lived pagination
state within a single call).  
**Testing**: pytest (unit tests around normalizers, query builders, iterators, and error
handling; integration tests for end-to-end ETL-style flows where feasible).  
**Target Platform**: Python library executed in ETL environments (e.g., scheduled batch jobs,
Airflow workers, or containerized jobs) on typical Linux/macOS servers.  
**Project Type**: Single Python package (`wikidata_collector/`) with corresponding test suite in
`tests/`.  
**Performance Goals**: Support fetching on the order of a few thousand public figures or
institutions per ETL run via iterator-based APIs, within WDQS limits, without exhausting memory or
requiring manual pagination by consumers.  
**Constraints**: No long-running service processes; no persistent database; library-first design;
respect Wikidata Query Service rate limits and timeouts; iterator-based public APIs (no bulk list
returns) to keep memory usage bounded; structured logging required for operations.  
**Scale/Scope**: Small-scale production ETL usage focused on public figures and institutions; the
scope of this feature is limited to query construction, normalization, and iterator-based
retrieval for these domains, with filters expressed as human-readable labels (e.g., country codes
like "US"/"DE" or institution type labels like "public broadcaster").

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

For Wikidata Collector, every feature plan MUST explicitly state how it complies with the
constitution in .specify/memory/constitution.md:

- Library-first, ETL-oriented usage (no long-running services or hidden side-effects).
- TDD workflow (tests defined and failing before implementation, including regression tests).
- Public API and data contracts (inputs/outputs) stable or versioned per semantic versioning.
- Reliability and observability for ETL usage (failure modes, logging, retries, caching impact).
- Pythonic quality and simplicity (style, type hints, docstrings, minimal abstractions).

**Assessment for this feature**:

- Library-first: This feature refactors and improves the existing `wikidata_collector` Python package with
  iterator-based APIs.
- TDD workflow: New functionality (iterators, models, query sub-templates, proxy handling) will be
  driven by pytest unit and integration tests, including regression tests for any discovered
  issues.
- Stable API & versioning: Public iterators and data models will be treated as public API;
  changes that break existing signatures or result schemas will require a MAJOR version bump and
  migration notes.
- Reliability & observability: Internal pagination and proxy usage will surface structured logs
  and well-typed errors so ETL callers can distinguish configuration issues, upstream failures,
  and invalid filters.
- Pythonic simplicity: Implementation will favor explicit, well-typed iterators built on top of
  existing query builders and Pydantic models, avoiding unnecessary abstractions.

No constitution violations are anticipated for this feature; the Complexity Tracking section
remains empty.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
wikidata_collector/
├── __init__.py
├── client.py              # High-level client; iterator-based APIs will be added/refined here
├── config.py
├── constants.py
├── exceptions.py
├── models.py              # Pydantic v2 models for PublicFigure, PublicInstitution, etc.
├── proxy.py
├── security.py
├── query_builders/
│   ├── __init__.py
│   ├── figures_query_builder.py
│   └── institutions_query_builder.py
└── normalizers/
  ├── __init__.py
  ├── figure_normalizer.py
  └── institution_normalizer.py

tests/
├── unit/
│   ├── test_normalizers.py
│   ├── test_sparql_builders.py
│   ├── test_sparql_security.py
│   └── test_proxy_service.py
└── integration/
  └── (new iterator-focused integration tests to be added for this feature)

```

**Structure Decision**: Take inspiration from the existing `wikidata_collector` and `tests` layout, but substantially refactor and improve it. New iterator-based public APIs will live in `wikidata_collector/client.py` (and, if needed, small
helpers), using `query_builders` and `normalizers` internally. Tests will be added under
`tests/unit` and `tests/integration` following the current conventions.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
