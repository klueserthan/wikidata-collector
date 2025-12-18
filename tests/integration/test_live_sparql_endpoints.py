"""
Live integration tests for Wikidata SPARQL connectivity.

These tests connect to the actual Wikidata SPARQL endpoint (no proxy).
They verify basic connectivity and foundational HTTP stack functionality.

Run these tests with: pytest -m live
Skip these tests with: pytest -m "not live"
"""

import pytest

from wikidata_collector import WikidataClient
from wikidata_collector.config import WikidataCollectorConfig


@pytest.mark.live
@pytest.mark.integration
class TestLiveSparqlConnectivity:
    """Test direct connectivity to Wikidata SPARQL endpoint."""

    def test_basic_sparql_connectivity_smoke_test(self):
        """
        Minimal connectivity smoke test.

        Verifies:
        - Direct connection to Wikidata SPARQL endpoint (no proxy)
        - Response arrives within configured timeout
        - HTTP stack is functioning correctly
        - SPARQL endpoint can process basic queries
        """
        # Create client with no proxies to ensure direct connection
        config = WikidataCollectorConfig(
            proxy_list=[],  # No proxies - direct connection only
            sparql_timeout_seconds=60,  # Generous timeout for live endpoint
            max_retries=1,  # Single attempt for smoke test
        )
        client = WikidataClient(config)

        # Minimal SPARQL query - equivalent to "SELECT 1"
        # This query returns a single empty result set, verifying endpoint connectivity
        minimal_query = """
        SELECT ?dummy WHERE {
            BIND(1 AS ?dummy)
        }
        LIMIT 1
        """

        # Execute query and verify response
        result, used_proxy = client.execute_sparql_query(minimal_query)

        # Assert response structure is valid
        assert result is not None, "SPARQL endpoint returned no response"
        assert "results" in result, "Response missing 'results' key"
        assert "bindings" in result["results"], "Response missing 'bindings' key"

        # Verify direct connection (no proxy used)
        assert used_proxy == "direct", f"Expected direct connection, got proxy: {used_proxy}"

        # Verify query execution returned data
        bindings = result["results"]["bindings"]
        assert len(bindings) == 1, f"Expected 1 result, got {len(bindings)}"
        assert "dummy" in bindings[0], "Expected 'dummy' variable in result"
        assert bindings[0]["dummy"]["value"] == "1", "Expected dummy value to be '1'"
