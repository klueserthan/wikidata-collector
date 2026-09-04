"""
WikidataClient - Pure Python client for Wikidata SPARQL queries.

This client has no FastAPI dependencies and can be used standalone.

Entity retrieval is a single generic pipeline (validate filters -> build query ->
fetch page -> normalize -> keyset-paginate -> honor max_results), parameterized by
an entity spec. The public per-entity methods are thin delegates onto it.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Protocol,
    Set,
    Tuple,
    TypeVar,
)

import requests

from .config import RETRYABLE_STATUS_CODES, WikidataCollectorConfig
from .constants import ORGANIZATION_TYPE_MAPPINGS
from .exceptions import (
    InvalidFilterError,
    ProxyMisconfigurationError,
    ProxyUnavailableError,
    QueryExecutionError,
    UpstreamUnavailableError,
)
from .models import (
    PublicFigureNormalizedRecord,
    PublicFigureWikiRecord,
    PublicOrganizationNormalizedRecord,
    PublicOrganizationWikiRecord,
    normalize_bindings,
)
from .proxy import ProxyManager, validate_proxy_list
from .query_builders.figures_query_builder import build_public_figures_query
from .query_builders.organizations_query_builder import (
    build_public_organizations_query,
    resolve_organization_type,
)
from .query_builders.social_handles_query_builder import build_social_handles_query

logger = logging.getLogger(__name__)


class _HasQid(Protocol):
    qid: str


TRecord = TypeVar("TRecord", bound=_HasQid)


def _log_query_execution(
    query_type: str,
    params: Dict[str, Any],
    page_num: int,
    raw_count: int,
    unique_qid_count: int,
    latency_ms: float,
    proxy_used: str,
) -> None:
    """Log structured information about query execution.

    Args:
        query_type: Type of query (e.g., 'public_figures', 'public_organizations')
        params: Query parameters used
        page_num: Page number (1-indexed)
        raw_count: Number of normalized records returned (may include duplicates due to SPARQL expansion)
        unique_qid_count: Number of unique QIDs in the page
        latency_ms: Query latency in milliseconds
        proxy_used: Proxy used for the query
    """
    logger.info(
        f"SPARQL query executed: type={query_type}, page={page_num}, "
        f"raw_records={raw_count}, unique_qids={unique_qid_count}, "
        f"latency={latency_ms:.2f}ms, proxy={proxy_used}",
        extra={
            "query_type": query_type,
            "page": page_num,
            "raw_count": raw_count,
            "unique_qid_count": unique_qid_count,
            "latency_ms": latency_ms,
            "proxy_used": proxy_used,
            "params": params,
        },
    )


def _log_page_fetch(
    query_type: str,
    page_num: int,
    after_qid: Optional[str],
    raw_count: int,
    unique_qid_count: int,
) -> None:
    """Log structured information about page fetching for iterators.

    Args:
        query_type: Type of query
        page_num: Page number being fetched
        after_qid: QID used for keyset pagination (if any)
        raw_count: Number of normalized records in this page (may include duplicates)
        unique_qid_count: Number of unique QIDs in this page
    """
    logger.debug(
        f"Fetched page: type={query_type}, page={page_num}, after_qid={after_qid}, "
        f"raw_records={raw_count}, unique_qids={unique_qid_count}",
        extra={
            "query_type": query_type,
            "page": page_num,
            "after_qid": after_qid,
            "raw_count": raw_count,
            "unique_qid_count": unique_qid_count,
        },
    )


def _log_retry_attempt(
    attempt: int, max_retries: int, reason: str, wait_time: float, proxy: Optional[str] = None
) -> None:
    """Log structured information about retry attempts.

    Args:
        attempt: Current attempt number (1-indexed)
        max_retries: Maximum number of retries configured
        reason: Reason for retry (e.g., 'throttled', 'timeout', 'connection_error')
        wait_time: Time to wait before retry in seconds
        proxy: Proxy being retried (if any)
    """
    logger.warning(
        f"Retry attempt {attempt}/{max_retries}: {reason}, waiting {wait_time:.2f}s",
        extra={
            "attempt": attempt,
            "max_retries": max_retries,
            "reason": reason,
            "wait_time_seconds": wait_time,
            "proxy": proxy,
            "event": "retry",
        },
    )


def _log_query_failure(
    query_type: str,
    error_category: str,
    error_message: str,
    attempts: int,
    filters: Optional[Dict[str, Any]] = None,
) -> None:
    """Log structured information about query failures.

    Args:
        query_type: Type of query that failed
        error_category: Category of error (e.g., 'upstream_unavailable', 'timeout', 'invalid_filter')
        error_message: Detailed error message
        attempts: Number of attempts made before failure
        filters: Filter parameters used in the query
    """
    logger.error(
        f"Query failed: type={query_type}, category={error_category}, attempts={attempts}",
        extra={
            "query_type": query_type,
            "error_category": error_category,
            "error_message": error_message,
            "attempts": attempts,
            "filters": filters or {},
            "event": "query_failure",
        },
    )


def _is_valid_date_format(date_str: str) -> bool:
    """Validate ISO date format (YYYY-MM-DD).

    Args:
        date_str: Date string to validate

    Returns:
        True if valid, False otherwise
    """
    if not date_str:
        return False

    try:
        # Use datetime.strptime for proper validation including leap years
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except (TypeError, ValueError):
        return False


def _no_filter_validation(filters: Dict[str, Any]) -> None:
    """Default entity spec validator: accept all filters."""


def _validate_figure_filters(filters: Dict[str, Any]) -> None:
    """Validate public figure filters (fail-fast on malformed dates).

    Args:
        filters: Filter dict keyed by the public filter vocabulary

    Raises:
        InvalidFilterError: If a birthday filter is not a valid ISO date
    """
    for field_name in ("birthday_from", "birthday_to"):
        value = filters.get(field_name)
        if value and not _is_valid_date_format(value):
            raise InvalidFilterError(
                f"Invalid {field_name} format: {value}. Expected ISO format (YYYY-MM-DD)"
            )


def _validate_organization_filters(filters: Dict[str, Any]) -> None:
    """Validate public organization filters (fail-fast on missing/malformed input).

    `types` is a required filter: Wikidata has no bounded "organization"
    umbrella class the builder can scan without it (see
    `build_public_organizations_query`'s docstring — an unfiltered scan always
    times out on WDQS), so a missing, `None`, or empty `types` is rejected
    here before any SPARQL is built. A bare string is rejected too: Python
    would otherwise iterate its characters as if each were a type, which is
    never what a caller means.

    Args:
        filters: Filter dict keyed by the public filter vocabulary

    Raises:
        InvalidFilterError: If `types` is missing, `None`, empty, a bare
            string, or contains a non-string entry; or if `country` is given
            and is not a string.
    """
    types = filters.get("types")

    if not types:
        raise InvalidFilterError(
            "types filter is required for public organizations (an unfiltered "
            "scan always times out on WDQS). "
            f"Supported values: {', '.join(sorted(ORGANIZATION_TYPE_MAPPINGS.keys()))}, "
            "or a QID starting with Q"
        )

    if isinstance(types, str):
        raise InvalidFilterError(
            f"types must be a list of strings, not a bare string ({types!r}); "
            f"did you mean [{types!r}]?"
        )

    # Require an actual list, not just any iterable. A one-shot iterable (e.g. a
    # generator) would be drained by the loop below and then reach decomposition
    # already exhausted, yielding zero streams and silently returning nothing.
    if not isinstance(types, list):
        raise InvalidFilterError(f"types must be a list of strings, got {type(types).__name__}")

    for value in types:
        if not isinstance(value, str):
            raise InvalidFilterError(f"types entries must be strings, got {value!r}")

    # Resolve every type up front so a malformed value in a multi-type filter
    # fails the whole call before any decomposed stream issues a request.
    # Without this, resolution happens one stream at a time in the builder, so
    # an earlier valid type could yield records — and, under max_results, even
    # satisfy the cap — before a later invalid type is ever reached.
    try:
        for value in types:
            resolve_organization_type(value)
    except ValueError as e:
        raise InvalidFilterError(f"Invalid filter parameters: {e}") from e

    country = filters.get("country")
    if country is not None and not isinstance(country, str):
        raise InvalidFilterError(f"country must be a string, got {country!r}")


def _no_decomposition(filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Default entity spec decomposer: run the filters as a single stream."""
    return [filters]


