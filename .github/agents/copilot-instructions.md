# Wikidata Collector - Copilot Instructions

## Project Overview

**wikidata-collector** is a pure Python library for fetching public figures and institutions from Wikidata using SPARQL queries. It provides robust proxy rotation, caching, and security features with no web framework dependencies.

**Core Purpose**: Standalone module for querying Wikidata entities via SPARQL with type-safe data handling, security validation, and efficient pagination.

## Technology Stack

- **Python**: 3.12+ (target version specified in `.python-version`)
- **Core Libraries**:
  - `pydantic` v2.12.3 - Type-safe data models and validation
  - `requests` 2.32.5 - HTTP client for SPARQL queries
  - `python-dotenv` 1.1.1 - Environment configuration
- **Testing**:
  - `pytest` 8.0.0 - Test framework
  - `pytest-cov` 4.1.0 - Code coverage
  - `pytest-mock` 3.12.0 - Mocking utilities
- **Code Quality**:
  - `ruff` 0.14.9+ - Linting and formatting

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
- **Target Version**: Python 3.12+
- **Type Hints**: Use type hints for all function signatures
- **Docstrings**: Use Google-style docstrings for modules, classes, and functions
- **Imports**: Group imports (stdlib, third-party, local) with blank lines between groups

### Naming Conventions
- **Classes**: PascalCase (e.g., `WikidataClient`, `PublicFigure`)
- **Functions/Methods**: snake_case (e.g., `get_public_figures`, `validate_qid`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `DEFAULT_TIMEOUT`)
- **Private members**: Prefix with underscore (e.g., `_get_current_timestamp`)

### Common Patterns

#### 1. Return Tuples for Data + Metadata
```python
# Always return (data, metadata) tuple for client methods
def get_public_figures(...) -> Tuple[List[Dict[str, Any]], str]:
    results = execute_query(...)
    return results, proxy_used  # Return data + which proxy was used
```

#### 2. Security-First Query Building
```python
# ALWAYS validate QIDs before use
from wikidata_collector.security import validate_qid, escape_sparql_literal

qid = validate_qid("Q42")  # Raises ValueError if invalid
escaped = escape_sparql_literal(user_input)  # Escape string literals
```

#### 3. Optional Configuration
```python
# Support both default and custom configuration
def __init__(self, config: Optional[WikidataCollectorConfig] = None):
    self.config = config or WikidataCollectorConfig()  # Load from env if None
```

#### 4. Pydantic Models for Data
```python
# Use Pydantic v2 for all data models
from pydantic import BaseModel, Field

class PublicFigure(BaseModel):
    id: str = Field(..., description="Wikidata QID")
    name: str
    professions: List[str] = Field(default_factory=list)
```

## Testing Practices

### Test Structure
- **Location**: All tests in `tests/` directory
- **Naming**: Test files must start with `test_` (e.g., `test_security.py`)
- **Organization**: Use test classes for grouping related tests

### Test Patterns
```python
class TestValidateQID:
    """Group related validation tests."""
    
    def test_valid_qid(self):
        """Test description should explain what is being tested."""
        result = validate_qid("Q42")
        assert result == "Q42"
    
    def test_invalid_qid_raises_error(self):
        """Test that invalid input raises appropriate error."""
        with pytest.raises(ValueError, match="Invalid QID format"):
            validate_qid("INVALID")
```

### Mocking External Calls
```python
# Use pytest-mock for mocking external dependencies
def test_sparql_query(mocker):
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"results": {"bindings": []}}
    mocker.patch('requests.get', return_value=mock_response)
    # Test your code...
```

### Coverage Expectations
- Aim for high test coverage on core functionality (security, query builders, client)
- Security functions should have 100% coverage
- Edge cases and error conditions must be tested

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
4. **Language Codes**: Validate against expected format (2-letter codes)

### Test Security Functions
Every security-related function MUST have tests for:
- Valid inputs (happy path)
- Invalid/malicious inputs (injection attempts)
- Edge cases (empty strings, special characters, Unicode)

## Common Tasks and Patterns

### Adding a New Query Builder
1. Create file in `wikidata_collector/query_builders/`
2. Implement builder function with security validations
3. Add comprehensive tests in `tests/unit/test_sparql_builders.py`
4. Document query parameters and return format

### Adding a New Data Model
1. Define Pydantic model in `wikidata_collector/models.py`
2. Use `Field()` for metadata and validation
3. Export from `__init__.py` if public API
4. Add normalizer if needed for SPARQL result transformation

### Adding Client Methods
1. Add method to `WikidataClient` class in `client.py`
2. Return `Tuple[data, proxy_used]` for consistency
3. Use existing query builders and validators
4. Add docstring with Args, Returns, and Raises sections
5. Write unit tests with mocked external calls

### Updating Dependencies
1. Modify `pyproject.toml` dependencies section
2. Run `uv lock` to update `uv.lock`
3. Test thoroughly before committing

## Error Handling

### Custom Exceptions
Use specific exceptions from `wikidata_collector.exceptions`:
- `WikidataCollectorError` - Base exception
- `InvalidQIDError` - Invalid Wikidata entity ID format
- `EntityNotFoundError` - Entity does not exist
- `QueryExecutionError` - SPARQL query failed

### Exception Pattern
```python
from wikidata_collector.exceptions import InvalidQIDError

def validate_and_fetch(qid: str):
    try:
        validated_qid = validate_qid(qid)
        return fetch_entity(validated_qid)
    except ValueError as e:
        raise InvalidQIDError(f"Invalid QID: {qid}") from e
```

## Environment Configuration

### Required Variables
```bash
CONTACT_EMAIL="your-email@example.com"  # Required for User-Agent header
```

### Optional Variables
```bash
PROXY_LIST="http://proxy1:8080,http://proxy2:8080"
CACHE_TTL_SECONDS=300
CACHE_MAX_SIZE=10000
SPARQL_TIMEOUT_SECONDS=60
PROXY_COOLDOWN_SECONDS=300
```

### Loading Configuration
```python
# Auto-loaded from .env file via python-dotenv
from wikidata_collector import WikidataClient

client = WikidataClient()  # Loads from environment

# Or explicit configuration
from wikidata_collector.config import WikidataCollectorConfig
config = WikidataCollectorConfig(contact_email="test@example.com")
client = WikidataClient(config)
```

## Best Practices for Contributors

1. **Make Minimal Changes**: Only modify what's necessary for the task
2. **Run Tests First**: Always run `pytest` before making changes to understand baseline
3. **Security First**: Validate all inputs, especially those used in SPARQL queries
4. **Type Safety**: Use type hints and Pydantic models
5. **Documentation**: Update docstrings when changing function signatures
6. **Test Coverage**: Add tests for new functionality
7. **No Breaking Changes**: Maintain backward compatibility in public API

## Debugging Tips

### Enable Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
# WikidataClient logs to 'wikidata_collector.client' logger
```

### Test Single Query
```python
from wikidata_collector.query_builders.figures_query_builder import build_public_figures_query

query = build_public_figures_query(profession=["Q33999"], limit=5)
print(query)  # Inspect generated SPARQL
```

### Validate Security
```python
# Test your validations
from wikidata_collector.security import validate_qid, escape_sparql_literal

try:
    validate_qid("Q42; DROP TABLE")  # Should raise ValueError
except ValueError as e:
    print(f"Caught injection attempt: {e}")
```

---

**Last Updated**: 2025-12-17
**Maintainer**: GitHub Copilot
**Status**: Active Development

<!-- MANUAL ADDITIONS START -->
<!-- Add any repository-specific instructions below this line -->
<!-- MANUAL ADDITIONS END -->
