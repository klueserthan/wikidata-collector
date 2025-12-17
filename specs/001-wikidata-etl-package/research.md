# Research: Wikidata Public Entities ETL Package

## Decisions

### 1. Python and Pydantic Version

- **Decision**: Implement the feature using Python 9>= 3.13 and Pydantic v2 for all new and updated
  data models.
- **Rationale**: Aligns with the project requirement for modern Python, and Pydantic v2 provides
  better performance and clearer model configuration semantics for ETL-style workloads.
- **Alternatives considered**:
  - Continue using an older Python version and Pydantic v1: rejected because it would diverge from
    the stated target environment and complicate future maintenance.
  - Use plain dataclasses or TypedDicts: rejected because we want built-in validation and export
    utilities that Pydantic already provides.

### 2. Iterator-Based Public APIs vs. Bulk Lists

- **Decision**: Expose iterator-based APIs that yield `PublicFigure` and `PublicInstitution`
  instances one by one, rather than returning large lists from public calls.
- **Rationale**: Iterators reduce peak memory usage for long result sets and better fit the
  streaming nature of ETL pipelines that transform or write records incrementally.
- **Alternatives considered**:
  - Return full lists of entities: rejected due to potential memory spikes and the need for
    callers to implement their own batching.
  - Require callers to manage pagination cursors directly: rejected to keep the public API
    simpler and reduce room for pagination bugs in consuming code.

### 3. Internal Pagination, Ordering, and Label-Based Filters Strategy

- **Decision**: Implement internal pagination over Wikidata SPARQL results using a stable ordering
  by entity identifier (e.g., QID), and iterate through all matching entities (or up to any
  `max_results`) before yielding them to callers. Public filters are expressed in human-readable
  labels (e.g., country codes such as "US"/"DE" or institution type labels such as
  "public broadcaster"), which are translated to appropriate SPARQL constraints inside the query
  builders. The internal SPARQL page size is fixed and configured via library configuration, with a
  default of 15 entities per page; callers do not manage page size directly.
- **Rationale**: Stable identifier ordering ensures deterministic iteration across runs and
  simplifies reasoning about which entities were processed, while keeping pagination internal
  preserves a simple API for consumers.
- **Alternatives considered**:
  - Order by label or other human-friendly fields: rejected due to instability and potential
    ambiguity in ordering.
  - Expose pagination tokens: rejected per spec; consumers should not manage pagination.
  - Require callers to provide QIDs in filters: rejected in favor of human-readable labels for
    better ergonomics and clearer ETL job configuration.

### 7. Structured Logging Schema

- **Decision**: Use a stable, structured logging schema across the library, with fields such as
  `event`, `entity_kind`, `filters`, `page`, `result_count`, `duration_ms`, `status`, and
  `error_type` for key events (query start/end, page fetches, retries, and failures).
- **Rationale**: A consistent schema makes it straightforward for ETL infrastructures to parse,
  aggregate, and alert on logs without coupling to internal implementation details.
- Alternatives considered:
  - Ad-hoc log messages per call-site: rejected because it would make automated analysis and
    monitoring brittle and increase the risk of missing important signals.

### 4. Query Construction and Sub-Templates

- **Decision**: Reuse the existing `figures_query_builder` and `institutions_query_builder`
  modules and factor out reusable SPARQL sub-templates (e.g., for common projections, filters,
  and joins) where needed, instead of rewriting queries from scratch.
- **Rationale**: Keeps domain-specific SPARQL logic in one place, reduces duplication, and makes
  it easier to evolve queries consistently for both figures and institutions.
- **Alternatives considered**:
  - Monolithic query strings per use case: rejected because they are harder to maintain and
    reuse across different filters and result shapes.
  - Introducing a brand-new query builder abstraction: rejected as unnecessary complexity given
    the existing builders.

### 5. Logging Approach

- **Decision**: Use the standard Python `logging` module with structured log messages (e.g.,
  JSON-like payloads in the log record `extra`) for key events: query start/end, page boundaries,
  errors, and retries.
- **Rationale**: Works with existing logging infrastructure in most ETL environments and aligns
  with the constitution requirement for structured, filterable logs.
- **Alternatives considered**:
  - Introducing a third-party structured logging library: rejected for now to keep dependencies
    minimal.

### 6. Error Handling and Exceptions

- **Decision**: Continue using and, where needed, extend the existing `exceptions` module to
  model invalid filters, upstream unavailability, and proxy configuration errors as distinct
  exception types.
- **Rationale**: ETL callers need to distinguish configuration errors from transient upstream
  issues to implement correct retry and alerting behavior.
- **Alternatives considered**:
  - Using only generic exceptions: rejected because it would make it harder for callers to
    implement robust error handling.
