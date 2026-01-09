"""
Unit tests for models (PublicFigure* and PublicInstitution* classes).
"""

from datetime import datetime, timezone

from wikidata_collector.models import (
    PublicFigureNormalizedRecord,
    PublicFigureWikiRecord,
    PublicInstitutionNormalizedRecord,
    PublicInstitutionWikiRecord,
)


class TestPublicFigureWikiRecord:
    """Test PublicFigureWikiRecord model validation and edge cases."""

    def test_minimal_wiki_record(self):
        """Test creating PublicFigureWikiRecord with minimal required fields."""
        record = PublicFigureWikiRecord(qid="Q42", name="Douglas Adams")

        assert record.qid == "Q42"
        assert record.entity_kind == "public_figure"
        assert record.name == "Douglas Adams"
        assert record.description is None
        assert record.birth_date is None
        assert record.gender is None

    def test_wiki_record_from_wikidata(self):
        """Test creating PublicFigureWikiRecord from Wikidata item."""
        item = {
            "person": {"value": "http://www.wikidata.org/entity/Q42"},
            "personLabel": {"value": "Douglas Adams"},
            "description": {"value": "English writer"},
            "birthDate": {"value": "1952-03-11T00:00:00Z"},
            "deathDate": {"value": "2001-05-11T00:00:00Z"},
            "genderLabel": {"value": "male"},
            "countryLabel": {"value": "United Kingdom"},
            "occupationLabel": {"value": "writer"},
            "image": {"value": "https://example.com/image.jpg"},
            "twitterHandle": {"value": "@douglasadams"},
        }

        record = PublicFigureWikiRecord.from_wikidata(item)

        assert record.qid == "Q42"
        assert record.name == "Douglas Adams"
        assert record.description == "English writer"
        assert record.birth_date == datetime(1952, 3, 11, tzinfo=timezone.utc)
        assert record.death_date == datetime(2001, 5, 11, tzinfo=timezone.utc)
        assert record.gender == "male"
        assert record.country == "United Kingdom"
        assert record.occupation == "writer"
        assert record.twitter_handle == "@douglasadams"

    def test_wiki_record_from_wikidata_missing_person(self):
        """Test that from_wikidata raises KeyError when person field is missing."""
        item = {
            "personLabel": {"value": "Test Person"},
        }

        try:
            PublicFigureWikiRecord.from_wikidata(item)
            assert False, "Should have raised KeyError"
        except KeyError as e:
            assert "person" in str(e).lower()

    def test_wiki_record_from_wikidata_partial_data(self):
        """Test from_wikidata with only required fields."""
        item = {
            "person": {"value": "http://www.wikidata.org/entity/Q999"},
            "personLabel": {"value": "Minimal Person"},
        }

        record = PublicFigureWikiRecord.from_wikidata(item)

        assert record.qid == "Q999"
        assert record.name == "Minimal Person"
        assert record.description is None
        assert record.twitter_handle is None


