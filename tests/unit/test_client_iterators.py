"""Tests for WikidataClient pagination through the public iterator interface.

The entity pipeline's fetch seam (``_fetch_page``) is substituted with fake
pages; everything above it — keyset pagination, unique-QID stop condition,
filter forwarding — runs for real.
"""

from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from tests.conftest import sparql_response
from wikidata_collector import InvalidFilterError, WikidataClient
from wikidata_collector.config import DEFAULT_LIMIT, WikidataCollectorConfig
from wikidata_collector.models import (
    PublicFigureNormalizedRecord,
    PublicOrganizationNormalizedRecord,
)


def _figure(qid: str) -> PublicFigureNormalizedRecord:
    return PublicFigureNormalizedRecord(qid=qid, name=f"Person {qid}")


def _organization(qid: str) -> PublicOrganizationNormalizedRecord:
    return PublicOrganizationNormalizedRecord(qid=qid, name=f"Organization {qid}")


def _client_with_page_size(page_size: int) -> WikidataClient:
    return WikidataClient(WikidataCollectorConfig(default_limit=page_size))


class TestIteratePublicFiguresPagination:
    """Test pagination behavior of iterate_public_figures."""

    def test_single_page(self, wikidata_client):
        """Results fitting in a single page are yielded once."""
        mock_results = [
            _figure("Q1"),
            _figure("Q2"),
        ]

        with patch.object(
            wikidata_client, "_fetch_page", return_value=(mock_results, "direct")
        ) as mock:
            results = list(wikidata_client.iterate_public_figures(nationality="Q30"))

        mock.assert_called_once()
        assert results == mock_results

    def test_multiple_pages(self, wikidata_client):
        """A full page triggers a keyset-paginated fetch of the next page."""
        page1_results = [_figure(f"Q{i}") for i in range(1, DEFAULT_LIMIT + 1)]
        page2_results = [_figure("Q100")]

        with patch.object(
            wikidata_client,
            "_fetch_page",
            side_effect=[(page1_results, "direct"), (page2_results, "direct")],
        ) as mock:
            results = list(wikidata_client.iterate_public_figures(nationality="Q30"))

        assert len(results) == DEFAULT_LIMIT + 1
        assert mock.call_count == 2
        # Second fetch paginates after the last QID of page 1
        assert mock.call_args.kwargs["after_qid"] == f"Q{DEFAULT_LIMIT}"

    def test_empty_results(self, wikidata_client):
        """No results yields an empty iteration."""
        with patch.object(wikidata_client, "_fetch_page", return_value=([], "direct")):
            results = list(wikidata_client.iterate_public_figures(nationality="Q30"))

        assert results == []

    def test_custom_page_size_from_config(self):
        """Page size comes from config.default_limit."""
        client = _client_with_page_size(5)
        mock_results = [_figure(f"Q{i}") for i in range(1, 4)]  # 3 results

        with patch.object(client, "_fetch_page", return_value=(mock_results, "direct")) as mock:
            results = list(client.iterate_public_figures(nationality="Q30"))

        # 3 unique QIDs < page size 5 — one fetch only
        mock.assert_called_once()
        assert mock.call_args.kwargs["limit"] == 5
        assert len(results) == 3

    def test_stops_on_unique_qids_less_than_limit(self):
        """Stop condition must be based on unique QIDs, not raw record count."""
        # Simulate SPARQL expansion: more rows/records than limit, but fewer unique QIDs.
        # If stop condition incorrectly checks len(results) < limit, we'd fetch another page.
        client = _client_with_page_size(5)
        page_results = [
            _figure("Q1"),
            _figure("Q1"),
            _figure("Q2"),
            _figure("Q2"),
            _figure("Q2"),
            _figure("Q3"),
        ]

        with patch.object(client, "_fetch_page", return_value=(page_results, "direct")) as mock:
            results = list(client.iterate_public_figures(nationality="Q30"))

        mock.assert_called_once()
        assert len(results) == len(page_results)

    def test_filters_forwarded(self, wikidata_client):
        """All public filters reach the fetch seam under their public names."""
        mock_results = [_figure("Q1")]

        with patch.object(
            wikidata_client, "_fetch_page", return_value=(mock_results, "direct")
        ) as mock:
            list(
                wikidata_client.iterate_public_figures(
                    birthday_from="1990-01-01",
                    birthday_to="2000-12-31",
                    nationality="Q30",
                    occupations=["Q33999"],
                    gender="female",
                )
            )

        filters = mock.call_args.args[1]
        assert filters == {
            "birthday_from": "1990-01-01",
            "birthday_to": "2000-12-31",
            "nationality": "Q30",
            "occupations": ["Q33999"],
            "gender": "female",
        }


