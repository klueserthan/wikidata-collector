"""
Unit tests for SPARQL query builders.
"""

import re

import pytest

from wikidata_collector.constants import ORGANIZATION_TYPE_MAPPINGS
from wikidata_collector.query_builders.figures_query_builder import build_public_figures_query
from wikidata_collector.query_builders.organizations_query_builder import (
    build_public_organizations_query,
)


class TestBuildPublicFiguresQuery:
    """Test build_public_figures_query method."""

    def test_basic_query(self):
        """Test basic query without filters."""
        query = build_public_figures_query()

        assert "SELECT ?person" in query
        assert "?person wdt:P31 wd:Q5" in query  # instance of human
        assert "wdt:P569" in query  # date of birth
        assert "ORDER BY ?qidNum" in query  # Keyset pagination ordering
        assert "LIMIT" in query
        assert "OPTIONAL" in query  # Should have optional clauses for outer query

    def test_birthday_filters(self):
        """Test query with birthday filters."""
        query = build_public_figures_query(birthday_from="1950-01-01", birthday_to="2000-12-31")

        assert 'FILTER(?birthDate >= "1950-01-01T00:00:00Z"' in query
        assert 'FILTER(?birthDate <= "2000-12-31T23:59:59Z"' in query

    def test_nationality_filter_qid(self):
        """Test nationality filter with QID."""
        query = build_public_figures_query(
            nationality="Q145"  # United Kingdom QID
        )

        assert "wdt:P27 wd:Q145" in query

    def test_nationality_filter_name(self):
        """Test nationality filter with mapped name."""
        query = build_public_figures_query(nationality="United Kingdom", lang="en")

        # United Kingdom is mapped to Q145 in constants
        assert "wdt:P27 wd:Q145" in query

    def test_profession_filter_qid(self):
        """Test profession filter with QID."""
        query = build_public_figures_query(
            occupations=["Q36180"]  # Writer QID
        )

        assert "wdt:P106 wd:Q36180" in query

    def test_profession_filter_name(self):
        """Test profession filter with mapped name."""
        query = build_public_figures_query(occupations=["writer"], lang="en")

        # writer is mapped to Q36180 in constants
        assert "wdt:P106 wd:Q36180" in query

    def test_multiple_professions(self):
        """Test multiple profession filters."""
        query = build_public_figures_query(
            occupations=["Q36180", "Q33999"]  # Writer and Actor
        )

        assert "wdt:P106 wd:Q36180" in query
        assert "wdt:P106 wd:Q33999" in query

    def test_keyset_pagination(self):
        """Test keyset pagination with QID."""
        query = build_public_figures_query(after_qid="Q100")

        assert 'BIND(xsd:integer(STRAFTER(STR(?person), "/entity/Q")) AS ?qidNum)' in query
        assert "FILTER(?qidNum > 100)" in query

    def test_offset_pagination(self):
        """Test offset pagination (backward compatibility)."""
        query = build_public_figures_query(cursor=50)

        assert "OFFSET 50" in query

    def test_limit(self):
        """Test limit parameter."""
        query = build_public_figures_query(limit=200)

        assert "LIMIT 200" in query  # Pagination now checks distinct QIDs

    def test_language_parameter(self):
        """Test language parameter in SERVICE block."""
        query = build_public_figures_query(lang="fr")

        assert (
            'bd:serviceParam wikibase:language "en"' in query or 'wikibase:language "fr"' in query
        )

    def test_nationality_filter_mapped_name(self):
        """Test nationality filter with mapped country name."""
        query = build_public_figures_query(
            nationality="Germany"  # Maps to Q183
        )

        # Should translate to mapped QID
        assert "wdt:P27 wd:Q183" in query

    def test_nationality_filter_short_code(self):
        """Test nationality filter with short country code."""
        query = build_public_figures_query(
            nationality="US"  # Maps to Q30
        )

        # Should handle US code mapping
        assert "wdt:P27 wd:Q30" in query

    def test_gender_filter_male(self):
        """Test gender filter for male."""
        query = build_public_figures_query(gender="male")

        assert "wdt:P21 wd:Q6581097" in query
        assert "FILTER NOT EXISTS" not in query

    def test_gender_filter_female(self):
        """Test gender filter for female."""
        query = build_public_figures_query(gender="female")

        assert "wdt:P21 wd:Q6581072" in query
        assert "FILTER NOT EXISTS" not in query

    def test_gender_filter_other(self):
        """Test gender filter for other (includes no gender info)."""
        query = build_public_figures_query(gender="other")

        assert "FILTER NOT EXISTS { ?person wdt:P21 wd:Q6581097 }" in query
        assert "FILTER NOT EXISTS { ?person wdt:P21 wd:Q6581072 }" in query
        assert "wdt:P21 wd:Q6581097 ." not in query
        assert "wdt:P21 wd:Q6581072 ." not in query

    def test_gender_filter_qid(self):
        """Test gender filter with a direct QID."""
        query = build_public_figures_query(gender="Q6581097")

        assert "wdt:P21 wd:Q6581097" in query
        assert "FILTER NOT EXISTS" not in query

    def test_gender_filter_invalid_raises_error(self):
        """Test that unknown gender label raises ValueError."""
        with pytest.raises(ValueError, match="Unknown gender"):
            build_public_figures_query(gender="helicopter")

    def test_gender_combined_with_country_and_occupation(self):
        """Test gender combined with country and occupation filters."""
        query = build_public_figures_query(
            nationality="Germany",
            occupations=["politician"],
            gender="female",
        )

        assert "wdt:P27 wd:Q183" in query
        assert "wdt:P106 wd:Q82955" in query
        assert "wdt:P21 wd:Q6581072" in query

    def test_gender_none_no_filter_applied(self):
        """Test that no gender filter is applied when gender=None."""
        query = build_public_figures_query(gender=None)

        assert "wdt:P21 wd:" not in query.split("OPTIONAL")[0]  # not in subquery triple patterns
        assert "FILTER NOT EXISTS" not in query


