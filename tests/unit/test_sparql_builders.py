"""
Unit tests for SPARQL query builders.
"""

from wikidata_collector.query_builders.figures_query_builder import build_public_figures_query
from wikidata_collector.query_builders.institutions_query_builder import (
    build_public_institutions_query,
)


class TestBuildPublicFiguresQuery:
    """Test build_public_figures_query method."""

    def test_basic_query(self):
        """Test basic query without filters."""
        query = build_public_figures_query()

        assert "SELECT ?person" in query
        assert "?person wdt:P31 wd:Q5" in query  # instance of human
        assert "wdt:P569" in query  # date of birth
        assert "ORDER BY ?person" in query
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
            profession=["Q36180"]  # Writer QID
        )

        assert "wdt:P106 wd:Q36180" in query

    def test_profession_filter_name(self):
        """Test profession filter with mapped name."""
        query = build_public_figures_query(profession=["writer"], lang="en")

        # writer is mapped to Q36180 in constants
        assert "wdt:P106 wd:Q36180" in query

    def test_multiple_professions(self):
        """Test multiple profession filters."""
        query = build_public_figures_query(
            profession=["Q36180", "Q33999"]  # Writer and Actor
        )

        assert "wdt:P106 wd:Q36180" in query
        assert "wdt:P106 wd:Q33999" in query

    def test_keyset_pagination(self):
        """Test keyset pagination with QID."""
        query = build_public_figures_query(after_qid="Q100")

        assert 'BIND(xsd:integer(STRAFTER(STR(?person), "Q")) AS ?qidNum)' in query
        assert "FILTER(?qidNum > 100)" in query

    def test_offset_pagination(self):
        """Test offset pagination (backward compatibility)."""
        query = build_public_figures_query(cursor=50)

        assert "OFFSET 50" in query

    def test_limit(self):
        """Test limit parameter."""
        query = build_public_figures_query(limit=200)

        assert "LIMIT 201" in query  # limit + 1 for has_more detection

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


class TestBuildPublicInstitutionsQuery:
    """Test build_public_institutions_query method."""

    def test_basic_query(self):
        """Test basic query without filters."""
        query = build_public_institutions_query()

        assert "SELECT DISTINCT" in query
        assert "?institution wdt:P31 ?type" in query
        assert "ORDER BY ?institution" in query
        assert "LIMIT" in query

    def test_country_filter_qid(self):
        """Test country filter with QID."""
        query = build_public_institutions_query(
            country="Q145"  # United Kingdom QID
        )

        assert "?institution wdt:P17 wd:Q145" in query

    def test_country_filter_name(self):
        """Test country filter with name."""
        query = build_public_institutions_query(country="United Kingdom", lang="en")

        assert "?institution wdt:P17 ?country" in query
        assert '?country rdfs:label "United Kingdom"@en' in query

    def test_type_filter_mapping(self):
        """Test type filter with mapped type name."""
        query = build_public_institutions_query(type=["political_party"])

        assert "wdt:P31 wd:Q7278" in query  # political_party mapping

    def test_type_filter_qid(self):
        """Test type filter with QID."""
        query = build_public_institutions_query(type=["Q7278"])

        assert "wdt:P31 wd:Q7278" in query

    def test_jurisdiction_filter(self):
        """Test jurisdiction filter."""
        query = build_public_institutions_query(jurisdiction="Q145", lang="en")

        assert "?institution wdt:P1001 wd:Q145" in query

    def test_keyset_pagination(self):
        """Test keyset pagination with QID."""
        query = build_public_institutions_query(after_qid="Q1000")

        assert 'BIND(xsd:integer(STRAFTER(STR(?institution), "Q")) AS ?qidNum)' in query
        assert "FILTER(?qidNum > 1000)" in query

    def test_country_filter_iso_code(self):
        """Test country filter with ISO country code (3-letter)."""
        query = build_public_institutions_query(
            country="USA"  # 3-letter ISO code
        )

        # Should translate to country code filter
        assert "?institution wdt:P17 ?country" in query
        assert '?country wdt:P298 "USA"' in query

    def test_type_filter_with_label(self):
        """Test type filter with human-readable label."""
        query = build_public_institutions_query(type=["government agency"], lang="en")

        assert "?institution wdt:P31 ?type" in query
        assert '?type rdfs:label "government agency"@en' in query

    def test_multiple_type_filters(self):
        """Test multiple type filters."""
        query = build_public_institutions_query(
            type=["political_party", "Q327333"]  # mapped key and QID
        )

        assert "wdt:P31 wd:Q7278" in query  # political_party mapping
        assert "wdt:P31 wd:Q327333" in query

    def test_jurisdiction_filter_with_label(self):
        """Test jurisdiction filter with label."""
        query = build_public_institutions_query(jurisdiction="California", lang="en")

        assert "?institution wdt:P1001 ?jurisdiction" in query
        assert '?jurisdiction rdfs:label "California"@en' in query

    def test_combined_filters(self):
        """Test combining multiple filters."""
        query = build_public_institutions_query(
            country="Q30",  # USA
            type=["government_agency"],
            jurisdiction="Q99",
            lang="en",
        )

        assert "?institution wdt:P17 wd:Q30" in query
        assert "wdt:P31 wd:Q327333" in query  # government_agency mapping
        assert "?institution wdt:P1001 wd:Q99" in query

    def test_offset_pagination(self):
        """Test offset pagination (backward compatibility)."""
        query = build_public_institutions_query(cursor=25)

        assert "OFFSET 25" in query

    def test_limit_parameter(self):
        """Test limit parameter."""
        query = build_public_institutions_query(limit=50)

        assert "LIMIT 51" in query  # limit + 1 for has_more detection

    def test_optional_fields_without_filters(self):
        """Test that optional fields are included when no filters applied."""
        query = build_public_institutions_query()

        assert "OPTIONAL { ?institution wdt:P17 ?country" in query
        assert "OPTIONAL { ?institution wdt:P1001 ?jurisdiction" in query
        assert "OPTIONAL { ?institution wdt:P571 ?foundedDate" in query
        assert "OPTIONAL { ?institution wdt:P18 ?image" in query

    def test_social_media_fields_included(self):
        """Test that social media fields are included in query."""
        query = build_public_institutions_query()

        assert "OPTIONAL { ?institution wdt:P2003 ?instagramHandle" in query
        assert "OPTIONAL { ?institution wdt:P2002 ?twitterHandle" in query
        assert "OPTIONAL { ?institution wdt:P2013 ?facebookHandle" in query
        assert "OPTIONAL { ?institution wdt:P2397 ?youtubeHandle" in query

    def test_service_label_block(self):
        """Test that SERVICE wikibase:label block is included."""
        query = build_public_institutions_query(lang="en")

        assert "SERVICE wikibase:label" in query
        assert "?institution rdfs:label ?institutionLabel" in query
        assert "?type rdfs:label ?typeLabel" in query
        assert "?country rdfs:label ?countryLabel" in query
        assert "?jurisdiction rdfs:label ?jurisdictionLabel" in query

    def test_mixed_type_filters_qid_mapping_label(self):
        """Test type filter with mixed QID, mapping key, and label."""
        query = build_public_institutions_query(
            type=["Q7278", "government_agency", "broadcaster"], lang="en"
        )

        # QID
        assert "wdt:P31 wd:Q7278" in query
        # Mapping
        assert "wdt:P31 wd:Q327333" in query
        # Label
        assert '?type rdfs:label "broadcaster"@en' in query

    def test_type_filter_with_whitespace(self):
        """Test that type filter handles whitespace correctly."""
        query = build_public_institutions_query(
            type=["  political_party  "]  # with extra spaces
        )

        # Should be stripped and matched to mapping
        assert "wdt:P31 wd:Q7278" in query


