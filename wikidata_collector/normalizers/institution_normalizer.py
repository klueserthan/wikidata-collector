from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..models import AccountEntry, Coordinates, PublicInstitution, WebsiteEntry


def normalize_public_institution(
    item: Dict[str, Any],
    expanded_data: Optional[Dict[str, Any]],
) -> PublicInstitution:
    """Normalize Wikidata result to the public institution schema."""

    qid = item["institution"]["value"].split("/")[-1]
    current_time = datetime.now(timezone.utc).isoformat()

    if expanded_data is None:
        expanded_data = {
            "aliases": [],
            "types": [],
            "country": [],
            "country_code": [],
            "jurisdiction": [],
            "founded": [],
            "legal_form": [],
            "headquarters": [],
            "headquarters_coords": [],
            "website": [],
            "official_language": [],
            "logo": [],
            "budget": [],
            "parent_institution": [],
            "sector": [],
            "affiliations": [],
            "accounts": [],
        }

    for key in [
        "aliases",
        "types",
        "country",
        "country_code",
        "jurisdiction",
        "founded",
        "legal_form",
        "headquarters",
        "headquarters_coords",
        "website",
        "official_language",
        "logo",
        "budget",
        "parent_institution",
        "sector",
        "affiliations",
        "accounts",
    ]:
        if key not in expanded_data or expanded_data[key] is None:
            expanded_data[key] = []

    name_value = item.get("institutionLabel", {}).get("value")

    # Fallback to aliases or QID if name is missing or is just a QID
    needs_label_fallback = not name_value or (
        isinstance(name_value, str)
        and name_value.startswith("Q")
        and name_value[1:].isdigit()
    )
    if needs_label_fallback:
        # Try to use aliases from expanded data
        aliases = (
            expanded_data.get("aliases", [])
            if isinstance(expanded_data, dict)
            else []
        )
        alias_name = next((alias for alias in aliases if alias), None)
        if alias_name:
            name_value = alias_name
        # Final fallback to QID
        if not name_value:
            name_value = qid

    description_value = item.get("description", {}).get("value")

    image_list = []
    if item.get("image", {}).get("value"):
        image_list.append(item["image"]["value"])

    website_list = [WebsiteEntry(**w) for w in expanded_data.get("website", [])]
    accounts_list = [AccountEntry(**a) for a in expanded_data.get("accounts", [])]

    hq_coords_list = []
    coords_list = expanded_data.get("headquarters_coords", []) or []
    for coords_dict in coords_list:
        if (
            isinstance(coords_dict, dict)
            and coords_dict.get("lat") is not None
            and coords_dict.get("lon") is not None
        ):
            hq_coords_list.append(
                Coordinates(lat=coords_dict["lat"], lon=coords_dict["lon"])
            )

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

    founded_value = None
    founded_dates = expanded_data.get("founded", []) or []
    if founded_dates:
        founded_value = founded_dates[0]
    elif not founded_dates:
        founded_date = item.get("foundedDate", {}).get("value")
        if founded_date:
            founded_value = founded_date

    country_codes = expanded_data.get("country_code", []) or []

    jurisdictions = expanded_data.get("jurisdiction", []) or []
    if not jurisdictions:
        jurisdiction_label = item.get("jurisdictionLabel", {}).get("value")
        if jurisdiction_label:
            jurisdictions = [jurisdiction_label]

    logos = expanded_data.get("logo", []) or []
    if not logos and image_list:
        logos = image_list

    def add_account(platform: str, handle: Optional[str]):
        if not handle:
            return
        if not any(
            acc.platform == platform and acc.handle == handle for acc in accounts_list
        ):
            accounts_list.append(
                AccountEntry(
                    platform=platform,
                    handle=handle,
                    source="wikidata",
                    retrieved_at=current_time,
                )
            )

    add_account("twitter", item.get("twitterHandle", {}).get("value"))
    add_account("instagram", item.get("instagramHandle", {}).get("value"))
    add_account("facebook", item.get("facebookHandle", {}).get("value"))
    add_account("youtube", item.get("youtubeHandle", {}).get("value"))
    add_account("tiktok", item.get("tiktokHandle", {}).get("value"))

    return PublicInstitution(
        id=qid,
        entity_kind="public_institution",
        name=name_value,
        aliases=expanded_data.get("aliases", []) or [],
        description=description_value,
        founded=founded_value,
        country=country_codes,
        jurisdiction=jurisdictions,
        types=types,
        legal_form=expanded_data.get("legal_form", []) or [],
        headquarters=expanded_data.get("headquarters", []) or [],
        headquarters_coords=hq_coords_list,
        website=website_list,
        official_language=expanded_data.get("official_language", []) or [],
        logo=logos,
        budget=expanded_data.get("budget", []) or [],
        parent_institution=expanded_data.get("parent_institution", []) or [],
        sub_institutions=[],  # populated when expand=sub_institutions
        sector=expanded_data.get("sector", []) or [],
        affiliations=expanded_data.get("affiliations", []) or [],
        accounts=accounts_list,
        updated_at=current_time,
    )
