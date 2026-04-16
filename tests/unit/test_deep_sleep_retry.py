"""
Unit tests for the deep-sleep retry behaviour on single-proxy setups.

When the collector is configured with exactly one proxy (which may route to an
external rotation service), all normal retries exhausting does NOT raise
immediately.  Instead the client enters a deep-sleep retry loop: it logs a
WARNING, sleeps for ``proxy_deep_sleep_seconds``, resets the proxy's cooldown
status, and then re-tries the full normal retry sequence.  This repeats up to
``proxy_deep_sleep_max_failures`` times before finally raising
``ProxyUnavailableError``.

Multi-proxy setups are unaffected — they keep the existing fail-fast behaviour
and raise ``ProxyMisconfigurationError``.
"""

import logging
from unittest.mock import MagicMock, call, patch

import pytest
import requests

from wikidata_collector.client import WikidataClient
from wikidata_collector.config import WikidataCollectorConfig
from wikidata_collector.exceptions import (
    ProxyMisconfigurationError,
    ProxyUnavailableError,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _single_proxy_config(
    proxy_deep_sleep_seconds: int = 1,
    proxy_deep_sleep_max_failures: int = 3,
    max_retries: int = 2,
) -> WikidataCollectorConfig:
    """Return a config with exactly one proxy and short sleep/retry values."""
    return WikidataCollectorConfig(
        proxy_list=["http://rotation-service.example.com:8080"],
        sparql_timeout_seconds=5,
        max_retries=max_retries,
        proxy_deep_sleep_seconds=proxy_deep_sleep_seconds,
        proxy_deep_sleep_max_failures=proxy_deep_sleep_max_failures,
    )


def _multi_proxy_config(max_retries: int = 2) -> WikidataCollectorConfig:
    """Return a config with two proxies."""
    return WikidataCollectorConfig(
        proxy_list=[
            "http://proxy1.example.com:8080",
            "http://proxy2.example.com:8080",
        ],
        sparql_timeout_seconds=5,
        max_retries=max_retries,
    )


_QUERY = "SELECT ?item WHERE { ?item wdt:P31 wd:Q5 }"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDeepSleepConfig:
    """Verify that the new config params are read correctly."""

    def test_default_values(self):
        """Default deep-sleep values are 1800s and 3 cycles."""
        config = WikidataCollectorConfig(proxy_list=["http://proxy.example.com:8080"])
        assert config.proxy_deep_sleep_seconds == 1800
        assert config.proxy_deep_sleep_max_failures == 3

    def test_constructor_override(self):
        """Constructor arguments override the defaults."""
        config = WikidataCollectorConfig(
            proxy_list=["http://proxy.example.com:8080"],
            proxy_deep_sleep_seconds=600,
            proxy_deep_sleep_max_failures=5,
        )
        assert config.proxy_deep_sleep_seconds == 600
        assert config.proxy_deep_sleep_max_failures == 5

    def test_env_var_override(self, monkeypatch):
        """Environment variables override constructor defaults."""
        monkeypatch.setenv("PROXY_DEEP_SLEEP_SECONDS", "900")
        monkeypatch.setenv("PROXY_DEEP_SLEEP_MAX_FAILURES", "7")
        config = WikidataCollectorConfig(proxy_list=["http://proxy.example.com:8080"])
        assert config.proxy_deep_sleep_seconds == 900
        assert config.proxy_deep_sleep_max_failures == 7


class TestSingleProxyDeepSleepTriggered:
    """Deep-sleep path is entered for single-proxy setups."""

    def test_deep_sleep_is_entered_and_raises_proxy_unavailable(self, caplog):
        """
        All normal retries fail → deep-sleep cycles run → ProxyUnavailableError raised.

        Verifies:
        - ``time.sleep`` is called once per deep-sleep cycle (plus short jitter sleeps)
        - WARNING log with event=proxy_deep_sleep_started is emitted for each cycle
        - Final exception is ProxyUnavailableError (not ProxyMisconfigurationError)
        """
        config = _single_proxy_config(proxy_deep_sleep_max_failures=2, proxy_deep_sleep_seconds=10)
        client = WikidataClient(config)

        with patch("requests.get") as mock_get, patch("time.sleep") as mock_sleep:
            mock_get.side_effect = requests.exceptions.ConnectionError("proxy down")

            with caplog.at_level(logging.WARNING):
                with pytest.raises(ProxyUnavailableError) as exc_info:
                    client.execute_sparql_query(_QUERY)

            # ProxyUnavailableError should mention the number of cycles
            assert "2" in str(exc_info.value)

        # Deep-sleep sleep calls: 2 cycles × 10s each
        deep_sleep_calls = [c for c in mock_sleep.call_args_list if c == call(10)]
        assert len(deep_sleep_calls) == 2

        # Structured logs must include proxy_deep_sleep_started for each cycle
        deep_sleep_logs = [
            r for r in caplog.records if getattr(r, "event", None) == "proxy_deep_sleep_started"
        ]
        assert len(deep_sleep_logs) == 2

    def test_deep_sleep_warning_contains_required_fields(self, caplog):
        """
        Each deep-sleep WARNING log must contain structured fields:
        proxy, deep_sleep_attempt, deep_sleep_max, deep_sleep_seconds.
        """
        config = _single_proxy_config(proxy_deep_sleep_max_failures=1, proxy_deep_sleep_seconds=5)
        client = WikidataClient(config)

        with patch("requests.get") as mock_get, patch("time.sleep"):
            mock_get.side_effect = requests.exceptions.ConnectionError("proxy down")

            with caplog.at_level(logging.WARNING):
                with pytest.raises(ProxyUnavailableError):
                    client.execute_sparql_query(_QUERY)

        ds_logs = [
            r for r in caplog.records if getattr(r, "event", None) == "proxy_deep_sleep_started"
        ]
        assert len(ds_logs) == 1
        log = ds_logs[0]
        assert hasattr(log, "proxy")
        assert hasattr(log, "deep_sleep_attempt")
        assert hasattr(log, "deep_sleep_max")
        assert hasattr(log, "deep_sleep_seconds")
        assert log.deep_sleep_seconds == 5

    def test_deep_sleep_exhausted_log_emitted(self, caplog):
        """An ERROR log with event=proxy_deep_sleep_exhausted is emitted when all cycles fail."""
        config = _single_proxy_config(proxy_deep_sleep_max_failures=1)
        client = WikidataClient(config)

        with patch("requests.get") as mock_get, patch("time.sleep"):
            mock_get.side_effect = requests.exceptions.ConnectionError("proxy down")

            with caplog.at_level(logging.ERROR):
                with pytest.raises(ProxyUnavailableError):
                    client.execute_sparql_query(_QUERY)

        exhausted_logs = [
            r for r in caplog.records if getattr(r, "event", None) == "proxy_deep_sleep_exhausted"
        ]
        assert len(exhausted_logs) == 1


class TestSingleProxyDeepSleepRecovery:
    """The client recovers successfully when the proxy becomes available after a deep sleep."""

    def test_recovers_on_second_deep_sleep_cycle(self):
        """
        Proxy is down for the first deep-sleep cycle but recovers on the second.
        The client should return the result rather than raising.
        """
        config = _single_proxy_config(proxy_deep_sleep_max_failures=3, proxy_deep_sleep_seconds=1)
        client = WikidataClient(config)

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {"results": {"bindings": []}}

        # Normal retries (cycle 0): all fail (max_retries=2 → 2 ConnectionErrors)
        # Deep sleep cycle 1 retries: all fail again (2 more ConnectionErrors)
        # Deep sleep cycle 2 retries: first attempt succeeds
        side_effects: list = (
            [requests.exceptions.ConnectionError("down")] * 2  # initial retries
            + [requests.exceptions.ConnectionError("down")] * 2  # cycle 1 retries
            + [success_response]  # cycle 2: success
        )

        with patch("requests.get") as mock_get, patch("time.sleep"):
            mock_get.side_effect = side_effects

            result, used_proxy = client.execute_sparql_query(_QUERY)

        assert result == {"results": {"bindings": []}}
        assert used_proxy == "http://rotation-service.example.com:8080"

    def test_recovers_immediately_after_first_deep_sleep(self):
        """Proxy recovers after the first deep-sleep cycle."""
        config = _single_proxy_config(proxy_deep_sleep_max_failures=3, proxy_deep_sleep_seconds=1)
        client = WikidataClient(config)

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {"results": {"bindings": []}}

        side_effects: list = (
            [requests.exceptions.ConnectionError("down")] * 2  # initial retries
            + [success_response]  # cycle 1: success
        )

        with patch("requests.get") as mock_get, patch("time.sleep"):
            mock_get.side_effect = side_effects

            result, _ = client.execute_sparql_query(_QUERY)

        assert result == {"results": {"bindings": []}}


class TestDeepSleepResetsProxyCooldown:
    """After each deep sleep the proxy's cooldown is cleared."""

    def test_proxy_available_after_reset(self):
        """
        After sleeping, reset_proxy() must clear the proxy from failed_proxies
        so the ProxyManager considers it available for the next attempt.
        """
        config = _single_proxy_config(proxy_deep_sleep_max_failures=1)
        client = WikidataClient(config)
        proxy_url = config.proxy_list[0]

        # Manually mark the proxy as failed
        client.proxy_manager.mark_proxy_failed(proxy_url)
        assert proxy_url in client.proxy_manager.failed_proxies

        # Reset should clear it
        client.proxy_manager.reset_proxy(proxy_url)
        assert proxy_url not in client.proxy_manager.failed_proxies
        assert client.proxy_manager.get_available_proxies() == [proxy_url]

    def test_reset_proxy_is_called_before_each_retry(self, caplog):
        """
        ``reset_proxy`` is invoked once per deep-sleep cycle so the proxy
        is not stuck in cooldown when the retry loop runs.
        """
        config = _single_proxy_config(proxy_deep_sleep_max_failures=2, proxy_deep_sleep_seconds=1)
        client = WikidataClient(config)

        with (
            patch("requests.get") as mock_get,
            patch("time.sleep"),
            patch.object(
                client.proxy_manager, "reset_proxy", wraps=client.proxy_manager.reset_proxy
            ) as mock_reset,
        ):
            mock_get.side_effect = requests.exceptions.ConnectionError("down")

            with pytest.raises(ProxyUnavailableError):
                client.execute_sparql_query(_QUERY)

        # reset_proxy should have been called once per cycle
        assert mock_reset.call_count == 2
        proxy_url = config.proxy_list[0]
        mock_reset.assert_any_call(proxy_url)


class TestMultiProxyUnaffected:
    """Multi-proxy setups retain the original fail-fast behaviour."""

    def test_multi_proxy_raises_proxy_misconfiguration_error(self):
        """
        With 2+ proxies and all failing, ProxyMisconfigurationError is raised —
        deep-sleep is NOT triggered.
        """
        config = _multi_proxy_config()
        client = WikidataClient(config)

        with patch("requests.get") as mock_get, patch("time.sleep") as mock_sleep:
            mock_get.side_effect = requests.exceptions.ConnectionError("down")

            with pytest.raises(ProxyMisconfigurationError):
                client.execute_sparql_query(_QUERY)

        # No deep-sleep (30-min) calls should have been made
        long_sleeps = [c for c in mock_sleep.call_args_list if c.args[0] >= 60]
        assert len(long_sleeps) == 0

    def test_multi_proxy_does_not_raise_proxy_unavailable_error(self):
        """ProxyUnavailableError must never be raised for multi-proxy setups."""
        config = _multi_proxy_config()
        client = WikidataClient(config)

        with patch("requests.get") as mock_get, patch("time.sleep"):
            mock_get.side_effect = requests.exceptions.ConnectionError("down")

            with pytest.raises(ProxyMisconfigurationError):
                client.execute_sparql_query(_QUERY)

    def test_no_proxy_raises_query_execution_error(self):
        """Without any proxy, no deep-sleep and no ProxyMisconfigurationError."""
        config = WikidataCollectorConfig(proxy_list=[], sparql_timeout_seconds=5, max_retries=2)
        client = WikidataClient(config)

        with patch("requests.get") as mock_get, patch("time.sleep"):
            mock_get.side_effect = requests.exceptions.ConnectionError("down")

            from wikidata_collector.exceptions import QueryExecutionError

            with pytest.raises(QueryExecutionError):
                client.execute_sparql_query(_QUERY)


class TestDeepSleepEdgeCases:
    """Edge-case regression tests for deep-sleep eligibility logic."""

    def test_invalid_proxy_raises_at_construction_time(self):
        """
        An invalid proxy (bad scheme, internal host, etc.) must raise
        ProxyMisconfigurationError immediately at WikidataClient construction time,
        not silently be filtered out and cause a hang later.
        """
        from wikidata_collector.exceptions import ProxyMisconfigurationError

        # "ftp://" scheme is rejected by validate_proxy_list
        config = WikidataCollectorConfig(
            proxy_list=["ftp://invalid-scheme.example.com:8080"],
            sparql_timeout_seconds=5,
            max_retries=2,
            proxy_deep_sleep_seconds=1,
            proxy_deep_sleep_max_failures=3,
        )
        with pytest.raises(ProxyMisconfigurationError, match="invalid or missing scheme"):
            WikidataClient(config)

    def test_override_proxies_single_proxy_triggers_deep_sleep(self):
        """
        When override_proxies contains exactly one valid proxy, deep-sleep
        should activate just as it would for a configured single proxy.
        """
        # Configure with zero proxies — the single effective proxy comes from override
        config = WikidataCollectorConfig(
            proxy_list=[],
            sparql_timeout_seconds=5,
            max_retries=2,
            proxy_deep_sleep_seconds=5,
            proxy_deep_sleep_max_failures=2,
        )
        client = WikidataClient(config)
        override = ["http://override-rotation.example.com:8080"]

        with patch("requests.get") as mock_get, patch("time.sleep") as mock_sleep:
            mock_get.side_effect = requests.exceptions.ConnectionError("down")

            with pytest.raises(ProxyUnavailableError):
                client.execute_sparql_query(_QUERY, override_proxies=override)

        # Deep-sleep calls: 2 cycles × 5s
        deep_sleep_calls = [c for c in mock_sleep.call_args_list if c == call(5)]
        assert len(deep_sleep_calls) == 2

    def test_override_proxies_multi_proxy_no_deep_sleep(self):
        """
        When override_proxies contains two valid proxies, deep-sleep must NOT
        trigger — only ProxyMisconfigurationError should be raised.
        """
        config = WikidataCollectorConfig(
            proxy_list=[],
            sparql_timeout_seconds=5,
            max_retries=2,
            proxy_deep_sleep_seconds=5,
            proxy_deep_sleep_max_failures=3,
        )
        client = WikidataClient(config)
        overrides = [
            "http://override1.example.com:8080",
            "http://override2.example.com:8080",
        ]

        with patch("requests.get") as mock_get, patch("time.sleep") as mock_sleep:
            mock_get.side_effect = requests.exceptions.ConnectionError("down")

            with pytest.raises(ProxyMisconfigurationError):
                client.execute_sparql_query(_QUERY, override_proxies=overrides)

        long_sleeps = [c for c in mock_sleep.call_args_list if c.args[0] >= 5]
        assert len(long_sleeps) == 0
