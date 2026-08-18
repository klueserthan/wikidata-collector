"""Pytest configuration and fixtures shared by the unit and integration suites."""

from typing import Any, Dict, List, Optional

import pytest

from wikidata_collector import WikidataClient
from wikidata_collector.config import WikidataCollectorConfig

WIKIDATA_ENTITY_PREFIX = "http://www.wikidata.org/entity/"


def sparql_response(bindings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Wrap raw bindings in the SPARQL JSON envelope the endpoint returns.

    Args:
        bindings: Result rows, each mapping a variable name to a value dict.

    Returns:
        A dict shaped like a ``application/sparql-results+json`` payload.
    """
    return {"results": {"bindings": bindings}}


def figure_binding(qid: str = "Q42", name: str = "Douglas Adams", **fields: Any) -> Dict[str, Any]:
    """Build one SPARQL result row for a public figure.

    Keyword arguments name SPARQL variables (``occupationLabel``, ``birthDate``,
    ``instagramHandle``, ...) and are wrapped in the ``{"value": ...}`` shape.
    Passing ``None`` omits the variable, mirroring an unbound OPTIONAL.

    Args:
        qid: Entity QID; becomes the ``person`` IRI.
        name: Value for ``personLabel``.
        **fields: Any further SPARQL variables to bind.

    Returns:
        One binding row.
    """
    binding: Dict[str, Any] = {
        "person": {"value": f"{WIKIDATA_ENTITY_PREFIX}{qid}"},
        "personLabel": {"value": name},
    }
    binding.update({key: {"value": value} for key, value in fields.items() if value is not None})
    return binding


def organization_binding(
    qid: str = "Q1", name: str = "United Nations", **fields: Any
) -> Dict[str, Any]:
    """Build one SPARQL result row for a public organization.

    Args:
        qid: Entity QID; becomes the ``organization`` IRI.
        name: Value for ``organizationLabel``.
        **fields: Any further SPARQL variables to bind (``None`` omits one).

    Returns:
        One binding row.
    """
    binding: Dict[str, Any] = {
        "organization": {"value": f"{WIKIDATA_ENTITY_PREFIX}{qid}"},
        "organizationLabel": {"value": name},
    }
    binding.update({key: {"value": value} for key, value in fields.items() if value is not None})
    return binding


def make_config(**overrides: Any) -> WikidataCollectorConfig:
    """Build a config with test-friendly defaults.

    Pins ``contact_email`` so the User-Agent is deterministic, and keeps retry
    counts low so failure paths do not loop needlessly.

    Args:
        **overrides: Any ``WikidataCollectorConfig`` argument to override.

    Returns:
        A configured ``WikidataCollectorConfig``.
    """
    defaults: Dict[str, Any] = {
        "contact_email": "tests@example.com",
        "proxy_list": [],
        "max_retries": 2,
        "sparql_timeout_seconds": 5,
    }
    defaults.update(overrides)
    return WikidataCollectorConfig(**defaults)


@pytest.fixture
def wikidata_client() -> WikidataClient:
    """Return a ``WikidataClient`` with default configuration."""
    return WikidataClient()


@pytest.fixture
def make_client():
    """Return a factory building a ``WikidataClient`` from config overrides.

    Returns:
        A callable accepting ``WikidataCollectorConfig`` keyword overrides and
        returning a client configured with them.
    """

    def _make(**overrides: Any) -> WikidataClient:
        return WikidataClient(config=make_config(**overrides))

    return _make


@pytest.fixture
def sample_sparql_response() -> Dict[str, Any]:
    """Return a one-row SPARQL response for a public figure."""
    return sparql_response(
        [
            figure_binding(
                description="English writer and humorist",
                birthDate="1952-03-11T00:00:00Z",
                countryLabel="United Kingdom",
                occupationLabel="writer",
            )
        ]
    )


@pytest.fixture
def figure_page():
    """Return a factory producing a SPARQL response page of public figures.

    Returns:
        A callable taking QIDs (and optional shared field overrides) and
        returning a full SPARQL response envelope.
    """

    def _page(qids: List[str], names: Optional[List[str]] = None, **fields: Any) -> Dict[str, Any]:
        labels = names or [f"Figure {qid}" for qid in qids]
        return sparql_response(
            [figure_binding(qid, name, **fields) for qid, name in zip(qids, labels)]
        )

    return _page
