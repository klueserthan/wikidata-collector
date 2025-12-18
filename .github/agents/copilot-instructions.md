# Wikidata Collector - Copilot Instructions

> **Note**: These instructions document the **target architecture** for the `001-wikidata-etl-package` refactoring. Code examples show the planned iterator-based APIs, not the current legacy implementation. See `specs/001-wikidata-etl-package/` for full details and `tasks.md` for implementation status.

## Project Overview

**wikidata-collector** is a pure Python ETL library for streaming public figures and public institutions from Wikidata via SPARQL queries. It provides iterator-based APIs with robust proxy support, structured logging, and security features—designed specifically for batch ETL pipelines with no web framework dependencies.

**Core Purpose**: Library-first, ETL-oriented tool for querying Wikidata entities via SPARQL with type-safe data handling, iterator-based streaming, internal pagination management, and human-readable filter labels.

**Current Status**: Branch `001-wikidata-etl-package` represents a major refactoring from legacy tuple-based APIs to modern iterator-based streaming APIs. The specs in `specs/001-wikidata-etl-package/` define the target architecture.

## Technology Stack

- **Python**: ≥ 3.13 (target version per specs; current `.python-version` is 3.12 for compatibility during transition)
- **Core Libraries**:
  - `pydantic` v2 - Type-safe data models and validation
  - `requests` - HTTP client for SPARQL queries
  - `python-dotenv` - Environment configuration
- **Testing**:
  - `pytest` 8.0.0+ - Test framework with TDD workflow
  - `pytest-cov` 4.1.0+ - Code coverage
  - `pytest-mock` 3.12.0+ - Mocking utilities
- **Code Quality**:
  - `ruff` 0.14.9+ - Linting and formatting
  - Type checking (e.g., pyright/mypy) - Enforced in CI

## Project Structure

```
wikidata_collector/          # Main library module
├── __init__.py              # Public API exports (WikidataClient, models, exceptions)
├── client.py                # WikidataClient - main entry point
├── config.py                # WikidataCollectorConfig for settings
├── exceptions.py            # Custom exception classes
├── constants.py             # Wikidata type mappings (QIDs)
├── security.py              # SPARQL injection prevention utilities
├── models.py                # Pydantic data models (PublicFigure, PublicInstitution)
├── proxy.py                 # ProxyManager for rotation and retry logic
├── query_builders/          # SPARQL query construction
│   ├── figures_query_builder.py
│   └── institutions_query_builder.py
└── normalizers/             # Raw SPARQL result transformers
    ├── figure_normalizer.py
    └── institution_normalizer.py

tests/                       # Test suite (61+ unit tests)
├── conftest.py              # Pytest configuration and fixtures
├── unit/                    # Unit tests
│   ├── test_normalizers.py
│   ├── test_sparql_builders.py
│   ├── test_sparql_security.py
│   └── test_proxy_service.py
└── integration/             # Integration tests (optional)
```

## Development Commands

### Setup
```bash
# Clone and navigate to repository
cd /path/to/wikidata-collector

# Install dependencies (using uv or pip)
uv sync
# OR
pip install -e .

# Install dev dependencies
pip install -e ".[dev]"
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=wikidata_collector --cov-report=html

# Run specific test file
pytest tests/unit/test_sparql_security.py -v

# Run tests excluding integration tests
pytest -m "not integration"

# Run tests with verbose output
pytest -v
```

### Code Quality
```bash
# Lint code with ruff
ruff check .

# Format code with ruff
ruff format .

# Run both linting and tests
ruff check . && pytest
```

### Running Examples
```bash
# Run example usage
python example.py

# Run main module
python main.py
```

## Code Style and Conventions

### Python Style
- **Target Version**: Python ≥ 3.13 (as specified in specs/001-wikidata-etl-package/)
- **Type Hints**: Use modern type hints for all function signatures (e.g., `list[str]` not `List[str]`)
- **Docstrings**: Use Google-style docstrings for modules, classes, and functions
- **Imports**: Group imports (stdlib, third-party, local) with blank lines between groups
- **Iterators**: Prefer `collections.abc.Iterator` for return types over generators

