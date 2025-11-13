"""
Integration tests with live SPARQL endpoint (optional, marked with pytest.mark.integration).

To run live integration tests:
    pytest tests/test_integration_live.py -m integration

These tests are skipped by default to avoid hitting the live endpoint unnecessarily.
"""
import pytest

from core.wiki_service import WikiService

pytestmark = pytest.mark.integration


pytestmark = pytest.mark.integration


class TestLiveSparqlEndpoint:
    """Integration tests with live Wikidata SPARQL endpoint."""
    
    @pytest.fixture
    def wiki_service(self):
        """Create a WikiService instance for live testing."""
        return WikiService()
    
    @pytest.mark.skipif(
        True,  # Skip by default - remove or set to False to enable
        reason="Live tests disabled. Set skipif to False or use --run-live-tests to enable."
    )
    def test_live_public_figures_query(self, wiki_service):
        """Test live query for public figures."""
        query = wiki_service.build_public_figures_query(
            birthday_from="1950-01-01",
            birthday_to="1960-12-31",
            limit=5
        )
        
        result, proxy = wiki_service.execute_sparql_query(query, limit=5)
        
        assert "results" in result
        assert "bindings" in result["results"]
        assert len(result["results"]["bindings"]) <= 6  # limit + 1
    
    @pytest.mark.skipif(
        True,  # Skip by default - remove or set to False to enable
        reason="Live tests disabled. Set skipif to False or use --run-live-tests to enable."
    )
    def test_live_entity_expansion(self, wiki_service):
        """Test live entity expansion for a known entity (Douglas Adams Q42)."""
        expanded = wiki_service.expand_entity_data("Q42", lang="en")
        
        assert isinstance(expanded, dict)
        assert "aliases" in expanded
        assert "nationalities" in expanded
        assert "professions" in expanded
    
    @pytest.mark.skipif(
        True,  # Skip by default - remove or set to False to enable
        reason="Live tests disabled. Set skipif to False or use --run-live-tests to enable."
    )
    def test_live_keyset_pagination(self, wiki_service):
        """Test live keyset pagination."""
        # First page
        query1 = wiki_service.build_public_figures_query(limit=5)
        result1, _ = wiki_service.execute_sparql_query(query1, limit=5)
        
        if len(result1["results"]["bindings"]) > 0:
            # Get first QID from results
            first_qid = result1["results"]["bindings"][0]["person"]["value"].split("/")[-1]
            
            # Second page using keyset
            query2 = wiki_service.build_public_figures_query(limit=5, after_qid=first_qid)
            result2, _ = wiki_service.execute_sparql_query(query2, limit=5)
            
            assert "results" in result2
            # Results should be different
            if len(result2["results"]["bindings"]) > 0:
                second_qid = result2["results"]["bindings"][0]["person"]["value"].split("/")[-1]
                assert second_qid != first_qid


# Note: To enable live tests, change skipif(True, ...) to skipif(False, ...)
# in the test methods above. Live tests are skipped by default to avoid
# unnecessary load on the Wikidata SPARQL endpoint.

