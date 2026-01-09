"""
Wikidata Collector - Standalone module for fetching Wikidata entities.

This module provides a pure Python interface for querying Wikidata via SPARQL,
with no FastAPI dependencies. It can be used standalone or as part of the API wrapper.
"""

from .client import WikidataClient
from .exceptions import (
    EntityNotFoundError,
    InvalidFilterError,
    InvalidQIDError,
    QueryExecutionError,
    WikidataCollectorError,
)
from .models import (
    PublicFigureNormalizedRecord,
    PublicInstitutionNormalizedRecord,
    SubInstitution,
)

__version__ = "1.0.0"
__all__ = [
    "WikidataClient",
    "PublicFigureNormalizedRecord",
    "PublicInstitutionNormalizedRecord",
    "SubInstitution",
    "WikidataCollectorError",
    "InvalidQIDError",
    "EntityNotFoundError",
    "QueryExecutionError",
    "InvalidFilterError",
]
