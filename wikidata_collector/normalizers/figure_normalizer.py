from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..models import PublicFigureWikiRecord


def normalize_public_figure(
    item: Dict[str, Any],
    expanded_data: Optional[Dict[str, Any]],
) -> PublicFigureWikiRecord:
    """Normalize Wikidata result to the public figure schema."""

    qid = item["person"]["value"].split("/")[-1]
    current_time = datetime.now(timezone.utc).isoformat()

    # Expanded data is optional; only keys we may use are gender/nationalities/professions
    if expanded_data is None:
        expanded_data = {}

    name_value = item.get("personLabel", {}).get("value")

    description_value = item.get("description", {}).get("value")

    gender_value = expanded_data.get("gender")
    if gender_value is None:
        gender_label = item.get("genderLabel", {}).get("value")
        if gender_label:
            gender_value = gender_label.lower()

    birth_date = item.get("birthDate", {}).get("value")
    death_date = item.get("deathDate", {}).get("value")

    image_value = item.get("image", {}).get("value")

    countries = expanded_data.get("nationalities", []) or []
    if not countries:
        country_label = item.get("countryLabel", {}).get("value")
        if country_label:
            countries = [country_label]

    occupations = expanded_data.get("professions", []) or []
    if not occupations:
        occupation_label = item.get("occupationLabel", {}).get("value")
        if occupation_label:
            occupations = [occupation_label]

    return PublicFigureWikiRecord(
        id=qid,
        entity_kind="public_figure",
        name=name_value,
        # aliases not part of the current query/model surface
        description=description_value,
        birth_date=birth_date,
        death_date=death_date,
        gender=gender_value,
        countries=countries,
        occupations=occupations,
        image=image_value,
        instagram_handle=item.get("instagramHandle", {}).get("value"),
        twitter_handle=item.get("twitterHandle", {}).get("value"),
        facebook_handle=item.get("facebookHandle", {}).get("value"),
        youtube_handle=item.get("youtubeHandle", {}).get("value"),
        updated_at=current_time,
    )
