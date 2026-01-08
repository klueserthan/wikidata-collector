"""
Integration tests for iterate_public_figures API.

These tests verify the iterator-based API for streaming public figures.
They use pytest markers to allow selective execution.
"""

import pytest

from wikidata_collector import InvalidFilterError, PublicFigureWikiRecord, WikidataClient
from wikidata_collector.exceptions import QueryExecutionError


@pytest.mark.integration
@pytest.mark.iterator
class TestIteratePublicFiguresHappyPath:
    """Test iterate_public_figures happy path scenarios."""

    def test_iterate_returns_public_figure_models(self, mocker):
        """Test that iterator yields PublicFigure model instances."""
        # Mock the underlying iter_public_figures to return sample SPARQL results
        sample_sparql_results = [
            {
                "person": {"value": "http://www.wikidata.org/entity/Q42"},
                "personLabel": {"value": "Douglas Adams"},
                "description": {"value": "English writer"},
                "birthDate": {"value": "1952-03-11T00:00:00Z"},
                "countryLabel": {"value": "United Kingdom"},
                "occupationLabel": {"value": "writer"},
            },
            {
                "person": {"value": "http://www.wikidata.org/entity/Q5593"},
                "personLabel": {"value": "Jane Austen"},
                "description": {"value": "English novelist"},
                "birthDate": {"value": "1775-12-16T00:00:00Z"},
                "countryLabel": {"value": "United Kingdom"},
                "occupationLabel": {"value": "novelist"},
            },
        ]

        client = WikidataClient()
        mocker.patch.object(client, "iter_public_figures", return_value=iter(sample_sparql_results))

        # Call the iterator API
        results = list(
            client.iterate_public_figures(birthday_from="1700-01-01", nationality="United Kingdom")
        )

        # Verify results
        assert len(results) == 2
        assert all(isinstance(r, PublicFigureWikiRecord) for r in results)
        assert results[0].id == "Q42"
        assert results[0].name == "Douglas Adams"
        assert results[1].id == "Q5593"
        assert results[1].name == "Jane Austen"

    def test_iterate_with_max_results(self, mocker):
        """Test that max_results limits the number of results."""
        # Create a large list of sample results
        sample_sparql_results = [
            {
                "person": {"value": f"http://www.wikidata.org/entity/Q{i}"},
                "personLabel": {"value": f"Person {i}"},
                "birthDate": {"value": "1990-01-01T00:00:00Z"},
            }
            for i in range(100)
        ]

        client = WikidataClient()
        mocker.patch.object(client, "iter_public_figures", return_value=iter(sample_sparql_results))

        # Request only 10 results
        results = list(client.iterate_public_figures(birthday_from="1990-01-01", max_results=10))

        # Verify only 10 results returned
        assert len(results) == 10
        assert all(isinstance(r, PublicFigureWikiRecord) for r in results)

    def test_iterate_with_birthday_filters(self, mocker):
        """Test iteration with birthday filters."""
        sample_sparql_results = [
            {
                "person": {"value": "http://www.wikidata.org/entity/Q100"},
                "personLabel": {"value": "Modern Person"},
                "birthDate": {"value": "1995-06-15T00:00:00Z"},
            }
        ]

        client = WikidataClient()
        mock_iter = mocker.patch.object(
            client, "iter_public_figures", return_value=iter(sample_sparql_results)
        )

        # Call with birthday filters
        results = list(
            client.iterate_public_figures(
                birthday_from="1990-01-01", birthday_to="2000-12-31", lang="en"
            )
        )

        # Verify the underlying iterator was called with correct parameters
        mock_iter.assert_called_once_with(
            birthday_from="1990-01-01", birthday_to="2000-12-31", nationality=None, lang="en"
        )

        assert len(results) == 1
        assert results[0].birth_date == "1995-06-15T00:00:00Z"

    def test_iterate_with_nationality_filter(self, mocker):
        """Test iteration with nationality filter."""
        sample_sparql_results = [
            {
                "person": {"value": "http://www.wikidata.org/entity/Q200"},
                "personLabel": {"value": "American Person"},
                "birthDate": {"value": "1980-01-01T00:00:00Z"},
                "countryLabel": {"value": "United States"},
            }
        ]

        client = WikidataClient()
        mock_iter = mocker.patch.object(
            client, "iter_public_figures", return_value=iter(sample_sparql_results)
        )

        # Call with nationality filter
        results = list(client.iterate_public_figures(nationality="United States", lang="en"))

        # Verify the underlying iterator was called with correct parameters
        mock_iter.assert_called_once()
        call_args = mock_iter.call_args
        assert call_args.kwargs["nationality"] == "United States"

        assert len(results) == 1
        assert results[0].countries == ["United States"]


