import json
import logging
import time
import hashlib
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
from contextvars import ContextVar
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict
import threading
from datetime import datetime, timezone

# Context variables to store request-scoped data (thread-safe per request)
request_id_ctx: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
request_start_time_ctx: ContextVar[Optional[float]] = ContextVar('request_start_time', default=None)
sparql_latency_ctx: ContextVar[Optional[float]] = ContextVar('sparql_latency_ms', default=None)
entity_expansion_latency_ctx: ContextVar[Optional[float]] = ContextVar('entity_expansion_latency_ms', default=None)
proxy_used_ctx: ContextVar[Optional[str]] = ContextVar('proxy_used', default=None)


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add context variables if available
        request_id = request_id_ctx.get(None)
        if request_id:
            log_data["request_id"] = request_id
        
        # Add extra fields from record
        for key in ['route', 'proxy_used', 'sparql_latency_ms', 'entity_expansion_latency_ms', 
                   'cache_hit', 'status_code', 'params_hash', 'error_type', 'error_detail',
                   'query_hash', 'attempt']:
            if hasattr(record, key):
                value = getattr(record, key)
                if value is not None:
                    log_data[key] = value
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Filter out None values
        return json.dumps({k: v for k, v in log_data.items() if v is not None})


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to generate or extract request ID and inject into context."""
    
    async def dispatch(self, request: Request, call_next):
        # Check if client provided X-Request-ID header
        req_id = request.headers.get("X-Request-ID")
        if not req_id:
            # Generate unique request ID
            req_id = str(uuid.uuid4())
        
        request_id_ctx.set(req_id)
        
        # Track request start time
        start_time = time.time()
        request_start_time_ctx.set(start_time)
        
        # Process request
        response = await call_next(request)
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = req_id
        
        return response


class MetricsCollector:
    """Thread-safe metrics collector for Prometheus-friendly metrics with JSON persistence."""
    
    def __init__(self, max_samples_per_route: int = 100, metrics_file: str = "metrics.json"):
        self._lock = threading.Lock()
        self.max_samples = max_samples_per_route
        self.metrics_file = Path(metrics_file)
        self._last_save_time = 0
        self._save_interval = 10  # Save every 10 seconds at most
        self.request_counts = defaultdict(int)  # route -> count
        self.error_counts = defaultdict(int)  # route -> error_count
        self.latency_samples = defaultdict(list)  # route -> [latencies in ms]
        self.cache_hits = defaultdict(int)
        self.cache_misses = defaultdict(int)
        self.sparql_errors = defaultdict(int)  # error_type -> count
        
        # Load existing metrics on startup
        self._load()
        
    def _save(self):
        """Save metrics to JSON file (caller must hold lock)."""
        try:
            # Convert defaultdicts to regular dicts for JSON serialization
            # Convert latency_samples lists to limited size (keep last N)
            metrics_data = {
                "request_counts": dict(self.request_counts),
                "error_counts": dict(self.error_counts),
                "cache_hits": dict(self.cache_hits),
                "cache_misses": dict(self.cache_misses),
                "sparql_errors": dict(self.sparql_errors),
                "latency_samples": {
                    route: samples[-self.max_samples:] if len(samples) > self.max_samples else samples
                    for route, samples in self.latency_samples.items()
                },
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            
            # Write to temp file first, then rename (atomic write)
            temp_file = self.metrics_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(metrics_data, f, indent=2, default=str)
            
            # Atomic rename
            temp_file.replace(self.metrics_file)
            self._last_save_time = time.time()
        except Exception as e:
            logging.getLogger("observability").warning(f"Failed to save metrics: {e}")
    
    def _load(self):
        """Load metrics from JSON file if it exists."""
        if not self.metrics_file.exists():
            return
        
        try:
            with open(self.metrics_file, 'r') as f:
                data = json.load(f)
            
            # Restore metrics
            self.request_counts = defaultdict(int, data.get("request_counts", {}))
            self.error_counts = defaultdict(int, data.get("error_counts", {}))
            self.cache_hits = defaultdict(int, data.get("cache_hits", {}))
            self.cache_misses = defaultdict(int, data.get("cache_misses", {}))
            self.sparql_errors = defaultdict(int, data.get("sparql_errors", {}))
            
            # Restore latency samples (convert back to lists)
            latency_data = data.get("latency_samples", {})
            self.latency_samples = defaultdict(list, {
                route: list(samples) if isinstance(samples, list) else []
                for route, samples in latency_data.items()
            })
            
            logging.getLogger("observability").info(
                f"Loaded metrics from {self.metrics_file}. "
                f"Total requests: {sum(self.request_counts.values())}"
            )
        except Exception as e:
            logging.getLogger("observability").warning(f"Failed to load metrics: {e}")
    
    def _maybe_save(self):
        """Save metrics if enough time has passed since last save (caller must hold lock)."""
        current_time = time.time()
        if current_time - self._last_save_time >= self._save_interval:
            self._save()
    
    def record_request(self, route: str, status_code: int, latency_ms: float):
        """Record a request with its status and latency."""
        with self._lock:
            self.request_counts[route] += 1
            if status_code >= 400:
                self.error_counts[route] += 1
            # Keep only last N samples for P95 calculation
            samples = self.latency_samples[route]
            if len(samples) >= self.max_samples:
                samples.pop(0)
            samples.append(latency_ms)
            self._maybe_save()
    
    def record_cache(self, route: str, hit: bool):
        """Record cache hit or miss."""
        with self._lock:
            if hit:
                self.cache_hits[route] += 1
            else:
                self.cache_misses[route] += 1
            self._maybe_save()
    
    def record_sparql_error(self, error_type: str):
        """Record a SPARQL error."""
        with self._lock:
            self.sparql_errors[error_type] += 1
            self._maybe_save()
    
    def save(self):
        """Force save metrics to disk (public method)."""
        with self._lock:
            self._save()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot in JSON format."""
        with self._lock:
            metrics = {
                "requests": dict(self.request_counts),
                "errors": dict(self.error_counts),
                "cache_hits": dict(self.cache_hits),
                "cache_misses": dict(self.cache_misses),
                "sparql_errors": dict(self.sparql_errors),
            }
            
            # Calculate P95 latencies
            p95_latencies = {}
            for route, samples in self.latency_samples.items():
                if samples:
                    sorted_samples = sorted(samples)
                    p95_index = int(len(sorted_samples) * 0.95)
                    p95_latencies[route] = sorted_samples[p95_index] if p95_index < len(sorted_samples) else sorted_samples[-1]
            
            metrics["p95_latency_ms"] = p95_latencies
            
            # Cache hit rates
            cache_hit_rates = {}
            for route in set(list(self.cache_hits.keys()) + list(self.cache_misses.keys())):
                hits = self.cache_hits.get(route, 0)
                misses = self.cache_misses.get(route, 0)
                total = hits + misses
                if total > 0:
                    cache_hit_rates[route] = (hits / total) * 100
                else:
                    cache_hit_rates[route] = 0.0
            
            metrics["cache_hit_rate_percent"] = cache_hit_rates
            
            return metrics
    
    def reset(self):
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self.request_counts.clear()
            self.error_counts.clear()
            self.latency_samples.clear()
            self.cache_hits.clear()
            self.cache_misses.clear()
            self.sparql_errors.clear()
            self._save()


