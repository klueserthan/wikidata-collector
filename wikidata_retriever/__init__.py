"""
Wikidata Retriever - Standalone module for fetching Wikidata entities.

This module provides a pure Python interface for querying Wikidata via SPARQL,
with no FastAPI dependencies. It can be used standalone or as part of the API wrapper.
"""

from .client import WikidataClient
from .models import PublicFigure, PublicInstitution, SubInstitution
from .exceptions import (
    WikidataRetrieverError,
    InvalidQIDError,
    EntityNotFoundError,
    QueryExecutionError,
)

__version__ = "1.0.0"
__all__ = [
    "WikidataClient",
    "PublicFigure",
    "PublicInstitution",
    "SubInstitution",
    "WikidataRetrieverError",
    "InvalidQIDError",
    "EntityNotFoundError",
    "QueryExecutionError",
]
