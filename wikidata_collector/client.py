"""
WikidataClient - Pure Python client for Wikidata SPARQL queries.

This client has no FastAPI dependencies and can be used standalone.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterator, List, Optional, Protocol, Tuple, TypeVar

import requests

from .config import WikidataCollectorConfig
from .exceptions import (
    InvalidFilterError,
    ProxyMisconfigurationError,
    QueryExecutionError,
    UpstreamUnavailableError,
)
from .models import (
    PublicFigureNormalizedRecord,
    PublicFigureWikiRecord,
    PublicInstitutionNormalizedRecord,
    PublicInstitutionWikiRecord,
)
from .proxy import ProxyManager
from .query_builders.figures_query_builder import build_public_figures_query
from .query_builders.institutions_query_builder import build_public_institutions_query

logger = logging.getLogger(__name__)

# Default page size for iterator-friendly pagination
DEFAULT_LIMIT = 15


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
        query_type: Type of query (e.g., 'public_figures', 'public_institutions')
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

        Args:
            query: SPARQL query string
            override_proxies: Optional list of proxy URLs to use instead of configured ones

        Returns:
            Tuple of (result_dict, used_proxy) where used_proxy is "direct" or proxy URL

        Raises:
            QueryExecutionError: If query execution fails after retries
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

                if response.status_code in (502, 503, 504):
                    last_status_code = response.status_code
                    wait_s = min(10, 2**attempt)
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
                    wait_time = 0.5 + 0.2 * attempt
                    _log_retry_attempt(
                        attempt=attempt + 1,
                        max_retries=self.config.max_retries,
                        reason=f"request_exception_{error_type}",
                        wait_time=wait_time,
                        proxy=proxy,
                    )

                # If this was the last attempt, determine error type and raise
                if attempt == self.config.max_retries - 1:
                    # Check for upstream errors based on tracked status code (not string matching)
                    if last_status_code in (502, 503, 504):
                        _log_query_failure(
                            query_type="sparql_query",
                            error_category="upstream_unavailable",
                            error_message=str(e),
                            attempts=self.config.max_retries,
                        )
                        raise UpstreamUnavailableError(
                            f"Upstream Wikidata service unavailable after {self.config.max_retries} attempts: {e}"
                        )
                    # Check if we were using proxies and all failed (proxy misconfiguration)
                    elif (
                        self.config.proxy_list
                        and len(self.proxy_manager.get_available_proxies()) == 0
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
                    time.sleep(0.5 + 0.2 * attempt)
        # This point should be unreachable: every loop iteration should either
        # return a result or raise on the final attempt. If we get here, it
        # indicates a logic error in the retry loop implementation.
        logger.critical(
            "Unreachable code reached in execute_sparql_query: "
            "retry loop exited without returning or raising. "
            "max_retries=%d, used_proxy=%s",
            self.config.max_retries,
            used_proxy,
        )
        raise QueryExecutionError(
            "Internal error: retry loop exited without returning or raising; "
            "this indicates a bug in execute_sparql_query."
        )

    def get_public_figures(
        self,
        birthday_from: Optional[str] = None,
        birthday_to: Optional[str] = None,
        nationality: Optional[str] = None,
        profession: Optional[List[str]] = None,
        lang: str = "en",
        limit: int = DEFAULT_LIMIT,
        cursor: int = 0,
        after_qid: Optional[str] = None,
        override_proxies: Optional[List[str]] = None,
    ) -> Tuple[List[PublicFigureNormalizedRecord], str]:
        """Get public figures with optional filters.

        Args:
            birthday_from: Birth date from (ISO format)
            birthday_to: Birth date to (ISO format)
            nationality: List of nationality filters (QIDs, ISO codes, or labels)
            profession: List of profession filters (QIDs or labels)
            lang: Language code for labels
            limit: Maximum results to return
            cursor: Offset for pagination
            after_qid: QID for keyset pagination
            override_proxies: Optional list of proxy URLs

        Returns:
            Tuple of (List[PublicFigureNormalizedRecord], used_proxy)
        """
        query = build_public_figures_query(
            birthday_from=birthday_from,
            birthday_to=birthday_to,
            nationality=nationality,
            profession=profession,
            lang=lang,
            limit=limit,
            cursor=cursor,
            after_qid=after_qid,
        )

        result, used_proxy = self.execute_sparql_query(query, override_proxies)
        bindings = result.get("results", {}).get("bindings", [])

        # Aggregate SPARQL bindings by QID (one page of normalized records)
        results: List[PublicFigureNormalizedRecord] = []
        current: Optional[PublicFigureNormalizedRecord] = None

        for binding in bindings:
            try:
                wiki_record = PublicFigureWikiRecord.from_wikidata(binding)
            except (KeyError, ValueError) as e:
                logger.warning(f"Failed to parse record: {e}")
                continue

            if current is None:
                current = PublicFigureNormalizedRecord.from_wikidata_record(wiki_record)
                continue

            if wiki_record.qid == current.qid:
                current = PublicFigureNormalizedRecord.add_from_wikidata_record(
                    current, wiki_record
                )
                continue

            results.append(current)
            current = PublicFigureNormalizedRecord.from_wikidata_record(wiki_record)

        if current is not None:
            results.append(current)

        return results, used_proxy

    def get_public_institutions(
        self,
        country: Optional[str] = None,
        type: Optional[List[str]] = None,
        lang: str = "en",
        limit: int = DEFAULT_LIMIT,
        cursor: int = 0,
        after_qid: Optional[str] = None,
        override_proxies: Optional[List[str]] = None,
    ) -> Tuple[List[PublicInstitutionNormalizedRecord], str]:
        """Get public institutions with optional filters.

        Args:
            country: Country filter (QID, ISO code, or label)
            type: List of institution type filters (mapped keys, QIDs, or labels)
            lang: Language code for labels
            limit: Maximum results to return
            cursor: Offset for pagination
            after_qid: QID for keyset pagination
            override_proxies: Optional list of proxy URLs

        Returns:
            Tuple of (List[PublicInstitutionNormalizedRecord], used_proxy)
        """
        query = build_public_institutions_query(
            country=country,
            type=type,
            lang=lang,
            limit=limit,
            cursor=cursor,
            after_qid=after_qid,
        )

        result, used_proxy = self.execute_sparql_query(query, override_proxies)
        bindings = result.get("results", {}).get("bindings", [])

        # Aggregate SPARQL bindings by QID (one page of normalized records)
        results: List[PublicInstitutionNormalizedRecord] = []
        current: Optional[PublicInstitutionNormalizedRecord] = None

        for binding in bindings:
            try:
                wiki_record = PublicInstitutionWikiRecord.from_wikidata(binding)
            except (KeyError, ValueError) as e:
                logger.warning(f"Failed to parse record: {e}")
                continue

            if current is None:
                current = PublicInstitutionNormalizedRecord.from_wikidata_record(wiki_record)
                continue

            if wiki_record.qid == current.qid:
                current = PublicInstitutionNormalizedRecord.add_from_wikidata_record(
                    current, wiki_record
                )
                continue

            results.append(current)
            current = PublicInstitutionNormalizedRecord.from_wikidata_record(wiki_record)

        if current is not None:
            results.append(current)

        return results, used_proxy

    # def get_entity(
    #     self, qid: str, lang: str = "en", override_proxies: Optional[List[str]] = None
    # ) -> Tuple[Dict[str, Any], str]:
    #     """Fetch raw entity data from Wikidata EntityData API.

    #     Args:
    #         qid: Wikidata entity QID (e.g., 'Q42')
    #         lang: Language code for labels
    #         override_proxies: Optional list of proxy URLs

    #     Returns:
    #         Tuple of (entity_dict, used_proxy)

    #     Raises:
    #         InvalidQIDError: If QID format is invalid
    #         EntityNotFoundError: If entity is not found
    #         QueryExecutionError: If entity cannot be fetched after retries
    #     """
    #     # Validate QID format
    #     try:
    #         qid = validate_qid(qid)
    #     except ValueError as e:
    #         raise InvalidQIDError(str(e))

    #     entity_url = self.config.wikidata_entity_api_url.format(qid=qid)
    #     used_proxy = "direct"

    #     for attempt in range(self.config.max_retries):
    #         proxy = None
    #         try:
    #             # Get proxy for this attempt
    #             proxy = self.proxy_manager.get_next_proxy(override_proxies)
    #             proxy_dict = self.proxy_manager.get_proxy_dict(proxy) if proxy else None

    #             headers = {"Accept": "application/json", "User-Agent": self.config.get_user_agent()}

    #             resp = requests.get(
    #                 entity_url,
    #                 params={"language": lang},
    #                 headers=headers,
    #                 proxies=proxy_dict,
    #                 timeout=self.config.sparql_timeout_seconds,
    #             )
    #             resp.raise_for_status()
    #             used_proxy = proxy or "direct"
    #             data = resp.json()

    #             entities = data.get("entities", {})
    #             ent = entities.get(qid)
    #             if not ent:
    #                 raise EntityNotFoundError(f"Entity {qid} not found")

    #             return ent, used_proxy

    #         except requests.exceptions.RequestException as e:
    #             logger.error(
    #                 f"Entity lookup failed (attempt {attempt + 1}/{self.config.max_retries}): {e}"
    #             )
    #             if proxy:
    #                 self.proxy_manager.mark_proxy_failed(proxy)
    #             if attempt == self.config.max_retries - 1:
    #                 raise QueryExecutionError(f"Failed to fetch entity {qid} from Wikidata")
    #             time.sleep(1)

    #     raise QueryExecutionError(f"Failed to fetch entity {qid} from Wikidata")

    def _paginate_sparql_results(
        self,
        query_type: str,
        fetch_page_fn: Callable[[Optional[str]], Tuple[List[TRecord], str]],
        params: Dict[str, Any],
        limit: int,
    ) -> Iterator[TRecord]:
        """Generic helper for paginating normalized record pages with keyset pagination.

        Args:
            query_type: Type of query (e.g., 'public_figures', 'public_institutions')
            fetch_page_fn: Function to fetch a page of results, must accept after_qid parameter
            params: Query parameters for logging
            limit: Number of results per page

        Yields:
            Individual normalized records
        """
        after_qid = None
        page_num = 0

        while True:
            page_num += 1
            start_time = time.time()

            # Fetch page using provided function
            results, proxy = fetch_page_fn(after_qid)
            latency_ms = (time.time() - start_time) * 1000

            # Calculate metrics for logging and pagination control
            raw_count = len(results)
            unique_qids_in_page = {record.qid for record in results}
            unique_qid_count = len(unique_qids_in_page)

            # Log page fetch
            _log_page_fetch(query_type, page_num, after_qid, raw_count, unique_qid_count)
            _log_query_execution(
                query_type,
                params,
                page_num,
                raw_count,
                unique_qid_count,
                latency_ms,
                proxy,
            )

            if not results:
                break

            for result in results:
                yield result

            # Records can be expanded in the SPARQL query (e.g., multi-row per entity),
            # so we must determine end-of-results based on the number of unique QIDs.
            if unique_qid_count < limit:
                break

            # Keyset pagination: use the last record's QID.
            after_qid = results[-1].qid

    def iter_public_figures(
        self,
        birthday_from: Optional[str] = None,
        birthday_to: Optional[str] = None,
        nationality: Optional[str] = None,
        profession: Optional[List[str]] = None,
        lang: str = "en",
        limit: int = DEFAULT_LIMIT,
        override_proxies: Optional[List[str]] = None,
    ) -> Iterator[PublicFigureNormalizedRecord]:
        """Iterate over public figures with automatic pagination.

        Uses keyset pagination with a fixed page size for efficient iteration.
        Yields individual results one at a time.

        Args:
            birthday_from: Birth date from (ISO format)
            birthday_to: Birth date to (ISO format)
            nationality: List of nationality filters (QIDs, ISO codes, or labels)
            profession: List of profession filters (QIDs or labels)
            lang: Language code for labels
            limit: Results per page (default: 15)
            override_proxies: Optional list of proxy URLs

        Yields:
            Individual public figure normalized records
        """

        def fetch_page(after_qid: Optional[str]) -> Tuple[List[PublicFigureNormalizedRecord], str]:
            return self.get_public_figures(
                birthday_from=birthday_from,
                birthday_to=birthday_to,
                nationality=nationality,
                profession=profession,
                lang=lang,
                limit=limit,
                after_qid=after_qid,
                override_proxies=override_proxies,
            )

        yield from self._paginate_sparql_results(
            query_type="public_figures",
            fetch_page_fn=fetch_page,
            params={
                "birthday_from": birthday_from,
                "birthday_to": birthday_to,
                "nationality": nationality,
                "profession": profession,
                "lang": lang,
            },
            limit=limit,
        )

    def iter_public_institutions(
        self,
        country: Optional[str] = None,
        type: Optional[List[str]] = None,
        lang: str = "en",
        limit: int = DEFAULT_LIMIT,
        override_proxies: Optional[List[str]] = None,
    ) -> Iterator[PublicInstitutionNormalizedRecord]:
        """Iterate over public institutions with automatic pagination.

        Uses keyset pagination with a fixed page size for efficient iteration.
        Yields individual results one at a time.

        Args:
            country: Country filter (QID, ISO code, or label)
            type: List of institution type filters (mapped keys, QIDs, or labels)
            jurisdiction: Jurisdiction filter (QID or label)
            lang: Language code for labels
            limit: Results per page (default: 15)
            override_proxies: Optional list of proxy URLs

        Yields:
            Individual public institution results (SPARQL bindings)
        """

        def fetch_page(
            after_qid: Optional[str],
        ) -> Tuple[List[PublicInstitutionNormalizedRecord], str]:
            return self.get_public_institutions(
                country=country,
                type=type,
                lang=lang,
                limit=limit,
                after_qid=after_qid,
                override_proxies=override_proxies,
            )

        yield from self._paginate_sparql_results(
            query_type="public_institutions",
            fetch_page_fn=fetch_page,
            params={"country": country, "type": type, "lang": lang},
            limit=limit,
        )

    def iterate_public_figures(
        self,
        *,
        birthday_from: Optional[str] = None,
        birthday_to: Optional[str] = None,
        nationality: Optional[str] = None,
        max_results: Optional[int] = None,
        lang: str = "en",
    ) -> Iterator[PublicFigureNormalizedRecord]:
        """Yield aggregated public figures matching the given filters.

        Applies filters on birthday and nationality as specified in the feature spec.
        Expects human-readable nationality label (e.g., "US", "Germany") or QID;
        query builders translate these into appropriate SPARQL constraints.
        Uses a stable internal ordering by entity ID.
        Hides SPARQL pagination; callers simply iterate over results.
        Respects `max_results` when provided; otherwise yields all matches subject to
        environment and upstream constraints.

        Args:
            birthday_from: Start date filter (ISO format, e.g., "1990-01-01")
            birthday_to: End date filter (ISO format, e.g., "2000-12-31")
            nationality: Nationality filter (country name like "Germany" or QID)
            max_results: Maximum number of results to yield (None for unlimited)
            lang: Language code for labels (default: "en")

        Yields:
            PublicFigure: Normalized public figure objects

        Raises:
            InvalidFilterError: If filter parameters are invalid or malformed
            QueryExecutionError: If upstream query execution fails
        """
        # Validate date filters if provided
        if birthday_from and not self._is_valid_date_format(birthday_from):
            raise InvalidFilterError(
                f"Invalid birthday_from format: {birthday_from}. Expected ISO format (YYYY-MM-DD)"
            )
        if birthday_to and not self._is_valid_date_format(birthday_to):
            raise InvalidFilterError(
                f"Invalid birthday_to format: {birthday_to}. Expected ISO format (YYYY-MM-DD)"
            )

        # Validate max_results if provided
        self._validate_max_results(max_results)

        count = 0
        success = False

        # Log iteration start
        logger.info(
            f"Starting iterate_public_figures: birthday_from={birthday_from}, "
            f"birthday_to={birthday_to}, nationality={nationality}, max_results={max_results}",
            extra={
                "event": "iteration_started",
                "entity_kind": "public_figure",
                "filters": {
                    "birthday_from": birthday_from,
                    "birthday_to": birthday_to,
                    "nationality": nationality,
                },
                "max_results": max_results,
            },
        )

        start_time = time.time()

        try:
            for record in self.iter_public_figures(
                birthday_from=birthday_from,
                birthday_to=birthday_to,
                nationality=nationality,
                lang=lang,
            ):
                yield record
                count += 1

                if max_results is not None and count >= max_results:
                    logger.info(
                        f"Reached max_results limit of {max_results}",
                        extra={
                            "event": "max_results_reached",
                            "entity_kind": "public_figure",
                            "result_count": count,
                        },
                    )
                    break

            # Mark as successful if we completed iteration without exception
            success = True

        except ValueError as e:
            # Query builder or validation errors
            logger.error(
                f"Invalid filter parameters: {e}",
                extra={
                    "event": "iteration_failed",
                    "entity_kind": "public_figure",
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
                    "entity_kind": "public_figure",
                    "error_type": type(e).__name__,
                },
            )
            raise
        finally:
            # Log iteration completion only if successful
            if success:
                duration_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"Completed iterate_public_figures: yielded {count} results in {duration_ms:.2f}ms",
                    extra={
                        "event": "iteration_completed",
                        "entity_kind": "public_figure",
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

    def _is_valid_date_format(self, date_str: str) -> bool:
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
        except ValueError:
            return False

    def iterate_public_institutions(
        self,
        *,
        country: Optional[str] = None,
        types: Optional[List[str]] = None,
        jurisdiction: Optional[str] = None,
        max_results: Optional[int] = None,
        lang: str = "en",
    ) -> Iterator[PublicInstitutionNormalizedRecord]:
        """Yield aggregated public institutions matching the given filters.

        Note: This is a simplified implementation matching the underlying SPARQL support.
        The full API contract (founded_from, founded_to, country list, headquarter) will be
        implemented when the underlying query builder supports these filters.

        Args:
            country: Country filter (single value: QID, ISO code, or label)
            types: List of institution type filters (labels or codes)
            jurisdiction: Jurisdiction filter (QID or label)
            max_results: Maximum number of results to yield (None for unlimited)
            lang: Language code for labels (default: "en")

        Yields:
            PublicInstitution: Normalized public institution objects

        Raises:
            InvalidFilterError: If filter parameters are invalid or malformed
            QueryExecutionError: If upstream query execution fails
        """
        # Validate max_results if provided
        self._validate_max_results(max_results)

        count = 0
        success = False

        # Log iteration start
        logger.info(
            f"Starting iterate_public_institutions: country={country}, "
            f"types={types}, jurisdiction={jurisdiction}, max_results={max_results}",
            extra={
                "event": "iteration_started",
                "entity_kind": "public_institution",
                "filters": {
                    "country": country,
                    "types": types,
                    "jurisdiction": jurisdiction,
                },
                "max_results": max_results,
            },
        )

        start_time = time.time()

        try:
            for record in self.iter_public_institutions(
                country=country,
                type=types,
                lang=lang,
            ):
                yield record
                count += 1

                if max_results is not None and count >= max_results:
                    logger.info(
                        f"Reached max_results limit of {max_results}",
                        extra={
                            "event": "max_results_reached",
                            "entity_kind": "public_institution",
                            "result_count": count,
                        },
                    )
                    break

            # Mark as successful if we completed iteration without exception
            success = True

        except ValueError as e:
            # Query builder or validation errors
            logger.error(
                f"Invalid filter parameters: {e}",
                extra={
                    "event": "iteration_failed",
                    "entity_kind": "public_institution",
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
                    "entity_kind": "public_institution",
                    "error_type": type(e).__name__,
                },
            )
            raise
        finally:
            # Log iteration completion only if successful
            if success:
                duration_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"Completed iterate_public_institutions: yielded {count} results in {duration_ms:.2f}ms",
                    extra={
                        "event": "iteration_completed",
                        "entity_kind": "public_institution",
                        "result_count": count,
                        "duration_ms": duration_ms,
                        "status": "success",
                    },
                )