class TestPublicFigureNormalizedRecord:
    """Test PublicFigureNormalizedRecord model validation and edge cases."""

    def test_normalized_record_from_wiki_record(self):
        """Test creating PublicFigureNormalizedRecord from WikiRecord."""
        wiki_record = PublicFigureWikiRecord(
            qid="Q42",
            name="Douglas Adams",
            description="English writer",
            birth_date=datetime(1952, 3, 11, tzinfo=timezone.utc),
            gender="male",
            country="United Kingdom",
            occupation="writer",
            twitter_handle="@douglasadams",
        )

        normalized = PublicFigureNormalizedRecord.from_wikidata_record(wiki_record)

        assert normalized.qid == "Q42"
        assert normalized.name == "Douglas Adams"
        assert normalized.description == "English writer"
        assert normalized.gender == "male"
        assert normalized.countries == ["United Kingdom"]
        assert normalized.occupations == ["writer"]
        assert len(normalized.accounts) == 1
        assert normalized.accounts[0].platform == "twitter"
        assert normalized.accounts[0].handle == "@douglasadams"

    def test_normalized_record_empty_lists(self):
        """Test that list fields default to empty lists."""
        wiki_record = PublicFigureWikiRecord(qid="Q1", name="Test Person")
        normalized = PublicFigureNormalizedRecord.from_wikidata_record(wiki_record)

        assert isinstance(normalized.countries, list)
        assert isinstance(normalized.occupations, list)
        assert isinstance(normalized.accounts, list)
        assert isinstance(normalized.websites, list)
        assert len(normalized.countries) == 0
        assert len(normalized.accounts) == 0

    def test_add_from_wikidata_record(self):
        """Test adding data from multiple wiki records."""
        # Create initial record
        wiki_record1 = PublicFigureWikiRecord(
            qid="Q42",
            name="Douglas Adams",
            country="United Kingdom",
            occupation="writer",
            twitter_handle="@douglasadams",
        )
        normalized = PublicFigureNormalizedRecord.from_wikidata_record(wiki_record1)

        # Add another record with additional data
        wiki_record2 = PublicFigureWikiRecord(
            qid="Q42",
            name="Douglas Adams",
            country="United States",
            occupation="humorist",
            instagram_handle="@douglasadams_insta",
        )
        updated = PublicFigureNormalizedRecord.add_from_wikidata_record(normalized, wiki_record2)

        assert len(updated.countries) == 2
        assert "United Kingdom" in updated.countries
        assert "United States" in updated.countries
        assert len(updated.occupations) == 2
        assert "writer" in updated.occupations
        assert "humorist" in updated.occupations
        assert len(updated.accounts) == 2

    def test_add_from_wikidata_record_no_duplicates(self):
        """Test that add_from_wikidata_record doesn't create duplicates."""
        wiki_record1 = PublicFigureWikiRecord(
            qid="Q42",
            name="Douglas Adams",
            country="United Kingdom",
            twitter_handle="@douglasadams",
        )
        normalized = PublicFigureNormalizedRecord.from_wikidata_record(wiki_record1)

        # Add same data again
        wiki_record2 = PublicFigureWikiRecord(
            qid="Q42",
            name="Douglas Adams",
            country="United Kingdom",
            twitter_handle="@douglasadams",
        )
        updated = PublicFigureNormalizedRecord.add_from_wikidata_record(normalized, wiki_record2)

        assert len(updated.countries) == 1
        assert len(updated.accounts) == 1


class TestPublicInstitutionWikiRecord:
    """Test PublicInstitutionWikiRecord model validation and edge cases."""

    def test_minimal_wiki_record(self):
        """Test creating PublicInstitutionWikiRecord with minimal required fields."""
        record = PublicInstitutionWikiRecord(qid="Q123", name="Test Organization")

        assert record.qid == "Q123"
        assert record.entity_kind == "public_institution"
        assert record.name == "Test Organization"
        assert record.description is None
        assert record.founded_date is None

    def test_wiki_record_from_wikidata(self):
        """Test creating PublicInstitutionWikiRecord from Wikidata item."""
        item = {
            "institution": {"value": "http://www.wikidata.org/entity/Q123"},
            "institutionLabel": {"value": "Test Organization"},
            "description": {"value": "A test organization"},
            "foundedDate": {"value": "2000-01-01T00:00:00Z"},
            "dissolvedDate": {"value": "2020-12-31T00:00:00Z"},
            "countryLabel": {"value": "United States"},
            "typeLabel": {"value": "Government Agency"},
            "image": {"value": "https://example.org/logo.png"},
            "twitterHandle": {"value": "@testorg"},
        }

        record = PublicInstitutionWikiRecord.from_wikidata(item)

        assert record.qid == "Q123"
        assert record.name == "Test Organization"
        assert record.description == "A test organization"
        assert record.founded_date == datetime(2000, 1, 1, tzinfo=timezone.utc)
        assert record.dissolved_date == datetime(2020, 12, 31, tzinfo=timezone.utc)
        assert record.country == "United States"
        assert record.type == "Government Agency"
        assert record.twitter_handle == "@testorg"

    def test_wiki_record_from_wikidata_missing_institution(self):
        """Test that from_wikidata raises KeyError when institution field is missing."""
        item = {
            "institutionLabel": {"value": "Test Organization"},
        }

        try:
            PublicInstitutionWikiRecord.from_wikidata(item)
            assert False, "Should have raised KeyError"
        except KeyError as e:
            assert "institution" in str(e).lower()

    def test_wiki_record_from_wikidata_partial_data(self):
        """Test from_wikidata with only required fields."""
        item = {
            "institution": {"value": "http://www.wikidata.org/entity/Q999"},
            "institutionLabel": {"value": "Minimal Institution"},
        }

        record = PublicInstitutionWikiRecord.from_wikidata(item)

        assert record.qid == "Q999"
        assert record.name == "Minimal Institution"
        assert record.description is None
        assert record.twitter_handle is None


