# Feature Specification: Wikidata Public Entities ETL Package

**Feature Branch**: `001-wikidata-etl-package`  
**Created**: 2025-12-17  
**Status**: Draft  
**Input**: User description: "Build a package that fetches public figures and public institutions (government institutions, NGOs, municipalities, media outlets, ...) from Wikidata via SPARQL, normalizes them to schemas, and returns paged results. For public figures, the package should fetch name, aliases, description, birthday, deadthday, gender, nationalities, professions, websites, social media (twitter/X, instagram, facebook, tiktok), identifiers (such as GND or VIAF). For public institutions, the package should fetch name, aliases, description, founded, country, types, headquater, website, sector, social media (twitter/X, instagram, facebook, tiktok). The survey should optionally accept a proxy server to avoid blocking. The proxy server takes care of rotation, so this is out of scope for this project). The package should have a robust pagination to paginate through long lists of records from Wikidata. Queries should accept the folloing filters: Public Figures: birthday, nationality; public institutions: founded, country, types, headquarter. Ensure structured logging."

## Clarifications

### Session 2025-12-17

- Q: Should the package impose a hard upper bound on the number of entities returned per call, or rely on environment limits when no `max_results` is provided? → A: No hard upper bound; return all matching entities when no `max_results` is specified, subject only to environment and upstream constraints.

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.
  
  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - Export public figures matching filters (Priority: P1)

An analytics engineer or data engineer needs to regularly export a list of public figures for
downstream analysis (for example, building dashboards or training simple models). They want to
filter by birthday and nationality, obtain a consistent set of core attributes (identity,
biographical data, locations, and online presence), and receive all matching results (or up to a
specified maximum) in one call, without having to manually manage pages or pagination tokens.

**Why this priority**: This is the primary value of the package: enabling ETL pipelines to
reliably collect public figure data in batches while controlling volume and filters, without
exposing pagination mechanics to consuming code.

**Independent Test**: Configure a sample ETL job that calls the package once with birthday and
nationality filters (and optionally a maximum results value), runs to completion without manual
intervention, and produces a structured dataset with the required fields for each person. The job
does not need to be aware of internal pagination.

**Acceptance Scenarios**:

1. **Given** a configured job with birthday and nationality filters, **When** the job calls the
  package to fetch public figures, **Then** it receives a collection of results containing only
  public figures matching those filters and each record includes the required attributes for
  public figures.
2. **Given** a configured job with birthday and nationality filters and a specified maximum number
  of results, **When** the job calls the package, **Then** it receives at most that number of
  matching public figures and does not need to manage any pagination tokens, while the package
  internally handles all necessary pagination.

---

### User Story 2 - Export public institutions matching filters (Priority: P2)

An analytics engineer or data engineer needs to regularly export a list of public institutions
(government institutions, NGOs, municipalities, media outlets, and similar organizations) for
downstream analysis. They want to filter by founding date, country, institution type, and
headquarter location, obtain a consistent set of core attributes, and receive all matching results
(or up to a specified maximum) in one call, without having to manage pages or pagination tokens.

**Why this priority**: Public institutions complement public figures in many analytical and
research use cases. Supporting them in a similar way creates a consistent experience for ETL
pipelines and minimizes one-off data collection scripts, while still hiding pagination from
consuming code.

**Independent Test**: Configure a sample ETL job that calls the package once with founding date,
country, type, and headquarter filters (and optionally a maximum results value), runs to
completion, and produces a structured dataset with the required fields for each institution. The
job does not need to manage any pagination tokens.

**Acceptance Scenarios**:

1. **Given** a configured job with founded, country, type, and headquarter filters, **When** the
  job calls the package to fetch public institutions, **Then** it receives a collection of
  results that all match the filters and each record includes the required attributes for public
  institutions.
2. **Given** a configured job with filters and a specified maximum number of results, **When** the
  job calls the package, **Then** it receives at most that number of matching public institutions
  and does not need to manage pagination tokens, while the package internally handles all
  necessary pagination.

---

### User Story 3 - Resilient, observable ETL runs with proxy support (Priority: P3)

