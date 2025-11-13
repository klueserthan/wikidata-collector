"""Domain-specific exceptions for the Wikidata Retriever module."""


class WikidataRetrieverError(Exception):
    """Base exception for all Wikidata Retriever errors."""
    pass


class InvalidQIDError(WikidataRetrieverError):
    """Raised when a QID is invalid or malformed."""
    pass


class EntityNotFoundError(WikidataRetrieverError):
    """Raised when a Wikidata entity cannot be found."""
    pass


class QueryExecutionError(WikidataRetrieverError):
    """Raised when a SPARQL query fails to execute."""
    pass


class ProxyError(WikidataRetrieverError):
    """Raised when proxy validation or usage fails."""
    pass
