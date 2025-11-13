from typing import List, Optional

from api.config import config
from api.utils import TYPE_MAPPINGS


def build_public_institutions_query(
    country: Optional[str] = None,
    type: Optional[List[str]] = None,
    jurisdiction: Optional[str] = None,
    lang: Optional[str] = None,
    limit: Optional[int] = None,
    cursor: int = 0,
    after_qid: Optional[str] = None,
) -> str:
    """Build SPARQL query for public institutions with optional filters."""

    lang = lang or config.DEFAULT_LANG
    query_limit = limit or config.DEFAULT_LIMIT
    type_mappings = TYPE_MAPPINGS

    query = f"""
    SELECT DISTINCT ?institution ?institutionLabel ?description ?type ?countryLabel ?jurisdictionLabel ?foundedDate ?dissolvedDate ?image ?instagramHandle ?twitterHandle ?facebookHandle ?youtubeHandle  WHERE {{
    ?institution wdt:P31 ?type.
    """

    if type:
        type_conditions = []
        for value in type:
            if value in type_mappings:
                type_conditions.append(f"?institution wdt:P31 wd:{type_mappings[value]}.")
            elif value.startswith("Q"):
                type_conditions.append(f"?institution wdt:P31 wd:{value}.")
            else:
                type_conditions.append(
                    f'?institution wdt:P31 ?type. ?type rdfs:label "{value}"@{lang}.'
                )
        query += "  " + " ".join(type_conditions) + "\n"

    country_filter_applied = False
    if country:
        country_value = country.strip()
        if country_value.startswith("Q"):
            query += f"  ?institution wdt:P17 wd:{country_value}.\n"
            country_filter_applied = True
        elif len(country_value) == 3 and country_value.isalpha():
            code = country_value.upper()
            query += "  ?institution wdt:P17 ?country.\n"
            query += f'  ?country wdt:P298 "{code}".\n'
            country_filter_applied = True
        else:
            query += (
                f'  ?institution wdt:P17 ?country. ?country rdfs:label "{country_value}"@{lang}.\n'
            )
            country_filter_applied = True

    jurisdiction_filter_applied = False
    if jurisdiction:
        if jurisdiction.startswith("Q"):
            query += f"  ?institution wdt:P1001 wd:{jurisdiction}.\n"
            jurisdiction_filter_applied = True
        else:
            query += (
                f'  ?institution wdt:P1001 ?jurisdiction. ?jurisdiction rdfs:label "{jurisdiction}"@{lang}.\n'
            )
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
        try:
            after_qnum = int(after_qid[1:])
            query += (
                '\nBIND(xsd:integer(STRAFTER(STR(?institution), "Q")) AS ?qidNum)\n'
                f"FILTER(?qidNum > {after_qnum})\n"
            )
        except ValueError:
            pass

    query += "}"

    query += "\nORDER BY ?institution"
    page_limit = max(1, int(query_limit) + 1)
    query += f"\nLIMIT {page_limit}"

    if (not after_qid) and cursor > 0:
        query += f"\nOFFSET {cursor}"

    return query