class TestPublicInstitutionNormalizedRecord:
    """Test PublicInstitutionNormalizedRecord model validation and edge cases."""

    def test_normalized_record_from_wiki_record(self):
        """Test creating PublicInstitutionNormalizedRecord from WikiRecord."""
        wiki_record = PublicInstitutionWikiRecord(
            qid="Q123",
            name="Test Organization",
            description="A test organization",
            founded_date=datetime(2000, 1, 1, tzinfo=timezone.utc),
            country="United States",
            type="Government Agency",
            twitter_handle="@testorg",
        )

        normalized = PublicInstitutionNormalizedRecord.from_wikidata_record(wiki_record)

        assert normalized.qid == "Q123"
        assert normalized.name == "Test Organization"
        assert normalized.description == "A test organization"
        assert normalized.founded_date == datetime(2000, 1, 1, tzinfo=timezone.utc)
        assert normalized.countries == ["United States"]
        assert normalized.types == ["Government Agency"]
        assert len(normalized.accounts) == 1
        assert normalized.accounts[0].platform == "twitter"
        assert normalized.accounts[0].handle == "@testorg"

    def test_normalized_record_empty_lists(self):
        """Test that list fields default to empty lists."""
        wiki_record = PublicInstitutionWikiRecord(qid="Q1", name="Test Institution")
        normalized = PublicInstitutionNormalizedRecord.from_wikidata_record(wiki_record)

        assert isinstance(normalized.countries, list)
        assert isinstance(normalized.types, list)
        assert isinstance(normalized.accounts, list)
        assert isinstance(normalized.websites, list)
        assert len(normalized.countries) == 0
        assert len(normalized.accounts) == 0

    def test_add_from_wikidata_record(self):
        """Test adding data from multiple wiki records."""
        # Create initial record
        wiki_record1 = PublicInstitutionWikiRecord(
            qid="Q123",
            name="Test Organization",
            country="United States",
            type="Government Agency",
            twitter_handle="@testorg",
        )
        normalized = PublicInstitutionNormalizedRecord.from_wikidata_record(wiki_record1)

        # Add another record with additional data
        wiki_record2 = PublicInstitutionWikiRecord(
            qid="Q123",
            name="Test Organization",
            country="Canada",
            type="Public Agency",
            instagram_handle="@testorg_insta",
        )
        updated = PublicInstitutionNormalizedRecord.add_from_wikidata_record(
            normalized, wiki_record2
        )

        assert len(updated.countries) == 2
        assert "United States" in updated.countries
        assert "Canada" in updated.countries
        assert len(updated.types) == 2
        assert "Government Agency" in updated.types
        assert "Public Agency" in updated.types
        assert len(updated.accounts) == 2

    def test_add_from_wikidata_record_no_duplicates(self):
        """Test that add_from_wikidata_record doesn't create duplicates."""
        wiki_record1 = PublicInstitutionWikiRecord(
            qid="Q123",
            name="Test Organization",
            country="United States",
            twitter_handle="@testorg",
        )
        normalized = PublicInstitutionNormalizedRecord.from_wikidata_record(wiki_record1)

        # Add same data again
        wiki_record2 = PublicInstitutionWikiRecord(
            qid="Q123",
            name="Test Organization",
            country="United States",
            twitter_handle="@testorg",
        )
        updated = PublicInstitutionNormalizedRecord.add_from_wikidata_record(
            normalized, wiki_record2
        )

        assert len(updated.countries) == 1
        assert len(updated.accounts) == 1


