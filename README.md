# Wikidata Fetch Microservice

A production-ready FastAPI microservice that fetches public figures and institutions from Wikidata using SPARQL queries with deterministic keyset pagination, streaming NDJSON responses, and robust proxy rotation.

## Features

- **SPARQL-Only Architecture**: All entity data fetched via SPARQL with direct label resolution (no EntityData API fallback)
- **Keyset Pagination**: Deterministic QID-based cursor pagination (no OFFSET drift)
- **Streaming NDJSON**: Page-sized incremental delivery with per-item timeouts
- **Multi-Valued Fields**: Correctly returns all professions, awards, nationalities, etc.
- **Proxy Rotation**: Round-robin with failure detection, retry/backoff, and Retry-After handling
- **Request-Level Proxy Override**: Per-request proxy configuration via headers
- **Comprehensive Filtering**: Birth dates, nationality, profession, institution types, country, jurisdiction
- **Caching**: TTL-based in-memory cache for SPARQL queries and entity expansion (5-minute TTL)
- **Observability**: Structured JSON logging, request ID tracking, metrics collection, and Prometheus endpoint
- **OpenAPI Documentation**: Auto-generated interactive API docs
- **Docker Support**: Containerized deployment with healthchecks
- **Testing**: Comprehensive test suite with integration and unit tests

## Quick Start

### Local Development

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Set contact email (required for WDQS User-Agent):**
```bash
export CONTACT_EMAIL="your-email@example.com"
```

3. **Optional proxy configuration:**
```bash
export PROXY_LIST="http://proxy1:8080,http://proxy2:8080"
```

4. **Run the service:**
```bash
python -m app.server
# or
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

5. **Access the API:**
- Health: http://localhost:8000/v1/health
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Metrics: http://localhost:8000/v1/metrics (JSON)
- Prometheus Metrics: http://localhost:8000/metrics (Prometheus format)

### Docker Deployment

```bash
# Build
docker build -t wikidata-fetch:latest .

# Run
docker run --rm -p 8000:8000 \
  -e CONTACT_EMAIL=your-email@example.com \
  -e PROXY_LIST="http://proxy1:8080,http://proxy2:8080" \
  wikidata-fetch:latest
```

Or use Docker Compose:
```bash
docker compose up --build
```

## API Endpoints

### GET /v1/meta
Returns service metadata including version, WDQS endpoint, supported filters, and institution type mappings.

```bash
curl "http://localhost:8000/v1/meta"
```

Response:
```json
{
  "service_version": "1.0.0",
  "wikidata_sparql": "https://query.wikidata.org/sparql",
  "default_limit": 100,
  "max_limit": 500,
  "supported_filters": {
    "public_figures": ["birthday_from", "birthday_to", "nationality", "profession"],
    "public_institutions": ["type", "country", "jurisdiction"]
  },
  "supported_institution_types": {
    "political_party": "Q7278",
    "government_agency": "Q327333",
    "municipality": "Q15284",
    "media_outlet": "Q1193236",
    "ngo": "Q79913",
    "ministry": "Q11862829"
  }
}
```

### GET /v1/health
Health check endpoint for monitoring and load balancers.

```bash
curl "http://localhost:8000/v1/health"
```

### GET /v1/entities/{qid}
Point lookup for a single Wikidata entity. Auto-detects person vs institution and returns normalized data.

**Query Parameters:**
- `lang` (default: `en`): Language code for labels/descriptions
- `expand` (optional): Comma-separated expansions
  - `sub_institutions` (institutions only) — Fetch child institutions via P749/P361
  - `affiliations` (people only) — Extract affiliation QIDs (P102, P463)

**Examples:**
```bash
# Person lookup
curl "http://localhost:8000/v1/entities/Q2831?lang=en"

# Institution with sub-institutions
curl "http://localhost:8000/v1/entities/Q95?expand=sub_institutions&lang=en"

