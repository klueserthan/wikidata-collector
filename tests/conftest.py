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
