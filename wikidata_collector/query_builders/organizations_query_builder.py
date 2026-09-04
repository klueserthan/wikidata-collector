"""SPARQL query builder for public organizations."""

import os
from typing import List, Optional

from ..config import DEFAULT_LIMIT
from ..constants import COUNTRY_MAPPINGS, ORGANIZATION_TYPE_MAPPINGS
from ..security import validate_qid


def resolve_organization_type(value: str) -> str:
    """Resolve one organization type to a validated Wikidata class QID.

    Accepts a curated mapping key (from ``ORGANIZATION_TYPE_MAPPINGS``) or a
    raw QID; surrounding whitespace is ignored. This is the single source of
    truth for organization-type resolution — the query builder, the client's
    filter validator, and stream decomposition all go through it, so a type is
    validated and canonicalized exactly once and identically everywhere.

    Args:
        value: A mapping key (e.g. ``"newspaper"``) or a QID (e.g. ``"Q11032"``).

    Returns:
        The Wikidata class QID the type resolves to.

    Raises:
        ValueError: If the value is neither a known mapping key nor a valid QID.
    """
    value = value.strip()
    if value in ORGANIZATION_TYPE_MAPPINGS:
        return ORGANIZATION_TYPE_MAPPINGS[value]
    if value.startswith("Q"):
        return validate_qid(value)
    raise ValueError(
        f"Unknown organization type '{value}'. "
        f"Supported types: {', '.join(sorted(ORGANIZATION_TYPE_MAPPINGS.keys()))}, "
        "or a QID starting with Q"
    )


def build_public_organizations_query(
    country: Optional[str] = None,
    types: Optional[List[str]] = None,
    lang: str = "en",
    limit: Optional[int] = None,
    cursor: int = 0,
    after_qid: Optional[str] = None,
) -> str:
    """Build SPARQL query for public organizations, filtered by type (required).

    Live WDQS benchmarking (see the ADR / PR description) showed that an
    unfiltered organization-umbrella subclass scan
    (``wdt:P31/wdt:P279* wd:Q43229``, ~51k subclasses) always times out (504)
    on WDQS, in every query shape tested. ``types`` is therefore a required
    filter, never an optional narrowing. Multiple values are ORed together via
    a single ``VALUES`` clause feeding one ``wdt:P31/wdt:P279*`` property-path
    triple — never AND-joined ``;``-chained ``wdt:P31`` triples, which is
    semantically wrong (one entity cannot simultaneously be a direct instance
    of two different classes) and returns no results on real data.

    Args:
        country: Country filter (QID or label)
        types: List of organization type filters (mapped keys or raw QIDs).
            Required: at least one value must be given.
        lang: Language code for labels
        limit: Maximum results to return (defaults to DEFAULT_LIMIT)
        cursor: Offset for pagination
        after_qid: QID for keyset pagination

    Returns:
        SPARQL query string

    Raises:
        ValueError: If ``types`` is missing/empty, if any type or country
            value fails validation or is not recognized, or if QID validation
            fails for ``after_qid``.
    """
    if limit is None:
        limit = DEFAULT_LIMIT

    if not types:
        raise ValueError(
            "types filter is required for public organizations (an unfiltered "
            "scan always times out on WDQS). "
            f"Supported values: {', '.join(sorted(ORGANIZATION_TYPE_MAPPINGS.keys()))}, "
            "or a QID starting with Q"
        )

    # Resolve every type entry to a class QID. Multiple classes are combined
    # with OR semantics via VALUES, never AND-joined `;` triples.
    class_qids: List[str] = [resolve_organization_type(value) for value in types]

    values_clause = " ".join(f"wd:{qid}" for qid in class_qids)

    # Build efficient subquery with core filters. ?qidNum must be selected so it is
    # available for keyset pagination and ordering in the outer query. SELECT
    # DISTINCT is mandatory: the multi-class wdt:P31/wdt:P279* property path
    # produces duplicate ?organization rows for entities matching more than
    # one VALUES class, and keyset pagination ends a page once the number of
    # *unique* QIDs falls below the limit — without DISTINCT, duplicate rows
    # would silently truncate a page's results.
    subquery = f"""
  {{
    SELECT DISTINCT ?organization ?qidNum WHERE {{
      VALUES ?orgClass {{ {values_clause} }}
      ?organization wdt:P31/wdt:P279* ?orgClass .
"""

    # Add country filter to subquery if provided
    if country:
        country_value = country.strip()
        if country_value.startswith("Q"):
            # Direct QID - validate it
            validated_qid = validate_qid(country_value)
            subquery += f"      ?organization wdt:P17 wd:{validated_qid} .\n"
        elif country_value in COUNTRY_MAPPINGS:
            # Map country name to QID
            country_qid = COUNTRY_MAPPINGS[country_value]
            subquery += f"      ?organization wdt:P17 wd:{country_qid} .\n"
        else:
            raise ValueError(
                f"Unknown country '{country_value}'. "
                f"Supported values: {', '.join(sorted(COUNTRY_MAPPINGS.keys()))}, "
                "or a QID starting with Q"
            )

    # Add quidNum for keyset pagination and outer ordering
    subquery += '      BIND(xsd:integer(STRAFTER(STR(?organization), "/entity/Q")) AS ?qidNum)\n'

    # Add keyset pagination to subquery if provided
    if after_qid and after_qid.startswith("Q"):
        validated_qid = validate_qid(after_qid)
        try:
            after_qnum = int(validated_qid[1:])
            subquery += f"      FILTER(?qidNum > {after_qnum})\n"
        except ValueError:
            pass

    # Close subquery with ordering and pagination
    subquery += "    }\n    ORDER BY ?qidNum\n"
    subquery += f"    LIMIT {limit}\n"

    if (not after_qid) and cursor > 0:
        subquery += f"    OFFSET {cursor}\n"

    subquery += "  }\n"

    # Build outer query with optional properties
    query = (
        "SELECT ?organization ?organizationLabel ?description\n"
        "       ?typeLabel ?countryLabel\n"
        "       ?foundedDate ?dissolvedDate\n"
        "       ?image\n"
        "WHERE {\n"
    )
    query += subquery
    query += """
  OPTIONAL { ?organization wdt:P31 ?type. }
  OPTIONAL { ?organization wdt:P17 ?country. }
  OPTIONAL { ?organization wdt:P571 ?foundedDate. }
  OPTIONAL { ?organization wdt:P576 ?dissolvedDate. }
  OPTIONAL { ?organization wdt:P18 ?image. }

  OPTIONAL {
    ?organization schema:description ?description.
    FILTER(LANG(?description) = "%s")
  }

  SERVICE wikibase:label { bd:serviceParam wikibase:language "%s,en". }
}
ORDER BY ?qidNum
""" % (lang, lang)

    # Write query to file for debugging if DEBUG_QUERIES environment variable is set
    if os.getenv("DEBUG_QUERIES", "").lower() in ("true", "1", "yes"):
        with open("query_organization.rq", "w", encoding="utf-8") as f:
            f.write(query)

    return query
