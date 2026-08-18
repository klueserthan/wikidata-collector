"""Unit tests for `normalize_bindings`, the single row-to-record folding path.

SPARQL expands one entity into one row per value combination, ordered by QID.
`normalize_bindings` folds consecutive same-QID rows back into one record. It is
the seam every entity kind shares, so its edge cases are tested directly rather
than only through the pipeline.
"""

import logging
from datetime import datetime, timezone

from tests.conftest import figure_binding, organization_binding
from wikidata_collector.models import (
    PublicFigureNormalizedRecord,
    PublicFigureWikiRecord,
    PublicOrganizationNormalizedRecord,
    PublicOrganizationWikiRecord,
)
from wikidata_collector.models import normalize_bindings as normalize

FIGURE_FAMILY = (PublicFigureWikiRecord, PublicFigureNormalizedRecord)
ORGANIZATION_FAMILY = (PublicOrganizationWikiRecord, PublicOrganizationNormalizedRecord)


class TestFolding:
    """How rows collapse into records."""

    def test_empty_bindings_produce_no_records(self):
        """An empty page yields an empty list, not a placeholder record."""
        assert normalize([], *FIGURE_FAMILY) == []

    def test_a_single_row_becomes_one_record(self):
        """One row in, one normalized record out."""
        records = normalize([figure_binding("Q42", "Douglas Adams")], *FIGURE_FAMILY)

        assert [record.qid for record in records] == ["Q42"]
        assert records[0].name == "Douglas Adams"

    def test_consecutive_rows_for_one_entity_fold_into_one_record(self):
        """Row expansion over occupations collapses into a single record."""
        records = normalize(
            [
                figure_binding("Q42", occupationLabel="writer"),
                figure_binding("Q42", occupationLabel="humorist"),
                figure_binding("Q42", occupationLabel="screenwriter"),
            ],
            *FIGURE_FAMILY,
        )

        assert len(records) == 1
        assert records[0].occupations == ["writer", "humorist", "screenwriter"]

    def test_multi_valued_fields_across_axes_are_all_collected(self):
        """Country and occupation expand independently and both accumulate."""
        records = normalize(
            [
                figure_binding("Q42", countryLabel="United Kingdom", occupationLabel="writer"),
                figure_binding("Q42", countryLabel="Ireland", occupationLabel="writer"),
            ],
            *FIGURE_FAMILY,
        )

        assert records[0].countries == ["United Kingdom", "Ireland"]
        assert records[0].occupations == ["writer"]

    def test_distinct_entities_become_distinct_records_in_order(self):
        """Different QIDs stay separate and keep the endpoint's ordering."""
        records = normalize(
            [
                figure_binding("Q1"),
                figure_binding("Q42"),
                figure_binding("Q7"),
                figure_binding("Q7"),
            ],
            *FIGURE_FAMILY,
        )

        assert [record.qid for record in records] == ["Q1", "Q42", "Q7"]

    def test_non_consecutive_rows_for_one_entity_do_not_fold(self):
        """Folding is by adjacency; an interleaved QID splits the entity in two.

        Keyset pagination orders by QID precisely so this cannot happen upstream.
        The test pins the behaviour so a change in ordering assumptions is visible.
        """
        records = normalize(
            [
                figure_binding("Q42", occupationLabel="writer"),
                figure_binding("Q7"),
                figure_binding("Q42", occupationLabel="humorist"),
            ],
            *FIGURE_FAMILY,
        )

        assert [record.qid for record in records] == ["Q42", "Q7", "Q42"]

    def test_last_entity_is_flushed(self):
        """The trailing in-progress record is emitted, not dropped."""
        records = normalize([figure_binding("Q1"), figure_binding("Q2")], *FIGURE_FAMILY)

        assert [record.qid for record in records] == ["Q1", "Q2"]


class TestMalformedRows:
    """Rows the endpoint should not have produced."""

    def test_a_row_without_an_entity_iri_is_skipped(self, caplog):
        """A row missing `person` is dropped with a warning, not fatal."""
        with caplog.at_level(logging.WARNING):
            records = normalize(
                [{"personLabel": {"value": "No IRI"}}, figure_binding("Q42")],
                *FIGURE_FAMILY,
            )

        assert [record.qid for record in records] == ["Q42"]
        assert "Failed to parse record" in caplog.text

    def test_a_row_without_a_label_is_skipped(self, caplog):
        """`name` is required, so an unlabelled row cannot become a record."""
        with caplog.at_level(logging.WARNING):
            records = normalize(
                [{"person": {"value": "http://www.wikidata.org/entity/Q42"}}],
                *FIGURE_FAMILY,
            )

        assert records == []
        assert "Failed to parse record" in caplog.text

    def test_an_unparseable_date_does_not_lose_the_record(self, caplog):
        """A bad birthDate is logged and nulled; the entity still comes through."""
        with caplog.at_level(logging.WARNING):
            records = normalize([figure_binding("Q42", birthDate="not-a-date")], *FIGURE_FAMILY)

        assert [record.qid for record in records] == ["Q42"]
        assert records[0].birth_date is None