class TestBuildPublicOrganizationsQuery:
    """Test build_public_organizations_query method.

    ``types`` is a required filter (see live WDQS benchmarks in the PR
    description): an unfiltered P31/P279* subclass-closure scan of the
    organization umbrella (51k subclasses) always times out upstream, so the
    builder refuses to build that query at all.
    """

    def test_basic_query(self):
        """Test basic query with a single type filter."""
        query = build_public_organizations_query(types=["political_party"])

        assert "SELECT ?organization" in query
        assert "SELECT DISTINCT ?organization ?qidNum WHERE" in query
        assert "VALUES ?orgClass { wd:Q7278 }" in query
        assert "?organization wdt:P31/wdt:P279* ?orgClass ." in query
        assert "ORDER BY ?qidNum" in query  # Keyset pagination ordering
        assert "LIMIT" in query
        assert "OPTIONAL" in query  # Should have optional clauses for outer query

    def test_types_none_raises_error(self):
        """types=None is rejected: an unfiltered scan always times out on WDQS."""
        with pytest.raises(ValueError, match="types filter is required"):
            build_public_organizations_query(types=None)

    def test_types_empty_list_raises_error(self):
        """types=[] is rejected the same way as types=None."""
        with pytest.raises(ValueError, match="types filter is required"):
            build_public_organizations_query(types=[])

    def test_types_required_error_names_supported_keys_and_qids(self):
        """The required-types error is actionable: it names the vocabulary and
        that raw QIDs are also accepted, not just the mapped keys."""
        with pytest.raises(ValueError) as exc_info:
            build_public_organizations_query(types=None)

        message = str(exc_info.value)
        assert "political_party" in message  # a sample curated key
        assert "QID" in message

    def test_country_filter_qid(self):
        """Test country filter with QID."""
        query = build_public_organizations_query(
            types=["political_party"],
            country="Q145",  # United Kingdom QID
        )

        assert "?organization wdt:P17 wd:Q145 ." in query

    def test_country_filter_name(self):
        """Test country filter with mapped country name."""
        query = build_public_organizations_query(
            types=["political_party"], country="United Kingdom", lang="en"
        )

        # United Kingdom is mapped to Q145 in constants
        assert "wdt:P17 wd:Q145" in query

    def test_type_filter_mapping(self):
        """Test type filter with mapped type name."""
        query = build_public_organizations_query(types=["political_party"])

        assert "VALUES ?orgClass { wd:Q7278 }" in query  # political_party mapping

    def test_type_filter_qid(self):
        """Test type filter with a raw QID."""
        query = build_public_organizations_query(types=["Q7278"])

        assert "VALUES ?orgClass { wd:Q7278 }" in query

    def test_country_filter_with_qid(self):
        """Test country filter with QID works correctly."""
        query = build_public_organizations_query(types=["political_party"], country="Q30")

        assert "wdt:P17 wd:Q30" in query

    def test_keyset_pagination(self):
        """Test keyset pagination with QID."""
        query = build_public_organizations_query(types=["political_party"], after_qid="Q1000")

        assert 'BIND(xsd:integer(STRAFTER(STR(?organization), "/entity/Q")) AS ?qidNum)' in query
        assert "FILTER(?qidNum > 1000)" in query

    def test_country_filter_iso_code_mapped(self):
        """Test country filter with ISO-like code mapped via constants."""
        query = build_public_organizations_query(types=["political_party"], country="USA")

        # USA is mapped to Q30 in constants
        assert "wdt:P17 wd:Q30" in query

    def test_type_filter_with_unmapped_label_raises_error(self):
        """Test type filter with unmapped label raises error."""
        with pytest.raises(ValueError, match="Unknown organization type"):
            build_public_organizations_query(types=["government agency"], lang="en")

    def test_multiple_types_or_semantics_single_values_clause(self):
        """Multiple types are ORed via one VALUES clause and one property-path
        triple — not the old AND-joined `;`-chained `wdt:P31 wd:Q...` pattern,
        which is semantically wrong (an entity cannot be P31 two different
        classes at once via `;`) and returns nothing on real data."""
        query = build_public_organizations_query(types=["newspaper", "parliament"])

        assert query.count("VALUES ?orgClass {") == 1
        assert "VALUES ?orgClass { wd:Q11032 wd:Q35749 }" in query
        assert query.count("wdt:P31/wdt:P279* ?orgClass") == 1
        # The old AND-joined pattern must be entirely absent.
        assert "wdt:P31 wd:Q11032" not in query
        assert "wdt:P31 wd:Q35749" not in query

    def test_subquery_selects_distinct(self):
        """`SELECT DISTINCT` is mandatory in the subquery: the multi-class
        `wdt:P31/wdt:P279*` property path produces duplicate ?organization
        rows for entities matching more than one VALUES class, and keyset
        pagination ends a page when unique QIDs < limit — without DISTINCT,
        those duplicate rows would silently truncate a page's results."""
        query = build_public_organizations_query(types=["newspaper", "parliament"])

        assert "SELECT DISTINCT ?organization ?qidNum WHERE" in query

    def test_mixed_mapped_key_and_raw_qid_both_land_in_values(self):
        """A mapped key and a raw QID can be combined in the same VALUES list."""
        query = build_public_organizations_query(types=["newspaper", "Q484652"])

        assert "VALUES ?orgClass { wd:Q11032 wd:Q484652 }" in query

    def test_multiple_type_filters(self):
        """Test multiple type filters."""
        query = build_public_organizations_query(
            types=["political_party", "Q327333"]  # mapped key and QID
        )

        assert "VALUES ?orgClass { wd:Q7278 wd:Q327333 }" in query

    def test_multiple_type_filters_combined(self):
        """Test multiple types combined correctly in subquery."""
        query = build_public_organizations_query(types=["political_party", "government_agency"])

        assert "VALUES ?orgClass { wd:Q7278 wd:Q327333 }" in query

    def test_combined_filters(self):
        """Test combining multiple filters."""
        query = build_public_organizations_query(
            country="Q30",  # USA
            types=["government_agency"],
            lang="en",
        )

        assert "wdt:P17 wd:Q30" in query
        assert "VALUES ?orgClass { wd:Q327333 }" in query  # government_agency mapping

    def test_offset_pagination(self):
        """Test offset pagination (backward compatibility)."""
        query = build_public_organizations_query(types=["political_party"], cursor=25)

        assert "OFFSET 25" in query

    def test_limit_parameter(self):
        """Test limit parameter."""
        query = build_public_organizations_query(types=["political_party"], limit=50)

        assert "LIMIT 50" in query  # Pagination now checks distinct QIDs

    def test_optional_fields_present(self):
        """Test that optional fields are included in the outer query."""
        query = build_public_organizations_query(types=["political_party"])

        assert "OPTIONAL { ?organization wdt:P17 ?country" in query
        assert "OPTIONAL { ?organization wdt:P571 ?foundedDate" in query
        assert "OPTIONAL { ?organization wdt:P18 ?image" in query

    def test_social_media_fields_included(self):
        """Test that social media fields are included in query."""
        query = build_public_organizations_query(types=["political_party"])

        assert "OPTIONAL { ?organization wdt:P2003 ?instagramHandle" in query
        assert "OPTIONAL { ?organization wdt:P2002 ?twitterHandle" in query
        assert "OPTIONAL { ?organization wdt:P2013 ?facebookHandle" in query
        assert "OPTIONAL { ?organization wdt:P2397 ?youtubeHandle" in query

    def test_service_label_block(self):
        """Test that SERVICE wikibase:label block is included."""
        query = build_public_organizations_query(types=["political_party"], lang="en")

        assert "SERVICE wikibase:label" in query
        assert "bd:serviceParam wikibase:language" in query

    def test_label_service_falls_back_to_english(self):
        """Organizations lacking a label in `lang` must fall back to English:
        the label service param is a fallback chain, not a single language."""
        query = build_public_organizations_query(types=["political_party"], lang="fr")

        assert 'bd:serviceParam wikibase:language "fr,en".' in query

    def test_label_service_fallback_chain_default_lang(self):
        """Default lang="en" still uses the fallback-chain form (`"en,en"`),
        keeping the label service param shape uniform regardless of lang."""
        query = build_public_organizations_query(types=["political_party"])

        assert 'bd:serviceParam wikibase:language "en,en".' in query

    def test_mixed_type_filters_qid_and_mapping(self):
        """Test type filter with mixed QID and mapping key."""
        query = build_public_organizations_query(types=["Q7278", "government_agency"], lang="en")

        assert "VALUES ?orgClass { wd:Q7278 wd:Q327333 }" in query

    def test_type_filter_with_whitespace(self):
        """Test that type filter handles whitespace correctly."""
        query = build_public_organizations_query(
            types=["  political_party  "]  # with extra spaces
        )

        # Should be stripped and matched to mapping
        assert "VALUES ?orgClass { wd:Q7278 }" in query


