# Wikidata Collector

A pure Python library for fetching public figures and institutions from Wikidata using SPARQL queries with robust proxy rotation, caching, and security features.

## Features

- **Pure Python Module**: No FastAPI or web framework dependencies - use in any Python project
- **SPARQL Query Builder**: Type-safe query construction with security validation
- **Keyset Pagination**: Deterministic QID-based cursor pagination (no OFFSET drift)
- **Iterator API**: High-level iterators that handle pagination automatically (internal page size: 15 entities)
- **Multi-Valued Fields**: Correctly returns all professions, awards, nationalities, etc.
- **Proxy Rotation**: Round-robin with failure detection, retry/backoff, and Retry-After handling
- **Comprehensive Filtering**: Birth dates, nationality, profession, institution types, country, jurisdiction
- **Caching**: TTL-based in-memory cache for SPARQL queries (configurable)
- **Security**: Built-in SPARQL injection prevention with QID validation and literal escaping
- **Data Models**: Pydantic models for type-safe data handling
- **Structured Logging**: Comprehensive structured logging for observability and monitoring
- **Testing**: Comprehensive test suite with 170 tests (125 unit, 42 integration, 3 live)

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

```python
from wikidata_collector import WikidataClient

# Initialize client with default configuration
client = WikidataClient()

# Or with custom configuration
from wikidata_collector.config import WikidataCollectorConfig

config = WikidataCollectorConfig(
    contact_email="your-email@example.com",
    proxy_list=["http://proxy1:8080", "http://proxy2:8080"],
    cache_ttl_seconds=300,
    sparql_timeout_seconds=60
)
client = WikidataClient(config)

# Iterator API (Recommended) - Returns normalized PublicFigure objects
for figure in client.iterate_public_figures(
    birthday_from="1990-01-01",
    nationality=["US"],  # United States (ISO code or label)
    max_results=50,
    lang="en"
):
    print(f"{figure.id}: {figure.name}")
    print(f"  Birthday: {figure.birthday}")
    print(f"  Nationalities: {', '.join(figure.nationalities)}")
    print(f"  Professions: {', '.join(figure.professions)}")

# Iterator API for institutions - Returns normalized PublicInstitution objects
for institution in client.iterate_public_institutions(
    country="US",  # Single country (ISO code or label)
    types=["public broadcaster"],  # Institution types
    max_results=50,
    lang="en"
):
    print(f"{institution.id}: {institution.name}")
    print(f"  Founded: {institution.founded}")
    print(f"  Country: {', '.join(institution.country)}")
    print(f"  Types: {', '.join(institution.types)}")

# Lower-level API - For advanced use cases, returns raw SPARQL bindings
results, proxy_used = client.get_public_figures(
    birthday_from="1990-01-01",
    nationality=["Q30"],  # QID preferred for performance
    profession=["Q33999"],  # Actor
    lang="en",
    limit=50
)

# Get single entity by QID
entity, proxy_used = client.get_entity(
    qid="Q42",  # Douglas Adams
    lang="en"
)
```

## Configuration

### Environment Variables

```bash
# Required: Contact email for User-Agent
export CONTACT_EMAIL="your-email@example.com"

# Optional: Proxy configuration
export PROXY_LIST="http://proxy1:8080,http://proxy2:8080"

# Optional: Cache settings
export CACHE_TTL_SECONDS=300
export CACHE_MAX_SIZE=10000

# Optional: Request settings
export SPARQL_TIMEOUT_SECONDS=60
export PROXY_COOLDOWN_SECONDS=300
```

### Programmatic Configuration

```python
from wikidata_collector import WikidataClient
from wikidata_collector.config import WikidataCollectorConfig

config = WikidataCollectorConfig(
    contact_email="your-email@example.com",
    proxy_list=["http://proxy:8080"],
    cache_ttl_seconds=300,
    cache_max_size=10000,
    sparql_timeout_seconds=60,
    max_retries=3,
    proxy_cooldown_seconds=300
)

client = WikidataClient(config)
```

## Pagination

### Iterator API (Recommended)

The iterator API handles pagination automatically and returns normalized objects:

```python
# Automatically paginates through all results
for figure in client.iterate_public_figures(
    nationality=["US"],
    max_results=100  # Optional limit
):
    print(f"{figure.name}")

# Without max_results, yields all matching entities
for institution in client.iterate_public_institutions(
    country="US",
    types=["university"]
):
    print(f"{institution.name}")
```

### Manual Keyset Pagination (Advanced)

For lower-level control, use keyset pagination:

