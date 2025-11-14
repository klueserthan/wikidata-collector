"""
Integration tests with mocked SPARQL endpoint.
"""
import pytest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from core.models import PublicFigure, PublicInstitution

pytestmark = pytest.mark.integration


@pytest.fixture
def mock_sparql_response():
    """Mock SPARQL response for testing."""
    return {
        "results": {
            "bindings": [
                {
                    "person": {"value": "http://www.wikidata.org/entity/Q42"},
                    "personLabel": {"value": "Douglas Adams"},
                    "description": {"value": "English writer and humorist"},
                    "birthDate": {"value": "1952-03-11T00:00:00Z"},
                    "genderLabel": {"value": "male"},
                    "countryLabel": {"value": "United Kingdom"},
                    "occupationLabel": {"value": "writer"}
                }
            ]
        }
    }


@pytest.fixture
def mock_institution_sparql_response():
    """Mock SPARQL response for institutions."""
    return {
        "results": {
            "bindings": [
                {
                    "institution": {"value": "http://www.wikidata.org/entity/Q123"},
                    "institutionLabel": {"value": "Test Organization"},
                    "description": {"value": "A test organization"},
                    "foundedDate": {"value": "2000-01-01T00:00:00Z"},
                    "type": {"value": "http://www.wikidata.org/entity/Q7278"},
                    "countryLabel": {"value": "United States"}
                }
            ]
        }
    }


@pytest.fixture
def mock_entity_expansion_response():
    """Mock entity expansion SPARQL response."""
    return {
        "results": {
            "bindings": [
                {
                    "entity": {"value": "http://www.wikidata.org/entity/Q42"},
                    "genderLabel": {"value": "male"},
                    "nationalityLabel": {"value": "United Kingdom"},
                    "professionLabel": {"value": "writer"},
                    "website": {"value": "https://www.douglasadams.com"}
                }
            ]
        }
    }


class TestSparqlExecution:
    """Test SPARQL query execution with mocking."""
    
    @patch("core.wiki_service.requests.get")
    def test_execute_sparql_query_success(self, mock_get, wiki_service, mock_sparql_response, mock_request):
        """Test successful SPARQL query execution."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_sparql_response
        mock_response.headers = {}
        mock_get.return_value = mock_response
        
        query = "SELECT ?person WHERE { ?person wdt:P31 wd:Q5 } LIMIT 10"
        result, proxy = wiki_service.execute_sparql_query(query, request=mock_request)
        
        assert result == mock_sparql_response
        assert proxy == "direct" or proxy.startswith("http")
        mock_get.assert_called_once()
    
    @patch("core.wiki_service.requests.get")
    def test_execute_sparql_query_caching(self, mock_get, wiki_service, mock_sparql_response, mock_request):
        """Test SPARQL query caching."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_sparql_response
        mock_response.headers = {}
        mock_get.return_value = mock_response
        
        query = "SELECT ?person WHERE { ?person wdt:P31 wd:Q5 } LIMIT 10"
        
        # First call - should hit API
        result1, proxy1 = wiki_service.execute_sparql_query(query, request=mock_request)
        assert mock_get.call_count == 1
        
        # Second call - should use cache
        result2, proxy2 = wiki_service.execute_sparql_query(query, request=mock_request)
        assert mock_get.call_count == 1  # No additional call
        assert proxy2 == "cached"
        assert result2 == mock_sparql_response
    
    @patch("core.wiki_service.requests.get")
    def test_execute_sparql_query_429_retry(self, mock_get, wiki_service, mock_sparql_response, mock_request):
        """Test 429 throttling with retry."""
        # First call returns 429
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"Retry-After": "2"}
        
        # Second call succeeds
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = mock_sparql_response
        mock_response_success.headers = {}
        
        mock_get.side_effect = [mock_response_429, mock_response_success]
        
        query = "SELECT ?person WHERE { ?person wdt:P31 wd:Q5 } LIMIT 10"
        result, proxy = wiki_service.execute_sparql_query(query, request=mock_request)
        
        assert result == mock_sparql_response
        assert mock_get.call_count == 2
    
    @patch("core.wiki_service.requests.get")
    def test_execute_sparql_query_502_retry(self, mock_get, wiki_service, mock_sparql_response, mock_request):
        """Test 502 error with retry."""
        # First call returns 502
        mock_response_502 = Mock()
        mock_response_502.status_code = 502
        
        # Second call succeeds
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = mock_sparql_response
        mock_response_success.headers = {}
        
        mock_get.side_effect = [mock_response_502, mock_response_success]
        
        query = "SELECT ?person WHERE { ?person wdt:P31 wd:Q5 } LIMIT 10"
        result, proxy = wiki_service.execute_sparql_query(query, request=mock_request)
        
        assert result == mock_sparql_response
        assert mock_get.call_count == 2


