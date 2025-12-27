"""
Unit tests for normalizers (normalize_public_figure and normalize_public_institution).
"""

from wikidata_collector.models import (
    AccountEntry,
    Identifier,
    PublicFigure,
    PublicInstitution,
    WebsiteEntry,
)
from wikidata_collector.normalizers.figure_normalizer import normalize_public_figure
from wikidata_collector.normalizers.institution_normalizer import normalize_public_institution


class TestPublicFigureModel:
    """Test PublicFigure model validation and edge cases."""

    def test_minimal_public_figure(self):
        """Test creating PublicFigure with minimal required fields."""
        figure = PublicFigure(id="Q42")

        assert figure.id == "Q42"
        assert figure.entity_kind == "public_figure"
        assert figure.name is None
        assert figure.aliases == []
        assert figure.nationalities == []
        assert figure.professions == []

    def test_public_figure_with_all_fields(self):
        """Test creating PublicFigure with all fields populated."""
        figure = PublicFigure(
            id="Q42",
            entity_kind="public_figure",
            name="Douglas Adams",
            aliases=["Douglas Noël Adams"],
            description="English writer",
            birthday="1952-03-11T00:00:00Z",
            deathday="2001-05-11T00:00:00Z",
            gender="male",
            nationalities=["United Kingdom"],
            professions=["writer", "humorist"],
            place_of_birth="Cambridge",
            place_of_death="Santa Barbara",
            residence=["London"],
            website=[
                WebsiteEntry(
                    url="https://example.com",
                    source="wikidata",
                    retrieved_at="2024-01-01T00:00:00Z",
                )
            ],
            accounts=[
                AccountEntry(
                    platform="twitter",
                    handle="@test",
                    source="wikidata",
                    retrieved_at="2024-01-01T00:00:00Z",
                )
            ],
            affiliations=["Affiliation 1"],
            notable_works=["The Hitchhiker's Guide to the Galaxy"],
            awards=["Award 1"],
            identifiers=[Identifier(scheme="VIAF", id="12345")],
            image=["https://example.com/image.jpg"],
            updated_at="2024-01-01T00:00:00Z",
        )

        assert figure.id == "Q42"
        assert figure.name == "Douglas Adams"
        assert len(figure.aliases) == 1
        assert len(figure.nationalities) == 1
        assert len(figure.professions) == 2
        assert figure.gender == "male"

    def test_public_figure_empty_lists_default(self):
        """Test that list fields default to empty lists."""
        figure = PublicFigure(id="Q1")

        assert isinstance(figure.aliases, list)
        assert isinstance(figure.nationalities, list)
        assert isinstance(figure.professions, list)
        assert isinstance(figure.website, list)
        assert isinstance(figure.accounts, list)
        assert len(figure.aliases) == 0


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

        assert isinstance(result, PublicFigure)
        assert result.id == "Q42"
        assert result.name == "Douglas Adams"
        assert result.description == "English writer"
        assert result.entity_kind == "public_figure"
        assert result.birthday == "1952-03-11T00:00:00Z"

    def test_with_expanded_data(self, sample_expanded_data):
        """Test normalization with expanded data."""
        item = {
            "person": {"value": "http://www.wikidata.org/entity/Q42"},
            "personLabel": {"value": "Douglas Adams"},
            "description": {"value": "English writer"},
        }

        result = normalize_public_figure(item, sample_expanded_data)

        assert result.nationalities == ["United Kingdom"]
        assert result.professions == ["writer", "humorist"]
        assert len(result.website) == 1
        assert result.website[0].url == "https://www.douglasadams.com"
        assert result.aliases == ["Douglas Noël Adams"]
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

        handles = {(acc.platform, acc.handle) for acc in result.accounts}
        assert ("twitter", "@testuser") in handles
        assert ("instagram", "@testuser_inst") in handles
        assert ("youtube", "testchannel") in handles

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

        assert result.nationalities == ["United States"]
        assert result.professions == ["Actor"]
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

        assert isinstance(result, PublicFigure)
        assert result.nationalities == []
        assert result.professions == []
        assert len(result.website) == 0


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

        expanded_data = {
            "aliases": [],
            "types": ["Organization"],
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
            "aliases": ["Alternative Name"],
            "types": ["Government Agency"],
            "country": ["United States"],
            "country_code": ["USA"],
            "jurisdiction": ["Federal"],
            "founded": ["2000-01-01"],
            "legal_form": ["Public Agency"],
            "headquarters": ["Washington, D.C."],
            "headquarters_coords": [{"lat": 38.9072, "lon": -77.0369}],
            "website": [
                {
                    "url": "https://example.org",
                    "source": "wikidata",
                    "retrieved_at": "2024-01-15T10:00:00Z",
                }
            ],
            "official_language": ["English"],
            "logo": ["https://example.org/logo.png"],
            "budget": ["1000000"],
            "parent_institution": ["Parent Org"],
            "sector": [],
            "affiliations": ["Affiliate 1"],
            "accounts": [],
        }

        result = normalize_public_institution(item, expanded_data)

        assert result.types == ["Government Agency"]
        assert result.country == ["USA"]
        assert result.jurisdiction == ["Federal"]
        assert result.founded == "2000-01-01"
        assert len(result.headquarters_coords) == 1
        assert result.headquarters_coords[0].lat == 38.9072
        assert len(result.website) == 1

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

        handles = {(acc.platform, acc.handle) for acc in result.accounts}
        assert ("twitter", "@testorg") in handles

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

        handles = {(acc.platform, acc.handle) for acc in result.accounts}
        assert ("youtube", "videoorgchannel") in handles

    def test_without_expanded_data(self):
        """Test normalization without expanded data."""
        item = {
            "institution": {"value": "http://www.wikidata.org/entity/Q123"},
            "institutionLabel": {"value": "Test Org"},
            "jurisdictionLabel": {"value": "State"},
        }

        result = normalize_public_institution(item, None)

        assert isinstance(result, PublicInstitution)
        assert result.jurisdiction == ["State"]

    def test_minimal_institution(self):
        """Test creating PublicInstitution with minimal required fields."""
        institution = PublicInstitution(id="Q456")

        assert institution.id == "Q456"
        assert institution.entity_kind == "public_institution"
        assert institution.name is None
        assert institution.aliases == []
        assert institution.country == []
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

        assert result.founded == "1850-06-15T00:00:00Z"

    def test_type_from_item_when_no_expanded_types(self):
        """Test extracting type from SPARQL item when expanded_data has no types."""
        item = {
            "institution": {"value": "http://www.wikidata.org/entity/Q111"},
            "institutionLabel": {"value": "Some Institution"},
            "type": {"value": "http://www.wikidata.org/entity/Q7278"},
            "typeLabel": {"value": "political party"},
        }

        expanded_data = {
            "aliases": [],
            "types": [],  # Empty - should use item's type
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

        handles = {(acc.platform, acc.handle) for acc in result.accounts}
        assert ("twitter", "@orgtwitter") in handles
        assert ("instagram", "@orginsta") in handles
        assert ("facebook", "orgfacebook") in handles
        assert ("youtube", "orgyoutube") in handles
        assert ("tiktok", "@orgtiktok") in handles
        assert len(result.accounts) == 5

    def test_institution_with_multiple_headquarters_coords(self):
        """Test institution with multiple headquarters coordinates."""
        item = {
            "institution": {"value": "http://www.wikidata.org/entity/Q222"},
            "institutionLabel": {"value": "Multi-location Org"},
        }

        expanded_data = {
            "aliases": [],
            "types": [],
            "country": [],
            "country_code": [],
            "jurisdiction": [],
            "founded": [],
            "legal_form": [],
            "headquarters": ["Location 1", "Location 2"],
            "headquarters_coords": [
                {"lat": 40.7128, "lon": -74.0060},
                {"lat": 51.5074, "lon": -0.1278},
            ],
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

        assert len(result.headquarters) == 2
        assert len(result.headquarters_coords) == 2
        assert result.headquarters_coords[0].lat == 40.7128
        assert result.headquarters_coords[1].lon == -0.1278

    def test_invalid_coordinates_ignored(self):
        """Test that invalid coordinates are ignored."""
        item = {
            "institution": {"value": "http://www.wikidata.org/entity/Q333"},
            "institutionLabel": {"value": "Test Org"},
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
            "headquarters_coords": [
                {"lat": None, "lon": -74.0060},  # Invalid - missing lat
                {"lat": 51.5074, "lon": None},  # Invalid - missing lon
                None,  # Invalid - None
                "not a dict",  # Invalid - not a dict
            ],
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

        # All invalid coords should be filtered out
        assert len(result.headquarters_coords) == 0


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
        assert result.aliases == []
        assert result.nationalities == []
        assert result.professions == []
        assert result.website == []
        assert result.accounts == []
        assert result.identifiers == []
        assert result.birthday is None
        assert result.deathday is None
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
        assert result.aliases == []
        assert result.types == []
        assert result.country == []
        assert result.website == []
        assert result.accounts == []
        assert result.founded is None
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
        assert len(result.aliases) == 3
        assert len(result.nationalities) == 3
        assert len(result.professions) == 4
        assert len(result.residence) == 2
        assert len(result.website) == 2
        assert len(result.accounts) == 3
        assert len(result.affiliations) == 3
        assert len(result.notable_works) == 5
        assert len(result.awards) == 2
        assert len(result.identifiers) == 3

    def test_institution_with_multiple_types_and_countries(self):
        """Test institution with multiple types and countries."""
        expanded_data = {
            "aliases": ["Alt Name 1", "Alt Name 2"],
            "types": ["Type 1", "Type 2", "Type 3"],
            "country": ["Country 1", "Country 2"],
            "country_code": ["C1", "C2"],
            "jurisdiction": ["Jurisdiction 1"],
            "founded": ["2000-01-01"],
            "legal_form": ["Form 1"],
            "headquarters": ["HQ 1", "HQ 2"],
            "headquarters_coords": [
                {"lat": 40.0, "lon": -74.0},
                {"lat": 51.0, "lon": -0.1},
            ],
            "website": [
                {"url": "https://org1.com", "source": "wikidata", "retrieved_at": "2024-01-01"},
                {"url": "https://org2.com", "source": "wikidata", "retrieved_at": "2024-01-01"},
                {"url": "https://org3.com", "source": "wikidata", "retrieved_at": "2024-01-01"},
            ],
            "accounts": [
                {
                    "platform": "twitter",
                    "handle": "@org",
                    "source": "wikidata",
                    "retrieved_at": "2024-01-01",
                },
                {
                    "platform": "instagram",
                    "handle": "@org_insta",
                    "source": "wikidata",
                    "retrieved_at": "2024-01-01",
                },
            ],
            "identifiers": [
                {"scheme": "LEI", "id": "ABC123"},
                {"scheme": "GRID", "id": "XYZ789"},
            ],
        }

        item = {
            "institution": {"value": "http://www.wikidata.org/entity/Q666"},
            "institutionLabel": {"value": "Multi-value Institution"},
        }

        result = normalize_public_institution(item, expanded_data)

        # Verify all multi-valued fields are properly populated
        assert len(result.aliases) == 2
        assert len(result.types) == 3
        assert len(result.country) == 2
        assert len(result.headquarters) == 2
        assert len(result.headquarters_coords) == 2
        assert len(result.website) == 3
        assert len(result.accounts) == 2
        # Note: PublicInstitution doesn't have 'identifiers' field in the model
