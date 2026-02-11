"""
Integration tests for resilience and logging.
Tests simulate upstream failures, proxy issues, and verify structured logging.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest
import requests

from wikidata_collector.client import WikidataClient
from wikidata_collector.config import WikidataCollectorConfig
from wikidata_collector.exceptions import (
    ProxyMisconfigurationError,
    UpstreamUnavailableError,
)


class LogCapture:
    """Helper class to capture log records during tests"""

    def __init__(self):
        self.records = []

    def __call__(self, record):
        self.records.append(record)
        return True


@pytest.fixture
def log_capture():
    """Fixture to capture log records"""
    capture = LogCapture()
    logger = logging.getLogger("wikidata_collector.client")
    logger.addFilter(capture)
    yield capture
    logger.removeFilter(capture)


class TestUpstreamTimeout:
    """Test behavior when upstream service times out"""

    def test_timeout_triggers_retry_and_logging(self, log_capture):
        """Test that timeouts trigger retries with appropriate logging"""
        config = WikidataCollectorConfig(proxy_list=[], max_retries=3)
        client = WikidataClient(config)

        # Mock requests to simulate timeout
        with patch("wikidata_collector.client.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout("Connection timeout")

            with pytest.raises(UpstreamUnavailableError) as exc_info:
                client.execute_sparql_query("SELECT * WHERE { ?s ?p ?o } LIMIT 1")

            assert "timeout" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()

        # Verify retry logging
        retry_records = [
            r for r in log_capture.records if hasattr(r, "event") and r.event == "query_failed"
        ]
        # Should have one log per attempt
        assert len(retry_records) == config.max_retries

        # Check that final attempt is marked as failure
        final_record = retry_records[-1]
        assert final_record.status == "failure"

    def test_throttling_triggers_backoff(self, log_capture):
        """Test that 429 throttling triggers exponential backoff"""
        config = WikidataCollectorConfig(proxy_list=[], max_retries=2)
        client = WikidataClient(config)

        # Mock requests to simulate 429 throttling
        with patch("wikidata_collector.client.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.headers = {"Retry-After": "1"}
            mock_get.return_value = mock_response

            with pytest.raises(UpstreamUnavailableError):
                client.execute_sparql_query("SELECT * WHERE { ?s ?p ?o } LIMIT 1")

        # Verify retry_scheduled logging
        retry_records = [
            r for r in log_capture.records if hasattr(r, "event") and r.event == "retry_scheduled"
        ]
        assert len(retry_records) > 0

        # Check that throttling is identified
        for record in retry_records:
            assert record.error_type == "upstream_throttled"
            assert record.status == "retry"

    def test_502_503_504_triggers_backoff(self, log_capture):
        """Test that 502/503/504 errors trigger backoff"""
        config = WikidataCollectorConfig(proxy_list=[], max_retries=2)
        client = WikidataClient(config)

        # Mock requests to simulate 503 service unavailable
        with patch("wikidata_collector.client.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 503
            mock_response.headers = {}
            mock_get.return_value = mock_response

            with pytest.raises(UpstreamUnavailableError):
                client.execute_sparql_query("SELECT * WHERE { ?s ?p ?o } LIMIT 1")

        # Verify retry_scheduled logging
        retry_records = [
            r for r in log_capture.records if hasattr(r, "event") and r.event == "retry_scheduled"
        ]
        assert len(retry_records) > 0

        # Check that upstream unavailability is identified
        for record in retry_records:
            assert record.error_type == "upstream_unavailable"


class TestProxyFailure:
    """Test behavior when proxy failures occur"""

    def test_proxy_failure_falls_back_when_enabled(self, caplog):
        """Test that proxy failure allows fallback to direct when enabled"""
        config = WikidataCollectorConfig(
            proxy_list=["http://proxy.example.com:8080"],
            proxy_fallback_to_direct=True,
            proxy_cooldown_seconds=300,  # Long cooldown to ensure no recovery during test
            max_retries=3,
        )
        client = WikidataClient(config)

        # Pre-mark the proxy as failed so it won't be used
        client.proxy_manager.mark_proxy_failed("http://proxy.example.com:8080")

        # Mock requests to succeed with direct connection
        with patch("wikidata_collector.client.requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {"results": {"bindings": []}}
            mock_get.return_value = response

            result, proxy = client.execute_sparql_query("SELECT * WHERE { ?s ?p ?o } LIMIT 1")
            assert result is not None
            # Should use direct connection since proxy is failed and fallback is enabled
            assert proxy == "direct"

    def test_proxy_failure_raises_when_fallback_disabled(self, caplog):
        """Test that proxy failure raises error when fallback is disabled"""
        config = WikidataCollectorConfig(
            proxy_list=["http://proxy.example.com:8080"],
            proxy_fallback_to_direct=False,
            max_retries=2,
        )
        client = WikidataClient(config)

        # Mock requests to always fail
        with patch("wikidata_collector.client.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError("Proxy connection failed")

            # Should raise ProxyMisconfigurationError or UpstreamUnavailableError
            with pytest.raises((UpstreamUnavailableError, ProxyMisconfigurationError)):
                client.execute_sparql_query("SELECT * WHERE { ?s ?p ?o } LIMIT 1")

        # Verify proxy was marked as failed
        assert "http://proxy.example.com:8080" in client.proxy_manager.failed_proxies

    def test_all_proxies_fail_closed(self):
        """Test that all proxy failures trigger fail-closed behavior"""
        config = WikidataCollectorConfig(
            proxy_list=["http://proxy1.example.com:8080", "http://proxy2.example.com:8080"],
            proxy_fallback_to_direct=False,
        )
        client = WikidataClient(config)

        # Mark all proxies as failed
        client.proxy_manager.mark_proxy_failed("http://proxy1.example.com:8080")
        client.proxy_manager.mark_proxy_failed("http://proxy2.example.com:8080")

        # Should raise ProxyMisconfigurationError when trying to get next proxy
        with pytest.raises(ProxyMisconfigurationError) as exc_info:
            client.proxy_manager.get_next_proxy()

        assert "fallback_to_direct" in str(exc_info.value).lower()


class TestResilienceForIterators:
    """Test resilience behavior for figure and institution iterators"""

    def test_figures_iterator_handles_transient_failures(self, log_capture):
        """Test that figures iterator can recover from transient failures"""
        config = WikidataCollectorConfig(proxy_list=[], max_retries=3)
        client = WikidataClient(config)

        # Mock requests: fail first 2 times, succeed on 3rd
        call_count = [0]

        def mock_get(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise requests.exceptions.ConnectionError("Transient failure")
            else:
                response = MagicMock()
                response.status_code = 200
                response.json.return_value = {"results": {"bindings": []}}
                return response

        with patch("wikidata_collector.client.requests.get", side_effect=mock_get):
            # Should succeed after retries
            results = list(client.iterate_public_figures(birthday_from="1990-01-01", max_results=1))
            assert isinstance(results, list)

        # Verify retry logging
        retry_records = [
            r for r in log_capture.records if hasattr(r, "event") and r.event == "query_failed"
        ]
        assert len(retry_records) >= 2  # At least 2 failures before success

    def test_institutions_iterator_handles_transient_failures(self, log_capture):
        """Test that institutions iterator can recover from transient failures"""
        config = WikidataCollectorConfig(proxy_list=[], max_retries=3)
        client = WikidataClient(config)

        # Mock requests: fail first time, succeed second time
        call_count = [0]

        def mock_get(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise requests.exceptions.ConnectionError("Transient failure")
            else:
                response = MagicMock()
                response.status_code = 200
                response.json.return_value = {"results": {"bindings": []}}
                return response

        with patch("wikidata_collector.client.requests.get", side_effect=mock_get):
            # Should succeed after retry
            results = list(client.iterate_public_institutions(country="US", max_results=1))
            assert isinstance(results, list)


class TestStructuredLoggingInFailureScenarios:
    """Test that structured logging works correctly in failure scenarios"""

    def test_logging_includes_error_types(self, log_capture):
        """Test that error_type is correctly categorized in logs"""
        config = WikidataCollectorConfig(proxy_list=[], max_retries=1)
        client = WikidataClient(config)

        # Test timeout error
        with patch("wikidata_collector.client.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout("timeout")
            try:
                client.execute_sparql_query("SELECT * WHERE { ?s ?p ?o } LIMIT 1")
            except Exception:
                # Expected to fail with UpstreamUnavailableError
                pass

        timeout_records = [
            r
            for r in log_capture.records
            if hasattr(r, "error_type") and r.error_type == "upstream_timeout"
        ]
        assert len(timeout_records) > 0

    def test_logging_includes_attempt_numbers(self, log_capture):
        """Test that retry attempts are numbered in logs"""
        config = WikidataCollectorConfig(proxy_list=[], max_retries=3)
        client = WikidataClient(config)

        with patch("wikidata_collector.client.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError("fail")
            try:
                client.execute_sparql_query("SELECT * WHERE { ?s ?p ?o } LIMIT 1")
            except Exception:
                # Expected to fail with UpstreamUnavailableError
                pass

        failed_records = [
            r for r in log_capture.records if hasattr(r, "event") and r.event == "query_failed"
        ]

        # Should have attempts 1, 2, 3
        attempts = [r.attempt for r in failed_records if hasattr(r, "attempt")]
        assert 1 in attempts
        assert 2 in attempts
        assert 3 in attempts

    def test_logging_distinguishes_retry_vs_failure_status(self, log_capture):
        """Test that logs distinguish between retry and final failure"""
        config = WikidataCollectorConfig(proxy_list=[], max_retries=2)
        client = WikidataClient(config)

        with patch("wikidata_collector.client.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError("fail")
            try:
                client.execute_sparql_query("SELECT * WHERE { ?s ?p ?o } LIMIT 1")
            except Exception:
                # Expected to fail with UpstreamUnavailableError
                pass

        failed_records = [
            r for r in log_capture.records if hasattr(r, "event") and r.event == "query_failed"
        ]

        # First attempts should be "retry", last should be "failure"
        assert failed_records[0].status == "retry"
        assert failed_records[-1].status == "failure"