# Person with affiliations
curl "http://localhost:8000/v1/entities/Q937?expand=affiliations&lang=en"
```

**Response includes:**
- Multiple professions, awards, nationalities (all values from Wikidata)
- Website URLs (if P856 property exists)
- Social media handles aggregated under the `accounts` list (Twitter, Instagram, Facebook, YouTube, TikTok)
- Place of birth/death, residence
- Identifiers (GND, VIAF, ISNI, LC, BNF)

### GET /v1/public-figures
Fetch public figures with optional filters and pagination/streaming.

**Query Parameters:**
- `birthday_from` (optional): Birth date from (ISO date, e.g., `1990-01-01`)
- `birthday_to` (optional): Birth date to (ISO date)
- `nationality` (optional, repeatable): Nationality filter (ISO alpha-3 code, label, or QID)
  - **Prefer QIDs** for performance: `nationality=Q30` (United States)
- ISO code example: `nationality=USA`
  - Label example: `nationality=United States`
- `profession` (optional, repeatable): Profession filter (label or QID)
  - **Prefer QIDs**: `profession=Q33999` (actor)
- `lang` (default: `en`): Language code
- `limit` (default: 100, max: 500): Results per page (capped at ~50 for streaming)
- `cursor` (optional): Pagination cursor
  - **Keyset mode**: Pass QID (e.g., `cursor=Q12345`) for deterministic pagination
  - **Offset fallback**: Pass integer (e.g., `cursor=100`)
- `stream` (optional): Set to `ndjson` for streaming
- `fields` (optional): Comma-separated sparse fieldset to limit response fields
  - Example: `fields=id,name,professions,website.url`
  - Always includes `id` and `entity_kind` regardless of fields parameter
- Supports nested fields with dot notation (e.g., `website.url`, `accounts.handle`)

**Examples:**

Non-streaming JSON (paginated):
```bash
# Basic query
curl "http://localhost:8000/v1/public-figures?birthday_from=1990-01-01&lang=en&limit=50"

# With nationality (QID preferred for speed)
curl "http://localhost:8000/v1/public-figures?birthday_from=1990-01-01&nationality=Q30&limit=50"

# Next page using QID cursor
curl "http://localhost:8000/v1/public-figures?birthday_from=1990-01-01&nationality=Q30&limit=50&cursor=Q123456"
```

Streaming NDJSON:
```bash
# Stream full page (capped at ~50 items for stability)
curl -i "http://localhost:8000/v1/public-figures?stream=ndjson&birthday_from=1990-01-01&nationality=Q30&limit=100"

# Headers include:
# X-Proxy-Used: direct (or proxy URL)
# X-Next-Cursor: Q123456 (if more pages exist)

# Body: NDJSON lines (one person per line)
```

**Response (non-streaming):**
```json
{
  "data": [
    {
      "id": "Q2831",
      "entity_kind": "public_figure",
      "name": "Michael Jackson",
      "professions": ["entrepreneur", "singer", "dancer", "actor", "voice actor"],
      "awards": ["Grammy Award for Record of the Year", "Grammy Award for Album of the Year", "..."],
      "nationalities": ["United States"],
      "website": [{"url": "https://www.michaeljackson.com", "source": "wikidata", "retrieved_at": "..."}],
      "accounts": [
        {"platform": "twitter", "handle": "michaeljackson", "source": "wikidata", "retrieved_at": "..."},
        {"platform": "instagram", "handle": "michaeljackson", "source": "wikidata", "retrieved_at": "..."}
      ],
      "birthday": "1958-08-29T00:00:00Z",
      "deathday": "2009-06-25T00:00:00Z",
      "..."
    }
  ],
  "next_cursor": "Q2831",
  "has_more": true
}
```

### GET /v1/public-institutions
Fetch public institutions with optional filters and pagination/streaming.

**Query Parameters:**
- `type` (optional, repeatable): Institution type (mapped key or QID)
  - **Mapped keys**: `political_party`, `government_agency`, `municipality`, `media_outlet`, `ngo`, `ministry`
  - **QID example**: `type=Q327333` (government agency)
- `country` (optional): Country filter (ISO alpha-3 code, label, or QID)
  - **Prefer QIDs**: `country=Q30` (United States)
- `jurisdiction` (optional): Jurisdiction filter (label or QID)
- `lang` (default: `en`): Language code
- `limit` (default: 100, max: 500): Results per page
- `cursor` (optional): QID for keyset pagination or integer for OFFSET
- `stream` (optional): Set to `ndjson` for streaming
- `fields` (optional): Comma-separated sparse fieldset to limit response fields
  - Example: `fields=id,name,types,website.url`
  - Always includes `id` and `entity_kind` regardless of fields parameter
- Supports nested fields with dot notation (e.g., `website.url`, `accounts.handle`)

**Examples:**

Non-streaming:
```bash
# Government agencies
curl "http://localhost:8000/v1/public-institutions?type=government_agency&lang=en&limit=50"

