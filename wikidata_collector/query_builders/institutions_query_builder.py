"""SPARQL query builder for public institutions."""

from typing import List, Optional

from ..constants import TYPE_MAPPINGS
from ..security import escape_sparql_literal, validate_qid


def build_public_institutions_query(
    country: Optional[str] = None,
    type: Optional[List[str]] = None,
    jurisdiction: Optional[str] = None,
    lang: str = "en",
    limit: int = 100,
    cursor: int = 0,
    after_qid: Optional[str] = None,
) -> str:
    """Build SPARQL query for public institutions with optional filters.

    Args:
        country: Country filter (QID, ISO code, or label)
        type: List of institution type filters (mapped keys, QIDs, or labels)
        jurisdiction: Jurisdiction filter (QID or label)
        lang: Language code for labels
        limit: Maximum results to return
        cursor: Offset for pagination
        after_qid: QID for keyset pagination

    Returns:
        SPARQL query string

    Raises:
        ValueError: If QID validation fails
    """
    query = """
    SELECT DISTINCT ?institution ?institutionLabel ?description ?type ?countryLabel ?jurisdictionLabel ?foundedDate ?dissolvedDate ?image ?instagramHandle ?twitterHandle ?facebookHandle ?youtubeHandle  WHERE {
    ?institution wdt:P31 ?type.
    """

    if type:
        type_conditions = []
        for value in type:
            value = value.strip()
            if value in TYPE_MAPPINGS:
                # Use mapped QID
                mapped_qid = TYPE_MAPPINGS[value]
                type_conditions.append(f"?institution wdt:P31 wd:{mapped_qid}.")
            elif value.startswith("Q"):
                # Validate QID format
                validated_qid = validate_qid(value)
                type_conditions.append(f"?institution wdt:P31 wd:{validated_qid}.")
            else:
                # Label filter - escape to prevent injection
                escaped_label = escape_sparql_literal(value)
                type_conditions.append(
                    f'?institution wdt:P31 ?type. ?type rdfs:label "{escaped_label}"@{lang}.'
                )
        query += "  " + " ".join(type_conditions) + "\n"

    country_filter_applied = False
    if country:
        country_value = country.strip()
        if country_value.startswith("Q"):
            # Validate QID format
            validated_qid = validate_qid(country_value)
            query += f"  ?institution wdt:P17 wd:{validated_qid}.\n"
            country_filter_applied = True
        elif len(country_value) == 3 and country_value.isalpha():
            # ISO country code
            code = escape_sparql_literal(country_value.upper())
            query += "  ?institution wdt:P17 ?country.\n"
            query += f'  ?country wdt:P298 "{code}".\n'
            country_filter_applied = True
        else:
            # Label filter - escape to prevent injection
            escaped_label = escape_sparql_literal(country_value)
            query += (
                f'  ?institution wdt:P17 ?country. ?country rdfs:label "{escaped_label}"@{lang}.\n'
            )
            country_filter_applied = True

    jurisdiction_filter_applied = False
    if jurisdiction:
        jurisdiction_value = jurisdiction.strip()
        if jurisdiction_value.startswith("Q"):
            # Validate QID format
            validated_qid = validate_qid(jurisdiction_value)
            query += f"  ?institution wdt:P1001 wd:{validated_qid}.\n"
            jurisdiction_filter_applied = True
        else:
            # Label filter - escape to prevent injection
            escaped_label = escape_sparql_literal(jurisdiction_value)
            query += f'  ?institution wdt:P1001 ?jurisdiction. ?jurisdiction rdfs:label "{escaped_label}"@{lang}.\n'
            jurisdiction_filter_applied = True

    if not country_filter_applied:
        query += "        OPTIONAL { ?institution wdt:P17 ?country. }\n"

    if not jurisdiction_filter_applied:
        query += "        OPTIONAL { ?institution wdt:P1001 ?jurisdiction. }\n"

    query += """
    OPTIONAL { ?institution wdt:P571 ?foundedDate. }
    OPTIONAL { ?institution wdt:P576 ?dissolvedDate. }
    OPTIONAL { ?institution wdt:P18 ?image. }
    OPTIONAL { ?institution wdt:P2003 ?instagramHandle. }
    OPTIONAL { ?institution wdt:P2002 ?twitterHandle. }
    OPTIONAL { ?institution wdt:P2013 ?facebookHandle. }
    OPTIONAL { ?institution wdt:P2397 ?youtubeHandle. }
    SERVICE wikibase:label {
        bd:serviceParam wikibase:language "en".
        ?institution rdfs:label ?institutionLabel.
        ?type rdfs:label ?typeLabel.
        ?country rdfs:label ?countryLabel.
        ?jurisdiction rdfs:label ?jurisdictionLabel.
        ?institution schema:description ?description.
    }
    """

    if after_qid and after_qid.startswith("Q"):
        # Validate and use keyset pagination
        validated_qid = validate_qid(after_qid)
        try:
            after_qnum = int(validated_qid[1:])
            query += (
                '\nBIND(xsd:integer(STRAFTER(STR(?institution), "Q")) AS ?qidNum)\n'
                f"FILTER(?qidNum > {after_qnum})\n"
            )
        except ValueError:
            pass

    query += "}"

    query += "\nORDER BY ?institution"
    page_limit = max(1, int(limit) + 1)
    query += f"\nLIMIT {page_limit}"

    if (not after_qid) and cursor > 0:
        query += f"\nOFFSET {cursor}"

    return query
