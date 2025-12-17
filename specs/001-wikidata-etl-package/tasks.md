# Tasks: Wikidata Public Entities ETL Package

**Input**: Design documents from `/specs/001-wikidata-etl-package/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/python-api.md

**Tests**: This feature explicitly expects tests (TDD workflow and pytest in the constitution). Include unit and integration tests per user story.

**Organization**: Tasks are grouped by user story (US1–US3) to enable independent implementation and testing. Phases 1–2 cover shared setup and foundations; later phases map directly to user stories. The final phase covers polish and cross-cutting concerns.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Ensure local and CI environments are ready for Python ≥ 3.13, Pydantic v2, pytest, and type checking for this feature.

- [ ] T001 Verify Python ≥ 3.13 and dependencies via pyproject in pyproject.toml
- [ ] T002 [P] Configure pytest for iterator-focused tests in tests/README.md and pytest.ini
- [ ] T003 [P] Confirm Pydantic v2 usage and upgrade path in wikidata_collector/models.py
- [ ] T004 [P] Ensure type checker configuration (e.g., pyright) covers wikidata_collector and tests in pyproject.toml
- [ ] T005 Configure or update CI workflows (e.g., GitHub Actions) to run the type checker and relevant pytest suites on each push and pull request

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core library infrastructure that MUST be complete before any user story implementation begins.

- [ ] T006 Introduce PublicFigure and PublicInstitution Pydantic v2 models per data-model in wikidata_collector/models.py
- [ ] T007 [P] Add supporting types (WebsiteEntry, AccountEntry, Identifier) in wikidata_collector/models.py
- [ ] T008 [P] Extend or create figure_normalizer for new models in wikidata_collector/normalizers/figure_normalizer.py
- [ ] T009 [P] Extend or create institution_normalizer for new models in wikidata_collector/normalizers/institution_normalizer.py
- [ ] T010 Define iterator-friendly abstractions and SPARQL page handling helpers (using a fixed internal page size default of 15) in wikidata_collector/client.py
- [ ] T011 [P] Ensure security and SPARQL safety checks reused for new queries in wikidata_collector/security.py
- [ ] T012 Add structured logging helper for queries and pages in wikidata_collector/client.py
- [ ] T013 Wire proxy configuration options into client construction in wikidata_collector/client.py and wikidata_collector/config.py

**Checkpoint**: Foundation ready — models, normalizers, pagination helpers, logging, and proxy wiring exist and are testable, but user-story-specific iterators are not yet implemented.

---

## Phase 3: User Story 1 - Export public figures matching filters (Priority: P1) 🎯 MVP

**Goal**: Provide an iterator-based API to stream public figures matching birthday and nationality filters in a single call, hiding SPARQL pagination and returning normalized PublicFigure models.

**Independent Test**: Run an ETL-style test that calls iterate_public_figures once with birthday and nationality filters (and optionally max_results) and verifies that it yields correctly filtered PublicFigure instances without exposing pagination.

### Tests for User Story 1

- [ ] T014 [P] [US1] Add unit tests for PublicFigure model and normalizer behavior in tests/unit/test_normalizers.py
- [ ] T015 [P] [US1] Add unit tests for figures SPARQL query building with birthday/nationality filters and label inputs in tests/unit/test_sparql_builders.py
- [ ] T016 [P] [US1] Add integration test for iterate_public_figures happy path in tests/integration/test_iterate_public_figures.py
- [ ] T017 [P] [US1] Add integration test for empty results and invalid filters for figures in tests/integration/test_iterate_public_figures.py

### Implementation for User Story 1

- [ ] T018 [P] [US1] Implement SPARQL sub-templates for public figures projections and filters in wikidata_collector/query_builders/figures_query_builder.py
- [ ] T019 [P] [US1] Implement label-to-SPARQL translation for nationality filters in wikidata_collector/query_builders/figures_query_builder.py
- [ ] T020 [US1] Implement internal pagination loop and stable ID ordering for figures in wikidata_collector/client.py
- [ ] T021 [US1] Implement WikidataClient.iterate_public_figures iterator API in wikidata_collector/client.py
- [ ] T022 [US1] Integrate figure_normalizer to map SPARQL rows to PublicFigure in wikidata_collector/client.py
- [ ] T023 [US1] Add structured logging for figures queries, pages, and errors (using the agreed schema) in wikidata_collector/client.py
- [ ] T024 [US1] Add figure-specific error handling for invalid filters and upstream failures in wikidata_collector/exceptions.py and wikidata_collector/client.py
- [ ] T025 [US1] Update quickstart examples for figures usage and max_results in specs/001-wikidata-etl-package/quickstart.md

**Checkpoint**: User Story 1 fully functional and testable independently via unit and integration tests.

---

## Phase 4: User Story 2 - Export public institutions matching filters (Priority: P2)

**Goal**: Provide an iterator-based API to stream public institutions matching founding date, country, types, and headquarter filters in a single call, hiding SPARQL pagination and returning normalized PublicInstitution models.

**Independent Test**: Run an ETL-style test that calls iterate_public_institutions once with founding date, country, types, and headquarter filters (and optionally max_results) and verifies that it yields correctly filtered PublicInstitution instances without exposing pagination.

### Tests for User Story 2

- [ ] T026 [P] [US2] Add unit tests for PublicInstitution model and normalizer behavior in tests/unit/test_normalizers.py
- [ ] T027 [P] [US2] Add unit tests for institutions SPARQL query building with founded/country/types/headquarter filters and label inputs in tests/unit/test_sparql_builders.py
- [ ] T028 [P] [US2] Add integration test for iterate_public_institutions happy path in tests/integration/test_iterate_public_institutions.py
- [ ] T029 [P] [US2] Add integration test for empty results and invalid filters for institutions in tests/integration/test_iterate_public_institutions.py

### Implementation for User Story 2

- [ ] T030 [P] [US2] Implement SPARQL sub-templates for public institutions projections and filters in wikidata_collector/query_builders/institutions_query_builder.py
- [ ] T031 [P] [US2] Implement label-to-SPARQL translation for country, types, and headquarter filters in wikidata_collector/query_builders/institutions_query_builder.py
- [ ] T032 [US2] Implement internal pagination loop and stable ID ordering for institutions in wikidata_collector/client.py
- [ ] T033 [US2] Implement WikidataClient.iterate_public_institutions iterator API in wikidata_collector/client.py
- [ ] T034 [US2] Integrate institution_normalizer to map SPARQL rows to PublicInstitution in wikidata_collector/client.py
- [ ] T035 [US2] Add structured logging for institutions queries, pages, and errors (using the agreed schema) in wikidata_collector/client.py
- [ ] T036 [US2] Add institution-specific error handling for invalid filters and upstream failures in wikidata_collector/exceptions.py and wikidata_collector/client.py
- [ ] T037 [US2] Update quickstart examples for institutions usage and filters in specs/001-wikidata-etl-package/quickstart.md

**Checkpoint**: User Stories 1 and 2 both work independently and can be exercised via their own integration tests.

---

## Phase 5: User Story 3 - Resilient, observable ETL runs with proxy support (Priority: P3)

**Goal**: Make ETL runs resilient to upstream issues by supporting optional proxy configuration and structured logging for all iterator operations, with clear error categories and configurable proxy fallback behavior.

**Independent Test**: Run a test job where some requests use a proxy endpoint and some encounter simulated failures; verify structured logs, retries or fail-fast behavior, and correct error categorization without corrupting downstream data.

### Tests for User Story 3

- [ ] T038 [P] [US3] Add unit tests for proxy configuration and fallback behavior in tests/unit/test_proxy_service.py
- [ ] T039 [P] [US3] Add unit tests for structured logging payloads and log fields in tests/unit/test_normalizers.py or new tests/unit/test_logging.py
- [ ] T040 [P] [US3] Add integration test simulating upstream timeouts and proxy failures for figures and institutions in tests/integration/test_resilience_and_logging.py

### Implementation for User Story 3

- [ ] T041 [P] [US3] Implement proxy-aware HTTP request handling with fail-closed default in wikidata_collector/proxy.py
- [ ] T042 [US3] Wire proxy handling into WikidataClient iterator flows in wikidata_collector/client.py
- [ ] T043 [US3] Implement structured logging for retries, failures, and filter usage (using the agreed schema) in wikidata_collector/client.py
- [ ] T044 [US3] Extend exceptions for proxy misconfiguration, upstream unavailability, and invalid filters in wikidata_collector/exceptions.py
- [ ] T045 [US3] Document error categories and logging fields in specs/001-wikidata-etl-package/spec.md and specs/001-wikidata-etl-package/research.md

**Checkpoint**: All three user stories are independently functional and observable, with proxy support and structured logging in place.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Apply cross-cutting improvements, documentation, and performance validation once user stories are implemented.

- [ ] T046 [P] Consolidate iterator and pagination helper utilities for reuse in wikidata_collector/client.py
- [ ] T047 [P] Update public API documentation and examples in specs/001-wikidata-etl-package/quickstart.md and README.md
- [ ] T048 Improve performance of SPARQL queries and confirm pagination defaults (including the 15-entity internal page size) for small-scale workloads in wikidata_collector/query_builders
- [ ] T049 Add any missing unit tests for edge cases (multi-valued fields, no results, max_results) in tests/unit/test_normalizers.py and tests/unit/test_sparql_builders.py
- [ ] T050 Run type checker and fix typing issues introduced by new models and iterators across wikidata_collector and tests
- [ ] T051 Configure and validate CI workflows so static type checks and relevant pytest suites run for this feature on every push and pull request

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1: Setup** — No dependencies; can start immediately.
- **Phase 2: Foundational** — Depends on Setup completion; blocks all user story implementation.
- **Phase 3: User Story 1 (P1)** — Depends on Phase 2; can proceed once models, normalizers, pagination helpers, and logging are in place.
- **Phase 4: User Story 2 (P2)** — Depends on Phase 2; can run in parallel with Phase 3 after foundations are ready.
- **Phase 5: User Story 3 (P3)** — Depends on Phase 2; can run in parallel with Phases 3 and 4 once foundational proxy and logging hooks exist.
- **Phase 6: Polish** — Depends on completion of the desired user stories (at minimum, Phase 3 as MVP).

### User Story Dependencies

- **User Story 1 (P1)** — Independent once foundations are ready; provides MVP iterator for public figures.
- **User Story 2 (P2)** — Independent once foundations are ready; may reuse abstractions from US1 but remains independently testable.
- **User Story 3 (P3)** — Builds on shared proxy and logging infrastructure and must not change public iterator signatures; independently testable through resilience and logging scenarios.

### Within Each User Story

- Write tests (unit and integration) first and ensure they fail before implementation tasks.
- Implement SPARQL query builders and label-to-SPARQL translation before wiring iterators.
- Implement iterators and internal pagination before integrating normalizers and logging.
- Integrate error handling and exceptions last, once behaviors are clear.

### Parallel Opportunities

- All tasks marked [P] within a phase can be worked on in parallel as long as they touch different files or non-overlapping sections.
- After Phase 2 completes, teams can work on US1, US2, and US3 in parallel:
  - US1 focused on figures iterators and filters.
  - US2 focused on institutions iterators and filters.
  - US3 focused on proxy, logging, and resilience across both iterators.

---

## Parallel Execution Examples

- During Phase 2, T006, T007, T008, T010, T011, and T012 can proceed in parallel since they primarily affect distinct files.
- For User Story 1, T014, T015, T016, and T017 can be developed in parallel while T018 and T019 evolve the query builders.
- For User Story 2, T026–T029 can run in parallel with T030 and T031 in the query builders.
- For User Story 3, T038–T040 can be implemented while T041–T043 evolve proxy and logging internals.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Implement and test Phase 3: User Story 1 (figures iterator) end to end.
4. Validate iterator behavior and logging using the examples in specs/001-wikidata-etl-package/quickstart.md.

### Incremental Delivery

1. Deliver MVP with User Story 1 complete and validated.
2. Add User Story 2 (institutions iterator) and validate independently.
3. Add User Story 3 (resilience, proxy, and logging hardening) and validate independently.
4. Apply Phase 6 polish tasks and verify all constitution and CI gates are satisfied.

### Team Parallelization

- One developer can focus on figures (US1), another on institutions (US2), and another on proxy/logging (US3) once foundational tasks are complete.
- Regularly synchronize on shared modules like wikidata_collector/client.py, wikidata_collector/query_builders, and wikidata_collector/exceptions.py to avoid merge conflicts.