# Global metrics instance
metrics = MetricsCollector(max_samples_per_route=100)


def get_request_id() -> Optional[str]:
    """Get current request ID from context."""
    return request_id_ctx.get(None)


def hash_params(params: Dict[str, Any]) -> str:
    """Create a hash of request parameters for logging/caching."""
    # Sort keys and convert to JSON string for consistent hashing
    param_str = json.dumps(params, sort_keys=True, default=str)
    return hashlib.md5(param_str.encode()).hexdigest()[:16]


def hash_query(query: str) -> str:
    """Create a hash of SPARQL query for logging/caching."""
    return hashlib.md5(query.encode()).hexdigest()[:16]


def log_request_info(
    route: str,
    params: Dict[str, Any],
    proxy_used: Optional[str] = None,
    sparql_latency_ms: Optional[float] = None,
    entity_expansion_latency_ms: Optional[float] = None,
    cache_hit: Optional[bool] = None,
    status_code: Optional[int] = None,
    error_type: Optional[str] = None,
    error_detail: Optional[str] = None
):
    """Log structured request information."""
    logger = logging.getLogger("observability")
    request_id = get_request_id()
    params_hash = hash_params(params)
    
    # Create log record with extra fields
    extra = {
        'request_id': request_id,
        'route': route,
        'params_hash': params_hash,
        'proxy_used': proxy_used,
        'sparql_latency_ms': sparql_latency_ms,
        'entity_expansion_latency_ms': entity_expansion_latency_ms,
        'cache_hit': cache_hit,
        'status_code': status_code,
        'error_type': error_type,
        'error_detail': error_detail,
    }
    
    if status_code and status_code >= 400:
        logger.error(f"Request failed: {route}", extra=extra)
    else:
        logger.info(f"Request completed: {route}", extra=extra)


def get_prometheus_metrics() -> str:
    """Generate Prometheus-formatted metrics string."""
    m = metrics.get_metrics()
    lines = []
    
    # Request counts
    for route, count in m['requests'].items():
        # Escape route name for Prometheus label
        route_escaped = route.replace('"', '\\"').replace('\n', '\\n')
        lines.append(f'wikidata_requests_total{{route="{route_escaped}"}} {count}')
    
    # Error counts
    for route, count in m['errors'].items():
        route_escaped = route.replace('"', '\\"').replace('\n', '\\n')
        lines.append(f'wikidata_errors_total{{route="{route_escaped}"}} {count}')
    
    # P95 latency
    for route, p95 in m['p95_latency_ms'].items():
        route_escaped = route.replace('"', '\\"').replace('\n', '\\n')
        lines.append(f'wikidata_p95_latency_ms{{route="{route_escaped}"}} {p95}')
    
    # Cache hit rate
    for route, rate in m['cache_hit_rate_percent'].items():
        route_escaped = route.replace('"', '\\"').replace('\n', '\\n')
        lines.append(f'wikidata_cache_hit_rate_percent{{route="{route_escaped}"}} {rate}')
    
    # SPARQL errors
    for error_type, count in m['sparql_errors'].items():
        error_type_escaped = error_type.replace('"', '\\"').replace('\n', '\\n')
        lines.append(f'wikidata_sparql_errors_total{{error_type="{error_type_escaped}"}} {count}')
    
    return '\n'.join(lines)


