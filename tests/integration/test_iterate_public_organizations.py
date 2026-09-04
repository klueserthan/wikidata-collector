"""
Integration tests for iterate_public_organizations API.

These tests verify the iterator-based API for streaming public organizations.
The entity pipeline's fetch seam (``_fetch_page``) is substituted with fake
pages; validation, pagination, and max_results handling run for real.
They use pytest markers to allow selective execution.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from wikidata_collector import (
    InvalidFilterError,
    PublicOrganizationNormalizedRecord,
    WikidataClient,
)
from wikidata_collector.config import WikidataCollectorConfig
from wikidata_collector.exceptions import QueryExecutionError


def _pi(
    qid: str,
    name: str = "Organization",
    *,
    founded: str | None = None,
    countries: list[str] | None = None,
    types: list[str] | None = None,
) -> PublicOrganizationNormalizedRecord:
    return PublicOrganizationNormalizedRecord(
        qid=qid,
        name=name,
        founded_date=datetime.fromisoformat(founded) if founded else None,
        countries=list(countries or []),
        types=list(types or []),
    )


@pytest.mark.integration
@pytest.mark.iterator
class TestIteratePublicOrganizationsHappyPath:
    """Test iterate_public_organizations happy path scenarios."""

    def test_iterate_returns_public_organization_models(self, mocker):
        """Test that iterator yields PublicOrganization model instances."""
        # Substitute the fetch seam with a fake page of normalized models
        sample_records = [
            _pi(
                "Q123",
                "Example Government Agency",
                founded="1950-01-01T00:00:00",
                countries=["United States"],
                types=["government agency"],
            ),
            _pi(
                "Q456",
                "Test Public Broadcaster",
                founded="1970-06-15T00:00:00",
                countries=["United Kingdom"],
                types=["public broadcaster"],
            ),
        ]

        client = WikidataClient()
        mocker.patch.object(client, "_fetch_page", return_value=(sample_records, "direct"))

        # Call the iterator API (single type: no decomposition, one fetch call)
        results = list(
            client.iterate_public_organizations(country="US", types=["government_agency"])
        )

        # Verify results
        assert len(results) == 2
        assert all(isinstance(r, PublicOrganizationNormalizedRecord) for r in results)
        assert results[0].id == "Q123"
        assert results[0].name == "Example Government Agency"
        assert results[1].id == "Q456"
        assert results[1].name == "Test Public Broadcaster"

    def test_iterate_with_max_results(self, mocker):
        """Test that max_results limits the number of results."""
        # Create a large page of sample results
        sample_records = [
            _pi(f"Q{i}", f"Organization {i}", founded="2000-01-01T00:00:00") for i in range(100)
        ]

        client = WikidataClient()
        mocker.patch.object(client, "_fetch_page", return_value=(sample_records, "direct"))

        # Request only 10 results (single type: no decomposition)
        results = list(
            client.iterate_public_organizations(
                country="US", types=["government_agency"], max_results=10
            )
        )

        # Verify only 10 results returned
        assert len(results) == 10
        assert all(isinstance(r, PublicOrganizationNormalizedRecord) for r in results)

    def test_iterate_with_country_filter(self, mocker):
        """Test iteration with country filter."""
        sample_records = [
            _pi("Q100", "German Organization", founded="1990-01-01T00:00:00", countries=["Germany"])
        ]

        client = WikidataClient()
        mock_fetch = mocker.patch.object(
            client, "_fetch_page", return_value=(sample_records, "direct")
        )

        # Call with country filter and the now-required types filter
        results = list(
            client.iterate_public_organizations(country="Germany", types=["ngo"], lang="en")
        )

        # Verify the fetch seam received the filters under their public names
        mock_fetch.assert_called_once()
        filters = mock_fetch.call_args.args[1]
        assert filters == {"country": "Germany", "types": ["ngo"]}
        assert mock_fetch.call_args.kwargs["lang"] == "en"

        assert len(results) == 1

    def test_iterate_with_types_filter(self, mocker):
        """Multiple types decompose into one fetch call per type; a record
        returned by more than one stream is de-duplicated."""
        sample_records = [_pi("Q200", "Political Party Example", types=["political party"])]

        client = WikidataClient()
        mock_fetch = mocker.patch.object(
            client, "_fetch_page", return_value=(sample_records, "direct")
        )

        # Call with two types filter
        results = list(
            client.iterate_public_organizations(
                types=["political_party", "government_agency"], lang="en"
            )
        )

        # One fetch call per type, each carrying only that one type
        assert mock_fetch.call_count == 2
        sub_filters = [call.args[1]["types"] for call in mock_fetch.call_args_list]
        assert sub_filters == [["political_party"], ["government_agency"]]

        # The same fake record ("Q200") comes back from both streams; it is
        # de-duplicated to a single yielded record.
        assert len(results) == 1

    def test_iterate_with_combined_filters(self, mocker):
        """Test iteration with country plus a single type filter combined."""
        sample_records = [
            _pi(
                "Q400",
                "US Government Agency",
                countries=["United States"],
                types=["government agency"],
            )
        ]

        client = WikidataClient()
        mock_fetch = mocker.patch.object(
            client, "_fetch_page", return_value=(sample_records, "direct")
        )

        # Call with combined filters
        results = list(
            client.iterate_public_organizations(
                country="US", types=["government_agency"], lang="en"
            )
        )

        # Verify the fetch seam received all filters
        mock_fetch.assert_called_once()
        filters = mock_fetch.call_args.args[1]
        assert filters == {"country": "US", "types": ["government_agency"]}

        assert len(results) == 1
        assert results[0].name == "US Government Agency"


@pytest.mark.integration
@pytest.mark.iterator
class TestIteratePublicOrganizationsEdgeCases:
    """Test edge cases and error handling for iterate_public_organizations."""

    def test_iterate_empty_results(self, mocker):
        """Test iteration with valid filters that happen to match nothing."""
        client = WikidataClient()
        mocker.patch.object(client, "_fetch_page", return_value=([], "direct"))

        # Well-formed filters (they pass validation); the mocked page is empty.
        results = list(
            client.iterate_public_organizations(country="Switzerland", types=["newspaper"])
        )

        # Verify empty results
        assert len(results) == 0
        assert isinstance(results, list)

    def test_invalid_max_results_zero(self):
        """Test that max_results=0 raises InvalidFilterError."""
        client = WikidataClient()

        with pytest.raises(InvalidFilterError) as exc_info:
            list(client.iterate_public_organizations(types=["ngo"], max_results=0))

        assert "max_results must be >= 1" in str(exc_info.value)

    def test_invalid_max_results_negative(self):
        """Test that negative max_results raises InvalidFilterError."""
        client = WikidataClient()

        with pytest.raises(InvalidFilterError) as exc_info:
            list(client.iterate_public_organizations(types=["ngo"], max_results=-10))

        assert "max_results must be >= 1" in str(exc_info.value)

    def test_none_types_raises_before_max_results_is_even_checked(self):
        """`types` is validated first: a filters-level error, not a
        max_results-level one, is what a caller with both invalid would see."""
        client = WikidataClient()

        with pytest.raises(InvalidFilterError) as exc_info:
            list(
                client.iterate_public_organizations(
                    types=None,  # type: ignore[arg-type]
                    max_results=0,
                )
            )

        assert "types filter is required" in str(exc_info.value)

    def test_query_execution_error_propagated(self, mocker):
        """Test that QueryExecutionError from the fetch seam is propagated."""
        client = WikidataClient()

        mocker.patch.object(
            client,
            "_fetch_page",
            side_effect=QueryExecutionError("Upstream SPARQL endpoint unavailable"),
        )

        with pytest.raises(QueryExecutionError) as exc_info:
            list(client.iterate_public_organizations(country="US", types=["ngo"]))

        assert "Upstream SPARQL endpoint unavailable" in str(exc_info.value)

    def test_value_error_converted_to_invalid_filter_error(self, mocker):
        """Test that ValueError from query builder is converted to InvalidFilterError."""
        client = WikidataClient()

        mocker.patch.object(client, "_fetch_page", side_effect=ValueError("Invalid QID format"))

        with pytest.raises(InvalidFilterError) as exc_info:
            list(client.iterate_public_organizations(country="Q!!!invalid", types=["ngo"]))

        assert "Invalid filter parameters" in str(exc_info.value)

    def test_iterate_with_only_the_required_types_filter(self, mocker):
        """Test iteration with no other filter than the now-required `types`."""
        sample_records = [_pi("Q1", "Organization 1", founded="2000-01-01T00:00:00")]

        client = WikidataClient()
        mocker.patch.object(client, "_fetch_page", return_value=(sample_records, "direct"))

        # Call with only the required types filter
        results = list(client.iterate_public_organizations(types=["ngo"]))

        assert len(results) == 1
        assert results[0].id == "Q1"

    def test_max_results_one(self, mocker):
        """Test with max_results=1."""
        sample_records = [_pi("Q1", "Organization 1"), _pi("Q2", "Organization 2")]

        client = WikidataClient()
        mocker.patch.object(client, "_fetch_page", return_value=(sample_records, "direct"))

        results = list(client.iterate_public_organizations(types=["ngo"], max_results=1))

        assert len(results) == 1
        assert results[0].id == "Q1"

    def test_country_iso_code_filter(self, mocker):
        """Test with country as ISO code."""
        sample_records = [_pi("Q999", "US Organization", countries=["United States"])]

        client = WikidataClient()
        mock_fetch = mocker.patch.object(
            client, "_fetch_page", return_value=(sample_records, "direct")
        )

        # Call with ISO code
        results = list(client.iterate_public_organizations(country="USA", types=["ngo"]))

        # Verify the ISO code was passed
        mock_fetch.assert_called_once()
        filters = mock_fetch.call_args.args[1]
        assert filters["country"] == "USA"

        assert len(results) == 1

    def test_country_qid_filter(self, mocker):
        """Test with country as QID."""
        sample_records = [_pi("Q888", "UK Organization", countries=["United Kingdom"])]

        client = WikidataClient()
        mock_fetch = mocker.patch.object(
            client, "_fetch_page", return_value=(sample_records, "direct")
        )

        # Call with QID
        results = list(client.iterate_public_organizations(country="Q145", types=["ngo"]))

        # Verify the QID was passed
        mock_fetch.assert_called_once()
        filters = mock_fetch.call_args.args[1]
        assert filters["country"] == "Q145"

        assert len(results) == 1

    def test_types_with_mapped_keys(self, mocker):
        """Multiple mapped-key types decompose into one fetch call each."""
        sample_records = [_pi("Q777", "Party Example", types=["political party"])]

        client = WikidataClient()
        mock_fetch = mocker.patch.object(
            client, "_fetch_page", return_value=(sample_records, "direct")
        )

        # Call with mapped type keys
        results = list(
            client.iterate_public_organizations(types=["political_party", "municipality"])
        )

        # One fetch call per type, each carrying only that one type
        assert mock_fetch.call_count == 2
        sub_filters = [call.args[1]["types"] for call in mock_fetch.call_args_list]
        assert sub_filters == [["political_party"], ["municipality"]]

        # The same fake record ("Q777") comes back from both streams; it is
        # de-duplicated to a single yielded record.
        assert len(results) == 1

    def test_empty_types_list_raises(self, mocker):
        """types=[] carries no filter at all and is rejected, not passed through:
        an unfiltered organization scan always times out on WDQS."""
        client = WikidataClient()

        with pytest.raises(InvalidFilterError, match="types filter is required"):
            list(client.iterate_public_organizations(types=[]))

    def test_none_types_raises(self, mocker):
        """types=None is rejected the same way as `types=[]`; omitting `types`
        entirely is instead a Python-level TypeError, since it has no default."""
        client = WikidataClient()

        with pytest.raises(InvalidFilterError, match="types filter is required"):
            list(client.iterate_public_organizations(types=None))  # type: ignore[arg-type]


@pytest.mark.integration
@pytest.mark.iterator
class TestIteratePublicOrganizationsMultiTypeOverMockedHTTP:
    """Round-trip multi-type OR / decomposition through the real client, with
    only the HTTP transport (``requests.get``) mocked — no ``_fetch_page``
    substitution. Proves the decomposition seam (``_decompose_organization_filters``)
    actually drives one real SPARQL query per type, each with exactly that
    type's QID in its ``VALUES`` clause, and that de-duplication and
    ``max_results`` behave correctly across those real streams.
    """

    def _client(self) -> WikidataClient:
        """Return a client with no proxies (direct connection only) and a
        single retry, matching mocked-HTTP integration tests elsewhere in
        this suite."""
        config = WikidataCollectorConfig(proxy_list=[], sparql_timeout_seconds=5, max_retries=1)
        return WikidataClient(config)

    @staticmethod
    def _http_get(pages: list):
        """Build a `requests.get` stand-in that pops one mocked page per call.

        Each real page triggers a follow-up social-handles query (identified
        by its ``VALUES ?entity`` clause); that call is answered with an
        empty envelope rather than popping from `pages`, since these tests
        care about the page-query round trips, not social handles.
        """

        def _get(url, params=None, headers=None, proxies=None, timeout=None):
            response = MagicMock()
            response.status_code = 200
            query = (params or {}).get("query", "")
            if "VALUES ?entity" in query:
                response.json.return_value = {"results": {"bindings": []}}
            else:
                response.json.return_value = pages.pop(0)
            return response

        return _get

    def test_multi_type_issues_one_query_per_type_each_with_one_qid_in_values(
        self, organization_page
    ):
        """types=["newspaper", "parliament"] must issue two HTTP requests, one
        per type, each carrying exactly one QID in its VALUES clause — never
        both QIDs OR-ed into a single combined query."""
        client = self._client()
        pages = [organization_page(["Q10"]), organization_page(["Q20"])]

        with patch("requests.get", side_effect=self._http_get(pages)) as mock_get:
            results = list(
                client.iterate_public_organizations(
                    types=["newspaper", "parliament"], country="Switzerland"
                )
            )

        # Each stream's non-empty page also triggers a follow-up social-handles
        # query, so 2 streams cost 4 HTTP round trips, not 2.
        assert mock_get.call_count == 4
        all_queries = [call.kwargs["params"]["query"] for call in mock_get.call_args_list]
        page_queries = [query for query in all_queries if "VALUES ?entity" not in query]
        assert len(page_queries) == 2

        assert "VALUES ?orgClass { wd:Q11032 }" in page_queries[0]
        assert "wd:Q35749" not in page_queries[0]
        assert "VALUES ?orgClass { wd:Q35749 }" in page_queries[1]
        assert "wd:Q11032" not in page_queries[1]
        # The country filter reaches every stream's query.
        assert all("wdt:P17 wd:Q39" in query for query in page_queries)

        assert [record.qid for record in results] == ["Q10", "Q20"]

    def test_duplicate_across_streams_yielded_once(self, organization_page):
        """The same entity returned by two type streams (it matches both
        classes) is de-duplicated to a single yielded record, end to end
        through the real HTTP -> normalize -> pagination -> decomposition
        path."""
        client = self._client()
        pages = [organization_page(["Q10", "Q20"]), organization_page(["Q20", "Q30"])]

        with patch("requests.get", side_effect=self._http_get(pages)):
            results = list(client.iterate_public_organizations(types=["newspaper", "parliament"]))

        assert [record.qid for record in results] == ["Q10", "Q20", "Q30"]

    def test_max_results_caps_across_streams(self, organization_page):
        """max_results is a single global budget spanning every stream, not a
        per-stream one: 2 types x 2 results each, capped at 3 total."""
        client = self._client()
        pages = [organization_page(["Q10", "Q20"]), organization_page(["Q30", "Q40"])]

        with patch("requests.get", side_effect=self._http_get(pages)) as mock_get:
            results = list(
                client.iterate_public_organizations(
                    types=["newspaper", "parliament"], max_results=3
                )
            )

        assert [record.qid for record in results] == ["Q10", "Q20", "Q30"]
        # Both streams' first pages are fetched (the cap is hit mid-second
        # stream); no further page beyond that is fetched. Each of those two
        # page fetches also costs one follow-up social-handles round trip.
        assert mock_get.call_count == 4
