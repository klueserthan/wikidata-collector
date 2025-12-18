"""Tests for WikidataClient iterator methods."""

from unittest.mock import patch

from wikidata_collector.client import DEFAULT_PAGE_SIZE


class TestIterPublicFigures:
    """Test iter_public_figures method."""

    def test_iter_single_page(self, wikidata_client):
        """Test iteration with results fitting in a single page."""
        # Mock data for one page
        mock_results = [
            {"person": {"value": "http://www.wikidata.org/entity/Q1"}},
            {"person": {"value": "http://www.wikidata.org/entity/Q2"}},
        ]

        with patch.object(
            wikidata_client, "get_public_figures", return_value=(mock_results, "direct")
        ):
            results = list(wikidata_client.iter_public_figures(nationality=["Q30"]))

            assert len(results) == 2
            assert results[0] == mock_results[0]
            assert results[1] == mock_results[1]

    def test_iter_multiple_pages(self, wikidata_client):
        """Test iteration across multiple pages."""
        # Create mock data for two pages
        page1_results = [
            {"person": {"value": f"http://www.wikidata.org/entity/Q{i}"}}
            for i in range(1, DEFAULT_PAGE_SIZE + 1)
        ]
        page2_results = [
            {"person": {"value": "http://www.wikidata.org/entity/Q100"}},
        ]

        call_count = 0

        def mock_get_figures(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (page1_results, "direct")
            else:
                return (page2_results, "direct")

        with patch.object(wikidata_client, "get_public_figures", side_effect=mock_get_figures):
            results = list(wikidata_client.iter_public_figures(nationality=["Q30"]))

            assert len(results) == DEFAULT_PAGE_SIZE + 1
            assert call_count == 2

    def test_iter_empty_results(self, wikidata_client):
        """Test iteration with no results."""
        with patch.object(wikidata_client, "get_public_figures", return_value=([], "direct")):
            results = list(wikidata_client.iter_public_figures(nationality=["Q30"]))

            assert len(results) == 0

    def test_iter_custom_page_size(self, wikidata_client):
        """Test iteration with custom page size."""
        # Return 3 results (less than page size of 5) - should only call once
        mock_results = [
            {"person": {"value": f"http://www.wikidata.org/entity/Q{i}"}}
            for i in range(1, 4)  # 3 results
        ]

        with patch.object(
            wikidata_client, "get_public_figures", return_value=(mock_results, "direct")
        ) as mock:
            results = list(wikidata_client.iter_public_figures(nationality=["Q30"], page_size=5))

            # Verify it was called with the custom page size
            mock.assert_called_once()
            assert mock.call_args[1]["limit"] == 5
            assert len(results) == 3

    def test_iter_with_filters(self, wikidata_client):
        """Test iteration with various filters."""
        mock_results = [{"person": {"value": "http://www.wikidata.org/entity/Q1"}}]

        with patch.object(
            wikidata_client, "get_public_figures", return_value=(mock_results, "direct")
        ) as mock:
            list(
                wikidata_client.iter_public_figures(
                    birthday_from="1990-01-01",
                    birthday_to="2000-12-31",
                    nationality=["Q30"],
                    profession=["Q33999"],
                )
            )

            # Verify filters were passed through
            call_kwargs = mock.call_args[1]
            assert call_kwargs["birthday_from"] == "1990-01-01"
            assert call_kwargs["birthday_to"] == "2000-12-31"
            assert call_kwargs["nationality"] == ["Q30"]
            assert call_kwargs["profession"] == ["Q33999"]


class TestIterPublicInstitutions:
    """Test iter_public_institutions method."""

    def test_iter_single_page(self, wikidata_client):
        """Test iteration with results fitting in a single page."""
        mock_results = [
            {"institution": {"value": "http://www.wikidata.org/entity/Q1"}},
            {"institution": {"value": "http://www.wikidata.org/entity/Q2"}},
        ]

        with patch.object(
            wikidata_client, "get_public_institutions", return_value=(mock_results, "direct")
        ):
            results = list(wikidata_client.iter_public_institutions(country="Q30"))

            assert len(results) == 2
            assert results[0] == mock_results[0]
            assert results[1] == mock_results[1]

    def test_iter_multiple_pages(self, wikidata_client):
        """Test iteration across multiple pages."""
        page1_results = [
            {"institution": {"value": f"http://www.wikidata.org/entity/Q{i}"}}
            for i in range(1, DEFAULT_PAGE_SIZE + 1)
        ]
        page2_results = [
            {"institution": {"value": "http://www.wikidata.org/entity/Q100"}},
        ]

        call_count = 0

        def mock_get_institutions(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (page1_results, "direct")
            else:
                return (page2_results, "direct")

        with patch.object(
            wikidata_client, "get_public_institutions", side_effect=mock_get_institutions
        ):
            results = list(wikidata_client.iter_public_institutions(country="Q30"))

            assert len(results) == DEFAULT_PAGE_SIZE + 1
            assert call_count == 2

    def test_iter_empty_results(self, wikidata_client):
        """Test iteration with no results."""
        with patch.object(wikidata_client, "get_public_institutions", return_value=([], "direct")):
            results = list(wikidata_client.iter_public_institutions(country="Q30"))

            assert len(results) == 0

    def test_iter_custom_page_size(self, wikidata_client):
        """Test iteration with custom page size."""
        # Return 8 results (less than page size of 10) - should only call once
        mock_results = [
            {"institution": {"value": f"http://www.wikidata.org/entity/Q{i}"}}
            for i in range(1, 9)  # 8 results
        ]

        with patch.object(
            wikidata_client, "get_public_institutions", return_value=(mock_results, "direct")
        ) as mock:
            results = list(wikidata_client.iter_public_institutions(country="Q30", page_size=10))

            # Verify it was called with the custom page size
            mock.assert_called_once()
            assert mock.call_args[1]["limit"] == 10
            assert len(results) == 8

    def test_iter_with_filters(self, wikidata_client):
        """Test iteration with various filters."""
        mock_results = [{"institution": {"value": "http://www.wikidata.org/entity/Q1"}}]

        with patch.object(
            wikidata_client, "get_public_institutions", return_value=(mock_results, "direct")
        ) as mock:
            list(
                wikidata_client.iter_public_institutions(
                    country="Q30", type=["Q327333"], jurisdiction="Q30"
                )
            )

            # Verify filters were passed through
            call_kwargs = mock.call_args[1]
            assert call_kwargs["country"] == "Q30"
            assert call_kwargs["type"] == ["Q327333"]
            assert call_kwargs["jurisdiction"] == "Q30"


class TestDefaultPageSize:
    """Test DEFAULT_PAGE_SIZE constant."""

    def test_default_page_size_is_15(self):
        """Verify the default page size is 15 as specified."""
        assert DEFAULT_PAGE_SIZE == 15
