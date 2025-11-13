# Code Review: Wikidata Fetch Microservice

**Review Date:** November 13, 2025  
**Reviewer:** AI Code Review Agent  
**Scope:** Full codebase semantic correctness, best practices, security, and maintainability

---

## Executive Summary

This FastAPI microservice demonstrates **strong architectural patterns** with clear separation of concerns, comprehensive observability, and robust error handling. The codebase follows Python best practices with type hints, structured logging, and extensive testing.

**Overall Assessment:** ✅ **Production-Ready** with recommended improvements

### Severity Legend
- **🔴 Blocker**: Must fix before production
- **🟠 High**: Fix soon, impacts reliability/security
- **🟡 Medium**: Should address, affects maintainability
- **🟢 Low**: Nice to have, minor improvements

---

## 🔴 Blocker Issues

### 1. **Type Assignment Error in Expansion Handler**
**File:** `api/services/expansion_handler.py:41, 64`  
**Severity:** 🔴 Blocker | Correctness

**Problem:**
```python
# Line 41
entity.sub_institutions = subs  # ❌ PublicFigure has no 'sub_institutions' attribute

# Line 64
entity.affiliations = affiliation_labels  # ❌ Type mismatch: list[str | None] vs List[str]
```

**Why it matters:**  
Runtime `AttributeError` when expanding a `PublicFigure` with `sub_institutions` parameter. Type checker detects incompatible list assignment (`None` can leak into list).

**Fix:**
```python
# Check entity type before assigning sub_institutions
if ExpansionType.SUB_INSTITUTIONS.value in expand_list and isinstance(entity, PublicInstitution):
    subs = self.wiki_service.expand_sub_institutions(qid, lang=lang, request=request)
    entity.sub_institutions = subs

# Filter None values from affiliations
if unique_qids:
    labels_map = self.wiki_service.get_labels_from_qids(unique_qids, lang=lang, request=request)
    affiliation_labels = [labels_map[qid] for qid in unique_qids if qid in labels_map]  # ✅ Filter None
    entity.affiliations = affiliation_labels
```

---

### 2. **Docker CMD Uses Wrong Module Path**
**File:** `dockerfile:40`  
**Severity:** 🔴 Blocker | Deployment

**Problem:**
```dockerfile
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```
Should be `app.main:app` based on project structure (`app/main.py`).

**Why it matters:**  
Container fails to start with `ModuleNotFoundError: No module named 'main'`.

**Fix:**
```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 🟠 High Severity Issues

### 3. **Unsafe Proxy Header Parsing (SSRF Risk)**
**File:** `infrastructure/proxy_service.py:28`  
**Severity:** 🟠 High | Security

**Problem:**
```python
def get_proxies_from_header(self, request: Request) -> List[str]:
    """Get proxy list from X-Proxy-List header."""
    proxy_header = request.headers.get('X-Proxy-List', '')
    if proxy_header:
        return [p.strip() for p in proxy_header.split(',') if p.strip()]  # ❌ No validation
    return []
```

**Why it matters:**  
Client can inject arbitrary proxy URLs (including `file://`, `localhost`, internal IPs), enabling SSRF attacks against internal services.

**Fix:**
```python
import re
from urllib.parse import urlparse

ALLOWED_PROXY_SCHEMES = {'http', 'https'}
BLOCKED_HOSTS = {'localhost', '127.0.0.1', '0.0.0.0', '::1'}

def get_proxies_from_header(self, request: Request) -> List[str]:
    """Get proxy list from X-Proxy-List header with validation."""
    proxy_header = request.headers.get('X-Proxy-List', '')
    if not proxy_header:
        return []
    
    validated_proxies = []
    for proxy in proxy_header.split(','):
        proxy = proxy.strip()
        if not proxy:
            continue
        
        try:
            parsed = urlparse(proxy)
            # Validate scheme
            if parsed.scheme not in ALLOWED_PROXY_SCHEMES:
                logger.warning(f"Rejected proxy with invalid scheme: {proxy}")
                continue
            # Block internal hosts
            if parsed.hostname in BLOCKED_HOSTS or parsed.hostname.startswith('192.168.') or parsed.hostname.startswith('10.'):
                logger.warning(f"Rejected proxy with internal host: {proxy}")
                continue
            validated_proxies.append(proxy)
        except Exception as e:
            logger.warning(f"Rejected malformed proxy: {proxy}, error: {e}")
    
    return validated_proxies
```

