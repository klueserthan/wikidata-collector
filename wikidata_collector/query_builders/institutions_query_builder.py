"""SPARQL query builder for public institutions."""

from typing import List, Optional

from ..constants import COUNTRY_MAPPINGS, TYPE_MAPPINGS
from ..security import validate_qid


def build_public_institutions_query(
    country: Optional[str] = None,
    type: Optional[List[str]] = None,
    lang: str = "en",
    limit: int = 100,
    cursor: int = 0,
    after_qid: Optional[str] = None,
) -> str:
    """Build SPARQL query for public institutions with optional filters.

    Args:
        country: Country filter (QID or label)
        type: List of institution type filters (mapped keys, QIDs, or labels)
        lang: Language code for labels
        limit: Maximum results to return
        cursor: Offset for pagination
        after_qid: QID for keyset pagination

    Returns:
        SPARQL query string

    Raises:
        ValueError: If QID validation fails
    """
    # Build efficient subquery with core filters
    subquery = """
  {
    SELECT ?institution WHERE {"""

    # Build the WHERE clause conditions
    conditions = []

    # Add type filters to subquery if provided
    if type:
        for value in type:
            value = value.strip()
            if value in TYPE_MAPPINGS:
                # Use mapped QID
                mapped_qid = TYPE_MAPPINGS[value]
                conditions.append(f"wdt:P31 wd:{mapped_qid}")
            elif value.startswith("Q"):
                # Validate QID format
                validated_qid = validate_qid(value)
                conditions.append(f"wdt:P31 wd:{validated_qid}")
            else:
                # Unknown type - skip or raise error
                raise ValueError(
                    f"Unknown institution type '{value}'. "
                    f"Supported types: {', '.join(sorted(TYPE_MAPPINGS.keys()))}"
                )

    # Add country filter to subquery if provided
    if country:
        country_value = country.strip()
        if country_value.startswith("Q"):
            # Direct QID - validate it
            validated_qid = validate_qid(country_value)
            conditions.append(f"wdt:P17 wd:{validated_qid}")

        elif country_value in COUNTRY_MAPPINGS:
            # Map country name to QID
            country_qid = COUNTRY_MAPPINGS[country_value]
            conditions.append(f"wdt:P17 wd:{country_qid}")
        else:
            raise ValueError(
                f"Country filter must be a QID (starting with Q), got: {country_value}"
            )

    # Build the triple pattern
    if conditions:
        subquery += "\n      ?institution " + conditions[0]
        for condition in conditions[1:]:
            subquery += " ;\n                   " + condition
        subquery += " .\n"
    else:
        # If no filters, just match any institution with a type
        subquery += "\n      ?institution wdt:P31 ?type .\n"

    # Add quidNum for keyset pagination and outer ordering
    subquery += '      BIND(xsd:integer(STRAFTER(STR(?institution), "/entity/Q")) AS ?qidNum)\n'

    # Add keyset pagination to subquery if provided
    if after_qid and after_qid.startswith("Q"):
        validated_qid = validate_qid(after_qid)
        try:
            after_qnum = int(validated_qid[1:])
            subquery += f"      FILTER(?qidNum > {after_qnum})\n"
        except ValueError:
            pass

    # Close subquery with ordering and pagination
    subquery += "    }\n    ORDER BY ?institution\n"
    subquery += f"    LIMIT {limit}\n"

    if (not after_qid) and cursor > 0:
        subquery += f"    OFFSET {cursor}\n"

    subquery += "  }\n"

    # Build outer query with optional properties
    query = (
        "SELECT ?institution ?institutionLabel ?description\n"
        "       ?typeLabel ?countryLabel\n"
        "       ?foundedDate ?dissolvedDate\n"
        "       ?image\n"
        "       ?instagramHandle ?twitterHandle ?facebookHandle ?youtubeHandle\n"
        "WHERE {\n"
    )
    query += subquery
    query += """
  OPTIONAL { ?institution wdt:P31 ?type. }
  OPTIONAL { ?institution wdt:P17 ?country. }
  OPTIONAL { ?institution wdt:P571 ?foundedDate. }
  OPTIONAL { ?institution wdt:P576 ?dissolvedDate. }
  OPTIONAL { ?institution wdt:P18 ?image. }

  OPTIONAL { ?institution wdt:P2003 ?instagramHandle. }
  OPTIONAL { ?institution wdt:P2002 ?twitterHandle. }
  OPTIONAL { ?institution wdt:P2013 ?facebookHandle. }
  OPTIONAL { ?institution wdt:P2397 ?youtubeHandle. }

  OPTIONAL {
    ?institution schema:description ?description.
    FILTER(LANG(?description) = "%s")
  }

  SERVICE wikibase:label { bd:serviceParam wikibase:language "%s". }
}
ORDER BY ?qidNum
""" % (lang, lang)

    # Write query to query.rq file for debugging
    with open("query_institution.rq", "w", encoding="utf-8") as f:
        f.write(query)

    return query
