"""Configuration for the Wikidata Collector module (no FastAPI dependencies)."""

import os
import threading
from typing import List, Optional

from dotenv import find_dotenv, load_dotenv
from random_user_agent.user_agent import UserAgent

# Load environment variables from .env
load_dotenv(find_dotenv())


# Query pagination constant
DEFAULT_LIMIT = int(
    os.getenv("DEFAULT_LIMIT", "15")
)  # Default limit for SPARQL queries and page size for iterators

# HTTP status codes requiring retry
RETRYABLE_STATUS_CODES = {429, 502, 503, 504}  # 429: throttled, 5xx: upstream unavailable

# Process-wide random User-Agent pool, built on first use.
# Constructing a UserAgent parses a large bundled dataset (1.5-5s of CPU), so it
# must never be rebuilt per request. None means "not built yet".
_user_agent_pool: Optional[UserAgent] = None
_user_agent_pool_lock = threading.Lock()


def _random_user_agent() -> str:
    """Return a random browser User-Agent from the shared pool.

    The pool is constructed lazily on first call and reused for the lifetime of
    the process, so import stays cheap and requests do not each pay to rebuild it.
    Construction is serialized: concurrent first calls would otherwise each build
    their own copy of the dataset, multiplying the cost the cache exists to avoid.

    Returns:
        A random User-Agent string.
    """
    global _user_agent_pool
    # Double-checked locking: the fast path never takes the lock, and only a
    # fully built pool is ever published to other threads.
    if _user_agent_pool is None:
        with _user_agent_pool_lock:
            if _user_agent_pool is None:
                _user_agent_pool = UserAgent()
    return _user_agent_pool.get_random_user_agent()


class WikidataCollectorConfig:
    """Module-only configuration for Wikidata retrieval."""

    def __init__(
        self,
        contact_email: Optional[str] = None,
        wikidata_sparql_url: Optional[str] = None,
        wikidata_entity_api_url: Optional[str] = None,
        proxy_list: Optional[List[str]] = None,
        sparql_timeout_seconds: Optional[int] = None,
        max_retries: Optional[int] = None,
        proxy_cooldown_seconds: Optional[int] = None,
        default_limit: Optional[int] = None,
        retry_max_wait_seconds: Optional[int] = None,
        retry_jitter_base: Optional[float] = None,
        retry_jitter_increment: Optional[float] = None,
        proxy_deep_sleep_seconds: Optional[int] = None,
        proxy_deep_sleep_max_failures: Optional[int] = None,
    ):
        """Initialize configuration.

        For every setting below, precedence is: explicit argument > environment
        variable > documented default. `None` (the default) means "not explicitly
        provided", so the environment variable is consulted; if that is unset too,
        the documented default applies.

        Args:
            contact_email: Contact email for User-Agent header
            wikidata_sparql_url: SPARQL endpoint URL
            wikidata_entity_api_url: Entity API URL template
            proxy_list: List of proxy URLs
            sparql_timeout_seconds: Timeout for SPARQL requests (default: 60)
            max_retries: Maximum retry attempts (default: 3)
            proxy_cooldown_seconds: Cooldown period for failed proxies (default: 300)
            default_limit: Default limit for SPARQL queries and page size for iterators
                (default: 15)
            retry_max_wait_seconds: Maximum wait time for exponential backoff on 5xx errors
                (default: 10)
            retry_jitter_base: Base jitter time in seconds for request exception retries
                (default: 0.5)
            retry_jitter_increment: Jitter increment per attempt (default: 0.2)
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

        self.sparql_timeout_seconds = (
            sparql_timeout_seconds
            if sparql_timeout_seconds is not None
            else int(os.getenv("SPARQL_TIMEOUT_SECONDS", "60"))
        )
        self.max_retries = (
            max_retries if max_retries is not None else int(os.getenv("MAX_RETRIES", "3"))
        )
        self.proxy_cooldown_seconds = (
            proxy_cooldown_seconds
            if proxy_cooldown_seconds is not None
            else int(os.getenv("PROXY_COOLDOWN_SECONDS", "300"))
        )

        # Query pagination settings
        self.default_limit = (
            default_limit if default_limit is not None else int(os.getenv("DEFAULT_LIMIT", "15"))
        )

        # Retry behavior settings
        self.retry_max_wait_seconds = (
            retry_max_wait_seconds
            if retry_max_wait_seconds is not None
            else int(os.getenv("RETRY_MAX_WAIT_SECONDS", "10"))
        )
        self.retry_jitter_base = (
            retry_jitter_base
            if retry_jitter_base is not None
            else float(os.getenv("RETRY_JITTER_BASE", "0.5"))
        )
        self.retry_jitter_increment = (
            retry_jitter_increment
            if retry_jitter_increment is not None
            else float(os.getenv("RETRY_JITTER_INCREMENT", "0.2"))
        )

        # Deep-sleep retry settings (single-proxy mode)
        self.proxy_deep_sleep_seconds = (
            proxy_deep_sleep_seconds
            if proxy_deep_sleep_seconds is not None
            else int(os.getenv("PROXY_DEEP_SLEEP_SECONDS", "1800"))
        )
        self.proxy_deep_sleep_max_failures = (
            proxy_deep_sleep_max_failures
            if proxy_deep_sleep_max_failures is not None
            else int(os.getenv("PROXY_DEEP_SLEEP_MAX_FAILURES", "3"))
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
            return _random_user_agent()
