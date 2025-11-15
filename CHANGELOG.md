# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2024-11-15

### Major Changes - API Removed, Pure Module Created

This release transforms the project from a FastAPI microservice into a pure Python library. This is a **breaking change** for users of the HTTP API.

### Added
- Pure Python `wikidata_collector` module with no web framework dependencies
- `WikidataClient` class for programmatic access
- `WikidataCollectorConfig` for configuration management
- Comprehensive README with library usage documentation
- Migration guide for users transitioning from the API
- Example usage script (`example.py`)
- Package setup script (`setup.py`) for pip installation
- Built-in SPARQL injection prevention

### Changed
- Normalizers are now self-contained (no external dependencies)
- Cache implementation no longer depends on API config
- Function signatures simplified for standalone use
- Test suite focused on module functionality (61 tests)
- Dependencies reduced from 28 to 7 core packages

### Removed
- FastAPI API layer (`api/` directory)
- Uvicorn server (`app/` directory)
- API-specific infrastructure (`infrastructure/` directory)
- Duplicate functionality (`core/`, `sparql/` directories)
- API-specific tests
- Docker support files
- 21 dependencies removed (FastAPI, Uvicorn, etc.)

### Security
- SPARQL injection prevention with QID validation
- String literal escaping in query builders
- Comprehensive security test suite

### Testing
- 61 unit tests passing
- Tests for normalizers, query builders, security, proxy
- 63% code coverage on module functionality

### Migration
Users of the HTTP API should refer to `MIGRATION_GUIDE.md` for migration instructions.

#### Before (API):
```python
import requests
response = requests.get("http://localhost:8000/v1/public-figures?nationality=Q30")
```

#### After (Module):
```python
from wikidata_collector import WikidataClient
client = WikidataClient()
results, proxy = client.get_public_figures(nationality=["Q30"])
```

### Dependencies
Core dependencies now include:
- pydantic==2.12.3
- requests==2.32.5
- python-dotenv==1.1.1
- pytest==8.0.0 (dev)
- pytest-mock==3.12.0 (dev)
- pytest-cov==4.1.0 (dev)

## [Pre-1.0.0] - Historical

Previous versions were FastAPI-based microservices. See git history for details.