def _decompose_organization_filters(filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Split multi-type organization filters into one filter dict per type.

    A single combined multi-type SPARQL query degrades badly on WDQS (see
    `build_public_organizations_query`'s docstring), so iteration instead runs
    one keyset-paginated query stream per type value and de-duplicates
    client-side. A single type decomposes to itself — one stream, same as the
    figures entity kind's identity decomposition.

    Args:
        filters: Filter dict keyed by the public filter vocabulary; `types`
            holds one or more values.

    Returns:
        One filter dict per distinct type *class*, in first-appearance order,
        each carrying a single-element `types` list and every other filter
        unchanged. Values that resolve to the same class — whether repeated
        outright, differing only by surrounding whitespace, or given once as a
        label and once as the QID it maps to — are collapsed: each redundant
        value would otherwise spawn a wholly redundant keyset stream whose
        every record is later dropped by cross-stream de-duplication.
    """
    types = filters.get("types") or []
    # De-duplicate by resolved class QID, keeping the first value seen for each
    # class (stripped, so the sub-stream filter is canonical). Validation has
    # already run, so resolution here never raises.
    canonical_by_qid: Dict[str, str] = {}
    for value in types:
        qid = resolve_organization_type(value)
        canonical_by_qid.setdefault(qid, value.strip())
    return [{**filters, "types": [one_type]} for one_type in canonical_by_qid.values()]


def _normalize_figure_bindings(
    bindings: List[Dict[str, Any]],
) -> List[PublicFigureNormalizedRecord]:
    return normalize_bindings(bindings, PublicFigureWikiRecord, PublicFigureNormalizedRecord)


def _normalize_organization_bindings(
    bindings: List[Dict[str, Any]],
) -> List[PublicOrganizationNormalizedRecord]:
    return normalize_bindings(
        bindings, PublicOrganizationWikiRecord, PublicOrganizationNormalizedRecord
    )


def _merge_social_bindings(
    page_bindings: List[Dict[str, Any]],
    social_bindings: List[Dict[str, Any]],
    entity_var: str,
) -> List[Dict[str, Any]]:
    """Merge a page's bindings with a keyed social-handles query's bindings.

    Reproduces the row cross-product a single combined query would have
    produced, purely at the bindings level, before `spec.normalize` runs.
    Every page row sharing a QID with one or more social rows is expanded
    into one merged row per social row; a page row with no matching social
    row is emitted unchanged. Page order is preserved throughout, so
    same-QID rows stay consecutive — a requirement of `normalize_bindings`,
    which folds consecutive same-QID rows into one record.

    Args:
        page_bindings: Bindings from the page query, keyed by `entity_var`.
        social_bindings: Bindings from `build_social_handles_query`, keyed by
            `?entity`.
        entity_var: The page binding's entity variable (`"person"` or
            `"organization"`) whose IRI ends in the QID.

    Returns:
        Merged rows in page order. The social binding's `entity` key is
        dropped from every merged row.
    """
    social_by_qid: Dict[str, List[Dict[str, Any]]] = {}
    for row in social_bindings:
        qid = row["entity"]["value"].split("/")[-1]
        social_row = {key: value for key, value in row.items() if key != "entity"}
        social_by_qid.setdefault(qid, []).append(social_row)

    merged: List[Dict[str, Any]] = []
    for page_row in page_bindings:
        qid = page_row[entity_var]["value"].split("/")[-1]
        social_rows = social_by_qid.get(qid)
        if social_rows:
            merged.extend({**page_row, **social_row} for social_row in social_rows)
        else:
            merged.append(page_row)
    return merged


@dataclass(frozen=True)
class _EntitySpec(Generic[TRecord]):
    """Everything the entity pipeline needs to know about one entity kind.

    Adding an entity kind means adding a spec (plus a record family and a query
    builder) — not a new pipeline.
    """

    entity_kind: str
    query_type: str
    build_query: Callable[..., str]
    normalize: Callable[[List[Dict[str, Any]]], List[TRecord]]
    entity_var: str
    validate_filters: Callable[[Dict[str, Any]], None] = _no_filter_validation
    decompose_filters: Callable[[Dict[str, Any]], List[Dict[str, Any]]] = _no_decomposition


_PUBLIC_FIGURES: "_EntitySpec[PublicFigureNormalizedRecord]" = _EntitySpec(
    entity_kind="public_figure",
    query_type="public_figures",
    build_query=build_public_figures_query,
    normalize=_normalize_figure_bindings,
    entity_var="person",
    validate_filters=_validate_figure_filters,
)

_PUBLIC_ORGANIZATIONS: "_EntitySpec[PublicOrganizationNormalizedRecord]" = _EntitySpec(
    entity_kind="public_organization",
    query_type="public_organizations",
    build_query=build_public_organizations_query,
    normalize=_normalize_organization_bindings,
    entity_var="organization",
    validate_filters=_validate_organization_filters,
    decompose_filters=_decompose_organization_filters,
)


class WikidataClient:
    """Client for fetching Wikidata entities via SPARQL and Entity API."""

    def __init__(self, config: Optional[WikidataCollectorConfig] = None):
        """Initialize the Wikidata client.

        Args:
            config: Configuration object. If None, uses defaults from environment.
        """
        self.config = config or WikidataCollectorConfig()
        self.proxy_manager = ProxyManager(
            proxy_list=self.config.proxy_list,
            timeout_per_hop=self.config.sparql_timeout_seconds,
            cooldown_period=self.config.proxy_cooldown_seconds,
        )

        logger.info(f"Initialized WikidataClient with {len(self.config.proxy_list)} proxies")

    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()

    def execute_sparql_query(
        self, query: str, override_proxies: Optional[List[str]] = None
    ) -> Tuple[Dict[str, Any], str]:
        """Execute SPARQL query against Wikidata with proxy support.

        For single-proxy setups (exactly one effective validated proxy), proxy
        exhaustion triggers a deep-sleep retry loop: the client sleeps for
        ``config.proxy_deep_sleep_seconds`` and retries up to
        ``config.proxy_deep_sleep_max_failures`` times before raising.

        For multi-proxy setups or no-proxy setups, failure is immediate.

        Args:
            query: SPARQL query string
            override_proxies: Optional list of proxy URLs to use instead of configured ones

        Returns:
            Tuple of (result_dict, used_proxy) where used_proxy is "direct" or proxy URL

        Raises:
            QueryExecutionError: If query execution fails after retries (no proxy configured)
            UpstreamUnavailableError: If Wikidata returns 502/503/504 after all retries
            ProxyMisconfigurationError: If all proxies in a multi-proxy setup fail
            ProxyUnavailableError: If the single configured proxy fails across all deep-sleep cycles
        """
        # Determine the effective validated proxy list for this call.
        # override_proxies (when given) fully replaces the configured proxy list;
        # ProxyManager.get_available_proxies already handles validation for overrides,
        # but we need the full (pre-cooldown-filter) effective list to decide whether
        # we are in single-proxy mode.  For overrides we validate them directly; for
        # configured proxies we use the already-validated self.proxy_manager.proxies.
        if override_proxies is not None:
            effective_proxy_list: List[str] = validate_proxy_list(override_proxies)
        else:
            effective_proxy_list = list(self.proxy_manager.proxies)

        # Single-proxy deep-sleep is only eligible when exactly one effective proxy exists.
        single_proxy: Optional[str] = (
            effective_proxy_list[0] if len(effective_proxy_list) == 1 else None
        )

        if single_proxy is not None:
            return self._execute_sparql_with_deep_sleep(query, override_proxies, single_proxy)
        else:
            return self._execute_sparql_attempt(query, override_proxies)

    def _execute_sparql_with_deep_sleep(
        self,
        query: str,
        override_proxies: Optional[List[str]],
        single_proxy: str,
    ) -> Tuple[Dict[str, Any], str]:
        """Outer deep-sleep retry loop for single-proxy mode.

        Calls ``_execute_sparql_attempt`` and, on proxy exhaustion, sleeps and
        retries up to ``config.proxy_deep_sleep_max_failures`` times.

        Args:
            query: SPARQL query string
            override_proxies: Proxy override list passed through to the attempt helper
            single_proxy: The one validated effective proxy URL (used for reset and logging)

        Returns:
            Tuple of (result_dict, used_proxy)

        Raises:
            ProxyUnavailableError: When all deep-sleep cycles are exhausted
            UpstreamUnavailableError: Propagated immediately from the attempt helper
            QueryExecutionError: Propagated immediately from the attempt helper
        """
        # First attempt (before any deep sleep)
        try:
            return self._execute_sparql_attempt(query, override_proxies)
        except ProxyMisconfigurationError as first_err:
            last_err: Exception = first_err

        # Normal retries failed — enter deep-sleep cycle
        for deep_attempt in range(self.config.proxy_deep_sleep_max_failures):
            sleep_s = self.config.proxy_deep_sleep_seconds
            logger.warning(
                f"Single proxy unavailable, deep sleeping for {sleep_s}s "
                f"(cycle {deep_attempt + 1}/{self.config.proxy_deep_sleep_max_failures})",
                extra={
                    "event": "proxy_deep_sleep_started",
                    "proxy": single_proxy,
                    "deep_sleep_attempt": deep_attempt + 1,
                    "deep_sleep_max": self.config.proxy_deep_sleep_max_failures,
                    "deep_sleep_seconds": sleep_s,
                },
            )
            time.sleep(sleep_s)
            # Clear the proxy's failed status so the inner retry loop can use it again
            self.proxy_manager.reset_proxy(single_proxy)
            try:
                return self._execute_sparql_attempt(query, override_proxies)
            except ProxyMisconfigurationError as retry_err:
                logger.warning(
                    f"Deep-sleep recovery attempt {deep_attempt + 1} failed: {retry_err}",
                    extra={
                        "event": "proxy_deep_sleep_recovery_failed",
                        "proxy": single_proxy,
                        "deep_sleep_attempt": deep_attempt + 1,
                        "error": str(retry_err),
                    },
                )
                last_err = retry_err
                continue

        # All deep-sleep cycles exhausted
        _log_query_failure(
            query_type="sparql_query",
            error_category="proxy_unavailable",
            error_message=str(last_err),
            attempts=self.config.proxy_deep_sleep_max_failures,
        )
        logger.error(
            f"Single proxy remained unavailable after "
            f"{self.config.proxy_deep_sleep_max_failures} deep-sleep cycles",
            extra={
                "event": "proxy_deep_sleep_exhausted",
                "proxy": single_proxy,
                "deep_sleep_cycles": self.config.proxy_deep_sleep_max_failures,
                "deep_sleep_seconds": self.config.proxy_deep_sleep_seconds,
            },
        )
        raise ProxyUnavailableError(
            f"Single proxy {single_proxy!r} remained unavailable after "
            f"{self.config.proxy_deep_sleep_max_failures} deep-sleep cycles "
            f"({self.config.proxy_deep_sleep_seconds}s each): {last_err}"
        )

    def _execute_sparql_attempt(
        self, query: str, override_proxies: Optional[List[str]] = None
    ) -> Tuple[Dict[str, Any], str]:
        """Inner retry loop: attempt the SPARQL query up to max_retries times.

        Does NOT perform deep-sleep — that is handled by the caller
        (``execute_sparql_query`` / ``_execute_sparql_with_deep_sleep``).

        A response status in ``RETRYABLE_STATUS_CODES`` (429, 502, 503, 504) is
        retried with backoff. Any other 4xx is not retryable — the query text
        itself was rejected, so a retry would just repeat the same request — and
        raises ``QueryExecutionError`` immediately, after a single request.

        Args:
            query: SPARQL query string
            override_proxies: Optional list of proxy URLs to use instead of configured ones

        Returns:
            Tuple of (result_dict, used_proxy)

        Raises:
            UpstreamUnavailableError: If Wikidata returns 502/503/504 on the final attempt
            ProxyMisconfigurationError: If proxies are configured and all fail
            QueryExecutionError: If no proxies are configured and execution fails, or if
                Wikidata returns a non-retryable 4xx (any status but 429)
        """
        sparql_start_time = time.time()

        headers = {
            "Accept": "application/sparql-results+json",
            "User-Agent": self.config.get_user_agent(),
        }

        params = {"query": query}
        used_proxy = "direct"
        # Track the last status code to properly categorize errors
        last_status_code = None

        for attempt in range(self.config.max_retries):
            proxy = None
            # Track if we already logged retry for this attempt (to avoid duplicates)
            already_logged_retry = False

            try:
                # Get proxy for this attempt
                proxy = self.proxy_manager.get_next_proxy(override_proxies)
                proxy_dict = None

                if proxy:
                    proxy_dict = self.proxy_manager.get_proxy_dict(proxy)
                    used_proxy = proxy

                # Make request with timeout
                response = requests.get(
                    self.config.wikidata_sparql_url,
                    params=params,
                    headers=headers,
                    proxies=proxy_dict,
                    timeout=self.config.sparql_timeout_seconds,
                )

                # Handle throttling gracefully
                if response.status_code == 429:
                    last_status_code = 429
                    retry_after = response.headers.get("Retry-After")
                    wait_s = (
                        int(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
                    )
                    if attempt < self.config.max_retries - 1:
                        _log_retry_attempt(
                            attempt=attempt + 1,
                            max_retries=self.config.max_retries,
                            reason="throttled_429",
                            wait_time=wait_s,
                            proxy=proxy,
                        )
                        already_logged_retry = True
                        time.sleep(wait_s)
                    raise requests.exceptions.HTTPError("429 Too Many Requests", response=response)

                if response.status_code in RETRYABLE_STATUS_CODES:
                    last_status_code = response.status_code
                    wait_s = min(self.config.retry_max_wait_seconds, 2**attempt)
                    if attempt < self.config.max_retries - 1:
                        _log_retry_attempt(
                            attempt=attempt + 1,
                            max_retries=self.config.max_retries,
                            reason=f"upstream_error_{response.status_code}",
                            wait_time=wait_s,
                            proxy=proxy,
                        )
                        already_logged_retry = True
                        time.sleep(wait_s)
                    raise requests.exceptions.HTTPError(
                        f"{response.status_code} Service Unavailable", response=response
                    )

                if 400 <= response.status_code < 500:
                    # A non-retryable 4xx (e.g. a WDQS WAF 403, or a malformed-query
                    # 400) means the query itself was rejected: retrying would send
                    # the same query text and get the same result, so fail on the
                    # first request instead of burning max_retries attempts and sleeps.
                    body_snippet = response.text[:200]
                    raise QueryExecutionError(
                        f"Non-retryable client error {response.status_code} from Wikidata: "
                        f"{body_snippet}"
                    )

                response.raise_for_status()

                # Calculate total SPARQL latency
                sparql_latency_ms = (time.time() - sparql_start_time) * 1000

                result = response.json()

                logger.info(
                    f"SPARQL query executed successfully "
                    f"(latency: {sparql_latency_ms:.2f}ms, proxy: {used_proxy})"
                )

                return result, used_proxy

            except requests.exceptions.RequestException as e:
                error_type = type(e).__name__

                if proxy:
                    self.proxy_manager.mark_proxy_failed(proxy)

                # Log retry attempt with structured format (only if not already logged)
                if attempt < self.config.max_retries - 1 and not already_logged_retry:
                    wait_time = (
                        self.config.retry_jitter_base + self.config.retry_jitter_increment * attempt
                    )
                    _log_retry_attempt(
                        attempt=attempt + 1,
                        max_retries=self.config.max_retries,
                        reason=f"request_exception_{error_type}",
                        wait_time=wait_time,
                        proxy=proxy,
                    )

                # If this was the last attempt, determine error type and raise
                if attempt == self.config.max_retries - 1:
                    # Check for upstream errors based on tracked status code (not string
                    # matching). 429 is excluded: it is throttling, not an upstream outage,
                    # so its exhaustion is classified as a QueryExecutionError below.
                    if last_status_code in RETRYABLE_STATUS_CODES - {429}:
                        _log_query_failure(
                            query_type="sparql_query",
                            error_category="upstream_unavailable",
                            error_message=str(e),
                            attempts=self.config.max_retries,
                        )
                        raise UpstreamUnavailableError(
                            f"Upstream Wikidata service unavailable after {self.config.max_retries} attempts: {e}"
                        )
                    # Check if we were using proxies and all failed.
                    # For override_proxies: failures are not tracked in proxy_manager.failed_proxies
                    # (overrides bypass the cooldown system), so we detect exhaustion purely
                    # from whether override_proxies was non-empty.
                    # For configured proxies: check that the available list (post-cooldown) is empty.
                    proxies_were_in_use = override_proxies is not None or bool(
                        self.proxy_manager.proxies
                    )
                    configured_proxies_exhausted = (
                        override_proxies is None
                        and len(self.proxy_manager.get_available_proxies()) == 0
                    )
                    override_proxies_exhausted = override_proxies is not None
                    if proxies_were_in_use and (
                        configured_proxies_exhausted or override_proxies_exhausted
                    ):
                        _log_query_failure(
                            query_type="sparql_query",
                            error_category="proxy_misconfiguration",
                            error_message=str(e),
                            attempts=self.config.max_retries,
                        )
                        raise ProxyMisconfigurationError(
                            f"All configured proxies failed after {self.config.max_retries} attempts: {e}"
                        )
                    else:
                        _log_query_failure(
                            query_type="sparql_query",
                            error_category="query_execution_error",
                            error_message=str(e),
                            attempts=self.config.max_retries,
                        )
                        raise QueryExecutionError(
                            f"Failed to execute SPARQL query after {self.config.max_retries} attempts: {e}"
                        )

                # Short jitter before retry (skip if already slept for status codes)
                if not already_logged_retry:
                    wait_time = (
                        self.config.retry_jitter_base + self.config.retry_jitter_increment * attempt
                    )
                    time.sleep(wait_time)
        # This point should be unreachable: every loop iteration should either
        # return a result or raise on the final attempt. If we get here, it
        # indicates a logic error in the retry loop implementation.
        logger.critical(
            "Unreachable code reached in _execute_sparql_attempt: "
            "retry loop exited without returning or raising. "
            "max_retries=%d, used_proxy=%s",
            self.config.max_retries,
            used_proxy,
        )
        raise QueryExecutionError(
            "Internal error: retry loop exited without returning or raising; "
            "this indicates a bug in _execute_sparql_attempt."
        )

    def _fetch_page(
        self,
        spec: _EntitySpec[TRecord],
        filters: Dict[str, Any],
        *,
        lang: str = "en",
        limit: Optional[int] = None,
        cursor: int = 0,
        after_qid: Optional[str] = None,
        override_proxies: Optional[List[str]] = None,
    ) -> Tuple[List[TRecord], str]:
        """Fetch and normalize one page of results for an entity kind.

        This is the pipeline's fetch seam: tests substitute fake pages here,
        production builds a SPARQL query and executes it via the proxy layer.
        Filters are validated here so every entry point (get_* and iterate_*)
        fails fast before anything is interpolated into SPARQL.

        Args:
            spec: Entity spec for the entity kind being fetched
            filters: Filter dict keyed by the entity's public filter vocabulary
            lang: Language code for labels
            limit: Maximum results to return (defaults to config.default_limit)
            cursor: Offset for pagination
            after_qid: QID for keyset pagination
            override_proxies: Optional list of proxy URLs

        Returns:
            Tuple of (normalized records, used_proxy)

        Raises:
            InvalidFilterError: If filter parameters are invalid or malformed
        """
        spec.validate_filters(filters)

        if limit is None:
            limit = self.config.default_limit

        # The type-only validator above cannot catch value-level filter errors
        # (unknown labels, malformed QIDs); those surface here as the builder's
        # plain ValueError. Translate them to InvalidFilterError at this shared
        # boundary so every entry point — get_* and iterate_* alike — honors its
        # documented InvalidFilterError contract instead of leaking a ValueError.
        try:
            query = spec.build_query(
                **filters, lang=lang, limit=limit, cursor=cursor, after_qid=after_qid
            )
        except ValueError as e:
            raise InvalidFilterError(f"Invalid filter parameters: {e}") from e
        result, used_proxy = self.execute_sparql_query(query, override_proxies)
        bindings = result.get("results", {}).get("bindings", [])

        # Social handles are fetched in a second, WAF-safe query keyed by this
        # page's QIDs (docs/adr/0002-social-handles-second-query.md): the five
        # handle OPTIONALs trip Wikidata's edge WAF combined with the page
        # query's SELECT shape. An empty page has no QIDs to key that query
        # on, so it makes no second request. `used_proxy` stays the page
        # query's proxy, not the social-handles query's.
        if bindings:
            qids: List[str] = []
            seen_qids: Set[str] = set()
            for row in bindings:
                qid = row[spec.entity_var]["value"].split("/")[-1]
                if qid not in seen_qids:
                    seen_qids.add(qid)
                    qids.append(qid)

            social_query = build_social_handles_query(qids)
            social_result, _ = self.execute_sparql_query(social_query, override_proxies)
            social_bindings = social_result.get("results", {}).get("bindings", [])
            bindings = _merge_social_bindings(bindings, social_bindings, spec.entity_var)

        return spec.normalize(bindings), used_proxy

    def _paginate_sparql_results(
        self,
        spec: _EntitySpec[TRecord],
        filters: Dict[str, Any],
        *,
        lang: str = "en",
        limit: Optional[int] = None,
        override_proxies: Optional[List[str]] = None,
    ) -> Iterator[TRecord]:
        """Yield normalized records across pages using keyset pagination.

        Records can be expanded in the SPARQL query (multi-row per entity), so
        end-of-results is determined by the number of unique QIDs per page, not
        the raw record count.

        Args:
            spec: Entity spec for the entity kind being paginated
            filters: Filter dict keyed by the entity's public filter vocabulary
            lang: Language code for labels
            limit: Page size (defaults to config.default_limit)
            override_proxies: Optional list of proxy URLs

        Yields:
            Individual normalized records
        """
        if limit is None:
            limit = self.config.default_limit

        after_qid: Optional[str] = None
        page_num = 0

        while True:
            page_num += 1
            start_time = time.time()

            results, proxy = self._fetch_page(
                spec,
                filters,
                lang=lang,
                limit=limit,
                after_qid=after_qid,
                override_proxies=override_proxies,
            )
            latency_ms = (time.time() - start_time) * 1000

            raw_count = len(results)
            unique_qid_count = len({record.qid for record in results})

            _log_page_fetch(spec.query_type, page_num, after_qid, raw_count, unique_qid_count)
            _log_query_execution(
                spec.query_type,
                filters,
                page_num,
                raw_count,
                unique_qid_count,
                latency_ms,
                proxy,
            )

            if not results:
                break

            yield from results

            if unique_qid_count < limit:
                break

            # Keyset pagination: use the last record's QID.
            after_qid = results[-1].qid

    def _iterate(
        self,
        spec: _EntitySpec[TRecord],
        filters: Dict[str, Any],
        *,
        max_results: Optional[int],
        lang: str,
    ) -> Iterator[TRecord]:
        """Run the full entity pipeline: validate, decompose, paginate, cap, log lifecycle.

        Filters are validated once, against the original (pre-decomposition)
        filter dict. `spec.decompose_filters` then splits them into one or
        more sub-streams run sequentially (identity decomposition — the
        default — yields exactly one sub-stream, so single-type organization
        calls and all figure calls behave exactly as before decomposition was
        introduced). When there is more than one sub-stream, a QID already
        yielded by an earlier sub-stream is skipped by a later one and does
        not count toward `max_results`, which is a single global budget
        spanning every sub-stream.

        Args:
            spec: Entity spec for the entity kind being iterated
            filters: Filter dict keyed by the entity's public filter vocabulary
            max_results: Maximum number of results to yield (None for unlimited)
            lang: Language code for labels

        Yields:
            Individual normalized records

        Raises:
            InvalidFilterError: If filter parameters are invalid or malformed
            QueryExecutionError: If upstream query execution fails
        """
        spec.validate_filters(filters)
        self._validate_max_results(max_results)

        sub_filter_list = spec.decompose_filters(filters)
        # Only decomposition into more than one sub-stream needs cross-stream
        # de-duplication; a single sub-stream must behave exactly as before
        # decomposition existed, including yielding raw, unfolded duplicate
        # QIDs coming out of one page (see the keyset pagination tests).
        seen_qids: Optional[Set[str]] = set() if len(sub_filter_list) > 1 else None

        count = 0
        success = False

        logger.info(
            f"Starting iterate_{spec.query_type}: filters={filters}, max_results={max_results}",
            extra={
                "event": "iteration_started",
                "entity_kind": spec.entity_kind,
                "filters": filters,
                "max_results": max_results,
            },
        )

        start_time = time.time()

        try:
            for sub_filters in sub_filter_list:
                reached_cap = False

                for record in self._paginate_sparql_results(spec, sub_filters, lang=lang):
                    if seen_qids is not None:
                        if record.qid in seen_qids:
                            continue
                        seen_qids.add(record.qid)

                    yield record
                    count += 1

                    if max_results is not None and count >= max_results:
                        logger.info(
                            f"Reached max_results limit of {max_results}",
                            extra={
                                "event": "max_results_reached",
                                "entity_kind": spec.entity_kind,
                                "result_count": count,
                            },
                        )
                        reached_cap = True
                        break

                if reached_cap:
                    break

            # Mark as successful if we completed iteration without exception
            success = True

        except ValueError as e:
            # Query builder or validation errors
            logger.error(
                f"Invalid filter parameters: {e}",
                extra={
                    "event": "iteration_failed",
                    "entity_kind": spec.entity_kind,
                    "error_type": "invalid_filters",
                },
            )
            raise InvalidFilterError(f"Invalid filter parameters: {e}")
        except Exception as e:
            # Log other errors
            logger.error(
                f"Iteration failed: {e}",
                extra={
                    "event": "iteration_failed",
                    "entity_kind": spec.entity_kind,
                    "error_type": type(e).__name__,
                },
            )
            raise
        finally:
            # Log iteration completion only if successful
            if success:
                duration_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"Completed iterate_{spec.query_type}: yielded {count} results in {duration_ms:.2f}ms",
                    extra={
                        "event": "iteration_completed",
                        "entity_kind": spec.entity_kind,
                        "result_count": count,
                        "duration_ms": duration_ms,
                        "status": "success",
                    },
                )

    def _validate_max_results(self, max_results: Optional[int]) -> None:
        """Validate max_results parameter.

        Args:
            max_results: Maximum number of results to yield

        Raises:
            InvalidFilterError: If max_results is less than 1
        """
        if max_results is not None and max_results < 1:
            raise InvalidFilterError(f"max_results must be >= 1, got {max_results}")

    def get_public_figures(
        self,
        birthday_from: Optional[str] = None,
        birthday_to: Optional[str] = None,
        nationality: Optional[str] = None,
        occupations: Optional[List[str]] = None,
        gender: Optional[str] = None,
        lang: str = "en",
        limit: Optional[int] = None,
        cursor: int = 0,
        after_qid: Optional[str] = None,
        override_proxies: Optional[List[str]] = None,
    ) -> Tuple[List[PublicFigureNormalizedRecord], str]:
        """Get one page of public figures with optional filters.

        Args:
            birthday_from: Birth date from (ISO format)
            birthday_to: Birth date to (ISO format)
            nationality: Nationality filter (QID, ISO code, or label)
            occupations: List of occupation filters (QIDs or labels)
            gender: Gender filter; one of "male", "female", "other", or a QID
            lang: Language code for labels; falls back to English if unavailable
            limit: Maximum results to return (defaults to config.default_limit)
            cursor: Offset for pagination
            after_qid: QID for keyset pagination
            override_proxies: Optional list of proxy URLs

        Returns:
            Tuple of (List[PublicFigureNormalizedRecord], used_proxy)
        """
        return self._fetch_page(
            _PUBLIC_FIGURES,
            {
                "birthday_from": birthday_from,
                "birthday_to": birthday_to,
                "nationality": nationality,
                "occupations": occupations,
                "gender": gender,
            },
            lang=lang,
            limit=limit,
            cursor=cursor,
            after_qid=after_qid,
            override_proxies=override_proxies,
        )

    def get_public_organizations(
        self,
        types: List[str],
        country: Optional[str] = None,
        lang: str = "en",
        limit: Optional[int] = None,
        cursor: int = 0,
        after_qid: Optional[str] = None,
        override_proxies: Optional[List[str]] = None,
    ) -> Tuple[List[PublicOrganizationNormalizedRecord], str]:
        """Get one page of public organizations, filtered by type (required).

        `types` is required: an unfiltered organization scan always times out
        on WDQS (see `build_public_organizations_query`). Multiple values are
        combined with OR semantics in a single query — unlike
        `iterate_public_organizations`, a single page never decomposes into
        multiple query streams.

        Args:
            types: List of organization type filters (mapped keys, QIDs, or
                labels). Required: at least one value must be given.
            country: Country filter (QID, ISO code, or label)
            lang: Language code for labels
            limit: Maximum results to return (defaults to config.default_limit)
            cursor: Offset for pagination
            after_qid: QID for keyset pagination
            override_proxies: Optional list of proxy URLs

        Returns:
            Tuple of (List[PublicOrganizationNormalizedRecord], used_proxy)

        Raises:
            InvalidFilterError: If `types` is missing, empty, or malformed.
        """
        return self._fetch_page(
            _PUBLIC_ORGANIZATIONS,
            {"country": country, "types": types},
            lang=lang,
            limit=limit,
            cursor=cursor,
            after_qid=after_qid,
            override_proxies=override_proxies,
        )

    def iterate_public_figures(
        self,
        *,
        birthday_from: Optional[str] = None,
        birthday_to: Optional[str] = None,
        nationality: Optional[str] = None,
        occupations: Optional[List[str]] = None,
        gender: Optional[str] = None,
        max_results: Optional[int] = None,
        lang: str = "en",
    ) -> Iterator[PublicFigureNormalizedRecord]:
        """Yield aggregated public figures matching the given filters.

        Expects human-readable filter labels (e.g., "US", "Germany", "writer") or QIDs;
        query builders translate these into appropriate SPARQL constraints.
        Uses a stable internal ordering by entity ID.
        Hides SPARQL pagination; callers simply iterate over results.
        Respects `max_results` when provided; otherwise yields all matches subject to
        environment and upstream constraints.

        Args:
            birthday_from: Start date filter (ISO format, e.g., "1990-01-01")
            birthday_to: End date filter (ISO format, e.g., "2000-12-31")
            nationality: Nationality filter (country name like "Germany", ISO code, or QID)
            occupations: List of occupation filters (labels or QIDs)
            gender: Gender filter; one of "male", "female", "other", or a QID
            max_results: Maximum number of results to yield (None for unlimited)
            lang: Language code for labels (default: "en"); falls back to English if unavailable

        Yields:
            PublicFigureNormalizedRecord: Normalized public figure objects

        Raises:
            InvalidFilterError: If filter parameters are invalid or malformed
            QueryExecutionError: If upstream query execution fails
        """
        yield from self._iterate(
            _PUBLIC_FIGURES,
            {
                "birthday_from": birthday_from,
                "birthday_to": birthday_to,
                "nationality": nationality,
                "occupations": occupations,
                "gender": gender,
            },
            max_results=max_results,
            lang=lang,
        )

    def iterate_public_organizations(
        self,
        *,
        types: List[str],
        country: Optional[str] = None,
        max_results: Optional[int] = None,
        lang: str = "en",
    ) -> Iterator[PublicOrganizationNormalizedRecord]:
        """Yield aggregated public organizations matching the given filters.

        `types` is required: an unfiltered organization scan always times out
        on WDQS (see `build_public_organizations_query`). Iterating over
        multiple `types` values runs one keyset-paginated query stream per
        type — a combined multi-type query degrades badly upstream — rather
        than the single OR query `get_public_organizations` uses for one page.
        Entities matching more than one type are de-duplicated across streams,
        and `max_results` is a single budget spanning every stream, not a
        per-stream one.

        Expects human-readable filter labels (e.g., "US", "government_agency") or QIDs;
        query builders translate these into appropriate SPARQL constraints.
        Uses a stable internal ordering by entity ID within each stream.
        Hides SPARQL pagination; callers simply iterate over results.
        Respects `max_results` when provided; otherwise yields all matches subject to
        environment and upstream constraints.

        Args:
            types: List of organization type filters (labels or QIDs).
                Required: at least one value must be given.
            country: Country filter (single value: QID, ISO code, or label)
            max_results: Maximum number of results to yield (None for unlimited)
            lang: Language code for labels (default: "en")

        Yields:
            PublicOrganizationNormalizedRecord: Normalized public organization objects

        Raises:
            InvalidFilterError: If filter parameters are invalid or malformed
            QueryExecutionError: If upstream query execution fails
        """
        yield from self._iterate(
            _PUBLIC_ORGANIZATIONS,
            {"country": country, "types": types},
            max_results=max_results,
            lang=lang,
        )
