"""Unit tests for the SPARQL HTTP layer: retries, backoff, and error mapping.

`execute_sparql_query` decides how upstream failures are classified — throttling,
upstream outage, proxy exhaustion, or a plain execution error — and how long the
client waits between attempts. Those decisions are exercised here against a
mocked HTTP endpoint, with `time.sleep` recorded rather than performed.
"""

from typing import Any, Dict, Iterator, List
from urllib.parse import parse_qs, urlparse

import pytest
import requests
import responses

from wikidata_collector.exceptions import (
    ProxyMisconfigurationError,
    QueryExecutionError,
    UpstreamUnavailableError,
)

SPARQL_URL = "https://query.wikidata.org/sparql"
QUERY = "SELECT ?item WHERE { ?item wdt:P31 wd:Q5 }"
PROXY_A = "http://proxy-a.example.com:8080"
PROXY_B = "http://proxy-b.example.com:8080"

EMPTY_RESULT: Dict[str, Any] = {"results": {"bindings": []}}


@pytest.fixture
def http() -> Iterator[responses.RequestsMock]:
    """Intercept outbound requests, allowing unfired registrations."""
    with responses.RequestsMock(assert_all_requests_are_fired=False) as mock:
        yield mock


def _register(mock: responses.RequestsMock, *statuses: int) -> None:
    """Queue one response per status code, served in order.

    Args:
        mock: The active responses mock.
        *statuses: HTTP status codes to return for successive requests.
    """
    for status in statuses:
        body = EMPTY_RESULT if status == 200 else {"error": status}
        mock.add(responses.GET, SPARQL_URL, json=body, status=status)


class TestSuccessfulExecution:
    """The happy path and what it reports back."""

    def test_returns_parsed_body_and_direct_when_unproxied(self, make_client, http):
        """Without proxies the result is returned and the hop reported as direct."""
        _register(http, 200)

        result, used_proxy = make_client().execute_sparql_query(QUERY)

        assert result == EMPTY_RESULT
        assert used_proxy == "direct"

    def test_reports_the_proxy_it_went_through(self, make_client, http):
        """With proxies configured, the proxy actually used is reported back."""
        _register(http, 200)

        _, used_proxy = make_client(proxy_list=[PROXY_A, PROXY_B]).execute_sparql_query(QUERY)

        assert used_proxy in {PROXY_A, PROXY_B}

    def test_sends_the_query_and_the_required_headers(self, make_client, http):
        """The query travels as a param under the JSON Accept and a real UA."""
        _register(http, 200)

        make_client(contact_email="ops@example.com").execute_sparql_query(QUERY)

        request = http.calls[0].request
        assert parse_qs(urlparse(request.url).query)["query"] == [QUERY]
        assert request.headers["Accept"] == "application/sparql-results+json"
        assert "ops@example.com" in request.headers["User-Agent"]

    def test_recovers_after_a_transient_upstream_error(self, make_client, http):
        """A 503 followed by a 200 succeeds without surfacing the blip."""
        _register(http, 503, 200)

        result, _ = make_client(max_retries=3).execute_sparql_query(QUERY)

        assert result == EMPTY_RESULT
        assert len(http.calls) == 2

    def test_does_not_sleep_when_the_first_attempt_succeeds(
        self, make_client, http, recorded_sleeps
    ):
        """A clean first attempt costs no backoff at all."""
        _register(http, 200)

        make_client().execute_sparql_query(QUERY)

        assert recorded_sleeps == []


class TestThrottling:
    """HTTP 429 handling and the Retry-After contract."""

    def test_retry_after_header_sets_the_wait(self, make_client, http, recorded_sleeps):
        """A numeric Retry-After is honoured verbatim rather than guessed at."""
        http.add(responses.GET, SPARQL_URL, json={}, status=429, headers={"Retry-After": "7"})
        _register(http, 200)

        make_client(max_retries=3).execute_sparql_query(QUERY)

        assert recorded_sleeps[0] == 7

    def test_missing_retry_after_falls_back_to_exponential_backoff(
        self, make_client, http, recorded_sleeps
    ):
        """Without the header the client backs off as 2**attempt."""
        _register(http, 429, 429, 200)

        make_client(max_retries=4).execute_sparql_query(QUERY)

        assert recorded_sleeps[:2] == [1, 2]

    def test_non_numeric_retry_after_falls_back_to_exponential_backoff(
        self, make_client, http, recorded_sleeps
    ):
        """An HTTP-date Retry-After is not parsed, so backoff takes over."""
        http.add(
            responses.GET,
            SPARQL_URL,
            json={},
            status=429,
            headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"},
        )
        _register(http, 200)

        make_client(max_retries=3).execute_sparql_query(QUERY)

        assert recorded_sleeps[0] == 1

    def test_sustained_throttling_is_not_reported_as_an_upstream_outage(self, make_client, http):
        """429 is a client-side rate limit, so it maps to QueryExecutionError."""
        _register(http, 429, 429)

        with pytest.raises(QueryExecutionError):
            make_client().execute_sparql_query(QUERY)

    def test_does_not_sleep_after_the_final_429_attempt(self, make_client, http, recorded_sleeps):
        """Nothing is retried after the last attempt, so it must not sleep either."""
        _register(http, 429, 429, 429)

        with pytest.raises(QueryExecutionError):
            make_client(max_retries=3).execute_sparql_query(QUERY)

        assert len(recorded_sleeps) == 2


