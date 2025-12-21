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
  `error_type` for key events (query start/end, page fetches, retries, and failures). The
  implementation uses Python's standard `logging` module with structured data passed in the
  `extra` parameter.
- **Rationale**: A consistent schema makes it straightforward for ETL infrastructures to parse,
  aggregate, and alert on logs without coupling to internal implementation details. The standard
  logging module is widely supported and integrates with existing log aggregation systems.
- **Implementation details**:
  - Event types: `iteration_started`, `iteration_completed`, `iteration_failed`,
    `max_results_reached`, `query_completed`, `query_failed`, `retry_scheduled`,
    `proxy_marked_failed`, `proxy_failure`
  - Error types: `invalid_filters`, `upstream_timeout`, `upstream_unavailable`,
    `upstream_throttled`, `proxy_unreachable`, `all_proxies_failed`
  - All log records include relevant context fields (attempt number, max retries, proxy used,
    latency, etc.)
- Alternatives considered:
  - Ad-hoc log messages per call-site: rejected because it would make automated analysis and
    monitoring brittle and increase the risk of missing important signals.
  - Using a third-party structured logging library: rejected to minimize dependencies.

### 8. Proxy Configuration and Fail-Closed Behavior

- **Decision**: Implement fail-closed proxy behavior by default, where the package raises
  `ProxyMisconfigurationError` when all configured proxies fail, rather than falling back to
  direct access. Provide an explicit `proxy_fallback_to_direct` configuration option to enable
  fallback when desired.
- **Rationale**: Fail-closed prevents unintentional exposure of requests when proxy
  infrastructure fails. Many environments require all requests to go through proxies for
  compliance, monitoring, or security reasons. Making fallback explicit ensures intentional
  decision-making.
- **Implementation details**:
  - `proxy_fallback_to_direct` configuration option (default: False)
  - `PROXY_FALLBACK_TO_DIRECT` environment variable support
  - `ProxyManager` validates all proxy URLs and blocks internal/private IPs (SSRF prevention)
  - Round-robin proxy selection with per-proxy failure tracking
  - Configurable cooldown period (default: 300 seconds) before retrying failed proxies
  - Structured logging for all proxy failures and fallback events
- **Alternatives considered**:
  - Always falling back to direct: rejected because it defeats the purpose of proxy configuration
    in many environments
  - No fallback option: rejected because some environments may want automatic fallback for
    resilience
  - Fail-open by default: rejected because it's less secure and could violate compliance
    requirements

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
  exception types. Specifically:
  - `InvalidFilterError`: Raised when filter parameters are invalid or malformed
  - `QueryExecutionError`: Raised when SPARQL query fails (legacy, replaced by more specific errors)
  - `UpstreamUnavailableError`: Raised when upstream Wikidata service is temporarily unavailable
    (timeouts, 5xx errors, rate limiting)
  - `ProxyMisconfigurationError`: Raised when proxy configuration is invalid or all proxies fail
    with fallback disabled (fail-closed mode)
  - `EntityNotFoundError`: Raised when a Wikidata entity cannot be found
  - `InvalidQIDError`: Raised when a QID is invalid or malformed
  - `ProxyError`: Base exception for proxy-related errors
- **Rationale**: ETL callers need to distinguish configuration errors from transient upstream
  issues to implement correct retry and alerting behavior. Specific exception types enable
  fine-grained error handling and better observability.
- **Alternatives considered**:
  - Using only generic exceptions: rejected because it would make it harder for callers to
    implement robust error handling and differentiate between permanent and transient failures.
