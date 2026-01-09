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
    print("Example: Iterating over public figures with auto-pagination")
    print("=" * 60)

    # Initialize client
    config = WikidataCollectorConfig(contact_email="example@example.com")
    client = WikidataClient(config)

    # Use iter_public_figures() for automatic pagination
    # Yields normalized PublicFigureNormalizedRecord objects one at a time
    # Handles page fetching internally
    print("\nFetching people born after 1990...")
    print("Using iter_public_figures() for automatic pagination\n")

    count = 0
    try:
        for figure in client.iter_public_figures(
            birthday_from="1990-01-01",
            birthday_to="1990-12-31",
            limit=15,  # Page size (records per page)
        ):
            count += 1
            print(f"{count:3d}. {figure.name:40s} ({figure.qid})")
            if count >= 20:  # Show first 20 for demo
                print("  ... (iterator continues)")
                break
    except Exception as e:
        print(f"Error: {e}")


def example_iterate_institutions():
    """Example: Iterate over public institutions using the new iterator."""
    print("\n" + "=" * 60)
    print("Example: Iterating over public institutions")
    print("=" * 60)

    # Initialize client
    config = WikidataCollectorConfig(contact_email="example@example.com")
    client = WikidataClient(config)

    # Use iter_public_institutions() for automatic pagination
    # Yields normalized PublicInstitutionNormalizedRecord objects one at a time
    print("\nFetching government agencies...")
    print("Using iter_public_institutions() for automatic pagination\n")

    count = 0
    try:
        for institution in client.iter_public_institutions(
            type=["Q327333"],  # Government agency
            limit=15,  # Page size
        ):
            count += 1
            print(f"{count:3d}. {institution.name:40s} ({institution.qid})")
            if institution.country:
                print(f"      Country: {institution.country}")
            if count >= 15:  # Show first 15 for demo
                print("  ... (iterator continues)")
                break
    except Exception as e:
        print(f"Error: {e}")


def example_high_level_iterator():
    """Example: High-level iterator with max_results filtering."""
    print("\n" + "=" * 60)
    print("Example: High-level iterate_public_figures() with max_results")
    print("=" * 60)

    # Initialize client
    config = WikidataCollectorConfig(contact_email="example@example.com")
    client = WikidataClient(config)

    # Use iterate_public_figures() for additional filtering and validation
    # Returns up to max_results normalized PublicFigureNormalizedRecord objects
    print("\nFetching US citizens born between 1985-01-01 and 1995-12-31...")
    print("Using iterate_public_figures() with max_results=25\n")

    try:
        count = 0
        for figure in client.iterate_public_figures(
            birthday_from="1985-01-01",
            birthday_to="1995-12-31",
            nationality="Q30",  # United States QID
            max_results=25,  # Stop after 25 results
        ):
            count += 1
            print(f"{count:3d}. {figure.name:40s} ({figure.qid})")
            if figure.countries:
                print(f"      Countries: {', '.join(figure.countries)}")
    except Exception as e:
        print(f"Error: {e}")

    print(f"\nFetched exactly {count} results (stopped at max_results limit)")


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
    print("Check the log output for page fetch and query execution information\n")

    # The iterator will log structured information about each page
    # including raw_records, unique_qids, latency, and proxy used
    count = 0
    try:
        for figure in client.iter_public_figures(
            birthday_from="1990-01-01",
            birthday_to="1990-01-31",
            limit=15,
        ):
            count += 1
            if count <= 5:
                print(f"  - {figure.name}")
            elif count == 6:
                print(f"  ... ({count} results and continuing)")
    except Exception as e:
        print(f"Error: {e}")

    print(f"\nFetched {count} results total")
    print("(Check logs above for structured pagination information)")


if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║  Iterator and Logging Examples                            ║
    ║  Demonstrating normalized model iteration and pagination  ║
    ╚════════════════════════════════════════════════════════════╝
    """)

    # NOTE: These examples require a working internet connection
    # and will make real API calls to Wikidata.
    # Uncomment the examples you want to run:

    example_iterate_figures()
    example_iterate_institutions()
    example_high_level_iterator()
    example_structured_logging()

    print("\n✓ Examples are ready to run!")
    print("  All examples demonstrate normalized model objects.")
    print("  Note: Requires internet connection to query Wikidata.\n")
