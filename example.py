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
    print("\n=== Example 1: Public Figures ===")
    # print("Querying actors born after 1990...")

    # try:
    #     results, proxy_used = client.get_public_figures(
    #         birthday_from="1990-01-01",
    #         birthday_to="1990-01-02",
    #         lang="de",
    #         limit=5,
    #     )

    #     print(f"Found {len(results)} results (using {proxy_used})")
    #     print("\nFirst few results:")
    #     for item in results[:3]:
    #         qid = item["person"]["value"].split("/")[-1]
    #         name = item.get("personLabel", {}).get("value", "Unknown")
    #         birthday = item.get("birthDate", {}).get("value", "Unknown")
    #         print(
    #             f"  - {qid}: {name} (born {birthday[:10] if birthday != 'Unknown' else 'Unknown'})"
    #         )

    #     # Normalize a result
    #     if results:
    #         print("\nNormalized first result:")
    #         normalized = normalize_public_figure(results[0], None)
    #         print(f"  ID: {normalized.id}")
    #         print(f"  Name: {normalized.name}")
    #         print(f"  Professions: {normalized.professions}")
    #         print(f"  Nationalities: {normalized.nationalities}")

    # except Exception as e:
    #     print(f"Error querying figures: {e}")

    # Example 2: Query public institutions
    print("\n=== Example 2: Public Institutions ===")
    print("Querying US government agencies...")

    try:
        results, proxy_used = client.get_public_institutions(
            type=["Q327333"],  # Government agency QID
            country="United States",  # Country name
            lang="en",
            limit=5,
        )

        print(f"Found {len(results)} results (using {proxy_used})")
        print("\nFirst few results:")
        for item in results[:3]:
            qid = item["institution"]["value"].split("/")[-1]
            name = item.get("institutionLabel", {}).get("value", "Unknown")
            print(f"  - {qid}: {name}")

    except Exception as e:
        print(f"Error querying institutions: {e}")

    # Example 3: Get single entity
    print("\n=== Example 3: Single Entity Lookup ===")
    print("Looking up Q42 (Douglas Adams)...")

    try:
        entity, proxy_used = client.get_entity("Q42", lang="en")

        labels = entity.get("labels", {})
        en_label = labels.get("en", {}).get("value", "Unknown")

        descriptions = entity.get("descriptions", {})
        en_desc = descriptions.get("en", {}).get("value", "Unknown")

        print(f"Entity found (using {proxy_used}):")
        print(f"  Label: {en_label}")
        print(f"  Description: {en_desc}")

    except Exception as e:
        print(f"Error getting entity: {e}")

    print("\n✅ Examples completed!")


if __name__ == "__main__":
    main()