class TestIteratePublicOrganizationsPagination:
    """Test pagination behavior of iterate_public_organizations."""

    def test_single_page(self, wikidata_client):
        """Results fitting in a single page are yielded once."""
        mock_results = [
            _organization("Q1"),
            _organization("Q2"),
        ]

        with patch.object(
            wikidata_client, "_fetch_page", return_value=(mock_results, "direct")
        ) as mock:
            results = list(
                wikidata_client.iterate_public_organizations(country="Q30", types=["parliament"])
            )

        mock.assert_called_once()
        assert results == mock_results

    def test_multiple_pages(self, wikidata_client):
        """A full page triggers a keyset-paginated fetch of the next page."""
        page1_results = [_organization(f"Q{i}") for i in range(1, DEFAULT_LIMIT + 1)]
        page2_results = [_organization("Q100")]

        with patch.object(
            wikidata_client,
            "_fetch_page",
            side_effect=[(page1_results, "direct"), (page2_results, "direct")],
        ) as mock:
            results = list(
                wikidata_client.iterate_public_organizations(country="Q30", types=["parliament"])
            )

        assert len(results) == DEFAULT_LIMIT + 1
        assert mock.call_count == 2
        assert mock.call_args.kwargs["after_qid"] == f"Q{DEFAULT_LIMIT}"

    def test_empty_results(self, wikidata_client):
        """No results yields an empty iteration."""
        with patch.object(wikidata_client, "_fetch_page", return_value=([], "direct")):
            results = list(
                wikidata_client.iterate_public_organizations(country="Q30", types=["parliament"])
            )

        assert results == []

    def test_custom_page_size_from_config(self):
        """Page size comes from config.default_limit."""
        client = _client_with_page_size(10)
        mock_results = [_organization(f"Q{i}") for i in range(1, 9)]  # 8 results

        with patch.object(client, "_fetch_page", return_value=(mock_results, "direct")) as mock:
            results = list(client.iterate_public_organizations(country="Q30", types=["parliament"]))

        mock.assert_called_once()
        assert mock.call_args.kwargs["limit"] == 10
        assert len(results) == 8

    def test_stops_on_unique_qids_less_than_limit(self):
        """Stop condition must be based on unique QIDs, not raw record count."""
        client = _client_with_page_size(5)
        page_results = [
            _organization("Q1"),
            _organization("Q1"),
            _organization("Q2"),
            _organization("Q2"),
            _organization("Q3"),
            _organization("Q3"),
        ]

        with patch.object(client, "_fetch_page", return_value=(page_results, "direct")) as mock:
            results = list(client.iterate_public_organizations(country="Q30", types=["parliament"]))

        mock.assert_called_once()
        assert len(results) == len(page_results)

    def test_duplicate_qid_rows_within_a_page_count_as_unique_for_pagination(
        self, make_client, organization_page
    ):
        """Row-expanded duplicate QIDs from a raw SPARQL page must not look like a
        full page and trigger a phantom second fetch.

        Mirrors the figure family's pinned unique-QID stop condition, but exercises
        it through raw bindings (via ``organization_page``) and the real
        ``execute_sparql_query`` -> normalize -> pagination path, rather than
        pre-built normalized records.
        """
        client = make_client(default_limit=3)
        page = organization_page(["Q1", "Q1", "Q2"])
        social = sparql_response([])

        with patch.object(
            client, "execute_sparql_query", side_effect=[(page, "direct"), (social, "direct")]
        ) as mock:
            results = list(client.iterate_public_organizations(country="Q30", types=["parliament"]))

        # One call for the page, one for the social-handles query it triggers.
        assert mock.call_count == 2
        assert [record.qid for record in results] == ["Q1", "Q2"]

    def test_filters_forwarded(self, wikidata_client):
        """All public filters reach the fetch seam under their public names."""
        mock_results = [_organization("Q1")]

        with patch.object(
            wikidata_client, "_fetch_page", return_value=(mock_results, "direct")
        ) as mock:
            list(wikidata_client.iterate_public_organizations(country="Q30", types=["Q327333"]))

        filters = mock.call_args.args[1]
        assert filters == {"country": "Q30", "types": ["Q327333"]}


