# Wikidata Collector

A pure Python library for fetching public figures and institutions from Wikidata using SPARQL queries with robust proxy rotation, caching, and security features.

## Features

- **Pure Python Module**: No FastAPI or web framework dependencies - use in any Python project
- **SPARQL Query Builder**: Type-safe query construction with security validation
- **Keyset Pagination**: Deterministic QID-based cursor pagination (no OFFSET drift)
- **Multi-Valued Fields**: Correctly returns all professions, awards, nationalities, etc.
- **Proxy Rotation**: Round-robin with failure detection, retry/backoff, and Retry-After handling
- **Comprehensive Filtering**: Birth dates, nationality, profession, institution types, country, jurisdiction
- **Caching**: TTL-based in-memory cache for SPARQL queries (configurable)
- **Security**: Built-in SPARQL injection prevention with QID validation and literal escaping
- **Data Models**: Pydantic models for type-safe data handling
- **Testing**: Comprehensive test suite with 61 unit tests

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

# Query public figures
results, proxy_used = client.get_public_figures(
    birthday_from="1990-01-01",
    nationality=["Q30"],  # United States (QID preferred for performance)
    profession=["Q33999"],  # Actor
    lang="en",
    limit=50
)

# Process results
for item in results:
    qid = item["person"]["value"].split("/")[-1]
    name = item.get("personLabel", {}).get("value")
    print(f"{qid}: {name}")

# Query institutions
results, proxy_used = client.get_public_institutions(
    type=["Q327333"],  # Government agency (use QID for better performance)
    country="Q30",  # United States
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

### Keyset Pagination (Recommended)

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

```python
from wikidata_collector.exceptions import (
    WikidataCollectorError,
    InvalidQIDError,
    EntityNotFoundError,
    QueryExecutionError
)

try:
    entity, proxy = client.get_entity("INVALID")
except InvalidQIDError as e:
    print(f"Invalid QID format: {e}")
except EntityNotFoundError as e:
    print(f"Entity not found: {e}")
except QueryExecutionError as e:
    print(f"Query failed: {e}")
```

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

### Use QIDs for Better Performance

```python
# ✓ Fast - uses direct QID matching
client.get_public_figures(nationality=["Q30"])  # United States

# ✗ Slow - requires label joins in SPARQL
client.get_public_figures(nationality=["United States"])
```

### Prefer Keyset Pagination

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

### Use Smaller Page Sizes

```python
# ✓ Recommended - avoids WDQS timeouts
results, _ = client.get_public_figures(limit=50)

# ✗ May timeout for complex queries
results, _ = client.get_public_figures(limit=500)
```

## Common Use Cases

### Finding All Actors Born After 1990

```python
results, _ = client.get_public_figures(
    birthday_from="1990-01-01",
    profession=["Q33999"],  # Actor QID
    lang="en",
    limit=100
)
```

### Finding US Government Agencies

```python
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
