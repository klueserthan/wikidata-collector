"""
Unit tests for structured logging in wikidata_collector/client.py

Tests validate structured logging payloads and log field consistency.
"""

import logging

import pytest

from wikidata_collector.client import (
    _log_page_fetch,
    _log_query_execution,
    _log_query_failure,
    _log_retry_attempt,
)


class LogCapture:
    """Helper class to capture log records with their extra fields"""

    def __init__(self):
        self.records = []

    def __call__(self, record):
        # Capture the LogRecord
        self.records.append(record)
        return True


@pytest.fixture
def log_capture(caplog):
    """Fixture to capture structured log records"""
    return caplog


class TestLogQueryExecution:
    """Test _log_query_execution structured logging"""

    def test_log_query_execution_includes_all_fields(self, log_capture):
        """Test that query execution logs include all required fields"""
        with log_capture.at_level(logging.INFO):
            _log_query_execution(
                query_type="public_figures",
                params={"birthday_from": "2000-01-01", "nationality": ["United States"]},
                page_num=1,
                raw_count=18,
                unique_qid_count=15,
                latency_ms=123.45,
                proxy_used="http://proxy.example.com:8080",
            )

        # Verify log was created
        assert len(log_capture.records) == 1
        record = log_capture.records[0]

        # Verify log level
        assert record.levelname == "INFO"

        # Verify message format
        assert "SPARQL query executed" in record.message
        assert "type=public_figures" in record.message
        assert "page=1" in record.message
        assert "raw_records=18" in record.message
        assert "unique_qids=15" in record.message
        assert "latency=123.45ms" in record.message
        assert "proxy=http://proxy.example.com:8080" in record.message

        # Verify structured extra fields
        assert record.query_type == "public_figures"
        assert record.page == 1
        assert record.raw_count == 18
        assert record.unique_qid_count == 15
        assert record.latency_ms == 123.45
        assert record.proxy_used == "http://proxy.example.com:8080"
        assert "birthday_from" in record.params
        assert record.params["nationality"] == ["United States"]

    def test_log_query_execution_with_direct_connection(self, log_capture):
        """Test logging when using direct connection (no proxy)"""
        with log_capture.at_level(logging.INFO):
            _log_query_execution(
                query_type="public_institutions",
                params={"country": "Q30"},
                page_num=2,
                raw_count=12,
                unique_qid_count=10,
                latency_ms=234.56,
                proxy_used="direct",
            )

        record = log_capture.records[0]
        assert record.proxy_used == "direct"
        assert "proxy=direct" in record.message


class TestLogPageFetch:
    """Test _log_page_fetch structured logging"""

    def test_log_page_fetch_includes_all_fields(self, log_capture):
        """Test that page fetch logs include all required fields"""
        with log_capture.at_level(logging.DEBUG):
            _log_page_fetch(
                query_type="public_figures",
                page_num=3,
                after_qid="Q12345",
                raw_count=18,
                unique_qid_count=15,
            )

        assert len(log_capture.records) == 1
        record = log_capture.records[0]

        # Verify log level
        assert record.levelname == "DEBUG"

        # Verify message format
        assert "Fetched page" in record.message
        assert "type=public_figures" in record.message
        assert "page=3" in record.message
        assert "after_qid=Q12345" in record.message
        assert "raw_records=18" in record.message
        assert "unique_qids=15" in record.message

        # Verify structured fields
        assert record.query_type == "public_figures"
        assert record.page == 3
        assert record.after_qid == "Q12345"
        assert record.raw_count == 18
        assert record.unique_qid_count == 15

    def test_log_page_fetch_with_no_after_qid(self, log_capture):
        """Test page fetch logging for first page (no after_qid)"""
        with log_capture.at_level(logging.DEBUG):
            _log_page_fetch(
                query_type="public_institutions",
                page_num=1,
                after_qid=None,
                raw_count=15,
                unique_qid_count=15,
            )

        record = log_capture.records[0]
        assert record.after_qid is None
        assert "after_qid=None" in record.message