class TestUpstreamUnavailable:
    """HTTP 502/503/504 handling."""

    @pytest.mark.parametrize("status", [502, 503, 504])
    def test_exhausted_upstream_errors_raise_upstream_unavailable(
        self, make_client, http, status: int
    ):
        """Each gateway status maps to UpstreamUnavailableError once retries run out."""
        _register(http, status, status)

        with pytest.raises(UpstreamUnavailableError, match="after 2 attempts"):
            make_client().execute_sparql_query(QUERY)

    def test_backoff_is_capped_by_retry_max_wait_seconds(self, make_client, http, recorded_sleeps):
        """Exponential growth stops at the configured ceiling."""
        _register(http, 503, 503, 503, 503)

        with pytest.raises(UpstreamUnavailableError):
            make_client(max_retries=4, retry_max_wait_seconds=3).execute_sparql_query(QUERY)

        assert recorded_sleeps == [1, 2, 3]

    def test_a_seen_gateway_status_outranks_a_later_connection_failure(self, make_client, http):
        """Once a gateway status is seen, the failure stays an upstream outage."""
        _register(http, 503)
        http.add(responses.GET, SPARQL_URL, body=requests.exceptions.ConnectionError("reset"))

        with pytest.raises(UpstreamUnavailableError):
            make_client().execute_sparql_query(QUERY)

    def test_does_not_sleep_after_the_final_5xx_attempt(self, make_client, http, recorded_sleeps):
        """Nothing is retried after the last attempt, so it must not sleep either."""
        _register(http, 503, 503, 503)

        with pytest.raises(UpstreamUnavailableError):
            make_client(max_retries=3).execute_sparql_query(QUERY)

        assert len(recorded_sleeps) == 2


class TestFailureClassification:
    """Which exception a caller sees when everything has failed."""

    def test_connection_failure_without_proxies_is_a_query_execution_error(self, make_client, http):
        """No proxies in play means the failure is not a proxy problem."""
        http.add(responses.GET, SPARQL_URL, body=requests.exceptions.ConnectionError("refused"))
        http.add(responses.GET, SPARQL_URL, body=requests.exceptions.ConnectionError("refused"))

        with pytest.raises(QueryExecutionError, match="after 2 attempts"):
            make_client().execute_sparql_query(QUERY)

    def test_exhausted_configured_proxies_raise_proxy_misconfiguration(self, make_client, http):
        """Every configured proxy failing points the operator at the proxies."""
        for _ in range(2):
            http.add(responses.GET, SPARQL_URL, body=requests.exceptions.ConnectionError("refused"))

        with pytest.raises(ProxyMisconfigurationError, match="All configured proxies failed"):
            make_client(proxy_list=[PROXY_A, PROXY_B]).execute_sparql_query(QUERY)

    def test_failing_proxies_are_put_into_cooldown(self, make_client, http):
        """A failed hop is marked so rotation skips it while it cools down."""
        for _ in range(2):
            http.add(responses.GET, SPARQL_URL, body=requests.exceptions.ConnectionError("refused"))
        client = make_client(proxy_list=[PROXY_A, PROXY_B])

        with pytest.raises(ProxyMisconfigurationError):
            client.execute_sparql_query(QUERY)

        assert set(client.proxy_manager.failed_proxies) == {PROXY_A, PROXY_B}

    def test_exhausted_override_proxies_raise_proxy_misconfiguration(self, make_client, http):
        """Overrides bypass cooldown tracking but still classify as proxy failure."""
        for _ in range(2):
            http.add(responses.GET, SPARQL_URL, body=requests.exceptions.ConnectionError("refused"))

        with pytest.raises(ProxyMisconfigurationError):
            make_client().execute_sparql_query(QUERY, override_proxies=[PROXY_A, PROXY_B])

    def test_client_error_status_is_a_query_execution_error(self, make_client, http):
        """A 400 from a malformed query is raised, not retried into an outage."""
        _register(http, 400, 400)

        with pytest.raises(QueryExecutionError):
            make_client().execute_sparql_query(QUERY)

    def test_jitter_backoff_grows_with_the_attempt_number(self, make_client, http, recorded_sleeps):
        """Connection failures back off by base + increment * attempt."""
        for _ in range(3):
            http.add(responses.GET, SPARQL_URL, body=requests.exceptions.ConnectionError("refused"))

        with pytest.raises(QueryExecutionError):
            make_client(
                max_retries=3, retry_jitter_base=0.5, retry_jitter_increment=0.25
            ).execute_sparql_query(QUERY)

        assert recorded_sleeps == [0.5, 0.75]


class TestProxyRotation:
    """Rotation across attempts, observed through the mocked transport."""

    def test_each_retry_takes_a_different_proxy(self, make_client, http):
        """Round-robin means a second attempt does not reuse the failed hop."""
        http.add(responses.GET, SPARQL_URL, body=requests.exceptions.ConnectionError("refused"))
        _register(http, 200)
        client = make_client(proxy_list=[PROXY_A, PROXY_B], max_retries=3)

        _, used_proxy = client.execute_sparql_query(QUERY)

        failed: List[str] = list(client.proxy_manager.failed_proxies)
        assert len(failed) == 1
        assert used_proxy != failed[0]
