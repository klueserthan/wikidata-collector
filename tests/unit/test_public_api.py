"""Unit tests pinning the package's public surface.

This is a library: the names exported from `wikidata_collector` are its contract.
Removing or renaming one is a breaking change for every consumer, so the surface
is asserted explicitly rather than left to drift.
"""

import inspect

import pytest

import wikidata_collector
from wikidata_collector.exceptions import WikidataCollectorError

EXPECTED_EXPORTS = {
    "WikidataClient",
    "PublicFigureNormalizedRecord",
    "PublicInstitutionNormalizedRecord",
    "SubInstitution",
    "WikidataCollectorError",
    "InvalidQIDError",
    "EntityNotFoundError",
    "QueryExecutionError",
    "InvalidFilterError",
    "ProxyMisconfigurationError",
    "ProxyUnavailableError",
    "UpstreamUnavailableError",
}


class TestExports:
    """`__all__` and what it promises."""

    def test_all_matches_the_documented_surface(self):
        """Changing the export list is a deliberate act, not a side effect."""
        assert set(wikidata_collector.__all__) == EXPECTED_EXPORTS

    def test_all_has_no_duplicates(self):
        """A duplicated export usually means a bad merge."""
        assert len(wikidata_collector.__all__) == len(set(wikidata_collector.__all__))

    @pytest.mark.parametrize("name", sorted(EXPECTED_EXPORTS))
    def test_every_exported_name_is_importable(self, name: str):
        """Every promised name resolves from the package root."""
        assert getattr(wikidata_collector, name) is not None

    def test_version_is_exposed(self):
        """Consumers pin against `__version__`."""
        assert isinstance(wikidata_collector.__version__, str)
        assert wikidata_collector.__version__


class TestExceptionHierarchy:
    """Callers catch the base class; every error must be reachable that way."""

    @pytest.mark.parametrize(
        "name",
        sorted(name for name in EXPECTED_EXPORTS if name.endswith("Error")),
    )
    def test_every_exported_error_derives_from_the_base(self, name: str):
        """One `except WikidataCollectorError` catches the whole library."""
        assert issubclass(getattr(wikidata_collector, name), WikidataCollectorError)

    def test_the_base_error_is_an_exception(self):
        """The root of the hierarchy is a real exception type."""
        assert issubclass(WikidataCollectorError, Exception)


class TestClientSurface:
    """The methods consumers call, and the shape of their signatures."""

    @pytest.mark.parametrize(
        "method",
        [
            "get_public_figures",
            "get_public_institutions",
            "iterate_public_figures",
            "iterate_public_institutions",
            "execute_sparql_query",
        ],
    )
    def test_public_method_exists(self, method: str):
        """Renaming a public method breaks consumers and must be deliberate."""
        assert callable(getattr(wikidata_collector.WikidataClient, method))

    @pytest.mark.parametrize("method", ["iterate_public_figures", "iterate_public_institutions"])
    def test_iterator_arguments_are_keyword_only(self, method: str):
        """Keyword-only filters keep call sites readable and order-independent."""
        parameters = inspect.signature(
            getattr(wikidata_collector.WikidataClient, method)
        ).parameters
        positional = [
            name
            for name, parameter in parameters.items()
            if name != "self" and parameter.kind is not inspect.Parameter.KEYWORD_ONLY
        ]

        assert positional == []

    @pytest.mark.parametrize(
        ("method", "expected"),
        [
            (
                "iterate_public_figures",
                {
                    "birthday_from",
                    "birthday_to",
                    "nationality",
                    "occupations",
                    "gender",
                    "max_results",
                    "lang",
                },
            ),
            ("iterate_public_institutions", {"country", "types", "max_results", "lang"}),
        ],
    )
    def test_iterator_filter_vocabulary_is_stable(self, method: str, expected: set):
        """Filter names are the documented vocabulary; synonyms are not allowed."""
        parameters = inspect.signature(
            getattr(wikidata_collector.WikidataClient, method)
        ).parameters

        assert set(parameters) - {"self"} == expected