class TestQueryBuilderEdgeCases:
    """Test edge cases for query builders."""

    def test_figures_with_limit_one(self):
        """Test query with limit=1 (minimum valid limit)."""
        query = build_public_figures_query(limit=1)

        # Should generate LIMIT 2 (limit + 1 for has_more detection)
        assert "LIMIT 2" in query

    def test_figures_with_large_limit(self):
        """Test query with very large limit."""
        query = build_public_figures_query(limit=1000)

        # Should generate LIMIT 1001
        assert "LIMIT 1001" in query

    def test_figures_with_all_filters_combined(self):
        """Test query with all possible filters at once."""
        query = build_public_figures_query(
            birthday_from="1990-01-01",
            birthday_to="2000-12-31",
            nationality="United States",
            profession=["Q36180", "writer"],
            lang="fr",
            limit=25,
        )

        # Verify all filters are present
        assert "1990-01-01" in query
        assert "2000-12-31" in query
        assert "wdt:P27 wd:Q30" in query  # United States mapped to Q30
        assert "wdt:P106 wd:Q36180" in query
        assert "wdt:P106 wd:Q36180" in query  # writer also maps to Q36180
        assert "LIMIT 26" in query

    def test_institutions_with_limit_one(self):
        """Test query with limit=1 (minimum valid limit)."""
        query = build_public_institutions_query(limit=1)

        # Should generate LIMIT 2 (limit + 1 for has_more detection)
        assert "LIMIT 2" in query

    def test_institutions_with_all_filters_combined(self):
        """Test query with all possible filters at once."""
        query = build_public_institutions_query(
            country="Q30",
            type=["Q327333", "university"],
            jurisdiction="Q30",
            lang="es",
            limit=50,
        )

        # Verify all filters are present
        assert "wdt:P17 wd:Q30" in query
        assert "wdt:P31 wd:Q327333" in query
        assert 'rdfs:label "university"' in query
        assert "wdt:P1001" in query  # jurisdiction property
        assert "LIMIT 51" in query

    def test_figures_none_nationality(self):
        """Test query with None nationality (no filter)."""
        query = build_public_figures_query(nationality=None)

        # Should have OPTIONAL clause for country
        assert "OPTIONAL { ?person wdt:P27  ?country. }" in query

    def test_institutions_empty_type_list(self):
        """Test query with empty type list."""
        query = build_public_institutions_query(type=[])

        # Should still have basic structure
        assert "?institution wdt:P31 ?type" in query