### Naming Conventions
- **Classes**: PascalCase (e.g., `WikidataClient`, `PublicFigure`)
- **Functions/Methods**: snake_case (e.g., `iterate_public_figures`, `validate_qid`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `DEFAULT_PAGE_SIZE`)
- **Private members**: Prefix with underscore (e.g., `_fetch_page`)
- **Iterator methods**: Prefix with `iterate_` (e.g., `iterate_public_figures`)

### Common Patterns

#### 1. Iterator-Based Streaming APIs (NEW Architecture)
```python
# NEW: Stream entities one-by-one with iterator-based APIs
# Pagination is handled internally; callers just iterate
from wikidata_collector import WikidataClient

client = WikidataClient()

# Stream public figures with human-readable filter labels
for figure in client.iterate_public_figures(
    birthday_from="1990-01-01",
    nationality=["US", "DE"],  # ISO codes, NOT QIDs
    max_results=100,            # Optional limit
    lang="en"
):
    process(figure)  # figure is a PublicFigure Pydantic model

# Stream public institutions
for institution in client.iterate_public_institutions(
    founded_from="1990-01-01",
    country=["US"],
    types=["public broadcaster"],  # Human-readable type labels
    lang="en"
):
    process(institution)  # PublicInstitution Pydantic model
```

#### 2. Security-First Query Building (UNCHANGED)
```python
# ALWAYS validate QIDs before use in SPARQL
from wikidata_collector.security import validate_qid, escape_sparql_literal

qid = validate_qid("Q42")  # Raises ValueError if invalid
escaped = escape_sparql_literal(user_input)  # Escape string literals
```

#### 3. Human-Readable Filters Over QIDs (NEW)
```python
# NEW: Use ISO country codes, type labels instead of QIDs
# Query builders translate labels to SPARQL constraints internally
client.iterate_public_figures(
    nationality=["US", "DE", "FR"],  # NOT ["Q30", "Q183", "Q142"]
)

client.iterate_public_institutions(
    types=["government agency", "public broadcaster"]  # NOT QIDs
)
```

#### 4. Pydantic Models for Data (UNCHANGED)
```python
# Use Pydantic v2 for all data models
from typing import Literal
from pydantic import BaseModel, Field

class PublicFigure(BaseModel):
    id: str = Field(..., description="Wikidata QID")
    entity_kind: Literal["public_figure"] | None
    name: str | None
    aliases: list[str] = Field(default_factory=list)
    professions: list[str] = Field(default_factory=list)
    nationalities: list[str] = Field(default_factory=list)
    # Note: Supporting types like AccountEntry defined in data-model.md
    # ... more fields per specs/001-wikidata-etl-package/data-model.md
```

#### 5. Structured Logging (NEW)
```python
# Library emits structured logs for ETL observability
# Standard schema fields: event, entity_kind, filters, page, 
# result_count, duration_ms, status, error_type
import logging

logging.basicConfig(level=logging.INFO)
# WikidataClient automatically emits structured logs for:
# - query_started, page_fetched, iteration_completed
# - retry_scheduled, error_raised
```

## Testing Practices

### Test Structure
- **Location**: All tests in `tests/` directory
- **Naming**: Test files must start with `test_` (e.g., `test_iterators.py`)
- **Organization**: Use test classes for grouping related tests
- **TDD Workflow**: Write tests first, verify they fail, then implement feature

### Test Patterns
```python
class TestIteratePublicFigures:
    """Group related iterator tests."""
    
    def test_yields_matching_figures(self, mocker):
        """Test that iterator yields PublicFigure models matching filters."""
        # Mock SPARQL responses
        mock_response = mocker.Mock()
        mock_response.json.return_value = {
            "results": {"bindings": [/* ... */]}
        }
        mocker.patch('requests.get', return_value=mock_response)
        
        client = WikidataClient()
        figures = list(client.iterate_public_figures(
            birthday_from="1990-01-01",
            nationality=["US"],
            max_results=10
        ))
        
        assert len(figures) <= 10
        assert all(isinstance(f, PublicFigure) for f in figures)
    
    def test_invalid_filter_raises_error(self):
        """Test that invalid filters raise appropriate error."""
        client = WikidataClient()
        with pytest.raises(InvalidFilterError, match="Invalid date format"):
            list(client.iterate_public_figures(birthday_from="invalid"))
```

