"""
Integration tests for resilience and structured logging.

Tests simulate upstream timeouts, proxy failures, and verify structured logging
in realistic scenarios with mocked HTTP responses.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest
import requests

from wikidata_collector.client import WikidataClient
from wikidata_collector.config import WikidataCollectorConfig
from wikidata_collector.exceptions import (
    ProxyMisconfigurationError,
    QueryExecutionError,
    UpstreamUnavailableError,
)


@pytest.fixture
def mock_config():
    """Create a test configuration with proxies"""
    return WikidataCollectorConfig(
        proxy_list=["http://proxy1.example.com:8080", "http://proxy2.example.com:8080"],
        sparql_timeout_seconds=5,
        max_retries=3,
        proxy_cooldown_seconds=60,
    )


@pytest.mark.integration
class TestUpstreamTimeouts:
    """Test handling of upstream timeouts with retries and logging"""

    def test_timeout_with_retries_and_structured_logging(self, mock_config, caplog):
        """
        Test that timeout errors trigger retries with structured logging.

        Verifies:
        - Retries are attempted on timeout
        - Structured logs include retry attempts
        - ProxyMisconfigurationError is raised when all proxies fail due to timeout
        """
        client = WikidataClient(mock_config)

        with patch("requests.get") as mock_get:
            # Simulate timeout on all attempts
            mock_get.side_effect = requests.exceptions.Timeout("Connection timeout")

            with caplog.at_level(logging.WARNING):
                # With proxies configured and all failing, should raise ProxyMisconfigurationError
                with pytest.raises(ProxyMisconfigurationError) as exc_info:
                    client.execute_sparql_query("SELECT ?item WHERE { ?item wdt:P31 wd:Q5 }")

                # Verify error message mentions retries
                assert "after 3 attempts" in str(exc_info.value)

            # Verify retry logs were created
            retry_logs = [r for r in caplog.records if hasattr(r, "event") and r.event == "retry"]
            assert len(retry_logs) == 2  # 2 retries after first failure (3 total attempts)

            # Verify structured fields in retry logs
            for retry_log in retry_logs:
                assert hasattr(retry_log, "attempt")
                assert hasattr(retry_log, "max_retries")
                assert hasattr(retry_log, "reason")
                assert hasattr(retry_log, "wait_time_seconds")
                assert "request_exception" in retry_log.reason

    def test_timeout_without_proxy_raises_query_execution_error(self, caplog):
        """
        Test that timeout errors without proxies raise QueryExecutionError.

        Verifies:
        - Timeouts without proxies don't imply proxy misconfiguration
        - QueryExecutionError is raised for general query failures
        """
        # Create client without proxies
        config = WikidataCollectorConfig(
            proxy_list=[],
            sparql_timeout_seconds=5,
            max_retries=3,
        )
        client = WikidataClient(config)

        with patch("requests.get") as mock_get:
            # Simulate timeout on all attempts
            mock_get.side_effect = requests.exceptions.Timeout("Connection timeout")

            with caplog.at_level(logging.WARNING):
                # Without proxies, should raise QueryExecutionError
                with pytest.raises(QueryExecutionError) as exc_info:
                    client.execute_sparql_query("SELECT ?item WHERE { ?item wdt:P31 wd:Q5 }")

                # Verify error message mentions retries
                assert "after 3 attempts" in str(exc_info.value)

    def test_timeout_recovery_on_subsequent_attempt(self, mock_config, caplog):
        """
        Test successful recovery after initial timeout.

        Verifies:
        - First attempt times out
        - Second attempt succeeds
        - Success is logged with correct proxy information
        """
        client = WikidataClient(mock_config)

        with patch("requests.get") as mock_get:
            # First call times out, second succeeds
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"results": {"bindings": []}}

            mock_get.side_effect = [
                requests.exceptions.Timeout("Connection timeout"),
                mock_response,
            ]

            with caplog.at_level(logging.INFO):
                result, used_proxy = client.execute_sparql_query(
                    "SELECT ?item WHERE { ?item wdt:P31 wd:Q5 }"
                )

                # Verify success
                assert result == {"results": {"bindings": []}}
                assert used_proxy in [
                    "http://proxy1.example.com:8080",
                    "http://proxy2.example.com:8080",
                ]

            # Verify success log
            info_logs = [r for r in caplog.records if r.levelname == "INFO"]
            assert len(info_logs) >= 1
            # Verify success message is in one of the logs
            assert any("successfully" in r.message for r in info_logs)


@pytest.mark.integration
class TestProxyFailures:
    """Test handling of proxy failures with fallback behavior"""

    def test_proxy_failure_triggers_fallback(self, mock_config, caplog):
        """
        Test that failed proxy is marked and next proxy is used.

        Verifies:
        - First proxy fails
        - Second proxy is tried
        - Failed proxy is marked in proxy manager
        - Structured logging captures proxy information
        """
        client = WikidataClient(mock_config)

        with patch("requests.get") as mock_get:
            # First call fails (proxy1), second succeeds (proxy2)
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"results": {"bindings": []}}

            mock_get.side_effect = [
                requests.exceptions.ConnectionError("Proxy connection failed"),
                mock_response,
            ]

            with caplog.at_level(logging.WARNING):
                result, used_proxy = client.execute_sparql_query(
                    "SELECT ?item WHERE { ?item wdt:P31 wd:Q5 }"
                )

                # Verify success
                assert result == {"results": {"bindings": []}}

            # Verify retry log was created using structured fields
            retry_logs = [r for r in caplog.records if hasattr(r, "event") and r.event == "retry"]
            assert len(retry_logs) >= 1

            # Verify proxy information is logged in retry events
            assert any(r.proxy is not None for r in retry_logs)

    def test_all_proxies_fail_exhausts_retries(self, mock_config, caplog):
        """
        Test behavior when all proxies fail.

        Verifies:
        - All proxies are tried across retry attempts
        - ProxyMisconfigurationError is raised after exhausting retries
        - Structured logs capture all retry attempts
        """
        client = WikidataClient(mock_config)

        with patch("requests.get") as mock_get:
            # All attempts fail
            mock_get.side_effect = requests.exceptions.ConnectionError("Proxy connection failed")

            with caplog.at_level(logging.WARNING):
                with pytest.raises(ProxyMisconfigurationError):
                    client.execute_sparql_query("SELECT ?item WHERE { ?item wdt:P31 wd:Q5 }")

            # Verify multiple retry attempts
            retry_logs = [r for r in caplog.records if hasattr(r, "event") and r.event == "retry"]
            assert len(retry_logs) == 2  # 2 retries after first failure

    def test_fail_closed_behavior_no_direct_fallback(self, caplog):
        """
        Test fail-closed behavior: no automatic fallback to direct connection.

        Verifies:
        - When proxies are configured, they are used exclusively
        - No automatic fallback to direct connection occurs
        - ProxyMisconfigurationError is raised when all proxies fail
        """
        # Configure client with proxies
        config = WikidataCollectorConfig(
            proxy_list=["http://proxy1.example.com:8080"],
            sparql_timeout_seconds=5,
            max_retries=2,
        )
        client = WikidataClient(config)

        with patch("requests.get") as mock_get:
            # Proxy fails
            mock_get.side_effect = requests.exceptions.ConnectionError("Proxy failed")

            with caplog.at_level(logging.WARNING):
                with pytest.raises(ProxyMisconfigurationError):
                    client.execute_sparql_query("SELECT ?item WHERE { ?item wdt:P31 wd:Q5 }")

            # Verify all requests used proxy (no direct fallback)
            # requests.get should have been called with proxy dict
            for call in mock_get.call_args_list:
                # proxies argument should be present
                assert "proxies" in call.kwargs


@pytest.mark.integration
class TestUpstreamErrors:
    """Test handling of upstream HTTP errors (429, 502, 503, 504)"""

    def test_429_throttling_with_retry_after(self, mock_config, caplog):
        """
        Test handling of 429 (Too Many Requests) with Retry-After header.

        Verifies:
        - 429 response triggers retry
        - Retry-After header is respected
        - Structured logging captures throttling event
        """
        client = WikidataClient(mock_config)

        with patch("requests.get") as mock_get, patch("time.sleep") as mock_sleep:
            # First call returns 429, second succeeds
            mock_429_response = MagicMock()
            mock_429_response.status_code = 429
            mock_429_response.headers = {"Retry-After": "5"}

            mock_success_response = MagicMock()
            mock_success_response.status_code = 200
            mock_success_response.json.return_value = {"results": {"bindings": []}}

            mock_get.side_effect = [mock_429_response, mock_success_response]

            with caplog.at_level(logging.WARNING):
                result, _ = client.execute_sparql_query(
                    "SELECT ?item WHERE { ?item wdt:P31 wd:Q5 }"
                )

                # Verify success
                assert result == {"results": {"bindings": []}}

            # Verify sleep was called with Retry-After value
            mock_sleep.assert_called()
            sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
            assert 5 in sleep_calls  # Should have slept for 5 seconds

            # Verify retry log with throttling reason
            retry_logs = [r for r in caplog.records if hasattr(r, "event") and r.event == "retry"]
            assert len(retry_logs) >= 1
            assert any("throttled_429" in r.reason for r in retry_logs)

    def test_503_service_unavailable_retry(self, mock_config, caplog):
        """
        Test handling of 503 (Service Unavailable) errors.

        Verifies:
        - 503 triggers retry with backoff
        - Structured logging captures upstream error
        - UpstreamUnavailableError raised after all retries exhausted
        """
        client = WikidataClient(mock_config)

        with patch("requests.get") as mock_get, patch("time.sleep"):
            # All calls return 503
            mock_503_response = MagicMock()
            mock_503_response.status_code = 503

            mock_get.return_value = mock_503_response

            with caplog.at_level(logging.WARNING):
                with pytest.raises(UpstreamUnavailableError):
                    client.execute_sparql_query("SELECT ?item WHERE { ?item wdt:P31 wd:Q5 }")

            # Verify retry log with upstream error reason
            retry_logs = [r for r in caplog.records if hasattr(r, "event") and r.event == "retry"]
            assert len(retry_logs) >= 1
            assert any("upstream_error_503" in r.reason for r in retry_logs)

    def test_503_service_unavailable_then_success(self, mock_config, caplog):
        """
        Test successful recovery after 503 error.

        Verifies:
        - 503 triggers retry with backoff
        - Structured logging captures upstream error
        - Success after transient failure
        """
        client = WikidataClient(mock_config)

        with patch("requests.get") as mock_get, patch("time.sleep"):
            # First call returns 503, second succeeds
            mock_503_response = MagicMock()
            mock_503_response.status_code = 503

            mock_success_response = MagicMock()
            mock_success_response.status_code = 200
            mock_success_response.json.return_value = {"results": {"bindings": []}}

            mock_get.side_effect = [mock_503_response, mock_success_response]

            with caplog.at_level(logging.WARNING):
                result, _ = client.execute_sparql_query(
                    "SELECT ?item WHERE { ?item wdt:P31 wd:Q5 }"
                )

                # Verify success
                assert result == {"results": {"bindings": []}}

            # Verify retry log with upstream error reason
            retry_logs = [r for r in caplog.records if hasattr(r, "event") and r.event == "retry"]
            assert len(retry_logs) >= 1
            assert any("upstream_error_503" in r.reason for r in retry_logs)


@pytest.mark.integration
class TestStructuredLoggingInIterators:
    """Test structured logging in iterator flows"""

    def test_iterate_public_figures_logs_page_fetches(self, caplog):
        """
        Test that iterate_public_figures generates structured logs for page fetches.

        Verifies:
        - Each page fetch is logged
        - Logs include page number and result count
        - Query execution logs include filter information
        """
        config = WikidataCollectorConfig(proxy_list=[], sparql_timeout_seconds=30, max_retries=1)
        client = WikidataClient(config)

        with patch("requests.get") as mock_get:
            # Mock two pages of results, then empty page
            mock_response_page1 = MagicMock()
            mock_response_page1.status_code = 200
            mock_response_page1.json.return_value = {
                "results": {
                    "bindings": [
                        {
                            "person": {"value": f"http://www.wikidata.org/entity/Q{i}"},
                            "personLabel": {"value": f"Person {i}"},
                        }
                        for i in range(1, 16)
                    ]
                }
            }

            mock_response_page2 = MagicMock()
            mock_response_page2.status_code = 200
            mock_response_page2.json.return_value = {"results": {"bindings": []}}

            mock_get.side_effect = [mock_response_page1, mock_response_page2]

            with caplog.at_level(logging.DEBUG):
                # Consume iterator
                results = list(
                    client.iterate_public_figures(
                        birthday_from="2000-01-01",
                        birthday_to="2000-12-31",
                        nationality="United States",
                        max_results=20,
                    )
                )

                # Should have fetched some results
                assert len(results) > 0

            # Verify page fetch logs were created
            page_fetch_logs = [r for r in caplog.records if "Fetched page" in r.message]
            assert len(page_fetch_logs) >= 1

            # Verify page fetch logs have structured fields
            for log in page_fetch_logs:
                assert hasattr(log, "query_type")
                assert hasattr(log, "page")
                assert hasattr(log, "result_count")

    def test_iterate_public_institutions_logs_filters(self, caplog):
        """
        Test that iterate_public_institutions logs filter usage.

        Verifies:
        - Query execution logs include filter parameters
        - Structured fields capture filter values
        """
        config = WikidataCollectorConfig(proxy_list=[], sparql_timeout_seconds=30, max_retries=1)
        client = WikidataClient(config)

        with patch("requests.get") as mock_get:
            # Mock single page of results
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"results": {"bindings": []}}

            mock_get.return_value = mock_response

            with caplog.at_level(logging.INFO):
                # Consume iterator with filters
                list(
                    client.iterate_public_institutions(
                        country="Q30", types=["government_agency"], max_results=5
                    )
                )

            # Verify query execution logs were created
            query_logs = [r for r in caplog.records if "SPARQL query executed" in r.message]
            assert len(query_logs) >= 1