# With QID type (faster)
curl "http://localhost:8000/v1/public-institutions?type=Q327333&lang=en&limit=50"

# Next page
curl "http://localhost:8000/v1/public-institutions?type=government_agency&cursor=Q100150535&limit=50"
```

Streaming:
```bash
curl -i "http://localhost:8000/v1/public-institutions?stream=ndjson&type=government_agency&limit=100"
```

**Response:**
```json
{
  "data": [
    {
      "id": "Q95",
      "entity_kind": "public_institution",
      "name": "Google",
      "types": ["business", "public company"],
      "country": ["USA"],
      "website": [{"url": "https://about.google/", "source": "wikidata", "retrieved_at": "..."}],
      "accounts": [
        {"platform": "twitter", "handle": "Google", "source": "wikidata", "retrieved_at": "..."}
      ],
      "founded": "1998-09-04T00:00:00Z",
      "..."
    }
  ],
  "next_cursor": "Q95",
  "has_more": true
}
```

## Pagination

### Keyset Pagination (Recommended)
- **How**: Pass the last QID from the current page as `cursor` parameter
- **Why**: Deterministic results, no drift, handles concurrent updates gracefully
- **Example**: 
  ```bash
  # Page 1
  curl "...?limit=50" → returns data + next_cursor: "Q12345"
  # Page 2
  curl "...?limit=50&cursor=Q12345"
  ```

### OFFSET Pagination (Fallback)
- **How**: Pass integer cursor (e.g., `cursor=100`)
- **Why**: Legacy support, can have drift if data changes
- **Note**: Only used if cursor is numeric and no QID keyset is available

## Streaming Details

When `stream=ndjson` is specified:

1. **Media Type**: `application/x-ndjson`
2. **Format**: One JSON object per line (newline-delimited)
3. **Page-Sized**: Streams an entire page (~50 items capped for stability)
4. **Ordered**: Results yielded in QID order
5. **Concurrent Expansion**: Uses ThreadPoolExecutor (max 3 workers) for parallel entity enrichment
6. **Timeout Handling**: Per-item timeout (45s) prevents head-of-line blocking
7. **Error Lines**: On expansion failure, yields error control line and continues
8. **Headers**:
   - `X-Proxy-Used`: Proxy that was used (or "direct" or "cached")
   - `X-Next-Cursor`: QID for next page (if `has_more`)
   - `X-Request-ID`: Unique request identifier for tracing

**Error Control Line Example:**
```json
{"error": "entity_expand_error", "qid": "Q12345", "detail": "TimeoutError"}
```

**Testing Streaming:**
```bash
# cURL with headers
curl -i "http://localhost:8000/v1/public-figures?stream=ndjson&birthday_from=1990-01-01&limit=100"

# Postman: Set Accept header to application/x-ndjson and check response body
```

## Environment Configuration

1. Copy the example environment file and tailor it to your deployment:
   ```bash
   cp .env.example .env
   ```
2. Key environment variables (all optional—defaults shown):

| Variable | Description | Default |
| --- | --- | --- |
| `CONTACT_EMAIL` | Contact email embedded in the Wikidata User-Agent header | `not-provided` |
| `WIKIDATA_SPARQL_URL` | Primary Wikidata SPARQL endpoint | `https://query.wikidata.org/sparql` |
| `PROXY_LIST` | Comma-separated list of outbound proxy URLs | *(empty)* |
| `CACHE_TTL_SECONDS` | TTL (seconds) for in-memory caches | `300` |
| `CACHE_MAX_SIZE` | Maximum cached entries per store | `10000` |
| `SPARQL_TIMEOUT_SECONDS` | HTTP timeout (seconds) for SPARQL requests | `60` |
| `STREAMING_PAGE_SIZE` | Maximum page size for NDJSON streaming responses | `50` |
| `MAX_WORKERS` | Thread pool workers used for entity expansion | `3` |
| `UVICORN_HOST` | Bind host for Uvicorn | `0.0.0.0` |
| `UVICORN_PORT` | Bind port for Uvicorn | `8000` |
| `UVICORN_WORKERS` | Worker count for production Uvicorn runs | `2` |

