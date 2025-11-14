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