---

### 4. **Potential SQL Injection in SPARQL Query Construction**
**File:** `sparql/builders/figures_query_builder.py:32-42, 52-58`  
**Severity:** 🟠 High | Security

**Problem:**
```python
# User input directly interpolated into SPARQL
if nat_value.startswith("Q"):
    nationality_conditions.append(f"?person wdt:P27 wd:{nat_value}.")  # ❌ Direct interpolation
else:
    nationality_conditions.append(
        f'?person wdt:P27 ?country. ?country rdfs:label "{nat_value}"@{lang}.'  # ❌ No escaping
    )
```

**Why it matters:**  
Malicious input like `" . } DROP GRAPH <urn:wikidata> ; { #` can break SPARQL syntax or potentially expose unintended data.

**Fix:**
```python
import re

def escape_sparql_literal(value: str) -> str:
    """Escape SPARQL literal values."""
    return value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

def validate_qid(qid: str) -> str:
    """Validate QID format."""
    if not re.match(r'^Q\d+$', qid):
        raise ValueError(f"Invalid QID format: {qid}")
    return qid

# In query builder:
if nat_value.startswith("Q"):
    validated_qid = validate_qid(nat_value)  # ✅ Validate
    nationality_conditions.append(f"?person wdt:P27 wd:{validated_qid}.")
else:
    escaped_nat = escape_sparql_literal(nat_value)  # ✅ Escape
    nationality_conditions.append(
        f'?person wdt:P27 ?country. ?country rdfs:label "{escaped_nat}"@{lang}.'
    )
```

---

### 5. **Missing Rate Limit on Metrics Endpoints**
**File:** `api/routes/metrics.py`  
**Severity:** 🟠 High | Security

**Problem:**
```python
@router.get("/v1/metrics")
async def get_metrics():
    """Get current metrics in JSON format."""
    return metrics.get_metrics()  # ❌ No authentication, no rate limit
```

**Why it matters:**  
Unauthenticated metrics exposure reveals internal service state (error rates, cache hit rates, latencies). No rate limiting enables DoS via metrics scraping.

**Fix:**
```python
from fastapi import Header, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.get("/v1/metrics")
@limiter.limit("10/minute")
async def get_metrics(
    authorization: str = Header(None)
):
    """Get current metrics in JSON format."""
    if config.METRICS_AUTH_TOKEN and authorization != f"Bearer {config.METRICS_AUTH_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return metrics.get_metrics()
```

---

## 🟡 Medium Severity Issues

### 6. **Unbounded Memory Growth in MetricsCollector**
**File:** `infrastructure/observability.py:93-95`  
**Severity:** 🟡 Medium | Performance

**Problem:**
```python
self.request_counts = defaultdict(int)  # ❌ Grows indefinitely
self.error_counts = defaultdict(int)
self.sparql_errors = defaultdict(int)
```

**Why it matters:**  
Unbounded dicts can grow indefinitely if unique route variations or error types are generated dynamically. Memory leak over time.

**Fix:**
```python
from collections import OrderedDict

class MetricsCollector:
    def __init__(self, max_routes: int = 100, max_samples_per_route: int = 100, metrics_file: str = "metrics.json"):
        self.max_routes = max_routes
        self.request_counts = OrderedDict()  # ✅ Bounded
        self.error_counts = OrderedDict()
        # ...
    
    def _ensure_bounded(self, dict_obj: OrderedDict):
        """Remove oldest entry if limit exceeded."""
        if len(dict_obj) > self.max_routes:
            dict_obj.popitem(last=False)
    
    def record_request(self, route: str, status_code: int, latency_ms: float):
        with self._lock:
            self.request_counts[route] = self.request_counts.get(route, 0) + 1
            self._ensure_bounded(self.request_counts)
            # ...
```

---

### 7. **Global Singleton Pattern Violates Dependency Injection**
**File:** `api/dependencies.py:7-14`  
**Severity:** 🟡 Medium | Maintainability

**Problem:**
```python
_wiki_service_instance = None  # ❌ Global mutable state

def get_wiki_service() -> WikiService:
    global _wiki_service_instance
    if _wiki_service_instance is None:
        _wiki_service_instance = WikiService()
    return _wiki_service_instance
```

