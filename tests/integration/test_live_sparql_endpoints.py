"""
Live integration tests for Wikidata SPARQL connectivity.

These tests connect to the actual Wikidata SPARQL endpoint (no proxy).
They verify basic connectivity and foundational HTTP stack functionality.

Run these tests with: pytest -m live
Skip these tests with: pytest -m "not live"
"""

import time

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

    def test_institutions_iterator_end_to_end(self):
        """
        End-to-end test for institutions SPARQL query template and iterator.

        Verifies:
        - iterate_public_institutions iterator works against live Wikidata endpoint
        - Iterator functionality (lazy evaluation, can be consumed incrementally)
        - SPARQL query template for institutions generates valid queries
        - At least one result is returned with restrictive filters
        - Total call duration is within configured time budget
        """
        # Create client with no proxies for direct connection
        config = WikidataCollectorConfig(
            proxy_list=[],  # Direct connection only
            sparql_timeout_seconds=60,  # Time budget for query execution
            max_retries=1,  # Single attempt for live test
        )
        client = WikidataClient(config)

        # Record start time for duration check
        start_time = time.time()

        # Exercise iterator with restrictive filters (one country + one type)
        # Using United States (Q30) and government_agency to get deterministic results
        iterator = client.iterate_public_institutions(
            country="Q30",  # United States
            types=["government_agency"],
            max_results=5,  # Limit results for faster test execution
        )

        # Verify that we get an iterator, not a list (lazy evaluation)
        assert hasattr(iterator, "__iter__"), "Should return an iterator"
        assert hasattr(iterator, "__next__"), "Should return an iterator with __next__"

        # Consume iterator incrementally to test iterator functionality
        results = []
        for institution in iterator:
            # Verify each yielded item is a valid PublicInstitution instance
            assert hasattr(institution, "id"), "Institution missing 'id' attribute"
            assert hasattr(institution, "name"), "Institution missing 'name' attribute"
            assert institution.id is not None, "Institution id should not be None"
            assert institution.name is not None, "Institution name should not be None"
            results.append(institution)

        # Calculate total duration
        duration = time.time() - start_time

        # Assert at least one result was returned
        assert len(results) >= 1, "Expected at least one institution to be returned"

        # Verify all results have unique IDs (no duplicates)
        result_ids = [r.id for r in results]
        assert len(result_ids) == len(set(result_ids)), "Results should have unique IDs"

        # Verify end-to-end call duration is within time budget
        time_budget = config.sparql_timeout_seconds
        assert duration <= time_budget, (
            f"End-to-end call duration ({duration:.2f}s) exceeded "
            f"time budget ({time_budget}s)"
        )