### Mocking External Calls
```python
# Use pytest-mock for mocking SPARQL responses
def test_iterator_pagination(mocker):
    """Test internal pagination handling."""
    # Mock multiple pages
    page1 = {"results": {"bindings": [/* 15 results */]}}
    page2 = {"results": {"bindings": [/* 10 results */]}}
    
    mock_resp1 = mocker.Mock()
    mock_resp1.json.return_value = page1
    mock_resp2 = mocker.Mock()
    mock_resp2.json.return_value = page2
    
    mocker.patch('requests.get', side_effect=[mock_resp1, mock_resp2])
    # Test that iterator correctly yields 25 total results...
```

### Coverage Expectations
- Aim for high test coverage on core functionality (iterators, query builders, normalizers)
- Security functions should have 100% coverage
- Edge cases must be tested: empty results, pagination boundaries, filter validation
- Integration tests for end-to-end ETL workflows when feasible

## Security Considerations

### SPARQL Injection Prevention
**CRITICAL**: All user inputs that go into SPARQL queries MUST be validated/escaped

```python
# QIDs - Validate format (Q followed by digits only)
from wikidata_collector.security import validate_qid
qid = validate_qid(user_qid)  # Raises ValueError if malformed

# String literals - Escape special characters
from wikidata_collector.security import escape_sparql_literal
safe_string = escape_sparql_literal(user_input)
query = f'FILTER(CONTAINS(LCASE(?label), "{safe_string}"))'
```

### Input Validation Rules
1. **QIDs**: Must match `^Q\d+$` pattern (e.g., Q42, Q12345)
2. **PIDs**: Must match `^P\d+$` pattern (e.g., P31, P279)
3. **String Literals**: Escape `\`, `"`, `\n`, `\r`, `\t` characters
4. **Date Formats**: Validate ISO-8601 format for birthday/founded filters
5. **Human-Readable Labels**: Validate and translate to QIDs internally in query builders

### Label Translation Security (NEW)
```python
# When accepting human-readable labels (e.g., "US", "public broadcaster"),
# query builders MUST translate them safely to SPARQL constraints
# Maintain approved label-to-QID mappings in constants.py
# Reject unknown labels with clear error messages
```

### Test Security Functions
Every security-related function MUST have tests for:
- Valid inputs (happy path)
- Invalid/malicious inputs (injection attempts)
- Edge cases (empty strings, special characters, Unicode)
- Label translation boundary cases (unknown labels, ambiguous labels)

## Common Tasks and Patterns

### Adding Iterator-Based APIs (NEW - Target Architecture)
1. Define iterator method in `wikidata_collector/client.py`
2. Accept human-readable filter labels (not QIDs)
3. Use query builders to translate labels and construct SPARQL
4. Implement internal pagination with fixed page size (default: 15)
5. Yield normalized Pydantic models one-by-one
6. Add structured logging for query events
7. Write tests that verify filtering, pagination, and model structure

Example (target API):
```python
def iterate_public_figures(
    self,
    *,
    birthday_from: str | None = None,
    nationality: list[str] | None = None,
    max_results: int | None = None,
    lang: str = "en",
) -> Iterator[PublicFigure]:
    """Yield public figures matching filters."""
    # Build SPARQL with label translation
    # Handle internal pagination
    # Emit structured logs
    # Yield PublicFigure models
```

### Adding a New Query Builder
1. Create or extend file in `wikidata_collector/query_builders/`
2. Translate human-readable labels to QIDs (use constants.py mappings)
3. Implement builder function with security validations
4. Support stable ordering by entity ID for pagination
5. Add comprehensive tests in `tests/unit/test_sparql_builders.py`
6. Document query parameters and SPARQL output format

### Adding a New Data Model
1. Define Pydantic v2 model in `wikidata_collector/models.py`
2. Use modern type hints: `list[str]` not `List[str]`
3. Include `entity_kind` discriminator field
4. Use `Field()` for metadata and validation
5. Export from `__init__.py` if public API
6. Add normalizer in `normalizers/` for SPARQL result transformation
7. Document in `specs/001-wikidata-etl-package/data-model.md`

### Adding Client Methods (DEPRECATED - Use Iterators Instead)
**Note**: New APIs should use iterator pattern, not tuple returns.
Legacy tuple-based methods may remain for backward compatibility.

