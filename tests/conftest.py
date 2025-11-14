"""
Pytest configuration and shared fixtures.
"""
import pytest
from unittest.mock import Mock, MagicMock

from fastapi import Request

from core.wiki_service import WikiService
from infrastructure.cache import entity_expansion_cache, sparql_cache

# Clear caches before each test
@pytest.fixture(autouse=True)
def clear_caches():
    """Clear all caches before each test."""
    from api.dependencies import get_wiki_service
    
    sparql_cache.clear()
    entity_expansion_cache.clear()
    get_wiki_service.cache_clear()  # Clear the dependency singleton cache
    yield
    sparql_cache.clear()
    entity_expansion_cache.clear()
    get_wiki_service.cache_clear()  # Clear after test as well


@pytest.fixture
def wiki_service():
    """Create a WikiService instance for testing."""
    return WikiService()


@pytest.fixture
def mock_request():
    """Create a mock FastAPI Request object."""
    request = Mock(spec=Request)
    request.headers = {}
    return request


@pytest.fixture
def sample_sparql_response():
    """Sample SPARQL JSON response."""
    return {
        "results": {
            "bindings": [
                {
                    "person": {"value": "http://www.wikidata.org/entity/Q42"},
                    "personLabel": {"value": "Douglas Adams"},
                    "description": {"value": "English writer and humorist"},
                    "birthDate": {"value": "1952-03-11T00:00:00Z"},
                    "countryLabel": {"value": "United Kingdom"},
                    "occupationLabel": {"value": "writer"}
                }
            ]
        }
    }


@pytest.fixture
def sample_expanded_data():
    """Sample expanded entity data."""
    return {
        "aliases": ["Douglas Noël Adams"],
        "nationalities": ["United Kingdom"],
        "gender": "male",
        "professions": ["writer", "humorist"],
        "place_of_birth": ["Cambridge"],
        "website": [
            {
                "url": "https://www.douglasadams.com",
                "source": "wikidata",
                "retrieved_at": "2024-01-15T10:00:00Z"
            }
        ],
        "accounts": [],
        "affiliations": [],
        "notable_works": ["The Hitchhiker's Guide to the Galaxy"],
        "awards": [],
        "identifiers": []
    }


