"""
Integration tests for iterate_public_institutions API.

These tests verify the iterator-based API for streaming public institutions.
They use pytest markers to allow selective execution.
"""

from datetime import datetime

import pytest

from wikidata_collector import InvalidFilterError, PublicInstitutionNormalizedRecord, WikidataClient
from wikidata_collector.exceptions import QueryExecutionError


def _pi(
    qid: str,
    name: str = "Institution",
    *,
    founded: str | None = None,
    countries: list[str] | None = None,
    types: list[str] | None = None,
) -> PublicInstitutionNormalizedRecord:
    return PublicInstitutionNormalizedRecord(
        qid=qid,
        name=name,
        founded_date=datetime.fromisoformat(founded) if founded else None,
        countries=list(countries or []),
        types=list(types or []),
    )


@pytest.mark.integration
@pytest.mark.iterator
class TestIteratePublicInstitutionsHappyPath:
    """Test iterate_public_institutions happy path scenarios."""

    def test_iterate_returns_public_institution_models(self, mocker):
        """Test that iterator yields PublicInstitution model instances."""
        # Mock the underlying iter_public_institutions to return normalized models
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
        mocker.patch.object(client, "iter_public_institutions", return_value=iter(sample_records))

        # Call the iterator API
        results = list(
            client.iterate_public_institutions(country="US", types=["government_agency"])
        )

        # Verify results
        assert len(results) == 2
        assert all(isinstance(r, PublicInstitutionNormalizedRecord) for r in results)
        assert results[0].id == "Q123"
        assert results[0].name == "Example Government Agency"
        assert results[1].id == "Q456"
        assert results[1].name == "Test Public Broadcaster"

    def test_iterate_with_max_results(self, mocker):
        """Test that max_results limits the number of results."""
        # Create a large list of sample results
        sample_records = [
            _pi(f"Q{i}", f"Institution {i}", founded="2000-01-01T00:00:00") for i in range(100)
        ]

        client = WikidataClient()
        mocker.patch.object(client, "iter_public_institutions", return_value=iter(sample_records))

        # Request only 10 results
        results = list(client.iterate_public_institutions(country="US", max_results=10))

        # Verify only 10 results returned
        assert len(results) == 10
        assert all(isinstance(r, PublicInstitutionNormalizedRecord) for r in results)

    def test_iterate_with_country_filter(self, mocker):
        """Test iteration with country filter."""
        sample_records = [
            _pi("Q100", "German Institution", founded="1990-01-01T00:00:00", countries=["Germany"])
        ]

        client = WikidataClient()
        mock_iter = mocker.patch.object(
            client, "iter_public_institutions", return_value=iter(sample_records)
        )

        # Call with country filter
        results = list(client.iterate_public_institutions(country="Germany", lang="en"))

        # Verify the underlying iterator was called with correct parameters
        mock_iter.assert_called_once_with(country="Germany", type=None, lang="en")

        assert len(results) == 1

    def test_iterate_with_types_filter(self, mocker):
        """Test iteration with types filter."""
        sample_records = [_pi("Q200", "Political Party Example", types=["political party"])]

        client = WikidataClient()
        mock_iter = mocker.patch.object(
            client, "iter_public_institutions", return_value=iter(sample_records)
        )

        # Call with types filter
        results = list(
            client.iterate_public_institutions(
                types=["political_party", "government_agency"], lang="en"
            )
        )

        # Verify the underlying iterator was called with correct parameters
        mock_iter.assert_called_once()
        call_args = mock_iter.call_args
        assert call_args.kwargs["type"] == ["political_party", "government_agency"]

        assert len(results) == 1

    def test_iterate_with_combined_filters(self, mocker):
        """Test iteration with multiple filters combined."""
        sample_records = [
            _pi(
                "Q400",
                "US Government Agency",
                countries=["United States"],
                types=["government agency"],
            )
        ]

        client = WikidataClient()
        mock_iter = mocker.patch.object(
            client, "iter_public_institutions", return_value=iter(sample_records)
        )

        # Call with combined filters
        results = list(
            client.iterate_public_institutions(country="US", types=["government_agency"], lang="en")
        )

        # Verify the underlying iterator was called with all filters
        mock_iter.assert_called_once_with(country="US", type=["government_agency"], lang="en")

        assert len(results) == 1
        assert results[0].name == "US Government Agency"