**Why it matters:**  
Makes testing difficult (can't inject mocks easily), violates FastAPI's dependency injection principles, and introduces race conditions during initialization.

**Fix:**
```python
from functools import lru_cache

@lru_cache(maxsize=1)
def get_wiki_service() -> WikiService:
    """Get WikiService instance (cached singleton)."""
    return WikiService()

# For testing:
def override_wiki_service(mock_service: WikiService):
    """Override wiki service for testing."""
    get_wiki_service.cache_clear()
    # Use FastAPI's dependency override mechanism
```

---

### 8. **Inconsistent Error Response Format**
**File:** `api/services/list_processor.py:372, 390`  
**Severity:** 🟡 Medium | Correctness

**Problem:**
```python
# Streaming error:
{"error": error_type, "status": status_code, "detail": error_detail}

# Non-streaming error:
raise HTTPException(status_code=status_code, detail=error_detail)  # Returns {"detail": ...}
```

**Why it matters:**  
Inconsistent error schemas break client parsing logic. API consumers need to handle two different error formats.

**Fix:**
```python
# Standardize on RFC 7807 Problem Details
from pydantic import BaseModel

class ErrorResponse(BaseModel):
    type: str  # Error type URI or constant
    title: str  # Human-readable summary
    status: int
    detail: str
    instance: Optional[str] = None  # Request ID

# Streaming:
yield json.dumps(ErrorResponse(
    type=error_type,
    title="SPARQL Query Failed",
    status=status_code,
    detail=error_detail,
    instance=request_id
).dict()) + "\n"

# Non-streaming:
raise HTTPException(
    status_code=status_code,
    detail=ErrorResponse(...).dict()
)
```

---

### 9. **Missing Input Validation for Date Parameters**
**File:** `api/routes/figures.py:13-14`  
**Severity:** 🟡 Medium | Correctness

**Problem:**
```python
@router.get("/v1/public-figures")
async def get_public_figures(
    birthday_from: Optional[str] = Query(None, description="Birth date from (ISO date)"),
    birthday_to: Optional[str] = Query(None, description="Birth date to (ISO date)"),
    # ...
```

**Why it matters:**  
No validation of ISO date format. Invalid dates like `"2024-13-01"` or `"not-a-date"` are passed to SPARQL, causing query failures.

**Fix:**
```python
from pydantic import validator, Field
from datetime import datetime

class FiguresQueryParams(BaseModel):
    birthday_from: Optional[str] = Field(None, regex=r'^\d{4}-\d{2}-\d{2}$')
    birthday_to: Optional[str] = Field(None, regex=r'^\d{4}-\d{2}-\d{2}$')
    
    @validator('birthday_from', 'birthday_to')
    def validate_iso_date(cls, v):
        if v:
            try:
                datetime.fromisoformat(v)
            except ValueError:
                raise ValueError(f"Invalid ISO date: {v}")
        return v
    
    @validator('birthday_to')
    def validate_date_range(cls, v, values):
        if v and values.get('birthday_from'):
            if v < values['birthday_from']:
                raise ValueError("birthday_to must be >= birthday_from")
        return v

@router.get("/v1/public-figures")
async def get_public_figures(
    params: FiguresQueryParams = Depends(),
    # ...
```

---

### 10. **Race Condition in Cache Cleanup**
**File:** `infrastructure/cache.py:72-79`  
**Severity:** 🟡 Medium | Correctness

**Problem:**
```python
def cleanup_expired(self):
    """Remove all expired entries (useful for periodic cleanup)."""
    with self._lock:
        current_time = time.time()
        expired_keys = [
            key for key, (timestamp, _) in self._cache.items()  # ❌ Iteration during modification
            if current_time - timestamp > self.ttl
        ]
        for key in expired_keys:
            del self._cache[key]
```

**Why it matters:**  
While holding the lock, dict iteration + modification is safe, but this pattern is fragile. Better to use atomic operations.

**Fix:**
```python
def cleanup_expired(self):
    """Remove all expired entries (useful for periodic cleanup)."""
    with self._lock:
        current_time = time.time()
        # Create a list of keys to delete first (avoid modification during iteration)
        keys_to_delete = [
            key for key, (timestamp, _) in list(self._cache.items())  # ✅ Snapshot
            if current_time - timestamp > self.ttl
        ]
        for key in keys_to_delete:
            self._cache.pop(key, None)  # ✅ Safe removal
```

---

## 🟢 Low Severity Issues

### 11. **Hardcoded Retry Logic Constants**
**File:** `core/wiki_service.py:103, 124`  
**Severity:** 🟢 Low | Maintainability

**Problem:**
```python
max_retries = 3  # ❌ Magic number
wait_s = 2 ** attempt  # ❌ Exponential backoff hardcoded
```

**Fix:**
```python
# In api/config.py
SPARQL_MAX_RETRIES: int = 3
SPARQL_RETRY_BASE_DELAY: float = 0.5
SPARQL_RETRY_MAX_DELAY: int = 32

# In wiki_service.py
max_retries = config.SPARQL_MAX_RETRIES
wait_s = min(config.SPARQL_RETRY_MAX_DELAY, config.SPARQL_RETRY_BASE_DELAY * (2 ** attempt))
```

---

### 12. **Missing Logging for Cache Evictions**
**File:** `infrastructure/cache.py:55-58`  
**Severity:** 🟢 Low | Observability

**Problem:**
```python
# Remove oldest if at max size
if len(self._cache) >= self.max_size:
    self._cache.popitem(last=False)  # ❌ Silent eviction
```

**Fix:**
```python
import logging
logger = logging.getLogger(__name__)

if len(self._cache) >= self.max_size:
    evicted_key, _ = self._cache.popitem(last=False)
    logger.debug(f"Cache eviction: removed oldest entry (key hash: {evicted_key[:8]}...)")
```

---

### 13. **Inconsistent Use of `typing.Dict` vs `dict`**
**File:** Multiple files  
**Severity:** 🟢 Low | Style

**Problem:**
```python
# Some files use:
from typing import Dict
def foo() -> Dict[str, Any]: ...

# Others use:
def foo() -> dict[str, Any]: ...  # Python 3.9+ style
```

**Fix:**  
Adopt Python 3.9+ lowercase generics consistently (since using `python:3.12-slim` in Docker):
```python
# Remove: from typing import Dict, List, Tuple
# Use: dict, list, tuple (built-in generics)
def foo() -> dict[str, Any]: ...
```

---

### 14. **Missing Docstrings for Public Methods**
**File:** `api/utils/entity_utils.py:48`  
**Severity:** 🟢 Low | Documentation

**Problem:**
```python
def determine_type(self, ent: Dict[str, Any]) -> Dict[str, Any]:
    """Determine entity type from Wikidata entity data.
    
    Args:
        ent: Wikidata entity dictionary
        
    Returns:
        Dictionary with 'is_person', 'is_institution', and 'p31_vals' keys
    """
    # ... implementation
```

Good! But some helper methods lack docstrings.

**Recommendation:**  
Add docstrings to all public methods in `EntityTypeDetector`, `FieldParser`, `CacheKeyGenerator`.

---

### 15. **Unused Imports**
**File:** `api/services/list_processor.py:3`  
**Severity:** 🟢 Low | Code Quality

**Problem:**
```python
from typing import Dict, Any, Optional, Union, List  # Some may be unused
```

**Fix:**  
Run `ruff check --select F401` to identify and remove unused imports.

---

## Best Practices Adherence

### ✅ **Strengths**

1. **Excellent Architecture**
   - Clean separation of concerns (API, Core, Infrastructure)
   - Dependency injection via FastAPI
   - Repository-like pattern with `WikiService`

2. **Comprehensive Observability**
   - Structured JSON logging with context vars
   - Request ID tracking across entire request lifecycle
   - Prometheus-compatible metrics

3. **Robust Error Handling**
   - Exponential backoff for transient failures
   - Graceful degradation with streaming errors
   - Detailed error context in logs

4. **Testing**
   - Unit tests for normalizers and SPARQL builders
   - Integration tests with mocked HTTP
   - Fixtures for test data

5. **Type Safety**
   - Extensive use of type hints
   - Pydantic models for request/response validation
   - Enums for constants

6. **Security-Conscious**
   - Non-root Docker user
   - Environment variable configuration
   - HTTPS-compatible User-Agent

### ⚠️ **Areas for Improvement**

1. **Security Hardening**
   - Add authentication for metrics endpoints
   - Validate proxy headers (SSRF risk)
   - Sanitize SPARQL inputs

2. **Resource Management**
   - Implement bounded collections in metrics
   - Add connection pooling for HTTP requests
   - Periodic cache cleanup job

3. **Observability**
   - Add distributed tracing (OpenTelemetry)
   - Expose health check with dependency status
   - Log cache evictions

4. **Testing**
   - Add load/performance tests
   - Integration tests for streaming endpoints
   - Contract tests for Wikidata API

---

## Recommendations by Priority

### Immediate (Before Production)
1. ✅ Fix type errors in `expansion_handler.py` (Blocker #1)
2. ✅ Fix Docker CMD path (Blocker #2)
3. ✅ Add proxy header validation (High #3)
4. ✅ Add SPARQL input sanitization (High #4)
5. ✅ Add metrics authentication (High #5)

### Short-term (Next Sprint)
6. ✅ Implement bounded metrics collections (Medium #6)
7. ✅ Replace global singleton with `lru_cache` (Medium #7)
8. ✅ Standardize error response format (Medium #8)
9. ✅ Add date validation (Medium #9)
10. ✅ Fix cache cleanup race condition (Medium #10)

### Long-term (Technical Debt)
11. ✅ Extract retry config to settings (Low #11)
12. ✅ Add cache eviction logging (Low #12)
13. ✅ Standardize type hints to Python 3.9+ (Low #13)
14. ✅ Complete docstring coverage (Low #14)
15. ✅ Remove unused imports (Low #15)

---

## Performance Considerations

### 1. **Connection Pooling**
Currently creates new `requests.Session` per request. Consider:
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class WikiService:
    def __init__(self):
        self.session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=Retry(total=0)  # Handle retries manually
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
```

### 2. **Async SPARQL Execution**
Current implementation uses synchronous `requests`. Consider `httpx` for async:
```python
import httpx

async def execute_sparql_query_async(self, query: str, ...):
    async with httpx.AsyncClient() as client:
        response = await client.get(...)
```

### 3. **Batch Entity Expansion**
Instead of expanding entities one-by-one, batch multiple QIDs:
```python
def expand_entities_batch(self, qids: List[str], lang: str) -> dict[str, dict]:
    """Fetch multiple entities in one SPARQL query."""
    qid_values = ' '.join([f"wd:{qid}" for qid in qids])
    query = f"SELECT ?entity WHERE {{ VALUES ?entity {{ {qid_values} }} ... }}"
```

---

## Security Checklist

- [x] Environment variables used for secrets
- [x] Non-root Docker user
- [ ] **MISSING:** Authentication for admin endpoints
- [ ] **MISSING:** Rate limiting per client
- [x] Input validation on QID format
- [ ] **PARTIAL:** SPARQL injection prevention (needs escaping)
- [ ] **MISSING:** SSRF protection on proxy headers
- [x] HTTPS User-Agent for Wikidata
- [x] Structured logging without sensitive data
- [x] Healthcheck endpoint (non-authenticated OK)

---

## Testing Gaps

### Missing Test Coverage
1. **Streaming endpoints** - No integration tests for NDJSON streaming
2. **Error scenarios** - Missing tests for malformed SPARQL responses
3. **Cache invalidation** - No tests for TTL expiration edge cases
4. **Proxy failover** - Missing tests for proxy rotation logic
5. **Concurrent requests** - No load tests for race conditions

### Recommended Test Additions
```python
# tests/integration/test_streaming.py
async def test_streaming_response_format():
    """Verify NDJSON streaming format."""
    # ...

# tests/unit/test_cache.py
def test_cache_ttl_expiration():
    """Verify cache entries expire after TTL."""
    # ...

# tests/integration/test_proxy_rotation.py
def test_proxy_failover_on_502():
    """Verify proxy rotation on gateway errors."""
    # ...
```

---

## Conclusion

This is a **well-architected microservice** with strong foundations in observability, error handling, and testing. The primary concerns are:

1. **Security hardening** (SSRF, SPARQL injection, metrics auth)
2. **Type correctness** (expansion handler bug)
3. **Resource bounding** (metrics, cache)

All issues are addressable with the provided fixes. Once blockers are resolved, the service is **production-ready** for deployment.

---

## Questions for Product/Team

1. **Authentication Strategy:** Should metrics endpoints require API keys or remain public? 
2. **Rate Limiting:** What are acceptable rate limits per client/IP?
3. **Proxy Allowlist:** Should `X-Proxy-List` be restricted to specific domains?
4. **SPARQL Timeout:** Is 60s timeout appropriate for Wikidata queries in production?
5. **Cache Size:** Are 10,000 entries and 5-min TTL appropriate for expected load?

---

**Review Complete.** Prioritize fixing Blocker #1 and #2, then address High severity security issues before production deployment.
