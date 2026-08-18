"""Tests for SPARQL security utilities and query injection prevention."""

from typing import Any, Dict

import pytest

from wikidata_collector import InvalidFilterError, WikidataClient
from wikidata_collector.query_builders.figures_query_builder import build_public_figures_query
from wikidata_collector.query_builders.organizations_query_builder import (
    build_public_organizations_query,
)
from wikidata_collector.security import escape_sparql_literal, validate_pid, validate_qid


class TestEscapeSparqlLiteral:
    """Test SPARQL literal escaping."""

    def test_escape_backslash(self):
        """Test that backslashes are properly escaped."""
        result = escape_sparql_literal("test\\value")
        assert result == "test\\\\value"

    def test_escape_quotes(self):
        """Test that double quotes are properly escaped."""
        result = escape_sparql_literal('test"value')
        assert result == 'test\\"value'

    def test_escape_newline(self):
        """Test that newlines are properly escaped."""
        result = escape_sparql_literal("test\nvalue")
        assert result == "test\\nvalue"

    def test_escape_carriage_return(self):
        """Test that carriage returns are properly escaped."""
        result = escape_sparql_literal("test\rvalue")
        assert result == "test\\rvalue"

    def test_escape_tab(self):
        """Test that tabs are properly escaped."""
        result = escape_sparql_literal("test\tvalue")
        assert result == "test\\tvalue"

    def test_escape_malicious_input(self):
        """Test escaping of potential injection attack."""
        malicious = '" . } DROP GRAPH <urn:wikidata> ; { #'
        result = escape_sparql_literal(malicious)
        assert '"' not in result or '\\"' in result
        assert result == '\\" . } DROP GRAPH <urn:wikidata> ; { #'

    def test_escape_multiple_special_chars(self):
        """Test escaping of multiple special characters."""
        result = escape_sparql_literal('test\\"value"\n')
        assert result == 'test\\\\\\"value\\"\\n'


class TestValidateQid:
    """Test QID validation."""

    def test_valid_qid(self):
        """Test that valid QIDs pass validation."""
        assert validate_qid("Q42") == "Q42"
        assert validate_qid("Q1") == "Q1"
        assert validate_qid("Q123456789") == "Q123456789"

    def test_invalid_qid_no_number(self):
        """Test that QIDs without numbers are rejected."""
        with pytest.raises(ValueError, match="Invalid QID format"):
            validate_qid("Q")

    def test_invalid_qid_lowercase(self):
        """Test that lowercase QIDs are rejected."""
        with pytest.raises(ValueError, match="Invalid QID format"):
            validate_qid("q42")

    def test_invalid_qid_wrong_prefix(self):
        """Test that non-Q prefixes are rejected."""
        with pytest.raises(ValueError, match="Invalid QID format"):
            validate_qid("P42")
        with pytest.raises(ValueError, match="Invalid QID format"):
            validate_qid("L42")

    def test_invalid_qid_with_injection(self):
        """Test that injection attempts in QIDs are rejected."""
        with pytest.raises(ValueError, match="Invalid QID format"):
            validate_qid("Q42 . } DROP")
        with pytest.raises(ValueError, match="Invalid QID format"):
            validate_qid("Q42; SELECT *")

    def test_invalid_qid_with_special_chars(self):
        """Test that QIDs with special characters are rejected."""
        with pytest.raises(ValueError, match="Invalid QID format"):
            validate_qid("Q42-test")
        with pytest.raises(ValueError, match="Invalid QID format"):
            validate_qid("Q42_test")


class TestValidatePid:
    """Test PID validation."""

    def test_valid_pid(self):
        """Test that valid PIDs pass validation."""
        assert validate_pid("P27") == "P27"
        assert validate_pid("P1") == "P1"
        assert validate_pid("P123456789") == "P123456789"

    def test_invalid_pid_no_number(self):
        """Test that PIDs without numbers are rejected."""
        with pytest.raises(ValueError, match="Invalid PID format"):
            validate_pid("P")

    def test_invalid_pid_wrong_prefix(self):
        """Test that non-P prefixes are rejected."""
        with pytest.raises(ValueError, match="Invalid PID format"):
            validate_pid("Q27")


class TestFiguresQueryInjectionPrevention:
    """Test that figures query builder prevents injection attacks."""

    def test_nationality_qid_injection_prevented(self):
        """Test that malicious QID in nationality is rejected."""
        with pytest.raises(ValueError, match="Invalid QID format"):
            build_public_figures_query(nationality="Q42; DROP TABLE")

    def test_nationality_label_injection_escaped(self):
        """Test that malicious label in nationality is rejected (not in mappings)."""
        malicious_input = '" . } DROP GRAPH <urn:wikidata> ; { #'
        # This input is not a valid country name or QID, so it should raise an error
        with pytest.raises(ValueError, match="Unknown nationality"):
            build_public_figures_query(nationality=malicious_input)

    def test_profession_qid_injection_prevented(self):
        """Test that malicious QID in profession is rejected."""
        with pytest.raises(ValueError, match="Invalid QID format"):
            build_public_figures_query(occupations=["Q42; DROP"])

    def test_profession_label_injection_escaped(self):
        """Test that malicious label in profession is rejected (not in mappings)."""
        malicious_input = '"; } FILTER(?x = "evil'
        # This input is not a valid profession in PROFESSION_MAPPINGS
        with pytest.raises(ValueError, match="Unknown profession"):
            build_public_figures_query(occupations=[malicious_input])


