"""Unit tests for the entity pipeline in `WikidataClient`.

`test_client_iterators.py` covers page-boundary arithmetic. This file covers the
rest of the pipeline contract: input validation, keyset threading, the
`max_results` cap, how failures are classified on the way out, and the lifecycle
logs operators rely on.
"""

import logging
from typing import Any, Dict, List, Tuple
from unittest.mock import patch

import pytest

from tests.conftest import figure_binding, sparql_response
from wikidata_collector.exceptions import InvalidFilterError, QueryExecutionError
from wikidata_collector.models import PublicFigureNormalizedRecord


def _figures(*qids: str) -> List[PublicFigureNormalizedRecord]:
    """Build normalized figure records for the given QIDs."""
    return [PublicFigureNormalizedRecord(qid=qid, name=f"Person {qid}") for qid in qids]


def _pages(*pages: List[PublicFigureNormalizedRecord]) -> List[Tuple[Any, str]]:
    """Wrap record pages in the (records, proxy) shape `_fetch_page` returns."""
    return [(page, "direct") for page in pages]


class TestFilterValidation:
    """Bad input fails before anything reaches SPARQL."""

    @pytest.mark.parametrize("field", ["birthday_from", "birthday_to"])
    @pytest.mark.parametrize("value", ["1990-13-01", "1990-02-30", "01-01-1990", "not-a-date"])
    def test_malformed_birthday_is_rejected(self, wikidata_client, field: str, value: str):
        """Impossible and misformatted dates raise before a request is made."""
        filters: Dict[str, Any] = {field: value}

        with patch.object(wikidata_client, "_fetch_page") as fetch:
            with pytest.raises(InvalidFilterError, match="Expected ISO format"):
                list(wikidata_client.iterate_public_figures(**filters))

        fetch.assert_not_called()

    def test_leap_day_is_accepted_in_a_leap_year(self, wikidata_client):
        """2024-02-29 is a real date and must not be rejected."""
        with patch.object(wikidata_client, "_fetch_page", side_effect=_pages([])):
            assert list(wikidata_client.iterate_public_figures(birthday_from="2024-02-29")) == []

    def test_unknown_filter_label_becomes_an_invalid_filter_error(self, wikidata_client):
        """A label the constants do not map raises InvalidFilterError, not ValueError."""
        with pytest.raises(InvalidFilterError, match="Invalid filter parameters"):
            list(wikidata_client.iterate_public_figures(nationality="Atlantis"))

    @pytest.mark.parametrize("max_results", [0, -1, -100])
    def test_non_positive_max_results_is_rejected(self, wikidata_client, max_results: int):
        """max_results below 1 asks for nothing and is a caller error."""
        with pytest.raises(InvalidFilterError, match="max_results must be >= 1"):
            list(wikidata_client.iterate_public_figures(max_results=max_results))

    def test_validation_runs_before_the_first_page_is_requested(self, wikidata_client):
        """Generators are lazy, but validation must still fail fast on first use."""
        with patch.object(wikidata_client, "_fetch_page") as fetch:
            with pytest.raises(InvalidFilterError):
                list(wikidata_client.iterate_public_institutions(max_results=0))

        fetch.assert_not_called()


class TestMaxResults:
    """The cap the caller asked for is honoured exactly."""

    def test_iteration_stops_at_the_cap_mid_page(self, wikidata_client):
        """A cap smaller than the page size truncates without a second fetch."""
        with patch.object(
            wikidata_client, "_fetch_page", side_effect=_pages(_figures("Q1", "Q2", "Q3"))
        ) as fetch:
            results = list(wikidata_client.iterate_public_figures(max_results=2))

        assert [record.qid for record in results] == ["Q1", "Q2"]
        assert fetch.call_count == 1

    def test_no_cap_drains_every_page(self, make_client):
        """Without max_results the iterator runs until a short page ends it."""
        client = make_client(default_limit=2)
        with patch.object(
            client, "_fetch_page", side_effect=_pages(_figures("Q1", "Q2"), _figures("Q3"))
        ):
            results = list(client.iterate_public_figures())

        assert [record.qid for record in results] == ["Q1", "Q2", "Q3"]

    def test_reaching_the_cap_is_logged(self, wikidata_client, caplog):
        """Operators can tell a truncated run from an exhausted one."""
        with caplog.at_level(logging.INFO):
            with patch.object(
                wikidata_client, "_fetch_page", side_effect=_pages(_figures("Q1", "Q2"))
            ):
                list(wikidata_client.iterate_public_figures(max_results=1))

        events = {getattr(record, "event", None) for record in caplog.records}
        assert "max_results_reached" in events


