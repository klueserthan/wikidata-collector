"""
Unit tests for structured logging in wikidata_collector.
Tests verify that log events contain expected fields and values.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from wikidata_collector.client import WikidataClient
from wikidata_collector.config import WikidataCollectorConfig


class TestStructuredLogging:
    """Test structured logging output"""

    def test_iteration_started_log_fields(self, caplog):
        """Test that iteration_started event contains required fields"""
        caplog.set_level(logging.INFO, logger="wikidata_collector.client")

        config = WikidataCollectorConfig(proxy_list=[])
        client = WikidataClient(config)

        # Mock the iterator to stop immediately
        with patch.object(client, "iter_public_figures", return_value=iter([])):
            list(
                client.iterate_public_figures(
                    birthday_from="1990-01-01", birthday_to="2000-12-31", nationality=["US"]
                )
            )

        # Find iteration_started log record
        started_records = [
            r for r in caplog.records if hasattr(r, "event") and r.event == "iteration_started"
        ]
        assert len(started_records) > 0

        record = started_records[0]
        # Verify required fields
        assert hasattr(record, "event")
        assert record.event == "iteration_started"
        assert hasattr(record, "entity_kind")
        assert record.entity_kind == "public_figure"
        assert hasattr(record, "filters")
        assert "birthday_from" in record.filters
        assert "nationality" in record.filters

    def test_iteration_completed_log_fields(self, caplog):
        """Test that iteration_completed event contains required fields"""
        caplog.set_level(logging.INFO, logger="wikidata_collector.client")

        config = WikidataCollectorConfig(proxy_list=[])
        client = WikidataClient(config)

        # Mock the iterator to return no results
        with patch.object(client, "iter_public_figures", return_value=iter([])):
            list(client.iterate_public_figures())

        # Find iteration_completed log record
        completed_records = [
            r for r in caplog.records if hasattr(r, "event") and r.event == "iteration_completed"
        ]
        assert len(completed_records) > 0

        record = completed_records[0]
        # Verify required fields
        assert hasattr(record, "event")
        assert record.event == "iteration_completed"
        assert hasattr(record, "entity_kind")
        assert record.entity_kind == "public_figure"
        assert hasattr(record, "result_count")
        assert hasattr(record, "duration_ms")
        assert hasattr(record, "status")
        assert record.status == "success"

    def test_retry_scheduled_log_fields(self, caplog):
        """Test that retry_scheduled event contains required fields"""
        caplog.set_level(logging.WARNING, logger="wikidata_collector.client")

        config = WikidataCollectorConfig(proxy_list=[], max_retries=2)
        client = WikidataClient(config)

        # Mock requests to simulate 429 throttling
        with patch("wikidata_collector.client.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.headers = {"Retry-After": "1"}
            mock_get.return_value = mock_response

            try:
                client.execute_sparql_query("SELECT * WHERE { ?s ?p ?o } LIMIT 1")
            except Exception:
                pass  # Expected to fail

        # Find retry_scheduled log records
        retry_records = [
            r for r in caplog.records if hasattr(r, "event") and r.event == "retry_scheduled"
        ]
        assert len(retry_records) > 0

        record = retry_records[0]
        # Verify required fields
        assert hasattr(record, "event")
        assert record.event == "retry_scheduled"
        assert hasattr(record, "error_type")
        assert record.error_type in ["upstream_throttled", "upstream_unavailable"]
        assert hasattr(record, "status")
        assert record.status == "retry"
        assert hasattr(record, "attempt")
        assert hasattr(record, "max_retries")

    def test_query_failed_log_fields(self, caplog):
        """Test that query_failed event contains required fields"""
        caplog.set_level(logging.ERROR, logger="wikidata_collector.client")

        config = WikidataCollectorConfig(proxy_list=[], max_retries=1)
        client = WikidataClient(config)

        # Mock requests to simulate timeout
        with patch("wikidata_collector.client.requests.get") as mock_get:
            import requests

            mock_get.side_effect = requests.exceptions.Timeout("Connection timeout")

            try:
                client.execute_sparql_query("SELECT * WHERE { ?s ?p ?o } LIMIT 1")
            except Exception:
                pass  # Expected to fail

        # Find query_failed log records
        failed_records = [
            r for r in caplog.records if hasattr(r, "event") and r.event == "query_failed"
        ]
        assert len(failed_records) > 0

        record = failed_records[0]
        # Verify required fields
        assert hasattr(record, "event")
        assert record.event == "query_failed"
        assert hasattr(record, "error_type")
        assert record.error_type in ["upstream_timeout", "upstream_unavailable"]
        assert hasattr(record, "status")
        assert record.status in ["retry", "failure"]
        assert hasattr(record, "attempt")

    def test_query_completed_log_fields(self, caplog):
        """Test that query_completed event contains required fields"""
        caplog.set_level(logging.INFO, logger="wikidata_collector.client")

        config = WikidataCollectorConfig(proxy_list=[])
        client = WikidataClient(config)

        # Mock successful response
        with patch("wikidata_collector.client.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"results": {"bindings": []}}
            mock_get.return_value = mock_response

            client.execute_sparql_query("SELECT * WHERE { ?s ?p ?o } LIMIT 1")

        # Find query_completed log records
        completed_records = [
            r for r in caplog.records if hasattr(r, "event") and r.event == "query_completed"
        ]
        assert len(completed_records) > 0

        record = completed_records[0]
        # Verify required fields
        assert hasattr(record, "event")
        assert record.event == "query_completed"
        assert hasattr(record, "duration_ms")
        assert hasattr(record, "status")
        assert record.status == "success"
        assert hasattr(record, "proxy_used")

    def test_proxy_marked_failed_log_fields(self, caplog):
        """Test that proxy failure logging contains required fields"""
        caplog.set_level(logging.WARNING, logger="wikidata_collector.proxy")

        config = WikidataCollectorConfig(proxy_list=["http://proxy.example.com:8080"])
        client = WikidataClient(config)

        # Manually mark a proxy as failed to trigger logging
        client.proxy_manager.mark_proxy_failed("http://proxy.example.com:8080")

        # Find proxy failure log records
        proxy_records = [
            r for r in caplog.records if hasattr(r, "event") and r.event == "proxy_marked_failed"
        ]
        assert len(proxy_records) > 0

        record = proxy_records[0]
        # Verify required fields
        assert hasattr(record, "event")
        assert record.event == "proxy_marked_failed"
        assert hasattr(record, "proxy")
        assert hasattr(record, "cooldown_period")


class TestLoggingIntegration:
    """Test logging integration in client methods"""

    def test_iterate_public_figures_logs_filters(self, caplog):
        """Test that iterate_public_figures logs filter usage"""
        caplog.set_level(logging.INFO, logger="wikidata_collector.client")

        config = WikidataCollectorConfig(proxy_list=[])
        client = WikidataClient(config)

        filters = {"birthday_from": "1990-01-01", "nationality": ["US", "UK"]}

        with patch.object(client, "iter_public_figures", return_value=iter([])):
            list(client.iterate_public_figures(**filters))

        # Find iteration_started log record
        started_records = [
            r for r in caplog.records if hasattr(r, "event") and r.event == "iteration_started"
        ]
        assert len(started_records) > 0

        record = started_records[0]
        assert hasattr(record, "filters")
        assert record.filters["birthday_from"] == "1990-01-01"
        assert record.filters["nationality"] == ["US", "UK"]

    def test_iterate_public_institutions_logs_filters(self, caplog):
        """Test that iterate_public_institutions logs filter usage"""
        caplog.set_level(logging.INFO, logger="wikidata_collector.client")

        config = WikidataCollectorConfig(proxy_list=[])
        client = WikidataClient(config)

        filters = {"country": "US", "types": ["university"]}

        with patch.object(client, "iter_public_institutions", return_value=iter([])):
            list(client.iterate_public_institutions(**filters))

        # Find iteration_started log record
        started_records = [
            r for r in caplog.records if hasattr(r, "event") and r.event == "iteration_started"
        ]
        assert len(started_records) > 0

        record = started_records[0]
        assert hasattr(record, "filters")
        assert record.filters["country"] == "US"
        assert record.filters["types"] == ["university"]

