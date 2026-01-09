"""Tests for SPARQL security utilities and query injection prevention."""

import pytest

from wikidata_collector.query_builders.figures_query_builder import build_public_figures_query
from wikidata_collector.query_builders.institutions_query_builder import (
    build_public_institutions_query,
)

# Test the NEW secure implementations from wikidata_collector module
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
            build_public_figures_query(country="Q42; DROP TABLE")

    def test_nationality_label_injection_escaped(self):
        """Test that malicious label in nationality is rejected (not in mappings)."""
        malicious_input = '" . } DROP GRAPH <urn:wikidata> ; { #'
        # This input is not a valid country name or QID, so it should raise an error
        with pytest.raises(ValueError, match="Unknown country"):
            build_public_figures_query(country=malicious_input)

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


class TestInstitutionsQueryInjectionPrevention:
    """Test that institutions query builder prevents injection attacks."""

    def test_country_qid_injection_prevented(self):
        """Test that malicious QID in country is rejected."""
        with pytest.raises(ValueError, match="Invalid QID format"):
            build_public_institutions_query(country="Q42; DROP")

    def test_country_label_injection_rejected(self):
        """Test that malicious label in country is rejected (only QIDs accepted)."""
        malicious_input = '" . } DROP GRAPH <urn:wikidata> ; { #'
        with pytest.raises(ValueError, match="Country filter must be a QID"):
            build_public_institutions_query(country=malicious_input)

    def test_type_qid_injection_prevented(self):
        """Test that malicious QID in type is rejected."""
        with pytest.raises(ValueError, match="Invalid QID format"):
            build_public_institutions_query(type=["Q42; SELECT *"])

    def test_type_label_injection_rejected(self):
        """Test that malicious label in type is rejected (not in mappings)."""
        malicious_input = '"; } FILTER(?x = "bad'
        with pytest.raises(ValueError, match="Unknown institution type"):
            build_public_institutions_query(type=[malicious_input])


class TestCountryCodeEscaping:
    """Test that country code escaping works correctly."""

    def test_valid_country_code_mapped(self):
        """Test that valid country codes in the mapping are used."""
        query = build_public_figures_query(country="US")
        # US is mapped to Q30 in COUNTRY_MAPPINGS
        assert "wdt:P27 wd:Q30" in query

    def test_malicious_country_not_in_mapping(self):
        """Test that malicious country codes not in mapping are rejected."""
        # This is not in COUNTRY_MAPPINGS, so it should raise an error
        malicious_input = 'US"'
        with pytest.raises(ValueError, match="Unknown country"):
            build_public_figures_query(country=malicious_input)
