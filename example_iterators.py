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
    config = WikidataCollectorConfig(
        contact_email="example@example.com"
    )
    client = WikidataClient(config)
    
    # Use the iterator to fetch public figures
    # The iterator automatically handles pagination with page_size=15 (default)
    print("\nFetching actors from the United States born after 1990...")
    print("Using iter_public_figures() with automatic pagination\n")
    
    count = 0
    for figure in client.iter_public_figures(
        birthday_from="1990-01-01",
        nationality=["US"],  # United States
        profession=["actor"],  # Actor
        page_size=15  # Uses DEFAULT_PAGE_SIZE internally
    ):
        count += 1
        qid = figure.get("person", {}).get("value", "").split("/")[-1]
        name = figure.get("personLabel", {}).get("value", "Unknown")
        
        print(f"{count}. {name} ({qid})")
        
        # Stop after 30 results for demo purposes
        if count >= 30:
            break
    
    print(f"\nTotal fetched: {count} figures")


def example_iterate_institutions():
    """Example: Iterate over public institutions using the new iterator."""
    print("\n" + "=" * 60)
    print("Example: Iterating over public institutions")
    print("=" * 60)
    
    # Initialize client
    config = WikidataCollectorConfig(
        contact_email="example@example.com"
    )
    client = WikidataClient(config)
    
    # Use the iterator to fetch institutions
    print("\nFetching government agencies in the United States...")
    print("Using iter_public_institutions() with automatic pagination\n")
    
    count = 0
    for institution in client.iter_public_institutions(
        country="US",  # United States
        type=["government_agency"],  # Government agency
        page_size=15
    ):
        count += 1
        qid = institution.get("institution", {}).get("value", "").split("/")[-1]
        name = institution.get("institutionLabel", {}).get("value", "Unknown")
        
        print(f"{count}. {name} ({qid})")
        
        # Stop after 20 results for demo purposes
        if count >= 20:
            break
    
    print(f"\nTotal fetched: {count} institutions")


def example_structured_logging():
    """Example: Structured logging output."""
    print("\n" + "=" * 60)
    print("Example: Structured logging")
    print("=" * 60)
    
    import logging
    
    # Configure logging to see structured log output
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    config = WikidataCollectorConfig(
        contact_email="example@example.com"
    )
    client = WikidataClient(config)
    
    print("\nFetching with structured logging enabled...")
    print("Check the log output for structured query and page information\n")
    
    # The iterator will log structured information about each page
    count = 0
    for figure in client.iter_public_figures(
        nationality=["US"],
        page_size=15
    ):
        count += 1
        if count >= 20:  # Just fetch a few for demo
            break
    
    print(f"\nFetched {count} results (check logs for structured output)")


if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║  Phase 2: Iterator and Logging Examples                   ║
    ║  Demonstrating new iterator functionality                 ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    # NOTE: These examples require a working internet connection
    # and will make real API calls to Wikidata.
    # Uncomment the examples you want to run:
    
    # example_iterate_figures()
    # example_iterate_institutions()
    # example_structured_logging()
    
    print("\n✓ Examples are ready to run!")
    print("  Uncomment the example calls in __main__ to test them.")
    print("  Note: Requires internet connection to query Wikidata.\n")