class TestOrganizationTypeVocabulary:
    """The curated ORGANIZATION_TYPE_MAPPINGS vocabulary is pinned end to end."""

    EXPECTED_KEYS = [
        "broadcaster",
        "court",
        "government_agency",
        "international_organization",
        "legislature",
        "media_outlet",
        "ministry",
        "municipality",
        "news_agency",
        "newspaper",
        "ngo",
        "parliament",
        "political_party",
        "trade_union",
        "university",
    ]

    def test_every_mapping_value_is_a_qid(self):
        """Every mapped value looks like a Wikidata QID, not a label or typo."""
        for key, value in ORGANIZATION_TYPE_MAPPINGS.items():
            assert re.fullmatch(r"Q\d+", value), f"{key!r} maps to non-QID value {value!r}"

    def test_the_builder_resolves_every_vocabulary_key(self):
        """Every curated key builds a query containing its mapped QID in VALUES."""
        for key, qid in ORGANIZATION_TYPE_MAPPINGS.items():
            query = build_public_organizations_query(types=[key])

            assert f"VALUES ?orgClass {{ wd:{qid} }}" in query, (
                f"{key!r} did not resolve to {qid!r} in the query"
            )

    def test_the_vocabulary_key_set_is_pinned(self):
        """The exact key set is pinned so accidental additions or removals fail loudly."""
        assert sorted(ORGANIZATION_TYPE_MAPPINGS.keys()) == self.EXPECTED_KEYS