### Updating Dependencies
1. Modify `pyproject.toml` dependencies section
2. Run `uv lock` to update `uv.lock`
3. Test thoroughly before committing

## Error Handling

### Custom Exceptions
Use specific exceptions from `wikidata_collector.exceptions`:
- `WikidataCollectorError` - Base exception
- `InvalidQIDError` - Invalid Wikidata entity ID format
- `InvalidFilterError` - Invalid filter parameters (PLANNED for refactoring)
- `EntityNotFoundError` - Entity does not exist
- `QueryExecutionError` - SPARQL query failed
- `ProxyConfigurationError` - Proxy misconfiguration (PLANNED for refactoring)
- `UpstreamUnavailableError` - Wikidata service temporarily unavailable (PLANNED for refactoring)

### Exception Pattern (Target Design)
```python
from wikidata_collector.exceptions import InvalidFilterError

def iterate_public_figures(
    self,
    birthday_from: str | None = None,
    # ...
) -> Iterator[PublicFigure]:
    """Yield public figures matching filters.
    
    Raises:
        InvalidFilterError: If filters are malformed or invalid.
        UpstreamUnavailableError: If WDQS is temporarily unavailable.
        ProxyConfigurationError: If proxy is misconfigured.
    """
    try:
        # Validate filters first (fail fast)
        if birthday_from and not is_valid_iso_date(birthday_from):
            raise InvalidFilterError(f"Invalid date format: {birthday_from}")
        # ... proceed with query
    except RequestException as e:
        raise UpstreamUnavailableError("WDQS unavailable") from e
```

### Structured Error Logging (NEW)
```python
# When errors occur, emit structured log with error_type
logger.error(
    "Query failed",
    extra={
        "event": "error_raised",
        "entity_kind": "public_figure",
        "error_type": "upstream_timeout",
        "filters": {"nationality": ["US"]},
        "duration_ms": 30000,
    }
)
```

## Environment Configuration

### Required Variables
```bash
CONTACT_EMAIL="your-email@example.com"  # Required for User-Agent header
```

### Optional Variables (Target Configuration)
```bash
PROXY_ENDPOINT="http://proxy:8080"           # Optional proxy endpoint (PLANNED - currently PROXY_LIST)
ALLOW_PROXY_FALLBACK="false"                  # Fail-closed by default (PLANNED)
INTERNAL_PAGE_SIZE="15"                       # SPARQL page size (default: 15, PLANNED)
SPARQL_TIMEOUT_SECONDS="60"
LOG_LEVEL="INFO"                              # For structured logging
```

### Loading Configuration
```python
# Auto-loaded from .env file via python-dotenv
from wikidata_collector import WikidataClient

client = WikidataClient()  # Loads from environment

# Or explicit configuration (target design)
from wikidata_collector.config import WikidataCollectorConfig
config = WikidataCollectorConfig(
    contact_email="test@example.com",
    proxy_endpoint="http://proxy:8080",      # PLANNED - currently proxy_list
    allow_proxy_fallback=False,               # PLANNED: Fail-closed default
    internal_page_size=15,                    # PLANNED: Fixed page size
)
client = WikidataClient(config)
```

## Best Practices for Contributors

1. **Follow TDD Workflow**: Write tests first, verify they fail, then implement (per constitution)
2. **Iterator-Based APIs**: New APIs should stream entities, not return bulk lists
3. **Human-Readable Filters**: Accept ISO codes/labels, not QIDs, in public APIs
4. **Make Minimal Changes**: Only modify what's necessary for the task
5. **Security First**: Validate all inputs, especially those used in SPARQL queries
6. **Type Safety**: Use modern type hints (`list[str]`) and Pydantic v2 models
7. **Structured Logging**: Emit logs with consistent schema for ETL observability
8. **Test Coverage**: Add tests for new functionality with clear scenarios
9. **No Breaking Changes**: Maintain backward compatibility or document migrations
10. **Consult Specs**: Refer to `specs/001-wikidata-etl-package/` for planned architecture

## Architecture Principles (from Constitution)

- **Library-first**: No long-running services, no hidden side-effects
- **ETL-oriented**: Designed for batch pipelines, not interactive use
- **Fail-fast validation**: Invalid filters raise clear exceptions early
- **Stable ordering**: Results ordered by entity ID for reproducibility
- **Observable**: Structured logs enable monitoring and debugging
- **Pythonic**: Simple, explicit APIs with minimal abstractions