class TestSocialMediaHandles:
    """Test social media handle extraction."""

    def test_all_social_media_platforms_figure(self):
        """Test extraction of all supported social media platforms for figures."""
        wiki_record = PublicFigureWikiRecord(
            qid="Q42",
            name="Test Person",
            twitter_handle="@twitter",
            instagram_handle="@instagram",
            facebook_handle="facebook",
            youtube_handle="youtube",
        )

        normalized = PublicFigureNormalizedRecord.from_wikidata_record(wiki_record)

        platforms = {acc.platform for acc in normalized.accounts}
        assert platforms == {"twitter", "instagram", "facebook", "youtube"}
        assert len(normalized.accounts) == 4

    def test_all_social_media_platforms_institution(self):
        """Test extraction of all supported social media platforms for institutions."""
        wiki_record = PublicInstitutionWikiRecord(
            qid="Q123",
            name="Test Org",
            twitter_handle="@twitter",
            instagram_handle="@instagram",
            facebook_handle="facebook",
            youtube_handle="youtube",
        )

        normalized = PublicInstitutionNormalizedRecord.from_wikidata_record(wiki_record)

        platforms = {acc.platform for acc in normalized.accounts}
        assert platforms == {"twitter", "instagram", "facebook", "youtube"}
        assert len(normalized.accounts) == 4

    def test_no_social_media_handles(self):
        """Test when no social media handles are present."""
        wiki_record = PublicFigureWikiRecord(qid="Q42", name="Test Person")
        normalized = PublicFigureNormalizedRecord.from_wikidata_record(wiki_record)

        assert len(normalized.accounts) == 0


class TestEdgeCases:
    """Test edge cases for models."""

    def test_invalid_date_handling(self):
        """Test that invalid dates are handled gracefully."""
        item = {
            "person": {"value": "http://www.wikidata.org/entity/Q42"},
            "personLabel": {"value": "Test Person"},
            "birthDate": {"value": "invalid-date"},
        }

        record = PublicFigureWikiRecord.from_wikidata(item)
        assert record.birth_date is None

    def test_missing_qid_extraction(self):
        """Test handling of malformed person URL."""
        item = {
            "person": {"value": "http://www.wikidata.org/entity/"},
            "personLabel": {"value": "Test Person"},
        }

        record = PublicFigureWikiRecord.from_wikidata(item)
        assert record.qid == ""

    def test_multiple_account_merging(self):
        """Test merging of accounts from multiple records."""
        wiki_record1 = PublicFigureWikiRecord(
            qid="Q42",
            name="Test Person",
            twitter_handle="@user1",
        )
        normalized = PublicFigureNormalizedRecord.from_wikidata_record(wiki_record1)

        wiki_record2 = PublicFigureWikiRecord(
            qid="Q42",
            name="Test Person",
            instagram_handle="@user1_insta",
        )
        updated = PublicFigureNormalizedRecord.add_from_wikidata_record(normalized, wiki_record2)

        assert len(updated.accounts) == 2
        handles = {(acc.platform, acc.handle) for acc in updated.accounts}
        assert ("twitter", "@user1") in handles
        assert ("instagram", "@user1_insta") in handles

    def test_overwrite_single_value_fields(self):
        """Test that single-value fields get overwritten when None."""
        wiki_record1 = PublicFigureWikiRecord(
            qid="Q42",
            name="Test Person",
            description=None,
        )
        normalized = PublicFigureNormalizedRecord.from_wikidata_record(wiki_record1)

        wiki_record2 = PublicFigureWikiRecord(
            qid="Q42",
            name="Test Person",
            description="New description",
            gender="female",
        )
        updated = PublicFigureNormalizedRecord.add_from_wikidata_record(normalized, wiki_record2)

        assert updated.description == "New description"
        assert updated.gender == "female"

    def test_preserve_existing_single_value_fields(self):
        """Test that existing single-value fields are preserved."""
        wiki_record1 = PublicFigureWikiRecord(
            qid="Q42",
            name="Test Person",
            description="Original description",
            gender="male",
        )
        normalized = PublicFigureNormalizedRecord.from_wikidata_record(wiki_record1)

        wiki_record2 = PublicFigureWikiRecord(
            qid="Q42",
            name="Test Person",
            description="New description",
            gender="female",
        )
        updated = PublicFigureNormalizedRecord.add_from_wikidata_record(normalized, wiki_record2)

        # Existing values should be preserved
        assert updated.description == "Original description"
        assert updated.gender == "male"