class TestQueryBuilderEdgeCases:
    """Test edge cases for query builders."""

    def test_figures_with_limit_one(self):
        """Test query with limit=1 (minimum valid limit)."""
        query = build_public_figures_query(limit=1)

        # Pagination now checks distinct QIDs, so LIMIT matches requested limit
        assert "LIMIT 1" in query

    def test_figures_with_large_limit(self):
        """Test query with very large limit."""
        query = build_public_figures_query(limit=1000)

        # Pagination now checks distinct QIDs, so LIMIT matches requested limit
        assert "LIMIT 1000" in query

    def test_figures_with_all_filters_combined(self):
        """Test query with all possible filters at once."""
        query = build_public_figures_query(
            birthday_from="1990-01-01",
            birthday_to="2000-12-31",
            nationality="United States",
            occupations=["Q36180", "writer"],
            gender="female",
            lang="fr",
            limit=25,
        )

        # Verify all filters are present
        assert "1990-01-01" in query
        assert "2000-12-31" in query
        assert "wdt:P27 wd:Q30" in query  # United States mapped to Q30
        assert "wdt:P106 wd:Q36180" in query
        assert "wdt:P106 wd:Q36180" in query  # writer also maps to Q36180
        assert "wdt:P21 wd:Q6581072" in query  # female
        assert "LIMIT 25" in query

    def test_organizations_with_limit_one(self):
        """Test query with limit=1 (minimum valid limit)."""
        query = build_public_organizations_query(types=["political_party"], limit=1)

        # Pagination now checks distinct QIDs, so LIMIT matches requested limit
        assert "LIMIT 1" in query

    def test_organizations_with_all_filters_combined(self):
        """Test query with all possible filters at once."""
        query = build_public_organizations_query(
            country="Q30",
            types=["Q327333", "political_party"],
            lang="es",
            limit=50,
        )

        # Verify all filters are present
        assert "wdt:P17 wd:Q30" in query
        assert "VALUES ?orgClass { wd:Q327333 wd:Q7278 }" in query  # QID + political_party
        assert "LIMIT 50" in query

    def test_figures_none_nationality(self):
        """Test query with None nationality (no filter)."""
        query = build_public_figures_query(nationality=None)

        # Should have OPTIONAL clause for country
        assert "OPTIONAL { ?person wdt:P27  ?country. }" in query

    def test_organizations_empty_type_list_raises_error(self):
        """types=[] is treated the same as types=None: it must raise, not silently
        build an unfiltered scan (which always times out on WDQS)."""
        with pytest.raises(ValueError, match="types filter is required"):
            build_public_organizations_query(types=[])
