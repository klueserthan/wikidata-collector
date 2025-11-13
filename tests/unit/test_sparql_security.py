"""Tests for SPARQL security utilities and query injection prevention."""

import pytest

from sparql.utils import escape_sparql_literal, validate_qid, validate_pid
from sparql.builders.figures_query_builder import build_public_figures_query
from sparql.builders.institutions_query_builder import build_public_institutions_query


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
            build_public_figures_query(nationality=["Q42; DROP TABLE"])

    def test_nationality_label_injection_escaped(self):
        """Test that malicious label in nationality is escaped."""
        malicious_input = '" . } DROP GRAPH <urn:wikidata> ; { #'
        query = build_public_figures_query(nationality=[malicious_input])
        # The escaped version should be in the query
        assert '\\"' in query or "DROP GRAPH" not in query
        # Verify the dangerous pattern is not present unescaped
        assert '" . }' not in query

    def test_profession_qid_injection_prevented(self):
        """Test that malicious QID in profession is rejected."""
        with pytest.raises(ValueError, match="Invalid QID format"):
            build_public_figures_query(profession=["Q42; DROP"])

    def test_profession_label_injection_escaped(self):
        """Test that malicious label in profession is escaped."""
        malicious_input = '"; } FILTER(?x = "evil'
        query = build_public_figures_query(profession=[malicious_input])
        # Verify escaping occurred
        assert '\\"' in query or '"; }' not in query


class TestInstitutionsQueryInjectionPrevention:
    """Test that institutions query builder prevents injection attacks."""

    def test_country_qid_injection_prevented(self):
        """Test that malicious QID in country is rejected."""
        with pytest.raises(ValueError, match="Invalid QID format"):
            build_public_institutions_query(country="Q42; DROP")

    def test_country_label_injection_escaped(self):
        """Test that malicious label in country is escaped."""
        malicious_input = '" . } DROP GRAPH <urn:wikidata> ; { #'
        query = build_public_institutions_query(country=malicious_input)
        # Verify escaping occurred
        assert '\\"' in query or '" . }' not in query

    def test_type_qid_injection_prevented(self):
        """Test that malicious QID in type is rejected."""
        with pytest.raises(ValueError, match="Invalid QID format"):
            build_public_institutions_query(type=["Q42; SELECT *"])

    def test_type_label_injection_escaped(self):
        """Test that malicious label in type is escaped."""
        malicious_input = '"; } FILTER(?x = "bad'
        query = build_public_institutions_query(type=[malicious_input])
        # Verify escaping occurred
        assert '\\"' in query or '"; }' not in query

    def test_jurisdiction_qid_injection_prevented(self):
        """Test that malicious QID in jurisdiction is rejected."""
        with pytest.raises(ValueError, match="Invalid QID format"):
            build_public_institutions_query(jurisdiction="Q42; DROP")

    def test_jurisdiction_label_injection_escaped(self):
        """Test that malicious label in jurisdiction is escaped."""
        malicious_input = '" UNION { ?x ?y ?z } . "'
        query = build_public_institutions_query(jurisdiction=malicious_input)
        # Verify escaping occurred
        assert '\\"' in query or '" UNION' not in query


class TestCountryCodeEscaping:
    """Test that country code escaping works correctly."""

    def test_valid_country_code_escaped(self):
        """Test that valid country codes are still escaped."""
        query = build_public_figures_query(nationality=["USA"])
        assert 'P298 "USA"' in query

    def test_malicious_country_code_escaped(self):
        """Test that malicious country code-like input is escaped."""
        # Even though this looks like a country code, if it contains quotes it's escaped
        malicious_input = 'US"'
        query = build_public_figures_query(nationality=[malicious_input])
        # Should be escaped
        assert 'US\\"' in query or 'US"' not in query