class TestOrganizationsQueryInjectionPrevention:
    """Test that organizations query builder prevents injection attacks."""

    def test_country_qid_injection_prevented(self):
        """Test that malicious QID in country is rejected."""
        with pytest.raises(ValueError, match="Invalid QID format"):
            build_public_organizations_query(country="Q42; DROP")

    def test_country_label_injection_rejected(self):
        """Test that malicious label in country is rejected (only QIDs accepted)."""
        malicious_input = '" . } DROP GRAPH <urn:wikidata> ; { #'
        with pytest.raises(ValueError, match="Country filter must be a QID"):
            build_public_organizations_query(country=malicious_input)

    def test_type_qid_injection_prevented(self):
        """Test that malicious QID in type is rejected."""
        with pytest.raises(ValueError, match="Invalid QID format"):
            build_public_organizations_query(types=["Q42; SELECT *"])

    def test_type_label_injection_rejected(self):
        """Test that malicious label in type is rejected (not in mappings)."""
        malicious_input = '"; } FILTER(?x = "bad'
        with pytest.raises(ValueError, match="Unknown organization type"):
            build_public_organizations_query(types=[malicious_input])


class TestCountryCodeEscaping:
    """Test that country code escaping works correctly."""

    def test_valid_country_code_mapped(self):
        """Test that valid country codes in the mapping are used."""
        query = build_public_figures_query(nationality="US")
        # US is mapped to Q30 in COUNTRY_MAPPINGS
        assert "wdt:P27 wd:Q30" in query

    def test_malicious_country_not_in_mapping(self):
        """Test that malicious country codes not in mapping are rejected."""
        # This is not in COUNTRY_MAPPINGS, so it should raise an error
        malicious_input = 'US"'
        with pytest.raises(ValueError, match="Unknown nationality"):
            build_public_figures_query(nationality=malicious_input)


class TestGenderFilterInjectionPrevention:
    """The gender filter reached SPARQL without an injection test of its own."""

    def test_gender_qid_injection_prevented(self):
        """A QID-shaped gender value with a payload is rejected."""
        with pytest.raises(ValueError, match="Invalid QID format"):
            build_public_figures_query(gender="Q6581097 . } DROP GRAPH <urn:x> ; {")

    def test_unknown_gender_label_is_rejected(self):
        """Anything outside GENDER_MAPPINGS never reaches the query."""
        with pytest.raises(ValueError, match="Unknown gender"):
            build_public_figures_query(gender='" . } #')

    def test_mapped_gender_emits_only_the_mapped_qid(self):
        """A known label resolves to its QID and nothing else."""
        query = build_public_figures_query(gender="female")

        assert "wdt:P21 wd:Q6581072" in query

    def test_other_gender_emits_negated_patterns_not_a_literal(self):
        """The 'other' sentinel becomes FILTER NOT EXISTS, never an interpolation."""
        query = build_public_figures_query(gender="other")

        assert "FILTER NOT EXISTS { ?person wdt:P21 wd:Q6581097 }" in query
        assert "FILTER NOT EXISTS { ?person wdt:P21 wd:Q6581072 }" in query
        assert "wd:other" not in query


class TestKeysetPaginationInjectionPrevention:
    """`after_qid` is caller-supplied and lands inside a numeric FILTER."""

    @pytest.mark.parametrize(
        "builder", [build_public_figures_query, build_public_organizations_query]
    )
    def test_malicious_after_qid_is_rejected(self, builder):
        """A QID-prefixed payload fails validation instead of being interpolated."""
        with pytest.raises(ValueError, match="Invalid QID format"):
            builder(after_qid="Q1) } DROP GRAPH <urn:wikidata> ; SELECT * WHERE { (")

    @pytest.mark.parametrize(
        "builder", [build_public_figures_query, build_public_organizations_query]
    )
    def test_valid_after_qid_becomes_a_numeric_comparison(self, builder):
        """A well-formed QID is reduced to its integer suffix."""
        query = builder(after_qid="Q42")

        assert "FILTER(?qidNum > 42)" in query


class TestDateFilterHandling:
    """Birthday bounds are interpolated as xsd:dateTime literals."""

    def test_valid_dates_are_emitted_as_typed_literals(self):
        """A well-formed range produces both bounds as typed literals."""
        query = build_public_figures_query(birthday_from="1990-01-01", birthday_to="1999-12-31")

        assert '"1990-01-01T00:00:00Z"^^xsd:dateTime' in query
        assert '"1999-12-31T23:59:59Z"^^xsd:dateTime' in query

    @pytest.mark.parametrize("field", ["birthday_from", "birthday_to"])
    def test_client_rejects_a_malformed_date_before_the_builder_sees_it(self, field: str):
        """The client validates dates so no payload can reach the builder.

        The builder itself does not parse dates, so this boundary is the only
        thing standing between a caller string and a SPARQL literal.
        """
        client = WikidataClient()
        payload = '1990-01-01T00:00:00Z"^^xsd:dateTime) } DROP GRAPH <urn:x> ; #'
        filters: Dict[str, Any] = {field: payload}

        with pytest.raises(InvalidFilterError, match="Expected ISO format"):
            list(client.iterate_public_figures(**filters))
