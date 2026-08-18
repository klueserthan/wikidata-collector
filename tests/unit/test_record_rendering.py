"""Unit tests for `generate_pretty_string` on both normalized record families.

These renderings are what operators read when eyeballing a collection run, so a
field silently dropping out of the output is a real regression.
"""

from datetime import datetime

from wikidata_collector.models import (
    AccountEntry,
    PublicFigureNormalizedRecord,
    PublicInstitutionNormalizedRecord,
    WebsiteEntry,
)


def _account(platform: str, handle: str) -> AccountEntry:
    """Build an AccountEntry with fixed provenance."""
    return AccountEntry(
        platform=platform, handle=handle, source="wikidata", retrieved_at="2026-01-01T00:00:00Z"
    )


def _website(url: str) -> WebsiteEntry:
    """Build a WebsiteEntry with fixed provenance."""
    return WebsiteEntry(url=url, source="wikidata", retrieved_at="2026-01-01T00:00:00Z")


class TestPublicFigureRendering:
    """Rendering a normalized public figure."""

    def test_minimal_record_renders_only_the_headline(self):
        """With nothing but identity, the output is a single line."""
        rendered = PublicFigureNormalizedRecord(qid="Q42", name="Douglas Adams")

        assert rendered.generate_pretty_string() == "Public Figure: Douglas Adams (Q42)"

    def test_every_populated_field_appears(self):
        """A fully populated record surfaces each field exactly once."""
        record = PublicFigureNormalizedRecord(
            qid="Q42",
            name="Douglas Adams",
            description="English writer and humorist",
            birth_date=datetime(1952, 3, 11),
            death_date=datetime(2001, 5, 11),
            gender="male",
            image="https://example.org/adams.jpg",
            countries=["United Kingdom", "Ireland"],
            occupations=["writer", "humorist"],
            websites=[_website("https://douglasadams.com")],
            accounts=[_account("instagram", "adams"), _account("twitter", "dna")],
        )

        rendered = record.generate_pretty_string()

        assert "Public Figure: Douglas Adams (Q42)" in rendered
        assert "Description: English writer and humorist" in rendered
        assert "Birth Date: 1952-03-11T00:00:00" in rendered
        assert "Death Date: 2001-05-11T00:00:00" in rendered
        assert "Gender: male" in rendered
        assert "Image: https://example.org/adams.jpg" in rendered
        assert "Countries: United Kingdom, Ireland" in rendered
        assert "Occupations: writer, humorist" in rendered
        assert "- https://douglasadams.com (source: wikidata)" in rendered
        assert "- instagram: adams (source: wikidata)" in rendered
        assert "- twitter: dna (source: wikidata)" in rendered

    def test_empty_collections_do_not_emit_headings(self):
        """No accounts means no dangling "Accounts:" heading."""
        rendered = PublicFigureNormalizedRecord(
            qid="Q42", name="Douglas Adams"
        ).generate_pretty_string()

        assert "Accounts:" not in rendered
        assert "Websites:" not in rendered
        assert "Countries:" not in rendered


class TestPublicInstitutionRendering:
    """Rendering a normalized public institution."""

    def test_minimal_record_renders_only_the_headline(self):
        """With nothing but identity, the output is a single line."""
        rendered = PublicInstitutionNormalizedRecord(qid="Q1065", name="United Nations")

        assert rendered.generate_pretty_string() == "Public Institution: United Nations (Q1065)"

    def test_every_populated_field_appears(self):
        """A fully populated record surfaces each field exactly once."""
        record = PublicInstitutionNormalizedRecord(
            qid="Q1065",
            name="United Nations",
            description="intergovernmental organization",
            founded_date=datetime(1945, 10, 24),
            dissolved_date=datetime(2100, 1, 1),
            image="https://example.org/un.jpg",
            countries=["United States"],
            types=["international organization"],
            websites=[_website("https://un.org")],
            accounts=[_account("twitter", "UN")],
        )

        rendered = record.generate_pretty_string()

        assert "Public Institution: United Nations (Q1065)" in rendered
        assert "Description: intergovernmental organization" in rendered
        assert "Founded Date: 1945-10-24T00:00:00" in rendered
        assert "Dissolved Date: 2100-01-01T00:00:00" in rendered
        assert "Countries: United States" in rendered
        assert "Types: international organization" in rendered
        assert "- https://un.org (source: wikidata)" in rendered
        assert "Social Media Accounts:" in rendered
        assert "- twitter: UN" in rendered

    def test_empty_collections_do_not_emit_headings(self):
        """No accounts means no dangling "Social Media Accounts:" heading."""
        rendered = PublicInstitutionNormalizedRecord(
            qid="Q1065", name="United Nations"
        ).generate_pretty_string()

        assert "Social Media Accounts:" not in rendered
        assert "Websites:" not in rendered
        assert "Types:" not in rendered