An operations engineer or ETL maintainer wants long-running or periodically scheduled jobs to be
resilient to upstream rate limits or temporary connectivity issues. They need the package to
optionally use a proxy endpoint (managed elsewhere) and to emit structured logs for successful
requests, retries, and failures, so that issues can be detected and diagnosed.

**Why this priority**: Without clear logging and controlled failure modes, ETL jobs become
fragile and hard to operate in production, even at small scale.

**Independent Test**: Run a sample ETL job in an environment where some requests go through a
proxy and some encounter simulated failures, and verify that the job either completes with
structured logs describing its behavior or fails in a clearly diagnosable way without corrupting
downstream data.

**Acceptance Scenarios**:

1. **Given** a configured proxy endpoint and a running ETL job using the package, **When** the job
  fetches multiple pages of public figures or institutions, **Then** the job executes using the
  proxy endpoint, and structured logs clearly indicate which calls succeeded or failed.
2. **Given** a configured job with structured logging enabled, **When** upstream errors or timeouts
  occur during data collection, **Then** the job either retries according to documented rules or
  fails with clear, structured log entries and well-defined error signals that downstream
  monitoring can detect.

---

[Add more user stories as needed, each with an assigned priority]

### Edge Cases

- No results: When filters match no public figures or institutions, the package MUST return an
  empty collection and clearly indicate in its return structure that no matching entities were
  found.
- End of pagination (internal): When the last page of results has been processed internally, the
  package MUST return a complete collection of all matching entities (or up to any configured
  maximum) without exposing page boundaries or pagination tokens to consuming code.
- Invalid filters: When filters are malformed or unsupported (for example, invalid date formats or
  unknown country or type identifiers), the package MUST fail fast with a clear and structured
  error that can be surfaced in logs and handled by the calling ETL job.
- Partial upstream failures: When upstream responses are temporarily unavailable or incomplete, the
  package MUST avoid silently returning partial or corrupted data and instead follow documented
  failure or retry behavior.
- Proxy configuration issues: When a proxy is configured but unreachable or misconfigured, the
  package MUST, by default, fail closed (not falling back to direct access) and MAY only fall back
  to direct access when an explicit configuration option enabling fallback has been set.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow ETL jobs to retrieve all public figures that match a given set
  of filters in a single call (or up to a specified maximum), without requiring the caller to
  manage pages or pagination tokens. When no maximum is specified, there is no hard upper bound
  enforced by the package; it returns all matching entities subject only to environment and
  upstream constraints.
- **FR-002**: The system MUST allow ETL jobs to filter public figures by birthday and nationality
  when retrieving results via the iterator-based single-call API, with internal pagination fully
  hidden from the caller.
- **FR-003**: For each public figure record, the system MUST provide at least: name, aliases,
  description, birthday, date of death (if applicable), gender, nationalities, professions,
  websites, social media accounts, and external identifiers.
- **FR-004**: The system MUST allow ETL jobs to retrieve all public institutions that match a given
  set of filters in a single call (or up to a specified maximum), without requiring the caller to
  manage pages or pagination tokens. When no maximum is specified, there is no hard upper bound
  enforced by the package; it returns all matching entities subject only to environment and
  upstream constraints.
- **FR-005**: The system MUST allow ETL jobs to filter public institutions by founding date,
  country, institution type, and headquarter location when retrieving results via the
  iterator-based single-call API, with internal pagination fully hidden from the caller.
- **FR-006**: For each public institution record, the system MUST provide at least: name, aliases,
  description, founding date, country, types, headquarter location, website, sector, and social
  media accounts.
- **FR-007**: The system MUST ensure that any internal pagination used to fetch long result sets is
  robust, so that the package can internally iterate through all matching public figures or
  institutions without gaps or duplicates, even when intermediate pages are large.
- **FR-008**: The system MUST define and document a stable internal ordering for results so that
  the same filter set consistently produces the same sequence of entities over time, ordering by a
  stable identifier for each entity (for example, the entity ID) and using that identifier as the
  primary internal key for pagination.
- **FR-010**: The system MUST optionally accept a proxy endpoint configuration so that requests can
  be routed through an external proxy service that is responsible for rotation and blocking
  avoidance.
- **FR-011**: The system MUST provide structured logging for key events, including successful page
  fetches, filter usage, errors, and retries, in a format that ETL infrastructure can parse and
  aggregate.
