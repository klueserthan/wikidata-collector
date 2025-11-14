"""
WikidataClient - Pure Python client for Wikidata SPARQL queries.

This client has no FastAPI dependencies and can be used standalone.
"""

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from .cache import TTLCache
from .config import WikidataCollectorConfig
from .constants import TYPE_MAPPINGS
from .exceptions import (
    EntityNotFoundError,
    InvalidQIDError,
    QueryExecutionError,
)
from .models import PublicFigure, PublicInstitution, SubInstitution
from .normalizers.figure_normalizer import normalize_public_figure
from .normalizers.institution_normalizer import normalize_public_institution
from .proxy import ProxyManager
from .query_builders.figures_query_builder import build_public_figures_query
from .query_builders.institutions_query_builder import build_public_institutions_query
from .security import validate_qid

logger = logging.getLogger(__name__)


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
        
        # Initialize caches
        self.sparql_cache = TTLCache(
            ttl_seconds=self.config.cache_ttl_seconds,
            max_size=self.config.cache_max_size
        )
        self.entity_expansion_cache = TTLCache(
            ttl_seconds=self.config.cache_ttl_seconds,
            max_size=self.config.cache_max_size
        )
        
        logger.info(f"Initialized WikidataClient with {len(self.config.proxy_list)} proxies")
    
    def _hash_query(self, query: str) -> str:
        """Generate MD5 hash of query for caching."""
        return hashlib.md5(query.encode('utf-8')).hexdigest()
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()
    
    def execute_sparql_query(
        self,
        query: str,
        override_proxies: Optional[List[str]] = None
    ) -> Tuple[Dict[str, Any], str]:
        """Execute SPARQL query against Wikidata with proxy support and caching.
        
        Args:
            query: SPARQL query string
            override_proxies: Optional list of proxy URLs to use instead of configured ones
            
        Returns:
            Tuple of (result_dict, used_proxy) where used_proxy is "cached", "direct", or proxy URL
            
        Raises:
            QueryExecutionError: If query execution fails after retries
        """
        query_hash = self._hash_query(query)
        
        # Check cache first
        cached_result = self.sparql_cache.get(query)
        if cached_result:
            logger.info(f"SPARQL query cache hit: {query_hash[:8]}")
            return cached_result, "cached"
        
        logger.info(f"SPARQL query cache miss: {query_hash[:8]}")
        
        # Cache miss - execute query
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
                
                # Store in cache
                self.sparql_cache.set(query, result)
                
                logger.info(
                    f"SPARQL query executed successfully: {query_hash[:8]} "
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
