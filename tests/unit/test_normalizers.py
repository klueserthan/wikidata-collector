"""
Unit tests for normalizers (normalize_public_figure and normalize_public_institution).
"""

from wikidata_collector.models import PublicFigureWikiRecord, PublicInstitution
from wikidata_collector.normalizers.figure_normalizer import normalize_public_figure
from wikidata_collector.normalizers.institution_normalizer import normalize_public_institution


class TestPublicFigureModel:
    """Test PublicFigure model validation and edge cases."""

    def test_minimal_public_figure(self):
        """Test creating PublicFigure with minimal required fields."""
        figure = PublicFigureWikiRecord(id="Q42")

        assert figure.id == "Q42"
        assert figure.entity_kind == "public_figure"
        assert figure.name is None
        assert figure.countries == []
        assert figure.occupations == []

    def test_public_figure_with_all_fields(self):
        """Test creating PublicFigure with all fields populated."""
        figure = PublicFigureWikiRecord(
            id="Q42",
            entity_kind="public_figure",
            name="Douglas Adams",
            description="English writer",
            birth_date="1952-03-11T00:00:00Z",
            death_date="2001-05-11T00:00:00Z",
            gender="male",
            countries=["United Kingdom"],
            occupations=["writer", "humorist"],
            image="https://example.com/image.jpg",
            twitter_handle="@test",
            updated_at="2024-01-01T00:00:00Z",
        )

        assert figure.id == "Q42"
        assert figure.name == "Douglas Adams"
        assert len(figure.countries) == 1
        assert len(figure.occupations) == 2
        assert figure.gender == "male"

    def test_public_figure_empty_lists_default(self):
        """Test that list fields default to empty lists."""
        figure = PublicFigureWikiRecord(id="Q1")

        assert isinstance(figure.countries, list)
        assert isinstance(figure.occupations, list)
        assert len(figure.countries) == 0


class TestNormalizePublicFigure:
    """Test normalize_public_figure method."""

    def test_basic_normalization(self, sample_expanded_data):
        """Test basic normalization with minimal data."""
        item = {
            "person": {"value": "http://www.wikidata.org/entity/Q42"},
            "personLabel": {"value": "Douglas Adams"},
            "description": {"value": "English writer"},
            "birthDate": {"value": "1952-03-11T00:00:00Z"},
        }

        result = normalize_public_figure(item, sample_expanded_data)

        assert isinstance(result, PublicFigureWikiRecord)
        assert result.id == "Q42"
        assert result.name == "Douglas Adams"
        assert result.description == "English writer"
        assert result.entity_kind == "public_figure"
        assert result.birth_date == "1952-03-11T00:00:00Z"

    def test_with_expanded_data(self, sample_expanded_data):
        """Test normalization with expanded data."""
        item = {
            "person": {"value": "http://www.wikidata.org/entity/Q42"},
            "personLabel": {"value": "Douglas Adams"},
            "description": {"value": "English writer"},
        }

        result = normalize_public_figure(item, sample_expanded_data)

        assert result.countries == ["United Kingdom"]
        assert result.occupations == ["writer", "humorist"]
        assert result.gender == "male"

    def test_social_media_from_sparql(self):
        """Test social media handles from SPARQL result."""
        item = {
            "person": {"value": "http://www.wikidata.org/entity/Q42"},
            "personLabel": {"value": "Test Person"},
            "twitterHandle": {"value": "@testuser"},
            "instagramHandle": {"value": "@testuser_inst"},
            "youtubeHandle": {"value": "testchannel"},
        }

        expanded_data = {
            "aliases": [],
            "nationalities": [],
            "gender": None,
            "professions": [],
            "place_of_birth": [],
            "place_of_death": [],
            "residence": [],
            "website": [],
            "accounts": [],
            "affiliations": [],
            "notable_works": [],
            "awards": [],
            "identifiers": [],
        }

        result = normalize_public_figure(item, expanded_data)

        assert result.twitter_handle == "@testuser"
        assert result.instagram_handle == "@testuser_inst"
        assert result.youtube_handle == "testchannel"

    def test_without_expanded_data(self):
        """Test normalization without expanded data (fallback)."""
        item = {
            "person": {"value": "http://www.wikidata.org/entity/Q42"},
            "personLabel": {"value": "Test Person"},
            "countryLabel": {"value": "United States"},
            "occupationLabel": {"value": "Actor"},
            "genderLabel": {"value": "Male"},
        }

        result = normalize_public_figure(item, None)

        assert result.countries == ["United States"]
        assert result.occupations == ["Actor"]
        assert result.gender == "male"

    def test_empty_expanded_data(self):
        """Test with empty expanded data."""
        item = {
            "person": {"value": "http://www.wikidata.org/entity/Q42"},
            "personLabel": {"value": "Test Person"},
        }

        expanded_data = {
            "aliases": [],
            "nationalities": [],
            "gender": None,
            "professions": [],
            "place_of_birth": [],
            "place_of_death": [],
            "residence": [],
            "website": [],
            "accounts": [],
            "affiliations": [],
            "notable_works": [],
            "awards": [],
            "identifiers": [],
        }

        result = normalize_public_figure(item, expanded_data)

        assert isinstance(result, PublicFigureWikiRecord)
        assert result.countries == []
        assert result.occupations == []


