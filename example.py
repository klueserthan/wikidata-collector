#!/usr/bin/env python
"""
Basic examples for wikidata-collector.

Shows the core workflow: initialize a client, fetch a page of results,
and inspect the normalized Pydantic models that come back.

Run: python example.py
"""

from wikidata_collector import WikidataClient
from wikidata_collector.config import WikidataCollectorConfig
from wikidata_collector.exceptions import InvalidFilterError


def example_default_client():
    """Initialize with defaults (reads CONTACT_EMAIL from env/.env)."""
    client = WikidataClient()
    return client


def example_custom_config():
    """Initialize with explicit configuration."""
    config = WikidataCollectorConfig(
        contact_email="you@example.com",
        sparql_timeout_seconds=30,
        max_retries=2,
    )
    return WikidataClient(config)


def example_get_public_figures():
    """Fetch a single page of public figures using the low-level API."""
    client = WikidataClient()

    # get_public_figures returns (List[PublicFigureNormalizedRecord], proxy_used)
    figures, proxy = client.get_public_figures(
        birthday_from="1990-01-01",
        birthday_to="1990-12-31",
        country="US",  # accepts country names, ISO codes, or QIDs
        occupations=["politician"],  # mapped key — see constants.py for options
        lang="en",
        limit=5,
    )

    print(f"Fetched {len(figures)} figures (proxy: {proxy})\n")
    for fig in figures:
        print(fig.generate_pretty_string())
        print()


def example_get_public_institutions():
    """Fetch a single page of public institutions using the low-level API."""
    client = WikidataClient()

    institutions, proxy = client.get_public_institutions(
        type=["government_agency"],  # mapped key
        country="US",
        lang="en",
        limit=5,
    )

    print(f"Fetched {len(institutions)} institutions (proxy: {proxy})\n")
    for inst in institutions:
        print(inst.generate_pretty_string())
        print()


def example_keyset_pagination():
    """Manually paginate through results using keyset (after_qid) pagination."""
    client = WikidataClient()

    # Page 1
    figures, _ = client.get_public_figures(country="Q30", limit=5)
    print(f"Page 1: {len(figures)} figures")
    for fig in figures:
        print(f"  {fig.qid}: {fig.name}")

    if not figures:
        return

    # Page 2 — pass the last QID from the previous page
    figures, _ = client.get_public_figures(country="Q30", limit=5, after_qid=figures[-1].qid)
    print(f"\nPage 2: {len(figures)} figures")
    for fig in figures:
        print(f"  {fig.qid}: {fig.name}")


def example_error_handling():
    """Demonstrate error handling for invalid inputs."""
    client = WikidataClient()

    try:
        # This raises InvalidFilterError — bad date format
        list(client.iterate_public_figures(birthday_from="not-a-date"))
    except InvalidFilterError as e:
        print(f"Caught InvalidFilterError: {e}")

    try:
        # This raises ValueError — unknown country
        client.get_public_figures(country="Atlantis")
    except ValueError as e:
        print(f"Caught ValueError: {e}")


if __name__ == "__main__":
    print("=== Public Figures (single page) ===\n")
    example_get_public_figures()

    print("\n=== Public Institutions (single page) ===\n")
    example_get_public_institutions()

    print("\n=== Keyset Pagination ===\n")
    example_keyset_pagination()

    print("\n=== Error Handling ===\n")
    example_error_handling()
