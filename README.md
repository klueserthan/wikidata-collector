# Wikidata Collector

A Python library for querying public figures and institutions from [Wikidata](https://www.wikidata.org/) via SPARQL. Returns typed, normalized Pydantic models with automatic pagination, proxy rotation, and high-level safeguards against SPARQL injection (validated QIDs, mapped filters, and date validation).

## Installation

```bash
pip install .
```

Requires Python 3.13+. Dependencies: `pydantic`, `requests`, `python-dotenv`.

## Quick Start

```python
from wikidata_collector import WikidataClient

client = WikidataClient()

# Iterate over public figures — handles pagination automatically
for figure in client.iterate_public_figures(
    birthday_from="1990-01-01",
    nationality="US",
    max_results=10,
):
    print(f"{figure.qid}: {figure.name}")
    print(f"  Born: {figure.birth_date}")
    print(f"  Countries: {', '.join(figure.countries)}")
    print(f"  Occupations: {', '.join(figure.occupations)}")

# Iterate over public institutions
for inst in client.iterate_public_institutions(
    country="US",
    types=["government_agency"],
    max_results=10,
):
    print(f"{inst.qid}: {inst.name}")
    print(f"  Countries: {', '.join(inst.countries)}")
    print(f"  Types: {', '.join(inst.types)}")
```

## API Overview

### High-Level Iterators (Recommended)

These handle pagination automatically and yield normalized Pydantic model objects one at a time.

#### `client.iterate_public_figures(...)`

```python
for figure in client.iterate_public_figures(
    birthday_from="1990-01-01",     # Optional: ISO date string
    birthday_to="2000-12-31",       # Optional: ISO date string
    nationality="Germany",          # Optional: country name, ISO code, or QID
    max_results=100,                # Optional: stop after N results
    lang="en",                      # Optional: language for labels (default: "en")
):
    ...  # figure is a PublicFigureNormalizedRecord
```

Supported nationality values: country names (`"Germany"`, `"United States"`), ISO codes (`"US"`, `"UK"`), or QIDs (`"Q30"`). See `constants.py` for the full mapping.

#### `client.iterate_public_institutions(...)`

```python
for inst in client.iterate_public_institutions(
    country="US",                   # Optional: country name, ISO code, or QID
    types=["government_agency"],    # Optional: list of type keys or QIDs
    max_results=100,                # Optional: stop after N results
    lang="en",                      # Optional: language for labels (default: "en")
):
    ...  # inst is a PublicInstitutionNormalizedRecord
```

Supported type keys: `political_party`, `government_agency`, `municipality`, `media_outlet`, `ngo`, `ministry`. Or pass QIDs directly (e.g., `"Q327333"`).

### Low-Level Page Methods

For manual pagination control. Return `(List[NormalizedRecord], proxy_used_str)`.

#### `client.get_public_figures(...)`

```python
figures, proxy = client.get_public_figures(
    birthday_from="1990-01-01",     # Optional
    birthday_to="2000-12-31",       # Optional
    country="Q30",                  # Optional: country name or QID
    occupations=["politician"],     # Optional: list of occupation keys or QIDs
    lang="en",                      # Optional
    limit=15,                       # Optional: page size (default: 15)
    cursor=0,                       # Optional: OFFSET pagination
    after_qid="Q12345",            # Optional: keyset pagination (preferred)
)
```

Supported occupation keys: `politician`, `actor`, `musician`, `writer`, `journalist`, `scientist`, `athlete`, and many more. See `constants.py` for the full mapping.

#### `client.get_public_institutions(...)`

```python
institutions, proxy = client.get_public_institutions(
    country="Q30",                  # Optional
    type=["Q327333"],               # Optional: list of type QIDs or mapped keys
    lang="en",                      # Optional
    limit=15,                       # Optional
    cursor=0,                       # Optional
    after_qid=None,                 # Optional
)
```

### Lower-Level Iterators

These also handle pagination but without input validation or `max_results`. Used internally by `iterate_*`.

- `client.iter_public_figures(birthday_from, birthday_to, nationality, profession, lang, limit)`
- `client.iter_public_institutions(country, type, lang, limit)`

### Raw SPARQL Execution

```python
result_dict, proxy = client.execute_sparql_query("SELECT ?item WHERE { ... }")
```

## Data Models

All query methods return Pydantic models. Key fields:

### `PublicFigureNormalizedRecord`

| Field | Type | Description |
|-------|------|-------------|
| `qid` | `str` | Wikidata QID (e.g., `"Q42"`) |
| `name` | `str` | Label in requested language |
| `description` | `Optional[str]` | Entity description |
| `birth_date` | `Optional[datetime]` | Date of birth |
| `death_date` | `Optional[datetime]` | Date of death |
| `gender` | `Optional[str]` | Gender label |
| `image` | `Optional[str]` | Image URL |
| `countries` | `List[str]` | Nationality labels |
| `occupations` | `List[str]` | Occupation labels |
| `accounts` | `List[AccountEntry]` | Social media accounts |
| `websites` | `List[WebsiteEntry]` | Associated websites |

### `PublicInstitutionNormalizedRecord`

| Field | Type | Description |
|-------|------|-------------|
| `qid` | `str` | Wikidata QID |
| `name` | `str` | Label in requested language |
| `description` | `Optional[str]` | Entity description |
| `founded_date` | `Optional[datetime]` | Date founded |
| `dissolved_date` | `Optional[datetime]` | Date dissolved |
| `image` | `Optional[str]` | Image URL |
| `countries` | `List[str]` | Country labels |
| `types` | `List[str]` | Institution type labels |
| `accounts` | `List[AccountEntry]` | Social media accounts |
| `websites` | `List[WebsiteEntry]` | Associated websites |

Both models have a `.generate_pretty_string()` method for human-readable output and a `.id` property alias for `.qid`.

**Data aggregation**: SPARQL returns one row per multi-valued field (each occupation, country, etc. produces a separate row). The library automatically groups rows by QID and merges multi-valued fields into lists.

## Configuration

### Environment Variables

```bash
CONTACT_EMAIL="you@example.com"       # User-Agent contact (recommended by Wikidata)
PROXY_LIST="http://p1:8080,http://p2:8080"  # Comma-separated proxy URLs
SPARQL_TIMEOUT_SECONDS=60             # Request timeout (default: 60)
MAX_RETRIES=3                         # Retry attempts (default: 3)
PROXY_COOLDOWN_SECONDS=300            # Failed proxy cooldown (default: 300)
DEFAULT_LIMIT=15                      # Page size for iterators (default: 15)
```

### Programmatic

```python
from wikidata_collector.config import WikidataCollectorConfig

config = WikidataCollectorConfig(
    contact_email="you@example.com",
    proxy_list=["http://proxy:8080"],
    sparql_timeout_seconds=60,
    max_retries=3,
    proxy_cooldown_seconds=300,
    default_limit=15,
)
client = WikidataClient(config)
```

## Pagination

### Keyset Pagination (Recommended)

The iterator APIs use keyset pagination automatically — no manual work needed. For manual control with the low-level `get_*` methods:

```python
# First page
figures, _ = client.get_public_figures(country="Q30", limit=15)

# Next page — use last QID as cursor
figures, _ = client.get_public_figures(
    country="Q30", limit=15, after_qid=figures[-1].qid
)
```

### OFFSET Pagination (Fallback)

```python
page1, _ = client.get_public_figures(country="Q30", limit=15, cursor=0)
page2, _ = client.get_public_figures(country="Q30", limit=15, cursor=15)
```

Keyset pagination is more reliable — OFFSET can drift when data changes between requests.

## Error Handling

```python
from wikidata_collector.exceptions import (
    WikidataCollectorError,       # Base exception
    InvalidQIDError,              # Malformed QID
    InvalidFilterError,           # Bad filter params (dates, max_results)
    QueryExecutionError,          # SPARQL query failed after retries
    ProxyMisconfigurationError,   # All proxies failed
    UpstreamUnavailableError,     # Wikidata returned 502/503/504
    EntityNotFoundError,          # Entity not found
)
```

## Security

All query builders validate QIDs (`Q` + digits only) and escape string literals to prevent SPARQL injection. Proxy URLs are validated against internal/private IP ranges (SSRF prevention).

```python
from wikidata_collector.security import validate_qid, escape_sparql_literal

validate_qid("Q42")                    # OK
validate_qid("Q42; DROP")              # Raises ValueError
escape_sparql_literal('test" inject')  # Returns: 'test\" inject'
```

## Structured Logging

The library uses Python's `logging` module under the `wikidata_collector` namespace. Enable it to see query execution details:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

Log events include structured `extra` fields:
- **Query execution**: `query_type`, `page`, `raw_count`, `unique_qid_count`, `latency_ms`, `proxy_used`
- **Retries**: `event="retry"`, `attempt`, `max_retries`, `reason`, `wait_time_seconds`
- **Failures**: `event="query_failure"`, `error_category`, `error_message`, `attempts`
- **Iteration lifecycle**: `event="iteration_started"`, `event="iteration_completed"`, `result_count`, `duration_ms`

## Performance Notes

- Default page size is 15 entities — tuned for Wikidata Query Service timeouts (~60s)
- Use QIDs instead of labels for faster queries (avoids SPARQL label joins)
- The iterator API uses keyset pagination, which is more efficient than OFFSET
- Typical latency: 1–3 seconds per page for simple queries

## Project Structure

```
wikidata_collector/
├── __init__.py              # Public exports
├── client.py                # WikidataClient (queries, iterators, pagination)
├── config.py                # WikidataCollectorConfig
├── models.py                # Pydantic models (WikiRecord + NormalizedRecord)
├── exceptions.py            # Exception hierarchy
├── constants.py             # Country, profession, institution type mappings
├── security.py              # QID validation, SPARQL literal escaping
├── proxy.py                 # Proxy rotation with failure detection
└── query_builders/
    ├── figures_query_builder.py
    └── institutions_query_builder.py
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=wikidata_collector --cov-report=html

# Lint
ruff check .

# Type check
pyright
```

## License

MIT
