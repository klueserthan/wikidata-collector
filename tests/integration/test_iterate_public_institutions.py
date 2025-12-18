"""
Integration tests for iterate_public_institutions API.

These tests verify the iterator-based API for streaming public institutions.
They use pytest markers to allow selective execution.
"""

import pytest

from wikidata_collector import WikidataClient, PublicInstitution, InvalidFilterError
from wikidata_collector.exceptions import QueryExecutionError


@pytest.mark.integration
@pytest.mark.iterator
class TestIteratePublicInstitutionsHappyPath:
    """Test iterate_public_institutions happy path scenarios."""
    
    def test_iterate_returns_public_institution_models(self, mocker):
        """Test that iterator yields PublicInstitution model instances."""
        # Mock the underlying iter_public_institutions to return sample SPARQL results
        sample_sparql_results = [
            {
                "institution": {"value": "http://www.wikidata.org/entity/Q123"},
                "institutionLabel": {"value": "Example Government Agency"},
                "description": {"value": "A test government agency"},
                "foundedDate": {"value": "1950-01-01T00:00:00Z"},
                "countryLabel": {"value": "United States"},
                "typeLabel": {"value": "government agency"}
            },
            {
                "institution": {"value": "http://www.wikidata.org/entity/Q456"},
                "institutionLabel": {"value": "Test Public Broadcaster"},
                "description": {"value": "A test broadcasting organization"},
                "foundedDate": {"value": "1970-06-15T00:00:00Z"},
                "countryLabel": {"value": "United Kingdom"},
                "typeLabel": {"value": "public broadcaster"}
            }
        ]
        
        client = WikidataClient()
        mocker.patch.object(
            client,
            'iter_public_institutions',
            return_value=iter(sample_sparql_results)
        )
        
        # Call the iterator API
        results = list(client.iterate_public_institutions(
            country="US",
            types=["government_agency"]
        ))
        
        # Verify results
        assert len(results) == 2
        assert all(isinstance(r, PublicInstitution) for r in results)
        assert results[0].id == "Q123"
        assert results[0].name == "Example Government Agency"
        assert results[1].id == "Q456"
        assert results[1].name == "Test Public Broadcaster"
    
    def test_iterate_with_max_results(self, mocker):
        """Test that max_results limits the number of results."""
        # Create a large list of sample results
        sample_sparql_results = [
            {
                "institution": {"value": f"http://www.wikidata.org/entity/Q{i}"},
                "institutionLabel": {"value": f"Institution {i}"},
                "foundedDate": {"value": "2000-01-01T00:00:00Z"},
            }
            for i in range(100)
        ]
        
        client = WikidataClient()
        mocker.patch.object(
            client,
            'iter_public_institutions',
            return_value=iter(sample_sparql_results)
        )
        
        # Request only 10 results
        results = list(client.iterate_public_institutions(
            country="US",
            max_results=10
        ))
        
        # Verify only 10 results returned
        assert len(results) == 10
        assert all(isinstance(r, PublicInstitution) for r in results)
    
    def test_iterate_with_country_filter(self, mocker):
        """Test iteration with country filter."""
        sample_sparql_results = [
            {
                "institution": {"value": "http://www.wikidata.org/entity/Q100"},
                "institutionLabel": {"value": "German Institution"},
                "foundedDate": {"value": "1990-01-01T00:00:00Z"},
                "countryLabel": {"value": "Germany"},
            }
        ]
        
        client = WikidataClient()
        mock_iter = mocker.patch.object(
            client,
            'iter_public_institutions',
            return_value=iter(sample_sparql_results)
        )
        
        # Call with country filter
        results = list(client.iterate_public_institutions(
            country="Germany",
            lang="en"
        ))
        
        # Verify the underlying iterator was called with correct parameters
        mock_iter.assert_called_once_with(
            country="Germany",
            type=None,
            jurisdiction=None,
            lang="en"
        )
        
        assert len(results) == 1
    
    def test_iterate_with_types_filter(self, mocker):
        """Test iteration with types filter."""
        sample_sparql_results = [
            {
                "institution": {"value": "http://www.wikidata.org/entity/Q200"},
                "institutionLabel": {"value": "Political Party Example"},
                "typeLabel": {"value": "political party"},
            }
        ]
        
        client = WikidataClient()
        mock_iter = mocker.patch.object(
            client,
            'iter_public_institutions',
            return_value=iter(sample_sparql_results)
        )
        
        # Call with types filter
        results = list(client.iterate_public_institutions(
            types=["political_party", "government_agency"],
            lang="en"
        ))
        
        # Verify the underlying iterator was called with correct parameters
        mock_iter.assert_called_once()
        call_args = mock_iter.call_args
        assert call_args.kwargs['type'] == ["political_party", "government_agency"]
        
        assert len(results) == 1
    
    def test_iterate_with_jurisdiction_filter(self, mocker):
        """Test iteration with jurisdiction filter."""
        sample_sparql_results = [
            {
                "institution": {"value": "http://www.wikidata.org/entity/Q300"},
                "institutionLabel": {"value": "State Agency"},
                "jurisdictionLabel": {"value": "California"},
            }
        ]
        
        client = WikidataClient()
        mock_iter = mocker.patch.object(
            client,
            'iter_public_institutions',
            return_value=iter(sample_sparql_results)
        )
        
        # Call with jurisdiction filter
        results = list(client.iterate_public_institutions(
            jurisdiction="California",
            lang="en"
        ))
        
        # Verify the underlying iterator was called with correct parameters
        mock_iter.assert_called_once_with(
            country=None,
            type=None,
            jurisdiction="California",
            lang="en"
        )
        
        assert len(results) == 1
    
    def test_iterate_with_combined_filters(self, mocker):
        """Test iteration with multiple filters combined."""
        sample_sparql_results = [
            {
                "institution": {"value": "http://www.wikidata.org/entity/Q400"},
                "institutionLabel": {"value": "US Government Agency"},
                "description": {"value": "Federal agency"},
                "countryLabel": {"value": "United States"},
                "typeLabel": {"value": "government agency"},
                "jurisdictionLabel": {"value": "United States"},
            }
        ]
        
        client = WikidataClient()
        mock_iter = mocker.patch.object(
            client,
            'iter_public_institutions',
            return_value=iter(sample_sparql_results)
        )
        
        # Call with combined filters
        results = list(client.iterate_public_institutions(
            country="US",
            types=["government_agency"],
            jurisdiction="Q30",
            lang="en"
        ))
        
        # Verify the underlying iterator was called with all filters
        mock_iter.assert_called_once_with(
            country="US",
            type=["government_agency"],
            jurisdiction="Q30",
            lang="en"
        )
        
        assert len(results) == 1
        assert results[0].name == "US Government Agency"


