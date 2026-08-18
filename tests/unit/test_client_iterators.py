"""Tests for WikidataClient pagination through the public iterator interface.

The entity pipeline's fetch seam (``_fetch_page``) is substituted with fake
pages; everything above it — keyset pagination, unique-QID stop condition,
filter forwarding — runs for real.
"""

from unittest.mock import patch

import pytest

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
            results = list(wikidata_client.iterate_public_organizations(country="Q30"))

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
            results = list(wikidata_client.iterate_public_organizations(country="Q30"))

        assert len(results) == DEFAULT_LIMIT + 1
        assert mock.call_count == 2
        assert mock.call_args.kwargs["after_qid"] == f"Q{DEFAULT_LIMIT}"

    def test_empty_results(self, wikidata_client):
        """No results yields an empty iteration."""
        with patch.object(wikidata_client, "_fetch_page", return_value=([], "direct")):
            results = list(wikidata_client.iterate_public_organizations(country="Q30"))

        assert results == []

    def test_custom_page_size_from_config(self):
        """Page size comes from config.default_limit."""
        client = _client_with_page_size(10)
        mock_results = [_organization(f"Q{i}") for i in range(1, 9)]  # 8 results

        with patch.object(client, "_fetch_page", return_value=(mock_results, "direct")) as mock:
            results = list(client.iterate_public_organizations(country="Q30"))

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
            results = list(client.iterate_public_organizations(country="Q30"))

        mock.assert_called_once()
        assert len(results) == len(page_results)

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


class TestDefaultPageSize:
    """Test DEFAULT_PAGE_SIZE constant."""

    def test_default_page_size_is_15(self):
        """Verify the default page size is 15 as specified."""
        assert DEFAULT_LIMIT == 15
