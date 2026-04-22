"""SPARQL query builder for public figures."""

import os
from typing import List, Optional

from ..config import DEFAULT_LIMIT
from ..constants import COUNTRY_MAPPINGS, GENDER_MAPPINGS, PROFESSION_MAPPINGS
from ..security import validate_qid


def build_public_figures_query(
    birthday_from: Optional[str] = None,
    birthday_to: Optional[str] = None,
    country: Optional[str] = None,
    occupations: Optional[List[str]] = None,
    gender: Optional[str] = None,
    lang: str = "en",
    limit: Optional[int] = None,
    cursor: int = 0,
    after_qid: Optional[str] = None,
) -> str:
    """Build SPARQL query for public figures with optional filters.

    Args:
        birthday_from: Start date filter (ISO format)
        birthday_to: End date filter (ISO format)
        country: Country filter (country name or QID)
        occupations: List of occupation filters (mapped keys or QIDs)
        gender: Gender filter; one of "male", "female", "other" (includes no gender info),
            or a direct Wikidata QID (e.g. "Q6581097")
        lang: Language code for labels
        limit: Maximum results to return (defaults to DEFAULT_LIMIT)
        cursor: Offset for pagination
        after_qid: QID for keyset pagination

    Returns:
        SPARQL query string

    Raises:
        ValueError: If QID validation fails or unknown gender label provided
    """
    if limit is None:
        limit = DEFAULT_LIMIT
    # Build efficient subquery with core filters
    subquery = """
  {
    SELECT ?person ?birthDate ?qidNum WHERE {
      ?person wdt:P31 wd:Q5 ;
              wdt:P569 ?birthDate"""

    # Add nationality filter to subquery if provided
    if country:
        country_value = country.strip()
        if country_value.startswith("Q"):
            # Direct QID - validate it
            validated_qid = validate_qid(country_value)
            subquery += f" ;\n              wdt:P27 wd:{validated_qid}"
        elif country_value in COUNTRY_MAPPINGS:
            # Map country name to QID
            country_qid = COUNTRY_MAPPINGS[country_value]
            subquery += f" ;\n              wdt:P27 wd:{country_qid}"
        else:
            # Unknown country - skip filter or raise error
            raise ValueError(
                f"Unknown country '{country_value}'. "
                f"Supported countries: {', '.join(sorted(COUNTRY_MAPPINGS.keys()))}"
            )

    # Add profession filters to subquery if provided
    if occupations:
        for occupation in occupations:
            occupation_value = occupation.strip()
            if occupation_value.startswith("Q"):
                # Direct QID - validate it
                validated_qid = validate_qid(occupation_value)
                subquery += f" ;\n              wdt:P106 wd:{validated_qid}"
            elif occupation_value in PROFESSION_MAPPINGS:
                # Map profession name to QID
                profession_qid = PROFESSION_MAPPINGS[occupation_value]
                subquery += f" ;\n              wdt:P106 wd:{profession_qid}"
            else:
                # Unknown profession - skip filter or raise error
                raise ValueError(
                    f"Unknown profession '{occupation_value}'. "
                    f"Supported professions: {', '.join(sorted(PROFESSION_MAPPINGS.keys()))}"
                )

    subquery += " .\n"

    # Add gender filter to subquery if provided
    if gender:
        gender_value = gender.strip()
        if gender_value.startswith("Q"):
            # Direct QID - validate it and add as triple pattern
            validated_qid = validate_qid(gender_value)
            subquery += f"      ?person wdt:P21 wd:{validated_qid} .\n"
        elif gender_value in GENDER_MAPPINGS:
            mapped = GENDER_MAPPINGS[gender_value]
            if mapped == "other":
                # "other" means not male AND not female (includes no gender claim)
                subquery += "      FILTER NOT EXISTS { ?person wdt:P21 wd:Q6581097 }\n"
                subquery += "      FILTER NOT EXISTS { ?person wdt:P21 wd:Q6581072 }\n"
            else:
                subquery += f"      ?person wdt:P21 wd:{mapped} .\n"
        else:
            raise ValueError(
                f"Unknown gender '{gender_value}'. "
                f"Supported genders: {', '.join(sorted(GENDER_MAPPINGS.keys()))} or a QID"
            )

    # Add date filters to subquery
    if birthday_from:
        subquery += f'      FILTER(?birthDate >= "{birthday_from}T00:00:00Z"^^xsd:dateTime)\n'
    if birthday_to:
        subquery += f'      FILTER(?birthDate <= "{birthday_to}T23:59:59Z"^^xsd:dateTime)\n'

    # Add quidNum for keyset pagination and outer ordering
    subquery += '      BIND(xsd:integer(STRAFTER(STR(?person), "/entity/Q")) AS ?qidNum)\n'

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
        "SELECT ?person ?personLabel ?description\n"
        "       ?birthDate ?deathDate\n"
        "       ?genderLabel\n"
        "       ?countryLabel\n"
        "       ?occupationLabel\n"
        "       ?image\n"
        "       ?instagramHandle ?twitterHandle ?facebookHandle ?youtubeHandle ?tiktokHandle\n"
        "WHERE {\n"
    )
    query += subquery
    query += """
  OPTIONAL { ?person wdt:P570 ?deathDate. }
  OPTIONAL { ?person wdt:P21  ?gender. }
  OPTIONAL { ?person wdt:P27  ?country. }
  OPTIONAL { ?person wdt:P18  ?image. }

  OPTIONAL { ?person wdt:P106 ?occupation. }

  OPTIONAL { ?person wdt:P2003 ?instagramHandle. }
  OPTIONAL { ?person wdt:P2002 ?twitterHandle. }
  OPTIONAL { ?person wdt:P2013 ?facebookHandle. }
  OPTIONAL { ?person wdt:P2397 ?youtubeHandle. }
  OPTIONAL { ?person wdt:P7085 ?tiktokHandle. }

  OPTIONAL {
    ?person schema:description ?description.
    FILTER(LANG(?description) = "%s")
  }

  SERVICE wikibase:label { bd:serviceParam wikibase:language "%s". }
}
ORDER BY ?qidNum
""" % (lang, lang)

    # Write query to file for debugging if DEBUG_QUERIES environment variable is set
    if os.getenv("DEBUG_QUERIES", "").lower() in ("true", "1", "yes"):
        with open("query_person.rq", "w", encoding="utf-8") as f:
            f.write(query)
    return query
