"""
WikidataClient - Pure Python client for Wikidata SPARQL queries.

This client has no FastAPI dependencies and can be used standalone.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional, Tuple

import requests

from .config import WikidataCollectorConfig
from .exceptions import (
    EntityNotFoundError,
    InvalidFilterError,
    InvalidQIDError,
    QueryExecutionError,
)
from .models import PublicFigure, PublicInstitution
from .normalizers.figure_normalizer import normalize_public_figure
from .normalizers.institution_normalizer import normalize_public_institution
from .proxy import ProxyManager
from .query_builders.figures_query_builder import build_public_figures_query
from .query_builders.institutions_query_builder import build_public_institutions_query
from .security import validate_qid

logger = logging.getLogger(__name__)

# Default page size for iterator-friendly pagination
DEFAULT_PAGE_SIZE = 15


def _log_query_execution(query_type: str, params: Dict[str, Any], page_num: int, result_count: int, latency_ms: float, proxy_used: str) -> None:
    """Log structured information about query execution.
    
    Args:
        query_type: Type of query (e.g., 'public_figures', 'public_institutions')
        params: Query parameters used
        page_num: Page number (1-indexed)
        result_count: Number of results returned
        latency_ms: Query latency in milliseconds
        proxy_used: Proxy used for the query
    """
    logger.info(
        f"SPARQL query executed: type={query_type}, page={page_num}, "
        f"results={result_count}, latency={latency_ms:.2f}ms, proxy={proxy_used}",
        extra={
            "query_type": query_type,
            "page": page_num,
            "result_count": result_count,
            "latency_ms": latency_ms,
            "proxy_used": proxy_used,
            "params": params
        }
    )


def _log_page_fetch(query_type: str, page_num: int, after_qid: Optional[str], result_count: int) -> None:
    """Log structured information about page fetching for iterators.
    
    Args:
        query_type: Type of query
        page_num: Page number being fetched
        after_qid: QID used for keyset pagination (if any)
        result_count: Number of results in this page
    """
    logger.debug(
        f"Fetched page: type={query_type}, page={page_num}, after_qid={after_qid}, results={result_count}",
        extra={
            "query_type": query_type,
            "page": page_num,
            "after_qid": after_qid,
            "result_count": result_count
        }
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
            cooldown_period=self.config.proxy_cooldown_seconds
        )
        
        logger.info(f"Initialized WikidataClient with {len(self.config.proxy_list)} proxies")
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()
    
    def execute_sparql_query(
        self,
        query: str,
        override_proxies: Optional[List[str]] = None
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
            "User-Agent": self.config.get_user_agent()
        }
        
        params = {'query': query}
        used_proxy = "direct"
        
        for attempt in range(self.config.max_retries):
            proxy = None
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
                    timeout=self.config.sparql_timeout_seconds
                )
                
                # Handle throttling gracefully
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    wait_s = int(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
                    logger.warning(f"WDQS 429 received. Waiting {wait_s}s before retry...")
                    time.sleep(wait_s)
                    raise requests.exceptions.RequestException("Throttled 429")
                
                if response.status_code in (502, 503, 504):
                    wait_s = min(10, 2 ** attempt)
                    logger.warning(f"WDQS {response.status_code} transient error. Backing off {wait_s}s...")
                    time.sleep(wait_s)
                    raise requests.exceptions.RequestException(f"Transient {response.status_code}")
                
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
                logger.error(f"SPARQL request failed (attempt {attempt + 1}/{self.config.max_retries}): {e}")
                
                if proxy:
                    self.proxy_manager.mark_proxy_failed(proxy)
                
                # If this was the last attempt, raise
                if attempt == self.config.max_retries - 1:
                    raise QueryExecutionError(f"Failed to execute SPARQL query after {self.config.max_retries} attempts: {e}")
                
                # Short jitter before retry
                time.sleep(0.5 + 0.2 * attempt)
        
        # Should never reach here
        raise QueryExecutionError("Failed to execute SPARQL query")
    
    def get_public_figures(
        self,
        birthday_from: Optional[str] = None,
        birthday_to: Optional[str] = None,
        nationality: Optional[List[str]] = None,
        profession: Optional[List[str]] = None,
        lang: str = "en",
        limit: int = 100,
        cursor: int = 0,
        after_qid: Optional[str] = None,
        override_proxies: Optional[List[str]] = None
    ) -> Tuple[List[Dict[str, Any]], str]:
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
            Tuple of (results_list, used_proxy)
        """
        query = build_public_figures_query(
            birthday_from=birthday_from,
            birthday_to=birthday_to,
            nationality=nationality,
            profession=profession,
            lang=lang,
            limit=limit,
            cursor=cursor,
            after_qid=after_qid
        )
        
        result, used_proxy = self.execute_sparql_query(query, override_proxies)
        bindings = result.get("results", {}).get("bindings", [])
        
        return bindings, used_proxy
    
    def get_public_institutions(
        self,
        country: Optional[str] = None,
        type: Optional[List[str]] = None,
        jurisdiction: Optional[str] = None,
        lang: str = "en",
        limit: int = 100,
        cursor: int = 0,
        after_qid: Optional[str] = None,
        override_proxies: Optional[List[str]] = None
    ) -> Tuple[List[Dict[str, Any]], str]:
        """Get public institutions with optional filters.
        
        Args:
            country: Country filter (QID, ISO code, or label)
            type: List of institution type filters (mapped keys, QIDs, or labels)
            jurisdiction: Jurisdiction filter (QID or label)
            lang: Language code for labels
            limit: Maximum results to return
            cursor: Offset for pagination
            after_qid: QID for keyset pagination
            override_proxies: Optional list of proxy URLs
            
        Returns:
            Tuple of (results_list, used_proxy)
        """
        query = build_public_institutions_query(
            country=country,
            type=type,
            jurisdiction=jurisdiction,
            lang=lang,
            limit=limit,
            cursor=cursor,
            after_qid=after_qid
        )
        
        result, used_proxy = self.execute_sparql_query(query, override_proxies)
        bindings = result.get("results", {}).get("bindings", [])
        
        return bindings, used_proxy
    
    def get_entity(
        self,
        qid: str,
        lang: str = "en",
        override_proxies: Optional[List[str]] = None
    ) -> Tuple[Dict[str, Any], str]:
        """Fetch raw entity data from Wikidata EntityData API.
        
        Args:
            qid: Wikidata entity QID (e.g., 'Q42')
            lang: Language code for labels
            override_proxies: Optional list of proxy URLs
            
        Returns:
            Tuple of (entity_dict, used_proxy)
            
        Raises:
            InvalidQIDError: If QID format is invalid
            EntityNotFoundError: If entity is not found
            QueryExecutionError: If entity cannot be fetched after retries
        """
        # Validate QID format
        try:
            qid = validate_qid(qid)
        except ValueError as e:
            raise InvalidQIDError(str(e))
        
        entity_url = self.config.wikidata_entity_api_url.format(qid=qid)
        used_proxy = "direct"
        
        for attempt in range(self.config.max_retries):
            proxy = None
            try:
                # Get proxy for this attempt
                proxy = self.proxy_manager.get_next_proxy(override_proxies)
                proxy_dict = self.proxy_manager.get_proxy_dict(proxy) if proxy else None
                
                headers = {
                    "Accept": "application/json",
                    "User-Agent": self.config.get_user_agent()
                }
                
                resp = requests.get(
                    entity_url,
                    params={"language": lang},
                    headers=headers,
                    proxies=proxy_dict,
                    timeout=self.config.sparql_timeout_seconds
                )
                resp.raise_for_status()
                used_proxy = proxy or "direct"
                data = resp.json()
                
                entities = data.get("entities", {})
                ent = entities.get(qid)
                if not ent:
                    raise EntityNotFoundError(f"Entity {qid} not found")
                
                return ent, used_proxy
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Entity lookup failed (attempt {attempt + 1}/{self.config.max_retries}): {e}")
                if proxy:
                    self.proxy_manager.mark_proxy_failed(proxy)
                if attempt == self.config.max_retries - 1:
                    raise QueryExecutionError(f"Failed to fetch entity {qid} from Wikidata")
                time.sleep(1)
        
        raise QueryExecutionError(f"Failed to fetch entity {qid} from Wikidata")
    
    def iter_public_figures(
        self,
        birthday_from: Optional[str] = None,
        birthday_to: Optional[str] = None,
        nationality: Optional[List[str]] = None,
        profession: Optional[List[str]] = None,
        lang: str = "en",
        page_size: int = DEFAULT_PAGE_SIZE,
        override_proxies: Optional[List[str]] = None
    ) -> Iterator[Dict[str, Any]]:
        """Iterate over public figures with automatic pagination.
        
        Uses keyset pagination with a fixed page size for efficient iteration.
        Yields individual results one at a time.
        
        Args:
            birthday_from: Birth date from (ISO format)
            birthday_to: Birth date to (ISO format)
            nationality: List of nationality filters (QIDs, ISO codes, or labels)
            profession: List of profession filters (QIDs or labels)
            lang: Language code for labels
            page_size: Results per page (default: 15)
            override_proxies: Optional list of proxy URLs
            
        Yields:
            Individual public figure results (SPARQL bindings)
        """
        after_qid = None
        page_num = 0
        
        while True:
            page_num += 1
            start_time = time.time()
            
            results, proxy = self.get_public_figures(
                birthday_from=birthday_from,
                birthday_to=birthday_to,
                nationality=nationality,
                profession=profession,
                lang=lang,
                limit=page_size,
                after_qid=after_qid,
                override_proxies=override_proxies
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Log page fetch
            _log_page_fetch("public_figures", page_num, after_qid, len(results))
            _log_query_execution(
                "public_figures",
                {"birthday_from": birthday_from, "birthday_to": birthday_to, 
                 "nationality": nationality, "profession": profession, "lang": lang},
                page_num,
                len(results),
                latency_ms,
                proxy
            )
            
            if not results:
                break
            
            for result in results:
                yield result
            
            # Set up next page using keyset pagination
            if len(results) < page_size:
                # Last page
                break
            
            # Get QID from last result for next page
            person_uri = results[-1].get("person", {}).get("value", "")
            if person_uri and "/" in person_uri:
                last_qid = person_uri.rsplit("/", 1)[-1]
                if last_qid:
                    after_qid = last_qid
                else:
                    break
            else:
                break
    
    def iter_public_institutions(
        self,
        country: Optional[str] = None,
        type: Optional[List[str]] = None,
        jurisdiction: Optional[str] = None,
        lang: str = "en",
        page_size: int = DEFAULT_PAGE_SIZE,
        override_proxies: Optional[List[str]] = None
    ) -> Iterator[Dict[str, Any]]:
        """Iterate over public institutions with automatic pagination.
        
        Uses keyset pagination with a fixed page size for efficient iteration.
        Yields individual results one at a time.
        
        Args:
            country: Country filter (QID, ISO code, or label)
            type: List of institution type filters (mapped keys, QIDs, or labels)
            jurisdiction: Jurisdiction filter (QID or label)
            lang: Language code for labels
            page_size: Results per page (default: 15)
            override_proxies: Optional list of proxy URLs
            
        Yields:
            Individual public institution results (SPARQL bindings)
        """
        after_qid = None
        page_num = 0
        
        while True:
            page_num += 1
            start_time = time.time()
            
            results, proxy = self.get_public_institutions(
                country=country,
                type=type,
                jurisdiction=jurisdiction,
                lang=lang,
                limit=page_size,
                after_qid=after_qid,
                override_proxies=override_proxies
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Log page fetch
            _log_page_fetch("public_institutions", page_num, after_qid, len(results))
            _log_query_execution(
                "public_institutions",
                {"country": country, "type": type, "jurisdiction": jurisdiction, "lang": lang},
                page_num,
                len(results),
                latency_ms,
                proxy
            )
            
            if not results:
                break
            
            for result in results:
                yield result
            
            # Set up next page using keyset pagination
            if len(results) < page_size:
                # Last page
                break
            
            # Get QID from last result for next page
            institution_uri = results[-1].get("institution", {}).get("value", "")
            if institution_uri and "/" in institution_uri:
                last_qid = institution_uri.rsplit("/", 1)[-1]
                if last_qid:
                    after_qid = last_qid
                else:
                    break
            else:
                break
    
    def iterate_public_figures(
        self,
        *,
        birthday_from: Optional[str] = None,
        birthday_to: Optional[str] = None,
        nationality: Optional[List[str]] = None,
        max_results: Optional[int] = None,
        lang: str = "en",
    ) -> Iterator[PublicFigure]:
        """Yield public figures matching the given filters.
        
        Applies filters on birthday and nationality as specified in the feature spec.
        Expects human-readable nationality labels or codes (e.g., "US", "DE") rather than QIDs;
        query builders translate these into appropriate SPARQL constraints.
        Uses a stable internal ordering by entity ID.
        Hides SPARQL pagination; callers simply iterate over results.
        Respects `max_results` when provided; otherwise yields all matches subject to
        environment and upstream constraints.
        
        Args:
            birthday_from: Start date filter (ISO format, e.g., "1990-01-01")
            birthday_to: End date filter (ISO format, e.g., "2000-12-31")
            nationality: List of nationality filters (ISO codes like "US", "DE", or labels)
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
            raise InvalidFilterError(f"Invalid birthday_from format: {birthday_from}. Expected ISO format (YYYY-MM-DD)")
        if birthday_to and not self._is_valid_date_format(birthday_to):
            raise InvalidFilterError(f"Invalid birthday_to format: {birthday_to}. Expected ISO format (YYYY-MM-DD)")
        
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
            }
        )
        
        start_time = time.time()
        
        try:
            for sparql_result in self.iter_public_figures(
                birthday_from=birthday_from,
                birthday_to=birthday_to,
                nationality=nationality,
                lang=lang,
            ):
                # Normalize the SPARQL result to PublicFigure model
                # Using None for expanded_data to rely on SPARQL bindings only
                figure = normalize_public_figure(sparql_result, expanded_data=None)
                
                yield figure
                count += 1
                
                # Check max_results limit
                if max_results is not None and count >= max_results:
                    logger.info(
                        f"Reached max_results limit of {max_results}",
                        extra={
                            "event": "max_results_reached",
                            "entity_kind": "public_figure",
                            "result_count": count,
                        }
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
                }
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
                }
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
                    }
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
    ) -> Iterator[PublicInstitution]:
        """Yield public institutions matching the given filters.
        
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
            }
        )
        
        start_time = time.time()
        
        try:
            for sparql_result in self.iter_public_institutions(
                country=country,
                type=types,
                jurisdiction=jurisdiction,
                lang=lang,
            ):
                # Normalize the SPARQL result to PublicInstitution model
                # Using None for expanded_data to rely on SPARQL bindings only
                institution = normalize_public_institution(sparql_result, expanded_data=None)
                
                yield institution
                count += 1
                
                # Check max_results limit
                if max_results is not None and count >= max_results:
                    logger.info(
                        f"Reached max_results limit of {max_results}",
                        extra={
                            "event": "max_results_reached",
                            "entity_kind": "public_institution",
                            "result_count": count,
                        }
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
                }
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
                }
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
                    }
                )