@pytest.mark.integration
@pytest.mark.iterator
class TestIteratePublicInstitutionsEdgeCases:
    """Test edge cases and error handling for iterate_public_institutions."""
    
    def test_iterate_empty_results(self, mocker):
        """Test iteration with no matching results."""
        client = WikidataClient()
        mocker.patch.object(
            client,
            'iter_public_institutions',
            return_value=iter([])
        )
        
        # Call the iterator with filters that return no results
        results = list(client.iterate_public_institutions(
            country="NonexistentCountry",
            types=["nonexistent_type"]
        ))
        
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
            client,
            'iter_public_institutions',
            side_effect=lambda **kwargs: error_generator()
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
            client,
            'iter_public_institutions',
            side_effect=lambda **kwargs: error_generator()
        )
        
        with pytest.raises(InvalidFilterError) as exc_info:
            list(client.iterate_public_institutions(country="Q!!!invalid"))
        
        assert "Invalid filter parameters" in str(exc_info.value)
    
    def test_iterate_without_filters(self, mocker):
        """Test iteration without any filters."""
        sample_sparql_results = [
            {
                "institution": {"value": "http://www.wikidata.org/entity/Q1"},
                "institutionLabel": {"value": "Institution 1"},
                "foundedDate": {"value": "2000-01-01T00:00:00Z"},
            }
        ]
        
        client = WikidataClient()
        mocker.patch.object(
            client,
            'iter_public_institutions',
            return_value=iter(sample_sparql_results)
        )
        
        # Call without filters
        results = list(client.iterate_public_institutions())
        
        assert len(results) == 1
        assert results[0].id == "Q1"
    
    def test_max_results_one(self, mocker):
        """Test with max_results=1."""
        sample_sparql_results = [
            {
                "institution": {"value": "http://www.wikidata.org/entity/Q1"},
                "institutionLabel": {"value": "Institution 1"},
            },
            {
                "institution": {"value": "http://www.wikidata.org/entity/Q2"},
                "institutionLabel": {"value": "Institution 2"},
            }
        ]
        
        client = WikidataClient()
        mocker.patch.object(
            client,
            'iter_public_institutions',
            return_value=iter(sample_sparql_results)
        )
        
        results = list(client.iterate_public_institutions(max_results=1))
        
        assert len(results) == 1
        assert results[0].id == "Q1"
    
    def test_country_iso_code_filter(self, mocker):
        """Test with country as ISO code."""
        sample_sparql_results = [
            {
                "institution": {"value": "http://www.wikidata.org/entity/Q999"},
                "institutionLabel": {"value": "US Institution"},
                "countryLabel": {"value": "United States"},
            }
        ]
        
        client = WikidataClient()
        mock_iter = mocker.patch.object(
            client,
            'iter_public_institutions',
            return_value=iter(sample_sparql_results)
        )
        
        # Call with ISO code
        results = list(client.iterate_public_institutions(country="USA"))
        
        # Verify the ISO code was passed
        mock_iter.assert_called_once()
        call_args = mock_iter.call_args
        assert call_args.kwargs['country'] == "USA"
        
        assert len(results) == 1
    
    def test_country_qid_filter(self, mocker):
        """Test with country as QID."""
        sample_sparql_results = [
            {
                "institution": {"value": "http://www.wikidata.org/entity/Q888"},
                "institutionLabel": {"value": "UK Institution"},
                "countryLabel": {"value": "United Kingdom"},
            }
        ]
        
        client = WikidataClient()
        mock_iter = mocker.patch.object(
            client,
            'iter_public_institutions',
            return_value=iter(sample_sparql_results)
        )
        
        # Call with QID
        results = list(client.iterate_public_institutions(country="Q145"))
        
        # Verify the QID was passed
        mock_iter.assert_called_once()
        call_args = mock_iter.call_args
        assert call_args.kwargs['country'] == "Q145"
        
        assert len(results) == 1
    
    def test_types_with_mapped_keys(self, mocker):
        """Test types filter with mapped keys."""
        sample_sparql_results = [
            {
                "institution": {"value": "http://www.wikidata.org/entity/Q777"},
                "institutionLabel": {"value": "Party Example"},
                "typeLabel": {"value": "political party"},
            }
        ]
        
        client = WikidataClient()
        mock_iter = mocker.patch.object(
            client,
            'iter_public_institutions',
            return_value=iter(sample_sparql_results)
        )
        
        # Call with mapped type keys
        results = list(client.iterate_public_institutions(
            types=["political_party", "municipality"]
        ))
        
        # Verify the types were passed
        mock_iter.assert_called_once()
        call_args = mock_iter.call_args
        assert call_args.kwargs['type'] == ["political_party", "municipality"]
        
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
            client,
            'iter_public_institutions',
            return_value=iter(sample_sparql_results)
        )
        
        # Call with empty types list - should be treated as None
        results = list(client.iterate_public_institutions(types=[]))
        
        mock_iter.assert_called_once()
        call_args = mock_iter.call_args
        # Empty list should be passed as is (query builder handles it)
        assert call_args.kwargs['type'] == []
        
        assert len(results) == 1
