# Tests

This directory contains unit tests and integration tests for the Wikidata Fetch Microservice.

## Test Structure

- `test_sparql_builders.py` - Unit tests for SPARQL query builders
- `test_normalizers.py` - Unit tests for data normalizers
- `test_integration.py` - Integration tests with mocked SPARQL endpoint
- `test_integration_live.py` - Integration tests with live SPARQL endpoint (optional)
- `conftest.py` - Shared pytest fixtures and configuration

## Running Tests

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test Files

```bash
# Unit tests only
pytest tests/test_sparql_builders.py tests/test_normalizers.py

# Integration tests (mocked)
pytest tests/test_integration.py

# All tests except live integration
pytest -m "not integration"
```

### Run with Coverage

```bash
pytest --cov=. --cov-report=html
```

### Run Live Integration Tests (Optional)

Live tests are skipped by default. To enable them, edit `test_integration_live.py` and set `skipif(True, ...)` to `skipif(False, ...)` for specific tests.

**Warning**: Live tests make actual requests to the Wikidata SPARQL endpoint. Use sparingly to avoid rate limiting.

## Test Coverage

### SPARQL Builders

- ✅ Basic query construction
- ✅ Birthday filters (from/to)
- ✅ Nationality filters (QID and name)
- ✅ Profession filters (QID and name)
- ✅ Multiple filters
- ✅ Keyset pagination
- ✅ Offset pagination (backward compatibility)
- ✅ Limit parameter
- ✅ Language parameter

### Normalizers

- ✅ Basic normalization
- ✅ With expanded data
- ✅ Social media from SPARQL
- ✅ Without expanded data (fallback)
- ✅ Empty/partial data handling

### Integration Tests (Mocked)

- ✅ SPARQL query execution
- ✅ Caching behavior
- ✅ Error handling (429, 502, 503, 504)
- ✅ Retry logic
- ✅ Complete endpoint flows
- ✅ Network error handling

### Integration Tests (Live - Optional)

- ✅ Live SPARQL query execution
- ✅ Entity expansion
- ✅ Keyset pagination

## Writing New Tests

1. Follow the existing test structure
2. Use fixtures from `conftest.py` when possible
3. Mock external dependencies (SPARQL endpoint)
4. Test both success and error cases
5. Add docstrings explaining what each test validates

## Continuous Integration

Tests should be run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    pip install -r requirements.txt
    pytest --cov=. --cov-report=xml
```