> Any other values defined in `api/config.py` can also be overridden by environment variables if required.

## Proxy Configuration

### Environment Variable
```bash
export PROXY_LIST="http://proxy1:8080,http://proxy2:8080,https://proxy3:8080"
```

### Per-Request Override
```bash
curl -H "X-Proxy-List: http://custom-proxy:8080" "http://localhost:8000/v1/public-figures"
```

### Proxy Features
- **Round-Robin Selection**: Automatic rotation through available proxies
- **Failure Detection**: Failed proxies marked and skipped for 5-minute cooldown
- **Retry Logic**: Exponential backoff for 502/503/504 errors
- **Retry-After Handling**: Honors 429 rate-limit headers from WDQS
- **Timeout**: 60-second timeout per proxy hop (configurable via `SPARQL_TIMEOUT_SECONDS`)
- **Response Headers**: `X-Proxy-Used` indicates which proxy was used
- **Direct Fallback**: Uses direct connection if no proxies available

## WDQS Best Practices

The service follows Wikidata Query Service operational limits:

1. **Query Timeout**: 60 seconds (keep pages ≤50-100 items)
2. **Rate Limiting**: Honors 429 Retry-After headers
3. **User-Agent**: Includes contact email via `CONTACT_EMAIL` env var
4. **Efficient Filtering**: 
   - **Use QIDs** for filters (e.g., `nationality=Q30` vs `nationality=United States`)
   - QID filters avoid slow label joins in SPARQL
5. **Keyset Pagination**: Avoids deep OFFSET (which is expensive on WDQS)
6. **Selective Fields**: Query only needed properties

**Avoid Blocking:**
- Set `CONTACT_EMAIL` for User-Agent identification
- Use smaller limits (50-100) for complex queries
- Prefer QID filters over label filters
- Use keyset pagination instead of large OFFSETs

## Data Schemas

### PublicFigure
```typescript
{
  id: string;                    // Wikidata QID
  entity_kind: "public_figure";
  name: string;
  aliases: string[];             // Alt labels
  description: string;
  birthday: string;              // ISO datetime
  deathday: string | null;
  gender: string;                // "male", "female", etc.
  nationalities: string[];       // Multiple values
  professions: string[];         // Multiple values
  place_of_birth: string[];
  place_of_death: string[];
  residence: string[];
  website: WebsiteEntry[];       // {url, source, retrieved_at}
  accounts: AccountEntry[];      // Unified social accounts
  affiliations: string[];        // Political party, memberships
  notable_works: string[];
  awards: string[];              // Multiple values
  identifiers: Identifier[];     // GND, VIAF, ISNI, LC, BNF
  image: string[];
  updated_at: string;
}
```

### PublicInstitution
```typescript
{
  id: string;                    // Wikidata QID
  entity_kind: "public_institution";
  name: string;
  aliases: string[];
  description: string;
  founded: string | null;        // ISO datetime
  dissolved: string | null;
  country: string[];             // ISO alpha-3 codes
  jurisdiction: string[];
  types: string[];               // Multiple instance-of types
  legal_form: string[];
  headquarters: string[];
  headquarters_coords: string[];
  website: WebsiteEntry[];
  official_language: string[];
  logo: string[];
  budget: string[];
  parent_institution: string[];
  sub_institutions: any[];       // If expand=sub_institutions
  sector: string[];
  affiliations: string[];
  accounts: AccountEntry[];
  updated_at: string;
}
```

### GET /v1/metrics
Get current metrics in JSON format including request counts, error counts, P95 latencies, cache hit rates, and SPARQL errors.

```bash
curl "http://localhost:8000/v1/metrics"
```

Response:
```json
{
  "requests": {
    "/v1/public-figures": 150,
    "/v1/public-institutions": 75
  },
  "errors": {
    "/v1/public-figures": 2
  },
  "cache_hits": {
    "/v1/public-figures": 45
  },
  "cache_misses": {
    "/v1/public-figures": 105
  },
  "sparql_errors": {
    "timeout": 1,
    "rate_limit": 1
  },
  "p95_latency_ms": {
    "/v1/public-figures": 1250.5
  },
  "cache_hit_rate_percent": {
    "/v1/public-figures": 30.0
  }
}
```

