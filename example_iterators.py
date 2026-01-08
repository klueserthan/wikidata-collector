#!/usr/bin/env python
"""
Example demonstrating the new iterator functionality for Phase 2.

This example shows how to use the iterator methods for efficient
paginated access to public figures and institutions.
"""

from wikidata_collector import WikidataClient
from wikidata_collector.config import WikidataCollectorConfig


def example_iterate_figures():
    """Example: Iterate over public figures using the new iterator."""
    print("=" * 60)
    print("Example: Iterating over public figures")
    print("=" * 60)

    # Initialize client
    config = WikidataCollectorConfig(contact_email="example@example.com")
    client = WikidataClient(config)

    # Use the high-level iterator to fetch public figures
    # Returns normalized PublicFigure model objects with automatic pagination
    print("\nFetching people from the United States born after 1990...")
    print("Using iterate_public_figures() with max_results limit\n")

    count = 0
    for figure in client.iterate_public_figures(
        birthday_from="1990-01-01",
        birthday_to="1990-01-31",
        nationality="US",  # United States
        max_results=30,  # Limit total results
    ):
        count += 1
        print(figure.name + f" ({figure.id})")

    print(f"\nTotal fetched: {count} figures")


def example_iterate_institutions():
    """Example: Iterate over public institutions using the new iterator."""
    print("\n" + "=" * 60)
    print("Example: Iterating over public institutions")
    print("=" * 60)

    # Initialize client
    config = WikidataCollectorConfig(contact_email="example@example.com")
    client = WikidataClient(config)

    # Use the high-level iterator to fetch institutions
    # Returns normalized PublicInstitution model objects with automatic pagination
    print("\nFetching government agencies in the United States...")
    print("Using iterate_public_institutions() with max_results limit\n")

    count = 0
    for institution in client.iterate_public_institutions(
        country="US",  # United States
        types=["government_agency"],  # Government agency
        max_results=20,  # Limit total results
    ):
        count += 1
        print(f"{count}. {institution.name} ({institution.qid})")
        if institution.country:
            print(f"    Country: {institution.country}")
        if institution.institution_type:
            print(f"    Type: {institution.institution_type}")

    print(f"\nTotal fetched: {count} institutions")


def example_structured_logging():
    """Example: Structured logging output."""
    print("\n" + "=" * 60)
    print("Example: Structured logging")
    print("=" * 60)

    import logging

    # Configure logging to see structured log output
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    config = WikidataCollectorConfig(contact_email="example@example.com")
    client = WikidataClient(config)

    print("\nFetching with structured logging enabled...")
    print("Check the log output for structured query and page information\n")

    # The iterator will log structured information about each page
    count = 0
    for figure in client.iterate_public_figures(nationality="US", max_results=20):
        count += 1
        print(f"  {figure.name}")

    print(f"\nFetched {count} results (check logs for structured output)")


if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║  Phase 2: Iterator and Logging Examples                   ║
    ║  Iterator Examples - High-Level API                       ║
    ║  Demonstrating normalized model iteration══════════════════╝
    """)

    # NOTE: These examples require a working internet connection
    # and will make real API calls to Wikidata.
    # Uncomment the examples you want to run:

    example_iterate_figures()
    example_iterate_institutions()
    example_structured_logging()

    print("\n✓ Examples are ready to run!")
    print("  Uncomment the example calls in __main__ to test them.")
    print("  Note: Requires internet connection to query Wikidata.\n")