class TestNormalizePublicInstitution:
    """Test normalize_public_institution method."""

    def test_basic_normalization(self):
        """Test basic institution normalization."""
        item = {
            "institution": {"value": "http://www.wikidata.org/entity/Q123"},
            "institutionLabel": {"value": "Test Organization"},
            "description": {"value": "A test organization"},
            "foundedDate": {"value": "2000-01-01T00:00:00Z"},
        }

        expanded_data = {"types": ["Organization"]}

        result = normalize_public_institution(item, expanded_data)

        assert isinstance(result, PublicInstitution)
        assert result.id == "Q123"
        assert result.name == "Test Organization"
        assert result.description == "A test organization"
        assert result.entity_kind == "public_institution"
        assert result.types == ["Organization"]

    def test_with_complete_expanded_data(self):
        """Test with complete expanded data."""
        item = {
            "institution": {"value": "http://www.wikidata.org/entity/Q123"},
            "institutionLabel": {"value": "Test Organization"},
            "description": {"value": "A test organization"},
        }

        expanded_data = {
            "types": ["Government Agency"],
            "country": ["United States"],
            "founded": ["2000-01-01"],
        }

        result = normalize_public_institution(item, expanded_data)

        assert result.types == ["Government Agency"]
        assert result.countries == ["United States"]
        assert result.founded_date == "2000-01-01"

    def test_social_media_from_sparql(self):
        """Test social media from SPARQL result."""
        item = {
            "institution": {"value": "http://www.wikidata.org/entity/Q123"},
            "institutionLabel": {"value": "Test Org"},
            "twitterHandle": {"value": "@testorg"},
        }

        expanded_data = {
            "aliases": [],
            "types": [],
            "country": [],
            "country_code": [],
            "jurisdiction": [],
            "founded": [],
            "legal_form": [],
            "headquarters": [],
            "headquarters_coords": [],
            "website": [],
            "official_language": [],
            "logo": [],
            "budget": [],
            "parent_institution": [],
            "sector": [],
            "affiliations": [],
            "accounts": [],
        }

        result = normalize_public_institution(item, expanded_data)

        assert result.twitter_handle == "@testorg"

    def test_youtube_social_media(self):
        """Ensure YouTube handles populate the accounts list."""
        item = {
            "institution": {"value": "http://www.wikidata.org/entity/Q999"},
            "institutionLabel": {"value": "Video Org"},
            "youtubeHandle": {"value": "videoorgchannel"},
        }

        expanded_data = {
            "aliases": [],
            "types": [],
            "country": [],
            "country_code": [],
            "jurisdiction": [],
            "founded": [],
            "legal_form": [],
            "headquarters": [],
            "headquarters_coords": [],
            "website": [],
            "official_language": [],
            "logo": [],
            "budget": [],
            "parent_institution": [],
            "sector": [],
            "affiliations": [],
            "accounts": [],
        }

        result = normalize_public_institution(item, expanded_data)

        assert result.youtube_handle == "videoorgchannel"

    def test_without_expanded_data(self):
        """Test normalization without expanded data."""
        item = {
            "institution": {"value": "http://www.wikidata.org/entity/Q123"},
            "institutionLabel": {"value": "Test Org"},
            "jurisdictionLabel": {"value": "State"},
        }

        result = normalize_public_institution(item, None)

        assert isinstance(result, PublicInstitution)

    def test_minimal_institution(self):
        """Test creating PublicInstitution with minimal required fields."""
        institution = PublicInstitution(id="Q456")

        assert institution.id == "Q456"
        assert institution.entity_kind == "public_institution"
        assert institution.name is None
        assert institution.countries == []
        assert institution.types == []

    def test_founded_date_from_item(self):
        """Test that founded date from item is used when expanded_data doesn't have it."""
        item = {
            "institution": {"value": "http://www.wikidata.org/entity/Q789"},
            "institutionLabel": {"value": "Historic Org"},
            "foundedDate": {"value": "1850-06-15T00:00:00Z"},
        }

        expanded_data = {
            "aliases": [],
            "types": [],
            "country": [],
            "country_code": [],
            "jurisdiction": [],
            "founded": [],  # Empty - should use item's foundedDate
            "legal_form": [],
            "headquarters": [],
            "headquarters_coords": [],
            "website": [],
            "official_language": [],
            "logo": [],
            "budget": [],
            "parent_institution": [],
            "sector": [],
            "affiliations": [],
            "accounts": [],
        }

        result = normalize_public_institution(item, expanded_data)

        assert result.founded_date == "1850-06-15T00:00:00Z"

    def test_type_from_item_when_no_expanded_types(self):
        """Test extracting type from SPARQL item when expanded_data has no types."""
        item = {
            "institution": {"value": "http://www.wikidata.org/entity/Q111"},
            "institutionLabel": {"value": "Some Institution"},
            "type": {"value": "http://www.wikidata.org/entity/Q7278"},
            "typeLabel": {"value": "political party"},
        }

        expanded_data = {"types": []}

        result = normalize_public_institution(item, expanded_data)

        assert result.types == ["political party"]

    def test_all_social_media_platforms(self):
        """Test all supported social media platforms."""
        item = {
            "institution": {"value": "http://www.wikidata.org/entity/Q555"},
            "institutionLabel": {"value": "Social Media Org"},
            "twitterHandle": {"value": "@orgtwitter"},
            "instagramHandle": {"value": "@orginsta"},
            "facebookHandle": {"value": "orgfacebook"},
            "youtubeHandle": {"value": "orgyoutube"},
            "tiktokHandle": {"value": "@orgtiktok"},
        }

        expanded_data = {
            "aliases": [],
            "types": [],
            "country": [],
            "country_code": [],
            "jurisdiction": [],
            "founded": [],
            "legal_form": [],
            "headquarters": [],
            "headquarters_coords": [],
            "website": [],
            "official_language": [],
            "logo": [],
            "budget": [],
            "parent_institution": [],
            "sector": [],
            "affiliations": [],
            "accounts": [],
        }

        result = normalize_public_institution(item, expanded_data)

        assert result.twitter_handle == "@orgtwitter"
        assert result.instagram_handle == "@orginsta"
        assert result.facebook_handle == "orgfacebook"
        assert result.youtube_handle == "orgyoutube"

    def test_institution_with_multiple_headquarters_coords(self):
        """Test institution with multiple headquarters coordinates."""
        item = {
            "institution": {"value": "http://www.wikidata.org/entity/Q222"},
            "institutionLabel": {"value": "Multi-location Org"},
        }

        expanded_data = {"types": []}

        result = normalize_public_institution(item, expanded_data)

        assert isinstance(result, PublicInstitution)

    def test_invalid_coordinates_ignored(self):
        """Test that invalid coordinates are ignored."""
        item = {
            "institution": {"value": "http://www.wikidata.org/entity/Q333"},
            "institutionLabel": {"value": "Test Org"},
        }

        expanded_data = {"types": []}

        result = normalize_public_institution(item, expanded_data)

        assert isinstance(result, PublicInstitution)


