"""
Wikidata Collector - Standalone module for fetching Wikidata entities.

This module provides a pure Python interface for querying Wikidata via SPARQL,
with no FastAPI dependencies. It can be used standalone or as part of the API wrapper.
"""

from importlib.metadata import version

from .client import WikidataClient
from .exceptions import (
    EntityNotFoundError,
    InvalidFilterError,
    InvalidQIDError,
    ProxyMisconfigurationError,
    ProxyUnavailableError,
    QueryExecutionError,
    UpstreamUnavailableError,
    WikidataCollectorError,
)
from .models import (
    PublicFigureNormalizedRecord,
    PublicOrganizationNormalizedRecord,
    SubInstitution,
)

__version__ = version("wikidata-collector")
__all__ = [
    "WikidataClient",
    "PublicFigureNormalizedRecord",
    "PublicOrganizationNormalizedRecord",
    "SubInstitution",
    "WikidataCollectorError",
    "InvalidQIDError",
    "EntityNotFoundError",
    "QueryExecutionError",
    "InvalidFilterError",
    "ProxyMisconfigurationError",
    "ProxyUnavailableError",
    "UpstreamUnavailableError",
]