class TestPublicFiguresIntegration:
    """Integration tests for public figures endpoint flow."""
    
    @patch("core.wiki_service.requests.get")
    def test_get_public_figures_flow(self, mock_get, wiki_service, mock_sparql_response, 
                                     mock_entity_expansion_response, mock_request):
        """Test complete flow for getting public figures."""
        # Mock SPARQL query response
        mock_main_query = Mock()
        mock_main_query.status_code = 200
        mock_main_query.json.return_value = mock_sparql_response
        mock_main_query.headers = {}
        
        # Mock entity expansion query response
        mock_expansion_query = Mock()
        mock_expansion_query.status_code = 200
        mock_expansion_query.json.return_value = mock_entity_expansion_response
        mock_expansion_query.headers = {}
        
        mock_get.side_effect = [mock_main_query, mock_expansion_query]
        
        # Build query
        query = wiki_service.build_public_figures_query(
            birthday_from="1950-01-01",
            birthday_to="1960-12-31",
            nationality=["United Kingdom"]
        )
        
        # Execute main query
        result, proxy = wiki_service.execute_sparql_query(query, request=mock_request)
        
        assert len(result["results"]["bindings"]) == 1
        assert result["results"]["bindings"][0]["personLabel"]["value"] == "Douglas Adams"
        
        # Test entity expansion
        qid = "Q42"
        expanded = wiki_service.expand_entity_data(qid, lang="en", request=mock_request)
        
        assert isinstance(expanded, dict)
        assert "aliases" in expanded
    
    @patch("core.wiki_service.requests.get")
    def test_normalize_public_figure_integration(self, mock_get, wiki_service, 
                                                  mock_sparql_response, mock_entity_expansion_response, 
                                                  mock_request):
        """Test normalization with real query execution flow."""
        # Mock responses
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_entity_expansion_response
        mock_response.headers = {}
        mock_get.return_value = mock_response
        
        # Get item from SPARQL result
        item = mock_sparql_response["results"]["bindings"][0]
        
        # Expand entity data
        expanded = wiki_service.expand_entity_data("Q42", lang="en", request=mock_request)
        
        # Normalize
        result = wiki_service.normalize_public_figure(item, expanded)
        
        assert isinstance(result, PublicFigure)
        assert result.id == "Q42"
        assert result.name == "Douglas Adams"


class TestPublicInstitutionsIntegration:
    """Integration tests for public institutions endpoint flow."""
    
    @patch("core.wiki_service.requests.get")
    def test_get_public_institutions_flow(self, mock_get, wiki_service, mock_institution_sparql_response, 
                                        mock_request):
        """Test complete flow for getting public institutions."""
        # Mock SPARQL query response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_institution_sparql_response
        mock_response.headers = {}
        mock_get.return_value = mock_response
        
        # Build query
        query = wiki_service.build_public_institutions_query(
            country="United States",
            type=["government_agency"]
        )
        
        # Execute query
        result, proxy = wiki_service.execute_sparql_query(query, request=mock_request)
        
        assert len(result["results"]["bindings"]) == 1
        assert result["results"]["bindings"][0]["institutionLabel"]["value"] == "Test Organization"
    
    @patch("core.wiki_service.requests.get")
    def test_normalize_public_institution_integration(self, mock_get, wiki_service, 
                                                     mock_institution_sparql_response, mock_request):
        """Test institution normalization with real query execution."""
        # Mock entity expansion response
        mock_expansion_response = {
            "results": {
                "bindings": [
                    {
                        "entity": {"value": "http://www.wikidata.org/entity/Q123"},
                        "typeLabel": {"value": "Government Agency"},
                        "countryLabel": {"value": "United States"}
                    }
                ]
            }
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_expansion_response
        mock_response.headers = {}
        mock_get.return_value = mock_response
        
        # Get item from SPARQL result
        item = mock_institution_sparql_response["results"]["bindings"][0]
        
        # Expand entity data
        expanded = wiki_service.expand_entity_data_institution("Q123", lang="en", request=mock_request)
        
        # Normalize
        result = wiki_service.normalize_public_institution(item, expanded, request=mock_request)
        
        assert isinstance(result, PublicInstitution)
        assert result.id == "Q123"
        assert result.name == "Test Organization"


class TestErrorHandling:
    """Test error handling in integration scenarios."""
    
    @patch("core.wiki_service.requests.get")
    def test_max_retries_exceeded(self, mock_get, wiki_service, mock_request):
        """Test behavior when max retries are exceeded."""
        # Mock repeated failures
        mock_response = Mock()
        mock_response.status_code = 502
        mock_get.return_value = mock_response
        
        query = "SELECT ?person WHERE { ?person wdt:P31 wd:Q5 } LIMIT 10"
        
        with pytest.raises(HTTPException) as exc_info:
            wiki_service.execute_sparql_query(query, request=mock_request)
        
        assert exc_info.value.status_code == 500
        assert mock_get.call_count == 3  # Max retries
    
    @patch("core.wiki_service.requests.get")
    def test_network_error(self, mock_get, wiki_service, mock_request):
        """Test network error handling."""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        query = "SELECT ?person WHERE { ?person wdt:P31 wd:Q5 } LIMIT 10"
        
        with pytest.raises(HTTPException) as exc_info:
            wiki_service.execute_sparql_query(query, request=mock_request)
        
        assert exc_info.value.status_code == 500


