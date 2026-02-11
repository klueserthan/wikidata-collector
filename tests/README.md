# Tests

This directory contains unit tests and integration tests for the Wikidata Collector library.

## Test Structure

### Unit Tests (`tests/unit/`)
- `test_sparql_builders.py` - Unit tests for SPARQL query builders (including iterator-focused query construction)
- `test_normalizers.py` - Unit tests for data normalizers (PublicFigure, PublicInstitution models)
- `test_proxy_service.py` - Unit tests for proxy configuration and behavior
- `test_sparql_security.py` - Unit tests for SPARQL security and safety checks

### Integration Tests (`tests/integration/`)
- `test_iterate_public_figures.py` - Integration tests for `iterate_public_figures` API
- `test_iterate_public_institutions.py` - Integration tests for `iterate_public_institutions` API
- `test_resilience_and_logging.py` - Integration tests for proxy, retries, and structured logging

### Shared Fixtures
- `conftest.py` - Shared pytest fixtures and configuration

## Running Tests

### Install Dependencies

```bash
pip install -e .
pip install -e '.[dev]'
```

### Run All Tests

```bash
pytest
```

### Run Unit Tests Only

```bash
pytest tests/unit -v
```

### Run Integration Tests Only

```bash
pytest tests/integration -v
```

### Run Iterator-Focused Tests

```bash
# Run tests specifically marked for iterator APIs
pytest -m iterator -v
```

### Run All Tests Except Integration

```bash
pytest -m "not integration" -v
```

### Run with Coverage

```bash
pytest --cov=wikidata_collector --cov-report=html --cov-report=term
```

### Type Checking

```bash
# Run type checker on library and tests
pyright wikidata_collector tests
```

### Linting

```bash
# Run ruff linter
ruff check wikidata_collector tests
```

## Test Coverage Goals

### Iterator-Based APIs (New Feature)

- Unit tests for `iterate_public_figures` and `iterate_public_institutions`
- Internal pagination logic (stable ID ordering, page size handling)
- Filter translation (human-readable labels to SPARQL)
- Empty results and error handling
- Integration tests for complete iterator flows

### SPARQL Query Builders

- Query construction with filters (birthday, nationality, founding date, country, types, headquarter)
- Label-to-SPARQL translation for nationality, country, and institution types
- SPARQL sub-templates for reusable query fragments
- Security and SPARQL injection protection

### Data Models & Normalizers

- Pydantic v2 model validation for `PublicFigure` and `PublicInstitution`
- Supporting types: `WebsiteEntry`, `AccountEntry`, `Identifier`
- Multi-valued attribute handling (nationalities, professions, types)
- Normalizers mapping SPARQL rows to Pydantic models

### Proxy & Resilience

- Proxy configuration and fail-closed behavior
- Upstream timeout and error handling
- Structured logging schema validation
- Retry logic and error categorization

## Writing New Tests

1. Follow TDD: write tests first, ensure they fail, then implement
2. Use fixtures from `conftest.py` for shared setup
3. Mock external dependencies (SPARQL endpoint, HTTP requests)
4. Test both success paths and error/edge cases
5. Add descriptive docstrings explaining test purpose
6. Use `@pytest.mark.iterator` for new iterator-focused tests
7. Use `@pytest.mark.integration` for tests requiring external systems

## Continuous Integration

The CI pipeline (`.github/workflows/ci.yml`) runs:

1. Type checking via `pyright`
2. Linting via `ruff`
3. Unit tests with coverage reporting
4. Integration tests (non-live only)

All checks must pass before merging to main.