class TestOrganizationFamily:
    """The same folding contract holds for the other entity kind."""

    def test_consecutive_rows_fold_and_collect_types(self):
        """Organization rows expand over P31 types and fold into one record."""
        records = normalize(
            [
                organization_binding("Q1", typeLabel="international organization"),
                organization_binding("Q1", typeLabel="intergovernmental organization"),
                organization_binding("Q2", countryLabel="Germany"),
            ],
            *ORGANIZATION_FAMILY,
        )

        assert [record.qid for record in records] == ["Q1", "Q2"]
        assert records[0].types == [
            "international organization",
            "intergovernmental organization",
        ]
        assert records[1].countries == ["Germany"]

    def test_a_row_without_an_organization_iri_is_skipped(self, caplog):
        """The organization family drops malformed rows the same way."""
        with caplog.at_level(logging.WARNING):
            records = normalize(
                [{"organizationLabel": {"value": "No IRI"}}, organization_binding("Q1")],
                *ORGANIZATION_FAMILY,
            )

        assert [record.qid for record in records] == ["Q1"]

    def test_multi_country_rows_accumulate_into_countries(self):
        """Country rows expand over P17 and fold into one record's country list."""
        records = normalize(
            [
                organization_binding("Q1", countryLabel="Germany"),
                organization_binding("Q1", countryLabel="France"),
            ],
            *ORGANIZATION_FAMILY,
        )

        assert records[0].countries == ["Germany", "France"]

    def test_account_handles_merge_without_duplicates(self):
        """Repeating a handle across expanded rows must not duplicate the account."""
        records = normalize(
            [
                organization_binding(
                    "Q1", instagramHandle="un", typeLabel="international organization"
                ),
                organization_binding(
                    "Q1", instagramHandle="un", typeLabel="intergovernmental organization"
                ),
                organization_binding(
                    "Q1", twitterHandle="unitednations", typeLabel="intergovernmental organization"
                ),
            ],
            *ORGANIZATION_FAMILY,
        )

        accounts = {(account.platform, account.handle) for account in records[0].accounts}
        assert accounts == {("instagram", "un"), ("twitter", "unitednations")}

    def test_scalar_fields_keep_the_first_rows_value(self):
        """description, image, and founded_date are first-wins, not last-wins."""
        records = normalize(
            [
                organization_binding(
                    "Q1",
                    description="original description",
                    image="https://example.org/first.jpg",
                    foundedDate="1945-06-26T00:00:00Z",
                    typeLabel="international organization",
                ),
                organization_binding(
                    "Q1",
                    description="a different description",
                    image="https://example.org/second.jpg",
                    foundedDate="1946-01-01T00:00:00Z",
                    typeLabel="intergovernmental organization",
                ),
            ],
            *ORGANIZATION_FAMILY,
        )

        assert records[0].description == "original description"
        assert records[0].image == "https://example.org/first.jpg"
        assert records[0].founded_date == datetime(1945, 6, 26, tzinfo=timezone.utc)

    def test_non_consecutive_rows_for_one_entity_do_not_fold(self):
        """Folding is by adjacency; an interleaved QID splits the entity in two.

        Mirrors the figure family's pinned behaviour: keyset pagination orders by
        QID precisely so this cannot happen upstream.
        """
        records = normalize(
            [
                organization_binding("Q1", typeLabel="international organization"),
                organization_binding("Q2"),
                organization_binding("Q1", typeLabel="intergovernmental organization"),
            ],
            *ORGANIZATION_FAMILY,
        )

        assert [record.qid for record in records] == ["Q1", "Q2", "Q1"]


class TestSocialAccounts:
    """Handles are folded into deduplicated account entries."""

    def test_handles_from_several_rows_merge_without_duplicates(self):
        """Repeating a handle across expanded rows must not duplicate the account."""
        records = normalize(
            [
                figure_binding("Q42", instagramHandle="adams", occupationLabel="writer"),
                figure_binding("Q42", instagramHandle="adams", occupationLabel="humorist"),
                figure_binding("Q42", twitterHandle="dna", occupationLabel="humorist"),
            ],
            *FIGURE_FAMILY,
        )

        accounts = {(account.platform, account.handle) for account in records[0].accounts}
        assert accounts == {("instagram", "adams"), ("twitter", "dna")}

    def test_every_supported_platform_is_collected(self):
        """All five platform properties map onto account entries."""
        records = normalize(
            [
                figure_binding(
                    "Q42",
                    instagramHandle="ig",
                    twitterHandle="tw",
                    facebookHandle="fb",
                    youtubeHandle="yt",
                    tiktokHandle="tt",
                )
            ],
            *FIGURE_FAMILY,
        )

        assert {account.platform for account in records[0].accounts} == {
            "instagram",
            "twitter",
            "facebook",
            "youtube",
            "tiktok",
        }