class TestGetPageDelegates:
    """Test that the lower-level get_* methods delegate onto the fetch seam."""

    def test_get_public_figures_forwards_filters(self, wikidata_client):
        with patch.object(
            wikidata_client, "_fetch_page", return_value=([_figure("Q1")], "direct")
        ) as mock:
            records, proxy = wikidata_client.get_public_figures(
                nationality="Q30", occupations=["Q36180"], limit=7, after_qid="Q5"
            )

        assert proxy == "direct"
        assert len(records) == 1
        filters = mock.call_args.args[1]
        assert filters["nationality"] == "Q30"
        assert filters["occupations"] == ["Q36180"]
        assert mock.call_args.kwargs["limit"] == 7
        assert mock.call_args.kwargs["after_qid"] == "Q5"

    def test_get_public_organizations_forwards_filters(self, wikidata_client):
        with patch.object(
            wikidata_client, "_fetch_page", return_value=([_organization("Q1")], "direct")
        ) as mock:
            records, proxy = wikidata_client.get_public_organizations(
                country="Q30", types=["Q327333"], limit=3
            )

        assert proxy == "direct"
        assert len(records) == 1
        filters = mock.call_args.args[1]
        assert filters == {"country": "Q30", "types": ["Q327333"]}
        assert mock.call_args.kwargs["limit"] == 3

    def test_get_public_figures_validates_dates(self, wikidata_client):
        """Date filters are validated at the fetch seam, before SPARQL interpolation."""
        with pytest.raises(InvalidFilterError) as exc_info:
            wikidata_client.get_public_figures(birthday_from="not-a-date")

        assert "Invalid birthday_from format" in str(exc_info.value)

        with pytest.raises(InvalidFilterError) as exc_info:
            wikidata_client.get_public_figures(birthday_to="2000/12/31")

        assert "Invalid birthday_to format" in str(exc_info.value)


class TestOrganizationMultiTypeQueryShape:
    """End-to-end through the real query builder (only `execute_sparql_query`
    is substituted): `get_public_organizations` stays a single VALUES-OR
    query for multiple types, while `iterate_public_organizations` decomposes
    into one query per type.
    """

    def test_get_multi_type_produces_one_query_with_both_qids_in_one_values(self, make_client):
        """A single page request never decomposes: both types ride in one
        VALUES clause of one query."""
        client = make_client()
        captured: Dict[str, Any] = {}

        def _capture(query: str, override_proxies: Any = None):
            captured["query"] = query
            return sparql_response([]), "direct"

        with patch.object(client, "execute_sparql_query", side_effect=_capture) as execute:
            client.get_public_organizations(types=["newspaper", "parliament"])

        execute.assert_called_once()
        assert "VALUES ?orgClass { wd:Q11032 wd:Q35749 }" in captured["query"]

    def test_iterate_multi_type_issues_one_query_stream_per_type(self, make_client):
        """Each type value drives its own query, containing only that type's
        QID in its VALUES clause."""
        client = make_client(default_limit=50)
        captured_queries: List[str] = []

        def _capture(query: str, override_proxies: Any = None):
            captured_queries.append(query)
            return sparql_response([]), "direct"

        with patch.object(client, "execute_sparql_query", side_effect=_capture):
            list(client.iterate_public_organizations(types=["newspaper", "parliament"]))

        assert len(captured_queries) == 2
        assert "VALUES ?orgClass { wd:Q11032 }" in captured_queries[0]
        assert "VALUES ?orgClass { wd:Q35749 }" in captured_queries[1]

    def test_iterate_single_type_issues_one_query(self, make_client):
        """A single type never decomposes: exactly one query is issued."""
        client = make_client(default_limit=50)

        with patch.object(
            client, "execute_sparql_query", return_value=(sparql_response([]), "direct")
        ) as execute:
            list(client.iterate_public_organizations(types=["newspaper"]))

        execute.assert_called_once()

    def test_iterate_multi_type_deduplicates_and_normalizes_through_the_real_pipeline(
        self, make_client, organization_page
    ):
        """A duplicate entity across two type streams is yielded once, through
        the real fetch -> normalize -> pagination -> decomposition path."""
        client = make_client(default_limit=50)
        pages = [organization_page(["Q1", "Q2"]), organization_page(["Q2", "Q3"])]

        def _capture(query: str, override_proxies: Any = None):
            if "VALUES ?entity" in query:
                return sparql_response([]), "direct"
            return pages.pop(0), "direct"

        with patch.object(client, "execute_sparql_query", side_effect=_capture):
            results = list(client.iterate_public_organizations(types=["newspaper", "parliament"]))

        assert [record.qid for record in results] == ["Q1", "Q2", "Q3"]

    def test_iterate_multi_type_max_results_caps_across_streams(
        self, make_client, organization_page
    ):
        """max_results=3 with 2 types x 2 results each yields exactly 3, with
        the second stream's query issued but only partially consumed."""
        client = make_client(default_limit=50)
        pages = [organization_page(["Q1", "Q2"]), organization_page(["Q3", "Q4"])]

        def _capture(query: str, override_proxies: Any = None):
            if "VALUES ?entity" in query:
                return sparql_response([]), "direct"
            return pages.pop(0), "direct"

        with patch.object(client, "execute_sparql_query", side_effect=_capture) as execute:
            results = list(
                client.iterate_public_organizations(
                    types=["newspaper", "parliament"], max_results=3
                )
            )

        assert [record.qid for record in results] == ["Q1", "Q2", "Q3"]
        # One page query per stream plus one social-handles query per page.
        assert execute.call_count == 4


class TestDefaultPageSize:
    """Test DEFAULT_PAGE_SIZE constant."""

    def test_default_page_size_is_15(self):
        """Verify the default page size is 15 as specified."""
        assert DEFAULT_LIMIT == 15