### GET /metrics
Prometheus-compatible metrics endpoint for monitoring systems.

```bash
curl "http://localhost:8000/metrics"
```

Response (Prometheus format):
```
wikidata_requests_total{route="/v1/public-figures"} 150
wikidata_errors_total{route="/v1/public-figures"} 2
wikidata_p95_latency_ms{route="/v1/public-figures"} 1250.5
wikidata_cache_hit_rate_percent{route="/v1/public-figures"} 30.0
wikidata_sparql_errors_total{error_type="timeout"} 1
```

## Caching

The service includes a TTL-based in-memory cache for:
- **SPARQL Queries**: Cached for 5 minutes (300 seconds)
- **Entity Expansion**: Cached for 5 minutes (300 seconds)

**Cache Configuration:**
- Default TTL: 300 seconds (5 minutes)
- Max size: 10,000 entries per cache
- Thread-safe: LRU eviction when cache is full
- Automatic expiration: Expired entries are removed on access

**Cache Behavior:**
- Cache hits are logged with `cache_hit: true` in structured logs
- Cache statistics available via `/v1/metrics` endpoint
- Cache is checked before executing SPARQL queries
- Cache key is MD5 hash of the query string

## Observability

### Structured Logging
All logs are emitted in JSON format with the following fields:
- `timestamp`: ISO 8601 timestamp
- `level`: Log level (INFO, ERROR, etc.)
- `logger`: Logger name
- `message`: Log message
- `request_id`: Unique request identifier (generated or from `X-Request-ID` header)
- `route`: API route
- `params_hash`: Hash of request parameters
- `proxy_used`: Proxy URL used (or "direct" or "cached")
- `sparql_latency_ms`: SPARQL query latency in milliseconds
- `entity_expansion_latency_ms`: Entity expansion latency in milliseconds
- `cache_hit`: Boolean indicating cache hit
- `status_code`: HTTP status code
- `error_type`: Error type (if applicable)
- `error_detail`: Error details (if applicable)

### Request ID Tracking
- Each request gets a unique `X-Request-ID` header
- Request ID is included in all logs and response headers
- Clients can provide their own `X-Request-ID` header for distributed tracing

### Metrics Collection
The service collects the following metrics:
- Request counts per route
- Error counts per route
- P95 latency per route (last 100 samples)
- Cache hit/miss counts
- Cache hit rate percentage
- SPARQL error counts by type

Metrics are exposed via:
- `/v1/metrics`: JSON format
- `/metrics`: Prometheus format

## Error Handling

**HTTP Status Codes:**
- `200`: Success
- `400`: Bad Request (invalid QID, malformed SPARQL)
- `404`: Entity not found
- `429`: Rate limited (retries with backoff)
- `500`: Internal error (WDQS timeout, network failure)
- `502/503/504`: Transient WDQS errors (auto-retry with backoff)

**Error Response:**
```json
{
  "detail": "We are facing an error"
}
```

**Streaming Error Lines:**
```json
{"error": "wdqs_error", "status": 504, "detail": "Gateway Timeout"}
{"error": "entity_expand_error", "qid": "Q12345", "detail": "Timeout"}
```

## Development

**Tech Stack:**
- **FastAPI**: Modern async web framework
- **Uvicorn**: ASGI server
- **Pydantic**: Data validation and serialization
- **Requests**: HTTP client for SPARQL queries
- **Python 3.12+**: Type hints, modern syntax
- **Pytest**: Testing framework
- **Pytest-cov**: Code coverage reporting

