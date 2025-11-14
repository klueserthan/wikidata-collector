"""SPARQL query builder for public figures."""

from typing import List, Optional

from ..security import validate_qid, escape_sparql_literal


def build_public_figures_query(
    birthday_from: Optional[str] = None,
    birthday_to: Optional[str] = None,
    nationality: Optional[List[str]] = None,
    profession: Optional[List[str]] = None,
    lang: str = "en",
    limit: int = 100,
    cursor: int = 0,
    after_qid: Optional[str] = None,
) -> str:
    """Build SPARQL query for public figures with optional filters.
    
    Args:
        birthday_from: Start date filter (ISO format)
        birthday_to: End date filter (ISO format)
        nationality: List of nationality filters (QIDs, ISO codes, or labels)
        profession: List of profession filters (QIDs or labels)
        lang: Language code for labels
        limit: Maximum results to return
        cursor: Offset for pagination
        after_qid: QID for keyset pagination
        
    Returns:
        SPARQL query string
        
    Raises:
        ValueError: If QID validation fails
    """
    query = f"""
    SELECT DISTINCT ?person ?personLabel ?description ?birthDate ?deathDate ?genderLabel ?countryLabel ?occupationLabel ?image ?instagramHandle ?twitterHandle ?facebookHandle ?youtubeHandle WHERE {{
    ?person wdt:P31 wd:Q5;
            wdt:P569 ?birthDate.
    """

    if birthday_from:
        query += f'  FILTER(?birthDate >= "{birthday_from}T00:00:00Z"^^xsd:dateTime)\n'
    if birthday_to:
        query += f'  FILTER(?birthDate <= "{birthday_to}T23:59:59Z"^^xsd:dateTime)\n'

    nationality_filter_applied = False
    if nationality:
        nationality_conditions = []
        for nat in nationality:
            nat_value = nat.strip()
            if nat_value.startswith("Q"):
                # Validate QID format
                validated_qid = validate_qid(nat_value)
                nationality_conditions.append(f"?person wdt:P27 wd:{validated_qid}.")
            elif len(nat_value) == 3 and nat_value.isalpha():
                # ISO country code
                code = escape_sparql_literal(nat_value.upper())
                nationality_conditions.append(f'?person wdt:P27 ?country. ?country wdt:P298 "{code}".')
            else:
                # Label filter - escape to prevent injection
                escaped_label = escape_sparql_literal(nat_value)
                nationality_conditions.append(
                    f'?person wdt:P27 ?country. ?country rdfs:label "{escaped_label}"@{lang}.'
                )
        query += "  " + " ".join(nationality_conditions) + "\n"
        nationality_filter_applied = True

    profession_filter_applied = False
    if profession:
        profession_conditions = []
        for prof in profession:
            prof_value = prof.strip()
            if prof_value.startswith("Q"):
                # Validate QID format
                validated_qid = validate_qid(prof_value)
                profession_conditions.append(f"?person wdt:P106 wd:{validated_qid}.")
            else:
                # Label filter - escape to prevent injection
                escaped_label = escape_sparql_literal(prof_value)
                profession_conditions.append(
                    f'?person wdt:P106 ?occupation. ?occupation rdfs:label "{escaped_label}"@{lang}.'
                )
        query += "  " + " ".join(profession_conditions) + "\n"
        profession_filter_applied = True

    query += """
    OPTIONAL { ?person wdt:P570 ?deathDate. }
    OPTIONAL { ?person wdt:P21 ?gender. }
    """

    if not nationality_filter_applied:
        query += """
    OPTIONAL { ?person wdt:P27 ?country. }
    """

    if not profession_filter_applied:
        query += """
    OPTIONAL { ?person wdt:P106 ?occupation. }
    """

    query += """
    OPTIONAL { ?person wdt:P18 ?image. }
    OPTIONAL { ?person wdt:P2003 ?instagramHandle. }
    OPTIONAL { ?person wdt:P2002 ?twitterHandle. }
    OPTIONAL { ?person wdt:P2013 ?facebookHandle. }
    OPTIONAL { ?person wdt:P2397 ?youtubeHandle. }
    SERVICE wikibase:label {
        bd:serviceParam wikibase:language "en".
        ?person rdfs:label ?personLabel.
        ?gender rdfs:label ?genderLabel.
        ?country rdfs:label ?countryLabel.
        ?occupation rdfs:label ?occupationLabel.
        ?person schema:description ?description.
    }
    """

    if after_qid and after_qid.startswith("Q"):
        # Validate and use keyset pagination
        validated_qid = validate_qid(after_qid)
        try:
            after_qnum = int(validated_qid[1:])
            query += (
                '\nBIND(xsd:integer(STRAFTER(STR(?person), "Q")) AS ?qidNum)\n'
                f"FILTER(?qidNum > {after_qnum})\n"
            )
        except ValueError:
            pass

    query += "}"

    query += "\nORDER BY ?person"
    page_limit = max(1, int(limit) + 1)
    query += f"\nLIMIT {page_limit}"

    if (not after_qid) and cursor > 0:
        query += f"\nOFFSET {cursor}"

    return query

