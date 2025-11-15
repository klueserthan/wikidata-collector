# Migration Guide: API to Pure Module

This guide helps users migrate from the FastAPI-based API wrapper to the pure `wikidata_collector` module.

## What Changed

The project has been refactored from a FastAPI microservice to a pure Python library. This provides:

- **Simpler deployment**: No web server required
- **Better reusability**: Use in any Python project (scripts, notebooks, other applications)
- **Reduced dependencies**: From 28 to 7 core dependencies
- **Cleaner separation**: Library logic separate from HTTP concerns

## Removed Components

The following components have been removed:

- `api/` - FastAPI routes and services
- `app/` - Uvicorn server
- `infrastructure/` - FastAPI-specific observability
- `core/` - Duplicated functionality (now in `wikidata_collector/`)
- `sparql/` - Duplicated query builders (now in `wikidata_collector/query_builders/`)

## Migration Path

### Before: FastAPI API

```python
# Old approach - required running Uvicorn server
# Access via HTTP endpoints like:
# GET http://localhost:8000/v1/public-figures?nationality=Q30&limit=50
```

### After: Pure Module

```python
# New approach - direct library usage
from wikidata_collector import WikidataClient

client = WikidataClient()
results, proxy = client.get_public_figures(
    nationality=["Q30"],
    limit=50
)
```

## Code Examples

### Querying Public Figures

**Before (API):**
```python
import requests

response = requests.get(
    "http://localhost:8000/v1/public-figures",
    params={
        "birthday_from": "1990-01-01",
        "nationality": "Q30",
        "profession": "Q33999",
        "limit": 50
    }
)
data = response.json()
figures = data["data"]
```

**After (Module):**
```python
from wikidata_collector import WikidataClient

client = WikidataClient()
results, proxy = client.get_public_figures(
    birthday_from="1990-01-01",
    nationality=["Q30"],
    profession=["Q33999"],
    limit=50
)

# Normalize results using the normalizers
from wikidata_collector.normalizers.figure_normalizer import normalize_public_figure

figures = [normalize_public_figure(item, None) for item in results]
```

### Querying Institutions

**Before (API):**
```python
response = requests.get(
    "http://localhost:8000/v1/public-institutions",
    params={
        "type": "government_agency",
        "country": "Q30",
        "limit": 50
    }
)
data = response.json()
institutions = data["data"]
```

**After (Module):**
```python
from wikidata_collector import WikidataClient

client = WikidataClient()
results, proxy = client.get_public_institutions(
    type=["government_agency"],  # or use QID: ["Q327333"]
    country="Q30",
    limit=50
)

# Normalize results
from wikidata_collector.normalizers.institution_normalizer import normalize_public_institution

institutions = [normalize_public_institution(item, None) for item in results]
```

### Getting Single Entity

**Before (API):**
```python
response = requests.get(
    "http://localhost:8000/v1/entities/Q42",
    params={"lang": "en"}
)
entity = response.json()
```

**After (Module):**
```python
from wikidata_collector import WikidataClient

client = WikidataClient()
entity, proxy = client.get_entity("Q42", lang="en")
```

### Configuration

**Before (API - Environment Variables):**
```bash
export CONTACT_EMAIL="your-email@example.com"
export PROXY_LIST="http://proxy:8080"
export UVICORN_HOST="0.0.0.0"
export UVICORN_PORT="8000"
```

**After (Module - Python Configuration):**
```python
from wikidata_collector.config import WikidataCollectorConfig

config = WikidataCollectorConfig(
    contact_email="your-email@example.com",
    proxy_list=["http://proxy:8080"],
    cache_ttl_seconds=300
)

from wikidata_collector import WikidataClient
client = WikidataClient(config)
```

## Feature Mapping

| API Feature | Module Equivalent |
|-------------|------------------|
| `GET /v1/public-figures` | `client.get_public_figures()` |
| `GET /v1/public-institutions` | `client.get_public_institutions()` |
| `GET /v1/entities/{qid}` | `client.get_entity(qid)` |
| `GET /v1/meta` | Not needed (configuration in code) |
| `GET /v1/health` | Not needed (library, not service) |
| `GET /v1/metrics` | Not needed (library, not service) |
| Query parameter `stream=ndjson` | Not applicable (use iterators if needed) |
| Query parameter `fields` | Filter results after retrieval |
| Header `X-Proxy-List` | `override_proxies` parameter |
| Response header `X-Proxy-Used` | Returned as tuple value |

## Dependency Changes

**Before (28 dependencies):**
- FastAPI, Starlette, Uvicorn
- Pydantic, pydantic-settings
- Many ASGI/web server dependencies

**After (7 core dependencies):**
- Pydantic (data models)
- Requests (HTTP client)
- python-dotenv (configuration)
- pytest, pytest-mock, pytest-cov (testing)

## Testing Changes

**Before:**
Tests covered both API routes and core functionality.

**After:**
Tests focus only on module functionality:
- Unit tests for query builders
- Unit tests for normalizers
- Unit tests for security functions
- Unit tests for proxy manager
- 61 tests passing ✅

## If You Need an API

If you still need a REST API, you can build one using the module:

```python
from fastapi import FastAPI
from wikidata_collector import WikidataClient

app = FastAPI()
client = WikidataClient()

@app.get("/figures")
async def get_figures(nationality: str, limit: int = 50):
    results, proxy = client.get_public_figures(
        nationality=[nationality],
        limit=limit
    )
    return {"data": results, "proxy_used": proxy}
```

This gives you full control over the API layer while using the module for Wikidata access.

## Benefits of the Change

1. **Simplicity**: No web server to manage
2. **Flexibility**: Use in scripts, notebooks, or other applications
3. **Testability**: Easier to test without HTTP layer
4. **Performance**: No HTTP overhead for local usage
5. **Reduced Dependencies**: Smaller installation footprint
6. **Better Reusability**: Can be imported as a library

## Support

For questions or issues, please use the GitHub issue tracker.