```python
# First page
results, proxy = client.get_public_figures(
    nationality=["Q30"],
    limit=50
)

# Get last QID for next page
last_qid = results[-1]["person"]["value"].split("/")[-1]

# Next page
results, proxy = client.get_public_figures(
    nationality=["Q30"],
    limit=50,
    after_qid=last_qid
)
```

### OFFSET Pagination (Fallback)

```python
# Page 1
results, proxy = client.get_public_figures(nationality=["Q30"], limit=50, cursor=0)

# Page 2
results, proxy = client.get_public_figures(nationality=["Q30"], limit=50, cursor=50)
```

## Security

The library includes built-in security features:

```python
from wikidata_collector.security import validate_qid, escape_sparql_literal

# QID validation
validate_qid("Q42")  # ✓ Passes
validate_qid("Q30; DROP TABLE")  # ✗ Raises ValueError

# Literal escaping
escaped = escape_sparql_literal('test" injection')  # Returns: 'test\" injection'
```

All query builders automatically validate QIDs and escape string literals to prevent injection attacks.

## Data Models

```python
from wikidata_collector.models import PublicFigure, PublicInstitution

# Public Figure
figure = PublicFigure(
    id="Q42",
    entity_kind="public_figure",
    name="Douglas Adams",
    professions=["writer", "humorist"],
    nationalities=["United Kingdom"],
    birthday="1952-03-11T00:00:00Z",
    # ... more fields
)

# Public Institution
institution = PublicInstitution(
    id="Q95",
    entity_kind="public_institution",
    name="Google",
    types=["business", "public company"],
    country=["USA"],
    founded="1998-09-04T00:00:00Z",
    # ... more fields
)
```

## Query Builders

For advanced use cases, use the query builders directly:

```python
from wikidata_collector.query_builders.figures_query_builder import build_public_figures_query
from wikidata_collector.query_builders.institutions_query_builder import build_public_institutions_query

# Build a custom SPARQL query
query = build_public_figures_query(
    birthday_from="1990-01-01",
    nationality=["Q30"],
    profession=["Q33999"],
    lang="en",
    limit=50,
    after_qid="Q12345"
)

# Execute with the client
result, proxy = client.execute_sparql_query(query)
```

## Error Handling

The library provides specific exception types for different error categories:

```python
from wikidata_collector.exceptions import (
    WikidataCollectorError,
    InvalidQIDError,
    EntityNotFoundError,
    QueryExecutionError,
    ProxyMisconfigurationError,
    UpstreamUnavailableError,
    InvalidFilterError,
)

try:
    results = list(client.iterate_public_figures(
        birthday_from="2000-01-01",
        nationality=["United States"]
    ))
except InvalidFilterError as e:
    print(f"Invalid filter configuration: {e}")
except ProxyMisconfigurationError as e:
    print(f"Proxy configuration issue: {e}")
except UpstreamUnavailableError as e:
    print(f"Wikidata service unavailable: {e}")
except QueryExecutionError as e:
    print(f"Query failed after retries: {e}")
```

## Structured Logging

The library emits structured logs for observability and monitoring:

```python
import logging
import json

# Configure structured logging handler
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(message)s'))

logger = logging.getLogger('wikidata_collector')
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Now all operations will emit structured logs with extra fields:
# - query_type: Type of query being executed
# - result_count: Number of results returned
# - latency_ms: Query execution time
# - proxy_used: Proxy URL or "direct"
# - event: Event type (e.g., "retry", "query_failure")
# - attempt, max_retries, reason: For retry events
# - error_category, error_message: For failure events

results = list(client.iterate_public_figures(
    birthday_from="2000-01-01",
    nationality="United States",
    max_results=100
))
```

Structured log fields can be accessed via `LogRecord.extra` for parsing and monitoring:
- Success logs include: `query_type`, `page`, `result_count`, `latency_ms`, `proxy_used`, `params`
- Retry logs include: `event="retry"`, `attempt`, `max_retries`, `reason`, `wait_time_seconds`, `proxy`
- Failure logs include: `event="query_failure"`, `error_category`, `error_message`, `attempts`, `filters`

## Performance

### Internal Per-Page Limit: 15 Entities

The library uses an internal per-page limit of 15 entities (`DEFAULT_PAGE_SIZE = 15`) for optimal performance with the Wikidata Query Service:

**Rationale**:
- Wikidata Query Service has strict timeouts (~60 seconds)
- Complex queries with multiple OPTIONAL clauses complete faster with smaller pages
- Memory-efficient streaming for large result sets
- Predictable latency (typically < 3 seconds per page)

