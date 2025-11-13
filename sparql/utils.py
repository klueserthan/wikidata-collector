"""Utility functions for SPARQL query construction with security validations."""

import re


def escape_sparql_literal(value: str) -> str:
    """Escape SPARQL literal values to prevent injection attacks.

    Args:
        value: The string value to escape

    Returns:
        Escaped string safe for use in SPARQL literals
    """
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def validate_qid(qid: str) -> str:
    """Validate QID format to ensure it matches Wikidata entity ID pattern.

    Args:
        qid: The QID string to validate

    Returns:
        The validated QID

    Raises:
        ValueError: If the QID format is invalid
    """
    if not re.match(r"^Q\d+$", qid):
        raise ValueError(f"Invalid QID format: {qid}")
    return qid


def validate_pid(pid: str) -> str:
    """Validate PID format to ensure it matches Wikidata property ID pattern.

    Args:
        pid: The PID string to validate

    Returns:
        The validated PID

    Raises:
        ValueError: If the PID format is invalid
    """
    if not re.match(r"^P\d+$", pid):
        raise ValueError(f"Invalid PID format: {pid}")
    return pid
