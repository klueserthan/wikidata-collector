from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..models import Coordinates, PublicInstitution


def normalize_public_institution(
    item: Dict[str, Any],
    expanded_data: Optional[Dict[str, Any]],
) -> PublicInstitution:
    """Normalize Wikidata result to the public institution schema."""

    qid = item["institution"]["value"].split("/")[-1]
    current_time = datetime.now(timezone.utc).isoformat()

    if expanded_data is None:
        expanded_data = {}

    name_value = item.get("institutionLabel", {}).get("value")

    # Fallback to aliases or QID if name is missing or is just a QID
    needs_label_fallback = not name_value or (
        isinstance(name_value, str) and name_value.startswith("Q") and name_value[1:].isdigit()
    )
    if needs_label_fallback:
        # Try to use aliases from expanded data
        aliases = expanded_data.get("aliases", []) if isinstance(expanded_data, dict) else []
        alias_name = next((alias for alias in aliases if alias), None)
        if alias_name:
            name_value = alias_name
        # Final fallback to QID
        if not name_value:
            name_value = qid

    description_value = item.get("description", {}).get("value")

    image_value = item.get("image", {}).get("value")

    hq_coords_list = []
    coords_list = expanded_data.get("headquarters_coords", []) or []
    for coords_dict in coords_list:
        if (
            isinstance(coords_dict, dict)
            and coords_dict.get("lat") is not None
            and coords_dict.get("lon") is not None
        ):
            hq_coords_list.append(Coordinates(lat=coords_dict["lat"], lon=coords_dict["lon"]))

    types = expanded_data.get("types", []) or []
    # If no types in expanded data, try to extract from item
    type_dict = item.get("type")
    if not types and type_dict and type_dict.get("value"):
        type_value = type_dict.get("value", "")
        type_qid = type_value.split("/")[-1] if "/" in type_value else type_value
        # Use the type label if available, otherwise use QID
        type_label = item.get("typeLabel", {}).get("value") or type_qid
        if type_label:
            types = [type_label]

    founded_date = None
    founded_dates = expanded_data.get("founded", []) or []
    if founded_dates:
        founded_date = founded_dates[0]
    else:
        founded_date = item.get("foundedDate", {}).get("value")

    dissolved_date = item.get("dissolvedDate", {}).get("value")

    # Countries as labels (from expanded_data if provided, else from item)
    countries = expanded_data.get("country", []) or []
    if not countries:
        country_label = item.get("countryLabel", {}).get("value")
        if country_label:
            countries = [country_label]

    # Social handles as direct fields on the model

    return PublicInstitution(
        id=qid,
        entity_kind="public_institution",
        name=name_value,
        # aliases not part of current model surface
        description=description_value,
        founded_date=founded_date,
        dissolved_date=dissolved_date,
        countries=countries,
        types=types,
        image=image_value,
        instagram_handle=item.get("instagramHandle", {}).get("value"),
        twitter_handle=item.get("twitterHandle", {}).get("value"),
        facebook_handle=item.get("facebookHandle", {}).get("value"),
        youtube_handle=item.get("youtubeHandle", {}).get("value"),
        updated_at=current_time,
    )
