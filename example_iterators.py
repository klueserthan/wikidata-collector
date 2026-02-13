#!/usr/bin/env python
"""
Iterator examples for wikidata-collector.

Shows the high-level iterate_* API that handles pagination automatically,
and how to use structured logging to observe query execution.

Run: python example_iterators.py
"""

import logging

from wikidata_collector import WikidataClient


def iterate_figures_with_max_results():
    """iterate_public_figures: auto-paginated, capped at max_results."""
    client = WikidataClient()

    count = 0
    for figure in client.iterate_public_figures(
        birthday_from="1990-01-01",
        birthday_to="1995-12-31",
        nationality="US",
        max_results=10,
    ):
        count += 1
        print(f"  {count}. {figure.name} ({figure.qid})")
        if figure.occupations:
            print(f"     Occupations: {', '.join(figure.occupations)}")
        if figure.countries:
            print(f"     Countries: {', '.join(figure.countries)}")

    print(f"\n  Yielded {count} total results.\n")


def iterate_institutions_with_max_results():
    """iterate_public_institutions: auto-paginated, capped at max_results."""
    client = WikidataClient()

    count = 0
    for inst in client.iterate_public_institutions(
        country="US",
        types=["government_agency"],
        max_results=10,
    ):
        count += 1
        print(f"  {count}. {inst.name} ({inst.qid})")
        if inst.types:
            print(f"     Types: {', '.join(inst.types)}")

    print(f"\n  Yielded {count} total results.\n")


def iterate_with_low_level_iter():
    """iter_public_figures: lower-level iterator without max_results.

    Useful when you want to control the page size and stop condition yourself.
    """
    client = WikidataClient()

    count = 0
    for figure in client.iter_public_figures(
        birthday_from="1990-01-01",
        birthday_to="1990-06-30",
        nationality="Germany",
        limit=5,
    ):
        count += 1
        print(f"  {count}. {figure.name} ({figure.qid})")
        if count >= 10:
            print("  ... (stopping early)")
            break

    print(f"\n  Iterated through {count} results.\n")


def iterate_with_logging():
    """Enable structured logging to see pagination and query execution details."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    client = WikidataClient()

    count = 0
    for figure in client.iterate_public_figures(
        birthday_from="1990-01-01",
        birthday_to="1990-01-31",
        nationality="US",
        max_results=5,
    ):
        count += 1
        print(f"  {count}. {figure.name}")

    print("\n  Done. Structured log records include query_type, latency_ms, etc.; configure your logging formatter to display those fields.\n")


if __name__ == "__main__":
    print("=== iterate_public_figures (with max_results) ===\n")
    iterate_figures_with_max_results()

    print("=== iterate_public_institutions (with max_results) ===\n")
    iterate_institutions_with_max_results()

    print("=== iter_public_figures (low-level, manual stop) ===\n")
    iterate_with_low_level_iter()

    print("=== Structured Logging ===\n")
    iterate_with_logging()