- **FR-012**: The system MUST support a test-first workflow, where new behavior is introduced via
  verifiable scenarios, and every defect fix includes a regression scenario that fails before the
  fix and passes afterward.
- **FR-013**: The system SHOULD expose clear, documented error types or categories so ETL jobs can
  distinguish between configuration problems, upstream unavailability, and invalid filters.
- **FR-014**: The system SHOULD use a fixed internal page size for SPARQL queries, configurable via
  library configuration (with a default of 15 entities per page), so small-scale production
  workloads have predictable behavior without exposing pagination controls to callers.
- **FR-015**: The system SHOULD document typical performance characteristics for small-scale
  workloads so operators can size and schedule ETL runs.
- **FR-016**: The system SHOULD specify how to handle multi-valued attributes (for example,
  multiple nationalities, professions, or social media accounts) and represent them consistently in
  the returned records, by default returning the full set of values for each multi-valued
  attribute so that downstream consumers can decide whether to derive a primary value.

### Key Entities *(include if feature involves data)*

- **Public Figure**: Represents an individual person considered a public figure for the purposes of
  the ETL job. Key attributes include stable identifiers, human-readable names and aliases,
  descriptive text, birth and death information, gender, nationalities, professions, official
  websites, social media accounts, and external identifiers from other reference systems.
- **Public Institution**: Represents an organization such as a government institution, NGO,
  municipality, media outlet, or similar public body. Key attributes include stable identifiers,
  names and aliases, descriptive text, founding date, country, organizational types, headquarter
  location, sector, websites, and social media accounts.
- **Result Set**: Represents the complete collection of entities returned by a single call to the
  system, including all matching public figures or institutions (or up to any specified maximum),
  along with any relevant metadata such as total count when available. Pagination details, if any,
  are handled internally and are not exposed to consuming code.
- **Filter Set**: Represents the set of filter parameters used to constrain a query for public
  figures or institutions, such as date ranges, country or nationality identifiers, institution
  types, and headquarter locations, and may include an optional maximum results value.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a typical small-scale production workload, an ETL job can retrieve at least a few
  thousand public figures or institutions in a single run via a single call per entity type,
  without manual intervention or job restarts, while the package internally manages any required
  pagination.
- **SC-002**: At least 95% of ETL runs that use valid filters complete successfully without
  user-visible data inconsistencies, such as duplicated or missing entities in the returned result
  sets.
- **SC-003**: At least 95% of error conditions encountered during data collection (for example,
  invalid filters, unreachable proxy endpoints, or upstream unavailability) produce structured log
  entries that clearly indicate the cause and allow operators to classify the issue without reading
  raw responses.
- **SC-004**: For a representative test workload, operators can configure and run automated tests
  that demonstrate the primary user stories (public figures, public institutions, and observable
  ETL runs) completing successfully within 10 minutes per user story run, without manual data
  repair steps.
- **SC-005**: New or changed behavior introduced by this feature is always accompanied by tests that
  initially fail and later pass after implementation, and these tests remain stable across at least
  one subsequent release.

### Structured Logging Schema (informative)

To satisfy FR-011 and SC-003, the package SHOULD emit structured log records for key events with a
consistent schema that ETL infrastructure can parse. At minimum, log records SHOULD include:

- `event`: a short machine-readable event name (e.g., `query_started`, `page_fetched`,
  `iteration_completed`, `retry_scheduled`, `error_raised`).
- `entity_kind`: `"public_figure"`, `"public_institution"`, or `null` when not applicable.
- `filters`: a summarized representation of the filter set used (for example, date ranges and
  country/type labels), redacted as needed for privacy.
- `page`: the internal page index or cursor information when relevant.
- `result_count`: number of entities returned in the event context (e.g., per page or per run).
- `duration_ms`: elapsed time in milliseconds for the operation represented by the event.
- `status`: high-level outcome such as `"success"`, `"retry"`, or `"failure"`.
- `error_type`: a machine-readable error category when an error occurs (e.g.,
  `"invalid_filters"`, `"upstream_timeout"`, `"proxy_unreachable"`).

The exact mapping of these fields to the underlying logging framework is defined in the
implementation plan and research notes, but the presence and semantics of these fields MUST remain
stable for ETL consumers.

