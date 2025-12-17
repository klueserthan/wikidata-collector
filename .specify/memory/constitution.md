<!--
Sync Impact Report
- Version change: 1.0.0 → 1.1.0
- Modified principles/sections:
  - Development Workflow & Quality Gates: CI gate now explicitly requires static type checks and
    relevant pytest suites to pass before PR review.
- Added sections: None
- Removed sections: None
- Templates status:
	- .specify/templates/plan-template.md: ✅ updated Constitution Check to mention type checks and
	  pytest gates.
	- .specify/templates/spec-template.md: ✅ generic, no changes required
	- .specify/templates/tasks-template.md: ✅ generic, no changes required
	- .specify/templates/checklist-template.md: ✅ generic, no changes required
	- .specify/templates/agent-file-template.md: ✅ generic, no changes required
	- .specify/templates/commands/*: ⚠ not present in this repo (no command templates to sync)
- Deferred TODOs: None
-->

# Wikidata Collector Constitution

## Core Principles

### I. Library-First, ETL-Oriented Design

- The project is a pure Python library consumed by ETL pipelines, not a long-running service.
- Public APIs MUST be stable, minimal, and oriented around idempotent data-extraction operations.
- All behavior exposed to ETL callers MUST be deterministic given the same configuration, input
	parameters, and external Wikidata state.
- Breaking changes to public classes, functions, configuration, or result schemas MUST follow the
	Governance section (semantic versioning and migration notes).

### II. Test-Driven Development (NON-NEGOTIABLE)

- New behavior MUST be introduced using TDD: write or extend tests first, see them fail, then
	implement the minimal code to make them pass, followed by refactoring.
- Every bug fix MUST include a regression test that fails before the fix and passes after it.
- Public API changes (new parameters, return fields, or behaviors) MUST be covered by tests in the
	tests/unit or tests/integration packages.
- No code MAY be merged to main without a green test suite in CI.

### III. Stable Public API & Semantic Versioning

- The library MUST follow semantic versioning: MAJOR.MINOR.PATCH.
- Removing or changing existing public functions, classes, arguments, or result fields in a
	backward-incompatible way REQUIRES a MAJOR version bump and documented migration guidance.
- Adding new, backwards-compatible capabilities (e.g., optional parameters, new result fields that
	have safe defaults) REQUIRES a MINOR version bump.
- Internal refactors, doc clarifications, and non-functional changes with no user-visible impact
	MAY be released as PATCH versions.

### IV. Reliability, Observability & Failure Handling

- All data-collection operations MUST handle network failures, timeouts, and upstream errors in a
	controlled, documented way (exceptions, retry semantics, and return contracts).
- Logging MUST be structured and filterable at the ETL host level (e.g., predictable message
	patterns, log levels, and inclusion of correlation identifiers where applicable).
- Error types and exception classes MUST be specific and documented so ETL callers can distinguish
	between retryable and non-retryable failures.
- Where caching, proxy rotation, or pagination are used, their effects on correctness and
	performance MUST be testable via automated tests.

### V. Pythonic Quality, Style & Simplicity

- Code MUST follow modern Python best practices (PEP 8 style, PEP 257 docstrings, and type
	annotations on public APIs).
- New modules and functions MUST include concise docstrings describing inputs, outputs, and
	side-effects relevant to ETL consumers.
- The implementation MUST favor simple, explicit solutions over clever or overly generic
	abstractions, especially given the small-scale production target.
- Static analysis (linters, formatters, and type checkers configured in this repo) SHOULD pass
	cleanly for all committed code; any intentional deviations MUST be justified in code review.

## ETL & Performance Constraints

- The library is intended for small-scale production ETL workloads (e.g., scheduled batch jobs or
	low-concurrency pipelines), not for high-frequency real-time APIs.
- ETL tasks using this library MUST be able to:
	- Control batch size and pagination to avoid upstream timeouts.
	- Configure timeouts, retry limits, and caching behavior explicitly.
	- Detect and handle partial failures via well-defined exceptions and result contracts.
- Performance and resource usage expectations for new features MUST be documented in the relevant
	spec and plan, with tests where feasible (e.g., upper bounds on batch sizes, latency targets for
	typical queries).
- External dependencies (network services, proxies, caches) MUST be abstracted such that they can
	be replaced or mocked in tests without requiring a running external system.

## Development Workflow & Quality Gates

- All feature work MUST start from a written spec and implementation plan generated via SpecKit
	templates in this repository.
- Each feature MUST define user scenarios and tests that can be executed independently, aligning
	with the TDD principle above.
- Before merging, every change MUST:
	- Pass the configured static type checks (for example, mypy or an equivalent tool) and the
	  relevant pytest test suites (unit and, where applicable, integration) in CI.
	- Respect the semantic versioning rules defined in this constitution.
	- Be reviewed by at least one other contributor for API impact, correctness, and Python style.
- Changes that impact ETL-facing behavior (inputs, outputs, configuration options, performance
	characteristics) MUST update the README or other user-facing documentation accordingly.

## Governance

- This constitution governs how the Wikidata Collector library is designed, implemented, tested,
	and versioned; it supersedes informal practices and ad-hoc conventions.
- Amendments to this constitution MUST:
	- Be proposed via a documented change (e.g., pull request) explaining the rationale and impact.
	- Specify the required semantic version bump (MAJOR/MINOR/PATCH) according to the rules above.
	- Include any necessary migration or upgrade guidance for ETL consumers.
- The constitution SHOULD be reviewed whenever a MAJOR release is planned or when significant
	changes to testing strategy, Python standards, or ETL usage patterns are introduced.
- CI and code review processes MUST verify that new work does not violate these principles; any
	intentional exceptions MUST be explicitly documented in the plan or spec for the change.

**Version**: 1.1.0 | **Ratified**: 2025-12-17 | **Last Amended**: 2025-12-17