**Project Structure:**
```
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app initialization and orchestration
│   └── server.py            # Uvicorn launcher
├── core/
│   ├── __init__.py
│   ├── models.py            # Pydantic models (PublicFigure, PublicInstitution, etc.)
│   ├── normalizers/
│   │   ├── __init__.py
│   │   ├── figure_normalizer.py
│   │   └── institution_normalizer.py
│   └── wiki_service.py      # Core SPARQL orchestration (querying, expansion)
├── infrastructure/
│   ├── __init__.py
│   ├── cache.py             # TTL cache implementation
│   ├── observability.py     # Structured logging & metrics
│   └── proxy_service.py     # Proxy rotation and failure detection
├── sparql/
│   ├── __init__.py
│   └── builders/
│       ├── __init__.py
│       ├── figures_query_builder.py
│       └── institutions_query_builder.py
├── docs/
│   └── (project documentation)
├── requirements.txt         # Python dependencies
├── pytest.ini               # Pytest configuration
├── dockerfile               # Container image
├── .github/
│   └── workflows/
│       └── ci.yml           # GitHub Actions CI/CD pipeline
├── api/                     # Modular API layer
│   ├── __init__.py
│   ├── config.py            # Application configuration (AppConfig)
│   ├── constants.py         # Type-safe enums (EntityType, ExpansionType, etc.)
│   ├── dependencies.py      # FastAPI dependency injection
│   ├── exceptions.py        # Custom HTTP exceptions
│   ├── validators.py        # Input validation (QIDValidator, EntityTypeValidator)
│   ├── routes/              # API endpoint handlers
│   │   ├── __init__.py      # Router aggregation
│   │   ├── entities.py      # GET /v1/entities/{qid}
│   │   ├── figures.py       # GET /v1/public-figures
│   │   ├── institutions.py  # GET /v1/public-institutions
│   │   ├── metrics.py       # GET /v1/metrics, /metrics
│   │   └── meta.py          # GET /v1/meta, /v1/health
│   ├── services/            # Business logic layer
│   │   ├── __init__.py
│   │   ├── entity_service.py      # Entity lookup logic
│   │   ├── expansion_handler.py   # Entity expansion (sub-institutions, affiliations)
│   │   ├── list_processor.py       # List endpoint processing (pagination, streaming)
│   │   └── response_builder.py     # HTTP response construction (headers, ETags)
│   └── utils/               # Utility functions
│       ├── __init__.py
│       ├── entity_utils.py  # Entity type detection, QID extraction
│       ├── etag_utils.py    # ETag generation
│       └── field_utils.py   # Sparse fieldset parsing and filtering
├── tests/                   # Test suite
│   ├── __init__.py
│   ├── conftest.py          # Pytest fixtures and configuration
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_normalizers.py
│   │   └── test_sparql_builders.py
│   └── integration/
│       ├── __init__.py
│       ├── test_integration.py
│       └── test_integration_live.py
└── README.md
```

**Testing:**
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_integration.py

# Run excluding live tests (network required)
pytest -m "not integration"

# Manual API testing
# Health check
curl http://localhost:8000/v1/health

# Entity lookup
curl "http://localhost:8000/v1/entities/Q2831?lang=en" | jq

# Public figures
curl "http://localhost:8000/v1/public-figures?birthday_from=1990-01-01&limit=10" | jq

# Streaming
curl -i "http://localhost:8000/v1/public-figures?stream=ndjson&birthday_from=1990-01-01&limit=100"

# Metrics
curl "http://localhost:8000/v1/metrics" | jq
curl "http://localhost:8000/metrics"
```

## CI/CD

The project includes a GitHub Actions CI/CD pipeline (`.github/workflows/ci.yml`) that:

**On Push/PR to `main` or `develop`:**
1. **Lint and Test Job:**
   - Runs on Python 3.12
   - Installs dependencies from `requirements.txt`
   - Runs the full test suite with coverage reporting
   - Generates coverage reports in XML and terminal formats
   - Optionally uploads coverage to Codecov

2. **Docker Build Job** (only on push):
   - Builds Docker image using the `dockerfile`
   - Tests the Docker image by running it and checking health endpoint
   - Uses Docker Buildx with GitHub Actions cache for faster builds

**Configuration:**
- Set `CONTACT_EMAIL` environment variable in repository secrets (optional, for WDQS User-Agent)
- Optional: Configure Docker Hub credentials in secrets (`DOCKER_USERNAME`, `DOCKER_PASSWORD`) for automated image pushes

**Manual Workflow Triggers:**
The pipeline automatically runs on:
- Push to `main` or `develop` branches
- Pull requests targeting `main` or `develop`

**Local CI Simulation:**
```bash
# Run tests locally (same as CI)
pytest tests/ -v --cov=. --cov-report=xml --cov-report=term

# Build and test Docker image locally
docker build -t wikidata-fetch:latest .
docker run --rm -d -e CONTACT_EMAIL="test@example.com" -p 8000:8000 --name test-container wikidata-fetch:latest
sleep 5 && curl -f http://localhost:8000/v1/health && docker stop test-container
```
