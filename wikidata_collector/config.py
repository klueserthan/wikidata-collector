"""Configuration for the Wikidata Collector module (no FastAPI dependencies)."""

import os
from typing import List, Optional

from dotenv import find_dotenv, load_dotenv

from random_user_agent.user_agent import UserAgent

# Load environment variables from .env
load_dotenv(find_dotenv())


# Retry behavior constants
RETRY_MAX_WAIT_SECONDS = int(
    os.getenv("RETRY_MAX_WAIT_SECONDS", "10")
)  # Maximum wait time for exponential backoff on 5xx errors
RETRY_JITTER_BASE = float(
    os.getenv("RETRY_JITTER_BASE", "0.5")
)  # Base jitter time in seconds for request exception retries
RETRY_JITTER_INCREMENT = float(
    os.getenv("RETRY_JITTER_INCREMENT", "0.2")
)  # Jitter increment per attempt

# Deep-sleep retry constants (single-proxy mode only)
PROXY_DEEP_SLEEP_SECONDS = int(
    os.getenv("PROXY_DEEP_SLEEP_SECONDS", "1800")
)  # Sleep duration between deep-sleep retry cycles (default: 30 minutes)
PROXY_DEEP_SLEEP_MAX_FAILURES = int(
    os.getenv("PROXY_DEEP_SLEEP_MAX_FAILURES", "3")
)  # Maximum consecutive deep-sleep cycles before giving up

# Query pagination constant
DEFAULT_LIMIT = int(
    os.getenv("DEFAULT_LIMIT", "15")
)  # Default limit for SPARQL queries and page size for iterators

# HTTP status codes requiring retry
RETRYABLE_STATUS_CODES = {429, 502, 503, 504}  # 429: throttled, 5xx: upstream unavailable


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
        default_limit: int = DEFAULT_LIMIT,
        retry_max_wait_seconds: int = RETRY_MAX_WAIT_SECONDS,
        retry_jitter_base: float = RETRY_JITTER_BASE,
        retry_jitter_increment: float = RETRY_JITTER_INCREMENT,
        proxy_deep_sleep_seconds: int = PROXY_DEEP_SLEEP_SECONDS,
        proxy_deep_sleep_max_failures: int = PROXY_DEEP_SLEEP_MAX_FAILURES,
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
            default_limit: Default limit for SPARQL queries and page size for iterators
            retry_max_wait_seconds: Maximum wait time for exponential backoff on 5xx errors
            retry_jitter_base: Base jitter time in seconds for request exception retries
            retry_jitter_increment: Jitter increment per attempt
            proxy_deep_sleep_seconds: Sleep duration (seconds) between deep-sleep retry cycles
                when a single proxy is unavailable (default: 1800 = 30 minutes)
            proxy_deep_sleep_max_failures: Maximum consecutive deep-sleep cycles before raising
                ProxyUnavailableError (default: 3)
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
        self.max_retries = int(os.getenv("MAX_RETRIES", max_retries))
        self.proxy_cooldown_seconds = int(
            os.getenv("PROXY_COOLDOWN_SECONDS", proxy_cooldown_seconds)
        )

        # Query pagination settings
        self.default_limit = int(os.getenv("DEFAULT_LIMIT", default_limit))

        # Retry behavior settings
        self.retry_max_wait_seconds = int(
            os.getenv("RETRY_MAX_WAIT_SECONDS", retry_max_wait_seconds)
        )
        self.retry_jitter_base = float(os.getenv("RETRY_JITTER_BASE", retry_jitter_base))
        self.retry_jitter_increment = float(
            os.getenv("RETRY_JITTER_INCREMENT", retry_jitter_increment)
        )

        # Deep-sleep retry settings (single-proxy mode)
        self.proxy_deep_sleep_seconds = int(
            os.getenv("PROXY_DEEP_SLEEP_SECONDS", proxy_deep_sleep_seconds)
        )
        self.proxy_deep_sleep_max_failures = int(
            os.getenv("PROXY_DEEP_SLEEP_MAX_FAILURES", proxy_deep_sleep_max_failures)
        )

    def get_user_agent(self) -> str:
        """Get User-Agent string for Wikidata requests.
        If self.contact_email is set, include it in the User-Agent for better transparency and to comply with Wikidata's guidelines.
        Otherwise, return a random User-Agent string from the random_user_agent library to avoid using a generic default."""
        if self.contact_email and self.contact_email != "not-provided":
            return (
                f"WikidataCollectorModule/1.0.0 "
                f"(https://github.com/klueserthan/wikidata-collector, contact: {self.contact_email})"
            )
        else:
            return UserAgent().get_random_user_agent()
