#!/usr/bin/env python
"""
Example usage of the wikidata_collector module.

This script demonstrates how to use the WikidataClient to query public figures
and institutions from Wikidata.
"""

from wikidata_collector import WikidataClient


def main():
    """Main example function."""

    # Initialize client with default configuration
    print("Initializing WikidataClient...")
    client = WikidataClient()

    # Or with custom configuration
    # config = WikidataCollectorConfig(
    #     contact_email="your-email@example.com"
    # )
    # client = WikidataClient(config)

    # Example 1: Query public figures born after 1990
    print("\n=== Example 1: Public Figures (Single Page) ===")
    print(
        "Querying public figures (occupations=['politician'], country='Q30') born between 1990-01-01 and 1990-01-02..."
    )

    try:
        results, proxy_used = client.get_public_figures(
            birthday_from="1990-01-01",
            birthday_to="1990-01-10",
            occupations=["politician"],
            country="Q30",  # United States QID
            lang="en",
            limit=5,
        )

        print(f"Found {len(results)} results (using {proxy_used})")
        print("\nResults (normalized model objects):")
        for item in results:
            print(f"  - {item.qid}: {item.name}")
            if item.birth_date:
                print(f"    Born: {item.birth_date}")
            if item.countries:
                print(f"    Countries: {', '.join(item.countries)}")

    except Exception as e:
        print(f"Error querying figures: {e}")

    # Example 2: Query public institutions
    print("\n=== Example 2: Public Institutions (Single Page) ===")
    print("Querying US institutions...")

    try:
        results, proxy_used = client.get_public_institutions(
            type=["Q327333"],  # Government agency QID
            country="Q30",  # United States QID
            lang="en",
            limit=5,
        )

        print(f"Found {len(results)} results (using {proxy_used})")
        print("\nResults (normalized model objects):")
        for item in results[:3]:
            print(f"  - {item.qid}: {item.name}")
            if item.countries:
                print(f"    Countries: {', '.join(item.countries)}")
            if item.types:
                print(f"    Types: {', '.join(item.types)}")

    except Exception as e:
        print(f"Error querying institutions: {e}")

    # Example 3: Use iterators for automatic pagination
    print("\n=== Example 3: Iterate Public Figures (Auto-Paginated) ===")
    print("Iterating over figures born between 1990-01-01 and 1990-01-05...")

    try:
        count = 0
        for figure in client.iter_public_figures(
            birthday_from="1990-01-01",
            birthday_to="1990-01-05",
            limit=5,  # Page size
        ):
            count += 1
            print(f"  {count}. {figure.name} ({figure.qid})")
            if count >= 10:  # Limit output
                break

        print("\nShowed first 10 figures (iterator continues beyond this)")

    except Exception as e:
        print(f"Error iterating figures: {e}")


if __name__ == "__main__":
    main()