### Error Categories and Exception Types

To satisfy FR-013, the system defines distinct exception types that ETL jobs can catch and handle
appropriately. These exception types provide clear categorization of failure modes:

- **`InvalidFilterError`**: Raised when filter parameters are invalid or malformed (e.g., invalid
  date formats, unknown country codes, or unsupported filter combinations). ETL jobs should treat
  this as a configuration error and fail fast.
  
- **`ProxyMisconfigurationError`**: Raised when proxy configuration is invalid or a configured
  proxy is unreachable. This indicates a deployment or infrastructure issue that requires operator
  intervention. The system follows a fail-closed policy: when proxies are configured but all fail,
  requests do not automatically fall back to direct connections.
  
- **`UpstreamUnavailableError`**: Raised when the upstream Wikidata service is unavailable after
  retries (e.g., persistent 503 errors, timeouts, or connection failures). ETL jobs may choose to
  retry the entire job later or alert operators.
  
- **`QueryExecutionError`**: A general-purpose exception raised when a SPARQL query fails after
  retries for reasons not covered by more specific exception types. Includes the underlying error
  details for debugging.
  
- **`EntityNotFoundError`**: Raised when a requested entity (by QID) cannot be found in Wikidata.
  This is typically not a system error but indicates that the requested entity does not exist.
  
- **`InvalidQIDError`**: Raised when a QID parameter is malformed or fails validation. This is a
  security-focused exception that prevents SPARQL injection attacks.

All exception types inherit from the base `WikidataCollectorError` class, allowing ETL jobs to
catch all package-specific errors with a single exception handler if desired.

### Structured Logging Implementation

The system implements structured logging using Python's standard `logging` module with structured
extra fields. All log records for key events include machine-readable fields accessible via the
`LogRecord.extra` attribute. The following logging functions are used consistently across the
codebase:

- **`_log_query_execution(query_type, params, page_num, result_count, latency_ms, proxy_used)`**:
  Logs successful SPARQL query execution with structured fields:
  - `query_type`: Type of query (e.g., "public_figures", "public_institutions")
  - `params`: Filter parameters used in the query (dict)
  - `page`: Page number (1-indexed, int)
  - `result_count`: Number of results returned (int)
  - `latency_ms`: Query execution time in milliseconds (float)
  - `proxy_used`: Proxy URL or "direct" (str)
  
- **`_log_page_fetch(query_type, page_num, after_qid, result_count)`**:
  Logs internal page fetch operations for iterators with structured fields:
  - `query_type`: Type of query (str)
  - `page`: Page number being fetched (int)
  - `after_qid`: QID cursor for keyset pagination, or None (str or None)
  - `result_count`: Number of results in this page (int)
  
- **`_log_retry_attempt(attempt, max_retries, reason, wait_time, proxy)`**:
  Logs retry attempts with detailed context:
  - `attempt`: Current attempt number, 1-indexed (int)
  - `max_retries`: Maximum configured retries (int)
  - `reason`: Machine-readable retry reason (str), e.g., "throttled_429", "upstream_error_503",
    "request_exception_Timeout"
  - `wait_time_seconds`: Wait time before retry in seconds (float)
  - `proxy`: Proxy URL being retried, or None (str or None)
  - `event`: Always "retry" (str)
  
- **`_log_query_failure(query_type, error_category, error_message, attempts, filters)`**:
  Logs query failures after all retries with structured fields:
  - `query_type`: Type of query that failed (str)
  - `error_category`: Machine-readable error category (str), e.g., "upstream_unavailable",
    "timeout", "invalid_filter", "proxy_misconfiguration"
  - `error_message`: Detailed human-readable error message (str)
  - `attempts`: Number of attempts made before failure (int)
  - `filters`: Filter parameters used in the query (dict)
  - `event`: Always "query_failure" (str)

Log levels are assigned as follows:
- `INFO`: Successful query execution, successful operations
- `DEBUG`: Internal pagination details, page fetches
- `WARNING`: Retry attempts, transient errors
- `ERROR`: Query failures after retries, unrecoverable errors

ETL infrastructure can parse these structured log records to implement alerting, monitoring, and
debugging workflows without relying on log message text parsing.