class TestLogRetryAttempt:
    """Test _log_retry_attempt structured logging"""

    def test_log_retry_attempt_includes_all_fields(self, log_capture):
        """Test that retry attempt logs include all required fields"""
        with log_capture.at_level(logging.WARNING):
            _log_retry_attempt(
                attempt=2,
                max_retries=3,
                reason="throttled_429",
                wait_time=5.0,
                proxy="http://proxy.example.com:8080",
            )

        assert len(log_capture.records) == 1
        record = log_capture.records[0]

        # Verify log level
        assert record.levelname == "WARNING"

        # Verify message format
        assert "Retry attempt 2/3" in record.message
        assert "throttled_429" in record.message
        assert "waiting 5.00s" in record.message

        # Verify structured fields
        assert record.attempt == 2
        assert record.max_retries == 3
        assert record.reason == "throttled_429"
        assert record.wait_time_seconds == 5.0
        assert record.proxy == "http://proxy.example.com:8080"
        assert record.event == "retry"

    def test_log_retry_attempt_without_proxy(self, log_capture):
        """Test retry logging when no proxy is used"""
        with log_capture.at_level(logging.WARNING):
            _log_retry_attempt(
                attempt=1, max_retries=3, reason="timeout", wait_time=2.0, proxy=None
            )

        record = log_capture.records[0]
        assert record.proxy is None

    def test_log_retry_attempt_different_reasons(self, log_capture):
        """Test retry logging with different failure reasons"""
        reasons = [
            "throttled_429",
            "upstream_error_503",
            "request_exception_Timeout",
            "connection_error",
        ]

        with log_capture.at_level(logging.WARNING):
            for i, reason in enumerate(reasons):
                _log_retry_attempt(
                    attempt=i + 1, max_retries=5, reason=reason, wait_time=1.0, proxy=None
                )

        assert len(log_capture.records) == len(reasons)
        for i, record in enumerate(log_capture.records):
            assert record.reason == reasons[i]
            assert reasons[i] in record.message


class TestLogQueryFailure:
    """Test _log_query_failure structured logging"""

    def test_log_query_failure_includes_all_fields(self, log_capture):
        """Test that query failure logs include all required fields"""
        filters = {"birthday_from": "2000-01-01", "nationality": ["United States"]}

        with log_capture.at_level(logging.ERROR):
            _log_query_failure(
                query_type="public_figures",
                error_category="upstream_unavailable",
                error_message="Failed after 3 retries: Connection timeout",
                attempts=3,
                filters=filters,
            )

        assert len(log_capture.records) == 1
        record = log_capture.records[0]

        # Verify log level
        assert record.levelname == "ERROR"

        # Verify message format
        assert "Query failed" in record.message
        assert "type=public_figures" in record.message
        assert "category=upstream_unavailable" in record.message
        assert "attempts=3" in record.message

        # Verify structured fields
        assert record.query_type == "public_figures"
        assert record.error_category == "upstream_unavailable"
        assert record.error_message == "Failed after 3 retries: Connection timeout"
        assert record.attempts == 3
        assert record.filters == filters
        assert record.event == "query_failure"

    def test_log_query_failure_without_filters(self, log_capture):
        """Test failure logging when no filters are provided"""
        with log_capture.at_level(logging.ERROR):
            _log_query_failure(
                query_type="public_institutions",
                error_category="timeout",
                error_message="Request timeout",
                attempts=1,
                filters=None,
            )

        record = log_capture.records[0]
        assert record.filters == {}

    def test_log_query_failure_different_error_categories(self, log_capture):
        """Test failure logging with different error categories"""
        error_categories = [
            "upstream_unavailable",
            "timeout",
            "invalid_filter",
            "proxy_misconfiguration",
            "connection_error",
        ]

        with log_capture.at_level(logging.ERROR):
            for category in error_categories:
                _log_query_failure(
                    query_type="public_figures",
                    error_category=category,
                    error_message=f"Error: {category}",
                    attempts=1,
                    filters={},
                )

        assert len(log_capture.records) == len(error_categories)
        for i, record in enumerate(log_capture.records):
            assert record.error_category == error_categories[i]


class TestLoggingSchema:
    """Test consistency of logging schema across different log types"""

    def test_all_logs_have_consistent_event_field(self, log_capture):
        """Test that event field is consistently used where appropriate"""
        with log_capture.at_level(logging.DEBUG):
            _log_retry_attempt(1, 3, "test", 1.0, None)
            _log_query_failure("test", "error", "message", 1, {})

        # Verify event field is present in appropriate logs
        retry_record = log_capture.records[0]
        failure_record = log_capture.records[1]

        assert hasattr(retry_record, "event")
        assert retry_record.event == "retry"
        assert hasattr(failure_record, "event")
        assert failure_record.event == "query_failure"

    def test_numeric_fields_are_numbers(self, log_capture):
        """Test that numeric fields are stored as numbers, not strings"""
        with log_capture.at_level(logging.INFO):
            _log_query_execution(
                "test",
                {},
                page_num=1,
                raw_count=10,
                unique_qid_count=10,
                latency_ms=123.45,
                proxy_used="direct",
            )

        record = log_capture.records[0]
        assert isinstance(record.page, int)
        assert isinstance(record.raw_count, int)
        assert isinstance(record.unique_qid_count, int)
        assert isinstance(record.latency_ms, float)

    def test_filter_params_preserved_as_dict(self, log_capture):
        """Test that filter parameters are preserved as dictionaries"""
        filters = {"birthday_from": "2000-01-01", "nationality": ["US", "UK"], "limit": 100}

        with log_capture.at_level(logging.INFO):
            _log_query_execution("test", filters, 1, 10, 10, 123.45, "direct")

        record = log_capture.records[0]
        assert isinstance(record.params, dict)
        assert record.params == filters