## Debugging Tips

### Enable Structured Logging
```python
import logging
import json

# Configure JSON-like structured logging for ETL
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

# WikidataClient emits structured logs with schema:
# event, entity_kind, filters, page, result_count, duration_ms, status, error_type
```

### Test Iterator Behavior
```python
from wikidata_collector import WikidataClient

client = WikidataClient()

# Test with small max_results first
figures = list(client.iterate_public_figures(
    nationality=["US"],
    max_results=5  # Small limit for debugging
))

print(f"Retrieved {len(figures)} figures")
for fig in figures:
    print(f"  {fig.id}: {fig.name}")
```

### Inspect Generated SPARQL
```python
from wikidata_collector.query_builders.figures_query_builder import build_public_figures_query

# Build query with human-readable labels
query = build_public_figures_query(
    birthday_from="1990-01-01",
    nationality=["US"],  # Will be translated to QID internally
    limit=15,
    lang="en"
)
print(query)  # Inspect generated SPARQL with label translations
```

### Validate Security
```python
# Test validations and label translations
from wikidata_collector.security import validate_qid, escape_sparql_literal

try:
    validate_qid("Q42; DROP TABLE")  # Should raise ValueError
except ValueError as e:
    print(f"Caught injection attempt: {e}")

# Test label translation (PLANNED - to be implemented)
# from wikidata_collector.constants import translate_country_label
# qid = translate_country_label("US")  # Should return "Q30"
```

## Structured Logging Schema (NEW)

When debugging ETL issues, look for these log fields:

| Field | Type | Description |
|-------|------|-------------|
| `event` | string | Event name: `query_started`, `page_fetched`, `iteration_completed`, `retry_scheduled`, `error_raised` |
| `entity_kind` | string | `"public_figure"`, `"public_institution"`, or `null` |
| `filters` | object | Summarized filter set (date ranges, labels) |
| `page` | int | Internal page index or cursor (when relevant) |
| `result_count` | int | Number of entities in this event context |
| `duration_ms` | int | Elapsed time in milliseconds |
| `status` | string | `"success"`, `"retry"`, or `"failure"` |
| `error_type` | string | Machine-readable error category (e.g., `"invalid_filters"`, `"upstream_timeout"`) |

Example log entry:
```json
{
  "event": "page_fetched",
  "entity_kind": "public_figure",
  "filters": {"nationality": ["US"], "birthday_from": "1990-01-01"},
  "page": 2,
  "result_count": 15,
  "duration_ms": 1234,
  "status": "success"
}
```

---

**Last Updated**: 2025-12-18  
**Maintainer**: GitHub Copilot  
**Status**: Active Development - Refactoring to Iterator-Based APIs  
**Specs**: See `specs/001-wikidata-etl-package/` for detailed architecture and requirements

## Key Refactoring (Branch: 001-wikidata-etl-package)

This branch implements a major architectural shift from the legacy codebase:

### What's Changing
- **APIs**: From tuple returns `(data, proxy_used)` → Iterator-based streaming `Iterator[PublicFigure]`
- **Filters**: From QIDs `["Q30"]` → Human-readable labels `["US", "DE"]`
- **Target**: Python 3.12 (current) → Python ≥ 3.13 (planned per specs)
- **Pagination**: From exposed cursors → Hidden internal pagination (fixed 15/page default)
- **Logging**: From basic logs → Structured logging with schema
- **Proxy**: From rotation list → Single endpoint with fail-closed default

### What's Staying
- Security validations (`validate_qid`, `escape_sparql_literal`)
- Pydantic v2 models
- Query builders (extended for label translation)
- Test-driven development workflow
- Library-first, ETL-oriented design

### Implementation Guidance
1. Read specs in `specs/001-wikidata-etl-package/` before implementing new features
2. Follow task breakdown in `specs/001-wikidata-etl-package/tasks.md`
3. Implement iterators in phases per user stories (US1 → US2 → US3)
4. Maintain backward compatibility where feasible; document breaking changes

<!-- MANUAL ADDITIONS START -->
<!-- Add any repository-specific instructions below this line -->
<!-- MANUAL ADDITIONS END -->