@pytest.mark.integration
@pytest.mark.iterator
class TestIteratePublicFiguresEdgeCases:
    """Test edge cases and error handling for iterate_public_figures."""

    def test_iterate_empty_results(self, mocker):
        """Test iteration with no matching results."""
        client = WikidataClient()
        mocker.patch.object(client, "iter_public_figures", return_value=iter([]))

        # Call the iterator with filters that return no results
        results = list(
            client.iterate_public_figures(
                birthday_from="3000-01-01",  # Future date
                nationality="NonexistentCountry",
            )
        )

        # Verify empty results
        assert len(results) == 0
        assert isinstance(results, list)

    def test_invalid_birthday_from_format(self):
        """Test that invalid birthday_from format raises InvalidFilterError."""
        client = WikidataClient()

        with pytest.raises(InvalidFilterError) as exc_info:
            list(client.iterate_public_figures(birthday_from="invalid-date"))

        assert "Invalid birthday_from format" in str(exc_info.value)

    def test_invalid_birthday_to_format(self):
        """Test that invalid birthday_to format raises InvalidFilterError."""
        client = WikidataClient()

        with pytest.raises(InvalidFilterError) as exc_info:
            list(client.iterate_public_figures(birthday_to="2000/12/31"))

        assert "Invalid birthday_to format" in str(exc_info.value)

    def test_invalid_date_february_30(self):
        """Test that invalid dates like February 30 raise InvalidFilterError."""
        client = WikidataClient()

        with pytest.raises(InvalidFilterError) as exc_info:
            list(client.iterate_public_figures(birthday_from="2000-02-30"))

        assert "Invalid birthday_from format" in str(exc_info.value)

    def test_invalid_date_april_31(self):
        """Test that invalid dates like April 31 raise InvalidFilterError."""
        client = WikidataClient()

        with pytest.raises(InvalidFilterError) as exc_info:
            list(client.iterate_public_figures(birthday_to="2000-04-31"))

        assert "Invalid birthday_to format" in str(exc_info.value)

    def test_valid_leap_year_date(self, mocker):
        """Test that February 29 in a leap year is accepted."""
        client = WikidataClient()

        sample_sparql_results = [
            {
                "person": {"value": "http://www.wikidata.org/entity/Q1"},
                "personLabel": {"value": "Leap Year Person"},
                "birthDate": {"value": "2000-02-29T00:00:00Z"},
            }
        ]

        mocker.patch.object(client, "iter_public_figures", return_value=iter(sample_sparql_results))

        # Should not raise an error
        results = list(client.iterate_public_figures(birthday_from="2000-02-29"))
        assert len(results) == 1

    def test_invalid_max_results_zero(self):
        """Test that max_results=0 raises InvalidFilterError."""
        client = WikidataClient()

        with pytest.raises(InvalidFilterError) as exc_info:
            list(client.iterate_public_figures(max_results=0))

        assert "max_results must be >= 1" in str(exc_info.value)

    def test_invalid_max_results_negative(self):
        """Test that negative max_results raises InvalidFilterError."""
        client = WikidataClient()

        with pytest.raises(InvalidFilterError) as exc_info:
            list(client.iterate_public_figures(max_results=-5))

        assert "max_results must be >= 1" in str(exc_info.value)

    def test_query_execution_error_propagated(self, mocker):
        """Test that QueryExecutionError from underlying iterator is propagated."""
        client = WikidataClient()

        # Mock iter_public_figures to raise QueryExecutionError
        def error_generator():
            raise QueryExecutionError("Upstream SPARQL endpoint unavailable")
            yield  # pragma: no cover

        mocker.patch.object(
            client, "iter_public_figures", side_effect=lambda **kwargs: error_generator()
        )

        with pytest.raises(QueryExecutionError) as exc_info:
            list(client.iterate_public_figures(birthday_from="1990-01-01"))

        assert "Upstream SPARQL endpoint unavailable" in str(exc_info.value)

    def test_value_error_converted_to_invalid_filter_error(self, mocker):
        """Test that ValueError from query builder is converted to InvalidFilterError."""
        client = WikidataClient()

        # Mock iter_public_figures to raise ValueError
        def error_generator():
            raise ValueError("Invalid QID format")
            yield  # pragma: no cover

        mocker.patch.object(
            client, "iter_public_figures", side_effect=lambda **kwargs: error_generator()
        )

        with pytest.raises(InvalidFilterError) as exc_info:
            list(client.iterate_public_figures(nationality="Q!!!invalid"))

        assert "Invalid filter parameters" in str(exc_info.value)

    def test_iterate_without_filters(self, mocker):
        """Test iteration without any filters."""
        sample_sparql_results = [
            {
                "person": {"value": "http://www.wikidata.org/entity/Q1"},
                "personLabel": {"value": "Person 1"},
                "birthDate": {"value": "1950-01-01T00:00:00Z"},
            }
        ]

        client = WikidataClient()
        mocker.patch.object(client, "iter_public_figures", return_value=iter(sample_sparql_results))

        # Call without filters
        results = list(client.iterate_public_figures())

        assert len(results) == 1
        assert results[0].id == "Q1"

    def test_max_results_one(self, mocker):
        """Test with max_results=1."""
        sample_sparql_results = [
            {
                "person": {"value": "http://www.wikidata.org/entity/Q1"},
                "personLabel": {"value": "Person 1"},
            },
            {
                "person": {"value": "http://www.wikidata.org/entity/Q2"},
                "personLabel": {"value": "Person 2"},
            },
        ]

        client = WikidataClient()
        mocker.patch.object(client, "iter_public_figures", return_value=iter(sample_sparql_results))

        results = list(client.iterate_public_figures(max_results=1))

        assert len(results) == 1
        assert results[0].id == "Q1"