class TestKeysetPagination:
    """Paging is driven by the last QID seen, not by an offset."""

    def test_after_qid_threads_the_last_record_of_the_previous_page(self, make_client):
        """Each fetch after the first asks for entities beyond the last QID."""
        client = make_client(default_limit=2)
        with patch.object(
            client,
            "_fetch_page",
            side_effect=_pages(_figures("Q1", "Q5"), _figures("Q7", "Q9"), _figures("Q11")),
        ) as fetch:
            list(client.iterate_public_figures())

        after_qids = [call.kwargs["after_qid"] for call in fetch.call_args_list]
        assert after_qids == [None, "Q5", "Q9"]

    def test_a_short_page_ends_iteration(self, make_client):
        """Fewer unique QIDs than the page size means the last page was reached."""
        client = make_client(default_limit=3)
        with patch.object(client, "_fetch_page", side_effect=_pages(_figures("Q1", "Q2"))) as fetch:
            list(client.iterate_public_figures())

        assert fetch.call_count == 1

    def test_row_expansion_does_not_fake_a_full_page(self, make_client):
        """Duplicate QIDs count once, so expansion cannot trigger a phantom page.

        Regression guard for the pre-keyset behaviour, which compared the raw row
        count against the limit and looped forever on heavily expanded entities.
        """
        client = make_client(default_limit=3)
        expanded = _figures("Q1", "Q1", "Q1", "Q2")
        with patch.object(client, "_fetch_page", side_effect=_pages(expanded)) as fetch:
            list(client.iterate_public_figures())

        assert fetch.call_count == 1

    def test_an_empty_page_ends_iteration_without_yielding(self, wikidata_client):
        """An empty first page yields nothing and stops."""
        with patch.object(wikidata_client, "_fetch_page", side_effect=_pages([])) as fetch:
            assert list(wikidata_client.iterate_public_figures()) == []

        assert fetch.call_count == 1


class TestFailurePropagation:
    """What escapes the pipeline when a page fetch fails."""

    def test_upstream_errors_are_not_swallowed(self, wikidata_client):
        """A QueryExecutionError from the fetch seam reaches the caller intact."""
        with patch.object(wikidata_client, "_fetch_page", side_effect=QueryExecutionError("boom")):
            with pytest.raises(QueryExecutionError, match="boom"):
                list(wikidata_client.iterate_public_figures())

    def test_failures_are_logged_with_the_entity_kind(self, wikidata_client, caplog):
        """A failed iteration says which entity kind it was working on."""
        with caplog.at_level(logging.ERROR):
            with patch.object(
                wikidata_client, "_fetch_page", side_effect=QueryExecutionError("boom")
            ):
                with pytest.raises(QueryExecutionError):
                    list(wikidata_client.iterate_public_institutions())

        failures = [r for r in caplog.records if getattr(r, "event", None) == "iteration_failed"]
        assert failures
        assert failures[0].entity_kind == "public_institution"
        assert failures[0].error_type == "QueryExecutionError"

    def test_a_failed_iteration_is_not_logged_as_completed(self, wikidata_client, caplog):
        """The completion log is a success signal and must not fire on failure."""
        with caplog.at_level(logging.INFO):
            with patch.object(
                wikidata_client, "_fetch_page", side_effect=QueryExecutionError("boom")
            ):
                with pytest.raises(QueryExecutionError):
                    list(wikidata_client.iterate_public_figures())

        events = {getattr(record, "event", None) for record in caplog.records}
        assert "iteration_completed" not in events

    def test_a_successful_iteration_reports_its_result_count(self, wikidata_client, caplog):
        """The completion log carries the number of records actually yielded."""
        with caplog.at_level(logging.INFO):
            with patch.object(
                wikidata_client, "_fetch_page", side_effect=_pages(_figures("Q1", "Q2"))
            ):
                list(wikidata_client.iterate_public_figures())

        completed = [
            r for r in caplog.records if getattr(r, "event", None) == "iteration_completed"
        ]
        assert completed
        assert completed[0].result_count == 2
        assert completed[0].status == "success"


class TestFetchSeam:
    """`_fetch_page` glues query building, execution, and normalization."""

    def test_a_page_of_bindings_is_normalized_into_records(self, make_client):
        """The seam returns normalized records plus the proxy that served them."""
        client = make_client()
        page = sparql_response(
            [
                figure_binding("Q42", "Douglas Adams", occupationLabel="writer"),
                figure_binding("Q42", "Douglas Adams", occupationLabel="humorist"),
            ]
        )
        with patch.object(client, "execute_sparql_query", return_value=(page, "direct")):
            records, used_proxy = client.get_public_figures()

        assert used_proxy == "direct"
        assert [record.qid for record in records] == ["Q42"]
        assert records[0].occupations == ["writer", "humorist"]

    def test_a_response_without_a_results_key_is_an_empty_page(self, make_client):
        """A malformed envelope yields no records rather than raising."""
        client = make_client()
        with patch.object(client, "execute_sparql_query", return_value=({}, "direct")):
            records, _ = client.get_public_figures()

        assert records == []

    def test_the_configured_page_size_is_used_when_no_limit_is_given(self, make_client):
        """`default_limit` reaches the query builder as the LIMIT clause."""
        client = make_client(default_limit=7)
        captured: Dict[str, Any] = {}

        def _capture(query: str, override_proxies: Any = None):
            captured["query"] = query
            return sparql_response([]), "direct"

        with patch.object(client, "execute_sparql_query", side_effect=_capture):
            client.get_public_figures()

        assert "LIMIT 7" in captured["query"]
