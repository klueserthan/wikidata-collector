"""Domain-specific exceptions for the Wikidata Collector module."""


class WikidataCollectorError(Exception):
    """Base exception for all Wikidata Collector errors."""

    pass


class InvalidQIDError(WikidataCollectorError):
    """Raised when a QID is invalid or malformed."""

    pass


class EntityNotFoundError(WikidataCollectorError):
    """Raised when a Wikidata entity cannot be found."""

    pass


class QueryExecutionError(WikidataCollectorError):
    """Raised when a SPARQL query fails to execute."""

    pass


class ProxyError(WikidataCollectorError):
    """Raised when proxy validation or usage fails."""

    pass


class InvalidFilterError(WikidataCollectorError):
    """Raised when filter parameters are invalid or malformed."""

    pass


class ProxyMisconfigurationError(WikidataCollectorError):
    """Raised when proxy configuration is invalid or unreachable (multi-proxy setups)."""

    pass


class ProxyUnavailableError(WikidataCollectorError):
    """Raised when a single proxy remains unreachable after all deep-sleep retry cycles."""

    pass


class UpstreamUnavailableError(WikidataCollectorError):
    """Raised when the upstream Wikidata service is unavailable."""

    pass
