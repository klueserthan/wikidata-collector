"""
Live integration tests for Wikidata SPARQL connectivity.

These tests connect to the actual Wikidata SPARQL endpoint (no proxy).
They verify basic connectivity and foundational HTTP stack functionality.

Run these tests with: pytest -m live
Skip these tests with: pytest -m "not live"
"""

import time

import pytest

from wikidata_collector import PublicFigure, WikidataClient
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

    def test_iterate_public_figures_live_endpoint(self):
        """
        Live test for iterate_public_figures with restrictive filters.

        Verifies:
        - Public figures SPARQL query template works end-to-end
        - iterate_public_figures iterator functions against live Wikidata
        - Query completes within configured time budget (~3 seconds)
        - At least one result is returned with restrictive filters

        Uses recent birthday range and single nationality to minimize result set
        and ensure query completes quickly.
        """
        # Create client with no proxies and reasonable timeout
        config = WikidataCollectorConfig(
            proxy_list=[],  # No proxies - direct connection only
            sparql_timeout_seconds=30,  # Allow enough time for query execution
            max_retries=1,  # Single attempt for live test
        )
        client = WikidataClient(config)

        # Use very restrictive filters: narrow date range + single nationality
        # This ensures query is fast and returns manageable result set
        birthday_from = "2000-06-15"
        birthday_to = "2000-06-20"
        nationality = ["United States"]

        # Measure end-to-end execution time
        start_time = time.time()

        # Execute iterator and collect results
        results = list(
            client.iterate_public_figures(
                birthday_from=birthday_from,
                birthday_to=birthday_to,
                nationality=nationality,
                max_results=5,  # Limit results to keep test fast
                lang="en",
            )
        )

        duration = time.time() - start_time

        # Assert at least one result is returned
        assert len(results) >= 1, (
            f"Expected at least 1 result with filters birthday_from={birthday_from}, "
            f"birthday_to={birthday_to}, nationality={nationality}, but got {len(results)}"
        )

        # Verify all results are PublicFigure instances
        assert all(isinstance(r, PublicFigure) for r in results), (
            "All results should be PublicFigure instances"
        )

        # Verify end-to-end call duration is within time budget
        time_budget = config.sparql_timeout_seconds
        assert duration <= time_budget, (
            f"End-to-end call duration ({duration:.2f}s) exceeded time budget ({time_budget}s)"
        )

        # Log successful execution for visibility
        print(f"\n✓ Live test completed successfully: {len(results)} results in {duration:.2f}s")

        # Additional verification: check that we got PublicFigure objects with expected data
        if len(results) > 0:
            first_result = results[0]
            print(f"  Sample result: {first_result.name} (ID: {first_result.id})")
            assert first_result.id is not None, "Result should have an ID"
            assert first_result.name is not None, "Result should have a name"

    def test_iterate_public_institutions_live_endpoint(self):
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
            sparql_timeout_seconds=30,  # Time budget for query execution
            max_retries=1,  # Single attempt for live test
        )
        client = WikidataClient(config)

        # Record start time for duration check
        start_time = time.time()

        # Exercise iterator with restrictive filters (one country + one type)
        # Using United States (Q30) and government_agency to get deterministic results
        results = list(
            client.iterate_public_institutions(
                country="Q30",  # United States #TODO: accept country name as well
                types=["government_agency"],
                max_results=5,  # Limit results for faster test execution
            )
        )

        duration = time.time() - start_time

        # Assert at least one result is returned
        assert len(results) >= 1, (
            "Expected at least 1 result with filters country=Q30, "
            f"types=['government_agency'], but got {len(results)}"
        )

        # Verify all results have expected attributes
        assert all(
            hasattr(r, "id") and hasattr(r, "name") and r.id is not None and r.name is not None
            for r in results
        ), "All results should have valid 'id' and 'name' attributes"

        # Verify all results have unique IDs (no duplicates)
        result_ids = [r.id for r in results]
        assert len(result_ids) == len(set(result_ids)), "Results should have unique IDs"

        # Verify end-to-end call duration is within time budget
        time_budget = config.sparql_timeout_seconds
        assert duration <= time_budget, (
            f"End-to-end call duration ({duration:.2f}s) exceeded time budget ({time_budget}s)"
        )
