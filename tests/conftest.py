"""
Pytest configuration and shared fixtures.
"""

import pytest

from wikidata_collector import WikidataClient


@pytest.fixture
def wikidata_client():
    """Create a WikidataClient instance for testing."""
    return WikidataClient()


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
                    "occupationLabel": {"value": "writer"},
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
                "retrieved_at": "2024-01-15T10:00:00Z",
            }
        ],
        "accounts": [],
        "affiliations": [],
        "notable_works": ["The Hitchhiker's Guide to the Galaxy"],
        "awards": [],
        "identifiers": [],
    }
