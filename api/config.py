from typing import Dict, List, Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore[import]

# Ensure environment variables from .env are loaded even when config is imported before main
load_dotenv()


class AppConfig(BaseSettings):
    """Centralized application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Pagination
    DEFAULT_LIMIT: int = 100
    MAX_LIMIT: int = 500
    STREAMING_PAGE_SIZE: int = 50

    # Timeouts
    ENTITY_EXPANSION_TIMEOUT: int = 45  # seconds
    STREAMING_TIMEOUT: int = 45
    SPARQL_TIMEOUT_SECONDS: int = 60

    # Threading
    MAX_WORKERS: int = 3

    # HTTP / status codes
    DEFAULT_STATUS_CODE: int = 200
    INTERNAL_ERROR_CODE: int = 500
    BAD_REQUEST_CODE: int = 400

    # Wikidata
    CONTACT_EMAIL: str = "not-provided"
    WIKIDATA_SPARQL_URL: str = "https://query.wikidata.org/sparql"
    WIKIDATA_ENTITY_API_URL: str = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"

    # Proxy
    PROXY_LIST: Optional[str] = None

    # Cache
    CACHE_TTL_SECONDS: int = 300
    CACHE_MAX_SIZE: int = 10000

    # Default language
    DEFAULT_LANG: str = "en"

    # Server
    UVICORN_HOST: str = "0.0.0.0"
    UVICORN_PORT: int = 8000
    UVICORN_WORKERS: int = 2

    # Error messages
    ERROR_MESSAGES: Dict[str, str] | None = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.ERROR_MESSAGES is None:
            self.ERROR_MESSAGES = {
                "invalid_qid": "Invalid QID provided; expected 'Q' followed by digits",
                "internal_error": "We are facing an error",
                "entity_expand_error": "Failed to expand entity data",
            }

    @property
    def proxy_list_values(self) -> List[str]:
        """Return proxy list as a parsed collection."""
        if not self.PROXY_LIST:
            return []
        return [proxy.strip() for proxy in self.PROXY_LIST.split(",") if proxy.strip()]


# Global config instance
config = AppConfig()