@pytest.mark.integration
@pytest.mark.iterator
class TestIteratePublicInstitutionsEdgeCases:
    """Test edge cases and error handling for iterate_public_institutions."""

    def test_iterate_empty_results(self, mocker):
        """Test iteration with no matching results."""
        client = WikidataClient()
        mocker.patch.object(client, "iter_public_institutions", return_value=iter([]))

        # Call the iterator with filters that return no results
        results = list(
            client.iterate_public_institutions(
                country="NonexistentCountry", types=["nonexistent_type"]
            )
        )

        # Verify empty results
        assert len(results) == 0
        assert isinstance(results, list)

    def test_invalid_max_results_zero(self):
        """Test that max_results=0 raises InvalidFilterError."""
        client = WikidataClient()

        with pytest.raises(InvalidFilterError) as exc_info:
            list(client.iterate_public_institutions(max_results=0))

        assert "max_results must be >= 1" in str(exc_info.value)

    def test_invalid_max_results_negative(self):
        """Test that negative max_results raises InvalidFilterError."""
        client = WikidataClient()

        with pytest.raises(InvalidFilterError) as exc_info:
            list(client.iterate_public_institutions(max_results=-10))

        assert "max_results must be >= 1" in str(exc_info.value)

    def test_query_execution_error_propagated(self, mocker):
        """Test that QueryExecutionError from underlying iterator is propagated."""
        client = WikidataClient()

        # Mock iter_public_institutions to raise QueryExecutionError
        def error_generator():
            raise QueryExecutionError("Upstream SPARQL endpoint unavailable")
            yield  # pragma: no cover

        mocker.patch.object(
            client, "iter_public_institutions", side_effect=lambda **kwargs: error_generator()
        )

        with pytest.raises(QueryExecutionError) as exc_info:
            list(client.iterate_public_institutions(country="US"))

        assert "Upstream SPARQL endpoint unavailable" in str(exc_info.value)

    def test_value_error_converted_to_invalid_filter_error(self, mocker):
        """Test that ValueError from query builder is converted to InvalidFilterError."""
        client = WikidataClient()

        # Mock iter_public_institutions to raise ValueError
        def error_generator():
            raise ValueError("Invalid QID format")
            yield  # pragma: no cover

        mocker.patch.object(
            client, "iter_public_institutions", side_effect=lambda **kwargs: error_generator()
        )

        with pytest.raises(InvalidFilterError) as exc_info:
            list(client.iterate_public_institutions(country="Q!!!invalid"))

        assert "Invalid filter parameters" in str(exc_info.value)

    def test_iterate_without_filters(self, mocker):
        """Test iteration without any filters."""
        sample_records = [_pi("Q1", "Institution 1", founded="2000-01-01T00:00:00")]

        client = WikidataClient()
        mocker.patch.object(client, "iter_public_institutions", return_value=iter(sample_records))

        # Call without filters
        results = list(client.iterate_public_institutions())

        assert len(results) == 1
        assert results[0].id == "Q1"

    def test_max_results_one(self, mocker):
        """Test with max_results=1."""
        sample_records = [_pi("Q1", "Institution 1"), _pi("Q2", "Institution 2")]

        client = WikidataClient()
        mocker.patch.object(client, "iter_public_institutions", return_value=iter(sample_records))

        results = list(client.iterate_public_institutions(max_results=1))

        assert len(results) == 1
        assert results[0].id == "Q1"

    def test_country_iso_code_filter(self, mocker):
        """Test with country as ISO code."""
        sample_records = [_pi("Q999", "US Institution", countries=["United States"])]

        client = WikidataClient()
        mock_iter = mocker.patch.object(
            client, "iter_public_institutions", return_value=iter(sample_records)
        )

        # Call with ISO code
        results = list(client.iterate_public_institutions(country="USA"))

        # Verify the ISO code was passed
        mock_iter.assert_called_once()
        call_args = mock_iter.call_args
        assert call_args.kwargs["country"] == "USA"

        assert len(results) == 1

    def test_country_qid_filter(self, mocker):
        """Test with country as QID."""
        sample_records = [_pi("Q888", "UK Institution", countries=["United Kingdom"])]

        client = WikidataClient()
        mock_iter = mocker.patch.object(
            client, "iter_public_institutions", return_value=iter(sample_records)
        )

        # Call with QID
        results = list(client.iterate_public_institutions(country="Q145"))

        # Verify the QID was passed
        mock_iter.assert_called_once()
        call_args = mock_iter.call_args
        assert call_args.kwargs["country"] == "Q145"

        assert len(results) == 1

    def test_types_with_mapped_keys(self, mocker):
        """Test types filter with mapped keys."""
        sample_records = [_pi("Q777", "Party Example", types=["political party"])]

        client = WikidataClient()
        mock_iter = mocker.patch.object(
            client, "iter_public_institutions", return_value=iter(sample_records)
        )

        # Call with mapped type keys
        results = list(
            client.iterate_public_institutions(types=["political_party", "municipality"])
        )

        # Verify the types were passed
        mock_iter.assert_called_once()
        call_args = mock_iter.call_args
        assert call_args.kwargs["type"] == ["political_party", "municipality"]

        assert len(results) == 1

    def test_empty_types_list(self, mocker):
        """Test with empty types list."""
        sample_sparql_results = [
            {
                "institution": {"value": "http://www.wikidata.org/entity/Q1"},
                "institutionLabel": {"value": "Institution 1"},
            }
        ]

        client = WikidataClient()
        mock_iter = mocker.patch.object(
            client, "iter_public_institutions", return_value=iter(sample_sparql_results)
        )

        # Call with empty types list - should be treated as None
        results = list(client.iterate_public_institutions(types=[]))

        mock_iter.assert_called_once()
        call_args = mock_iter.call_args
        # Empty list should be passed as is (query builder handles it)
        assert call_args.kwargs["type"] == []

        assert len(results) == 1
