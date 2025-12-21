"""Configuration for the Wikidata Collector module (no FastAPI dependencies)."""

import os
from typing import List, Optional


class WikidataCollectorConfig:
    """Module-only configuration for Wikidata retrieval."""

    def __init__(
        self,
        contact_email: Optional[str] = None,
        wikidata_sparql_url: Optional[str] = None,
        wikidata_entity_api_url: Optional[str] = None,
        proxy_list: Optional[List[str]] = None,
        sparql_timeout_seconds: int = 60,
        max_retries: int = 3,
        proxy_cooldown_seconds: int = 300,
        proxy_fallback_to_direct: bool = False,
    ):
        """Initialize configuration.

        Args:
            contact_email: Contact email for User-Agent header
            wikidata_sparql_url: SPARQL endpoint URL
            wikidata_entity_api_url: Entity API URL template
            proxy_list: List of proxy URLs
            sparql_timeout_seconds: Timeout for SPARQL requests
            max_retries: Maximum retry attempts
            proxy_cooldown_seconds: Cooldown period for failed proxies
            proxy_fallback_to_direct: Allow fallback to direct access when proxies fail (default: False)
        """
        self.contact_email = contact_email or os.getenv("CONTACT_EMAIL", "not-provided")
        self.wikidata_sparql_url = wikidata_sparql_url or os.getenv(
            "WIKIDATA_SPARQL_URL", "https://query.wikidata.org/sparql"
        )
        self.wikidata_entity_api_url = wikidata_entity_api_url or os.getenv(
            "WIKIDATA_ENTITY_API_URL", "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
        )

        # Parse proxy list from environment if not provided
        if proxy_list is None:
            proxy_env = os.getenv("PROXY_LIST", "")
            self.proxy_list = [p.strip() for p in proxy_env.split(",") if p.strip()]
        else:
            self.proxy_list = proxy_list

        self.sparql_timeout_seconds = int(
            os.getenv("SPARQL_TIMEOUT_SECONDS", sparql_timeout_seconds)
        )
        self.max_retries = max_retries
        self.proxy_cooldown_seconds = int(
            os.getenv("PROXY_COOLDOWN_SECONDS", proxy_cooldown_seconds)
        )
        # Fail-closed by default: do not fallback to direct access unless explicitly enabled
        self.proxy_fallback_to_direct = (
            os.getenv("PROXY_FALLBACK_TO_DIRECT", "false").lower() in ("true", "1", "yes")
            if proxy_fallback_to_direct is None
            else proxy_fallback_to_direct
        )

    def get_user_agent(self) -> str:
        """Get User-Agent string for Wikidata requests."""
        return (
            f"WikidataCollectorModule/1.0.0 "
            f"(https://github.com/klueserthan/wikidata-collector, contact: {self.contact_email})"
        )