**Performance Guidelines**:
- Small workloads (< 1,000 entities): Default per-page limit works well
- Large workloads (> 10,000 entities): Use restrictive filters or off-peak hours
- Time-sensitive queries: Use `max_results` to limit total results
- Best throughput: Iterator API uses keyset pagination automatically

**Query Optimization**:
- Use QIDs instead of labels for faster queries (e.g., `nationality=["Q30"]` vs `["United States"]`)
- Keyset pagination (automatic) is more efficient than OFFSET pagination
- Monitor latency using structured logging (`latency_ms` field)

**Measured Performance** (based on live integration tests):
- Simple queries (1-2 filters): ~1-2 seconds per page
- Complex queries (multiple filters + labels): ~2-4 seconds per page
- Empty result queries: < 1 second

The `limit` parameter is available in `iter_public_figures` and `iter_public_institutions` for tuning when needed.

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=wikidata_collector --cov-report=html

# Run specific test file
pytest tests/unit/test_sparql_builders.py -v
```

### Project Structure

```
wikidata_collector/          # Main module
├── __init__.py              # Public API exports
├── client.py                # WikidataClient
├── config.py                # Configuration
├── exceptions.py            # Custom exceptions
├── constants.py             # Type mappings
├── security.py              # Security validation
├── models.py                # Pydantic data models
├── cache.py                 # TTL cache implementation
├── proxy.py                 # Proxy rotation manager
├── query_builders/          # SPARQL query builders
│   ├── figures_query_builder.py
│   └── institutions_query_builder.py
└── normalizers/             # Data normalizers
    ├── figure_normalizer.py
    └── institution_normalizer.py

tests/                       # Test suite
├── conftest.py              # Pytest configuration
└── unit/                    # Unit tests
    ├── test_normalizers.py
    ├── test_sparql_builders.py
    ├── test_sparql_security.py
    └── test_proxy_service.py
```

## Best Practices

### Use Iterator API for ETL Workflows

```python
# ✓ Recommended - handles pagination automatically, returns typed objects
for figure in client.iterate_public_figures(
    nationality=["US"],
    max_results=1000
):
    process(figure)

# ✗ Manual pagination - more code, raw SPARQL bindings
results, _ = client.get_public_figures(nationality=["Q30"], limit=50)
```

### Use QIDs for Better Performance (Lower-level API)

```python
# ✓ Fast - uses direct QID matching
client.get_public_figures(nationality=["Q30"])  # United States

# ✗ Slow - requires label joins in SPARQL
client.get_public_figures(nationality=["United States"])

# Note: Iterator API accepts both and handles translation
```

### Prefer Keyset Pagination (Lower-level API)

```python
# ✓ Deterministic and efficient
results, _ = client.get_public_figures(limit=50, after_qid="Q12345")

# ✗ Can have drift if data changes
results, _ = client.get_public_figures(limit=50, cursor=100)
```

### Set Contact Email

```python
# Required by Wikidata Query Service
config = WikidataCollectorConfig(
    contact_email="your-email@example.com"
)
```

### Use Appropriate Result Limits

```python
# ✓ Recommended - internal page size is 15, max_results controls total
for figure in client.iterate_public_figures(max_results=100):
    process(figure)

# ✓ Also good - no limit, yields all matches
for figure in client.iterate_public_figures(nationality=["US"]):
    process(figure)
```

## Common Use Cases

### Finding All Actors Born After 1990

```python
# Using iterator API (recommended)
for figure in client.iterate_public_figures(
    birthday_from="1990-01-01",
    max_results=100,
    lang="en"
):
    # Filter by profession in your code or add profession filter
    if "actor" in [p.lower() for p in figure.professions]:
        print(f"{figure.name} - {figure.birthday}")

# Using lower-level API with QID
results, _ = client.get_public_figures(
    birthday_from="1990-01-01",
    profession=["Q33999"],  # Actor QID
    lang="en",
    limit=100
)
```

### Finding US Government Agencies

```python
# Using iterator API (recommended)
for institution in client.iterate_public_institutions(
    country="US",  # ISO code
    types=["government agency"],
    max_results=100,
    lang="en"
):
    print(f"{institution.name} - Founded: {institution.founded}")

# Using lower-level API with QID
results, _ = client.get_public_institutions(
    type=["Q327333"],  # Government agency QID
    country="Q30",  # United States QID
    lang="en",
    limit=100
)
```

### Fetching Entity Details

```python
entity, _ = client.get_entity("Q42")  # Douglas Adams

# Access entity data
labels = entity.get("labels", {})
claims = entity.get("claims", {})
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[Add your license information here]