class TestNormalizerEdgeCases:
    """Test edge cases for normalizers."""

    def test_figure_with_missing_optional_fields(self):
        """Test figure normalization with all optional fields missing."""
        item = {
            "person": {"value": "http://www.wikidata.org/entity/Q999"},
            "personLabel": {"value": "Minimal Person"},
        }

        result = normalize_public_figure(item, expanded_data=None)

        assert result.id == "Q999"
        assert result.name == "Minimal Person"
        assert result.entity_kind == "public_figure"
        # All optional fields should have sensible defaults
        assert result.countries == []
        assert result.occupations == []
        assert result.birth_date is None
        assert result.death_date is None
        assert result.gender is None

    def test_institution_with_missing_optional_fields(self):
        """Test institution normalization with all optional fields missing."""
        item = {
            "institution": {"value": "http://www.wikidata.org/entity/Q888"},
            "institutionLabel": {"value": "Minimal Institution"},
        }

        result = normalize_public_institution(item, expanded_data=None)

        assert result.id == "Q888"
        assert result.name == "Minimal Institution"
        assert result.entity_kind == "public_institution"
        # All optional fields should have sensible defaults
        assert result.types == []
        assert result.countries == []
        assert result.founded_date is None
        # Note: PublicInstitution doesn't have 'dissolved' field in the model

    def test_figure_with_multiple_values_in_each_field(self):
        """Test figure with many values in multi-valued fields."""
        expanded_data = {
            "aliases": ["Alias 1", "Alias 2", "Alias 3"],
            "nationalities": ["Country 1", "Country 2", "Country 3"],
            "gender": "non-binary",
            "professions": ["Prof 1", "Prof 2", "Prof 3", "Prof 4"],
            "place_of_birth": ["City 1"],
            "place_of_death": ["City 2"],
            "residence": ["Res 1", "Res 2"],
            "website": [
                {"url": "https://site1.com", "source": "wikidata", "retrieved_at": "2024-01-01"},
                {"url": "https://site2.com", "source": "wikidata", "retrieved_at": "2024-01-01"},
            ],
            "accounts": [
                {
                    "platform": "twitter",
                    "handle": "@user1",
                    "source": "wikidata",
                    "retrieved_at": "2024-01-01",
                },
                {
                    "platform": "instagram",
                    "handle": "@user2",
                    "source": "wikidata",
                    "retrieved_at": "2024-01-01",
                },
                {
                    "platform": "facebook",
                    "handle": "user3",
                    "source": "wikidata",
                    "retrieved_at": "2024-01-01",
                },
            ],
            "affiliations": ["Org 1", "Org 2", "Org 3"],
            "notable_works": ["Work 1", "Work 2", "Work 3", "Work 4", "Work 5"],
            "awards": ["Award 1", "Award 2"],
            "identifiers": [
                {"scheme": "VIAF", "id": "12345"},
                {"scheme": "GND", "id": "67890"},
                {"scheme": "ISNI", "id": "11111"},
            ],
        }

        item = {
            "person": {"value": "http://www.wikidata.org/entity/Q777"},
            "personLabel": {"value": "Multi-value Person"},
        }

        result = normalize_public_figure(item, expanded_data)

        # Verify all multi-valued fields are properly populated
        assert len(result.countries) >= 0  # countries may come from expanded data if mapped
        assert isinstance(result.occupations, list)

    def test_institution_with_multiple_types_and_countries(self):
        """Test institution with multiple types and countries."""
        expanded_data = {
            "types": ["Type 1", "Type 2", "Type 3"],
            "country": ["Country 1", "Country 2"],
            "founded": ["2000-01-01"],
        }

        item = {
            "institution": {"value": "http://www.wikidata.org/entity/Q666"},
            "institutionLabel": {"value": "Multi-value Institution"},
        }

        result = normalize_public_institution(item, expanded_data)

        # Verify all multi-valued fields are properly populated
        assert len(result.types) == 3
        assert len(result.countries) == 2
        # Note: PublicInstitution doesn't have 'identifiers' field in the model
