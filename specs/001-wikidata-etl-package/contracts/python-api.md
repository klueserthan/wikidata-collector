# Python API Contracts: Wikidata Public Entities ETL Package

## Overview

The library exposes iterator-based functions that hide pagination and yield normalized
`PublicFigure` and `PublicInstitution` models. Callers provide filter parameters and optionally a
maximum number of results; the library handles SPARQL query construction, pagination, and
normalization internally.

## Public API (Conceptual Signatures)

### Public Figures Iterator

```python
from collections.abc import Iterator
from wikidata_collector.models import PublicFigure

class WikidataClient:
    def iterate_public_figures(
        self,
        *,
        birthday_from: str | None = None,
        birthday_to: str | None = None,
        nationality: list[str] | None = None,
        max_results: int | None = None,
        lang: str = "en",
    ) -> Iterator[PublicFigure]:
        """Yield public figures matching the given filters.

        - Applies filters on birthday and nationality as specified in the feature spec.
        - Expects human-readable nationality labels or codes (e.g., "US", "DE") rather than QIDs;
          query builders translate these into appropriate SPARQL constraints.
        - Uses a stable internal ordering by entity ID.
        - Hides SPARQL pagination; callers simply iterate over results.
        - Respects `max_results` when provided; otherwise yields all matches subject to
          environment and upstream constraints.
        """
```

### Public Institutions Iterator

```python
from collections.abc import Iterator
from wikidata_collector.models import PublicInstitution

class WikidataClient:
    def iterate_public_institutions(
        self,
        *,
        founded_from: str | None = None,
        founded_to: str | None = None,
        country: list[str] | None = None,
        types: list[str] | None = None,
        headquarter: list[str] | None = None,
        max_results: int | None = None,
        lang: str = "en",
    ) -> Iterator[PublicInstitution]:
        """Yield public institutions matching the given filters.

        - Applies filters on founding date, country, types, and headquarter.
        - Expects human-readable labels or codes for country (e.g., "US", "DE") and institution
          types (e.g., "public broadcaster"), with translation to SPARQL handled internally.
        - Uses a stable internal ordering by entity ID.
        - Hides SPARQL pagination; callers simply iterate over results.
        - Respects `max_results` when provided; otherwise yields all matches subject to
          environment and upstream constraints.
        """
```

### Proxy and Logging Configuration (Conceptual)

Proxy and logging are configured via the client configuration object (details to be finalized
in implementation):

- Proxy endpoint: optional; when set, calls are routed through the proxy, with a fail-closed
  default and an explicit option to allow fallback.
- Structured logging: library emits structured log records (e.g., JSON payloads) for queries,
  internal pages, and errors.

## Error Contracts

- Invalid filters (e.g., malformed dates, unknown identifiers) raise specific exceptions from
  `wikidata_collector.exceptions`.
- Upstream failures or timeouts raise distinct exceptions, allowing callers to distinguish
  retryable conditions.
- Proxy misconfiguration or unreachability raises clearly identified errors; fallback behavior
  is controlled by configuration.

## Compatibility and Versioning

- The iterator methods and their parameter names constitute part of the public API and are
  subject to semantic versioning rules in the project constitution.
- Changes to required fields or semantics of the returned models must be treated as breaking
  changes and documented accordingly.
