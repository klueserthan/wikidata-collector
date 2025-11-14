from typing import Any, Dict, Optional

from core.models import AccountEntry, Identifier, PublicFigure, WebsiteEntry


def normalize_public_figure(
    item: Dict[str, Any],
    expanded_data: Optional[Dict[str, Any]],
    lang: str,
    wiki_service,
) -> PublicFigure:
    """Normalize Wikidata result to the public figure schema."""

    qid = item["person"]["value"].split("/")[-1]
    current_time = wiki_service.get_current_timestamp()

    if expanded_data is None:
        expanded_data = {
            "aliases": [],
            "gender": None,
            "nationalities": [],
            "professions": [],
            "place_of_birth": [],
            "place_of_death": [],
            "residence": [],
            "website": [],
            "accounts": [],
            "affiliations": [],
            "notable_works": [],
            "awards": [],
            "identifiers": [],
        }

    for key in [
        "aliases",
        "nationalities",
        "professions",
        "place_of_birth",
        "place_of_death",
        "residence",
        "website",
        "accounts",
        "affiliations",
        "notable_works",
        "awards",
        "identifiers",
    ]:
        if key not in expanded_data or expanded_data[key] is None:
            expanded_data[key] = []

    name_value = item.get("personLabel", {}).get("value")

    description_value = item.get("description", {}).get("value")

    gender_value = expanded_data.get("gender")
    if gender_value is None:
        gender_label = item.get("genderLabel", {}).get("value")
        if gender_label:
            gender_value = gender_label.lower()

    birthday_value = item.get("birthDate", {}).get("value")
    deathday_value = item.get("deathDate", {}).get("value")

    image_list = []
    if item.get("image", {}).get("value"):
        image_list.append(item["image"]["value"])

    website_list = [WebsiteEntry(**w) for w in expanded_data.get("website", [])]
    accounts_list = [AccountEntry(**a) for a in expanded_data.get("accounts", [])]
    identifiers_list = [Identifier(**i) for i in expanded_data.get("identifiers", [])]

    def add_account(platform: str, handle: Optional[str]):
        if not handle:
            return
        if not any(acc.platform == platform and acc.handle == handle for acc in accounts_list):
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

    nationalities = expanded_data.get("nationalities", []) or []
    if not nationalities:
        country_label = item.get("countryLabel", {}).get("value")
        if country_label:
            nationalities = [country_label]

    professions = expanded_data.get("professions", []) or []
    if not professions:
        occupation_label = item.get("occupationLabel", {}).get("value")
        if occupation_label:
            professions = [occupation_label]

    place_of_birth_list = expanded_data.get("place_of_birth", []) or []
    place_of_birth_value = place_of_birth_list[0] if place_of_birth_list else None

    place_of_death_list = expanded_data.get("place_of_death", []) or []
    place_of_death_value = place_of_death_list[0] if place_of_death_list else None

    return PublicFigure(
        id=qid,
        entity_kind="public_figure",
        name=name_value,
        aliases=expanded_data.get("aliases", []) or [],
        description=description_value,
        birthday=birthday_value,
        deathday=deathday_value,
        gender=gender_value,
        nationalities=nationalities,
        professions=professions,
        place_of_birth=place_of_birth_value,
        place_of_death=place_of_death_value,
        residence=expanded_data.get("residence", []) or [],
        website=website_list,
        accounts=accounts_list,
        affiliations=expanded_data.get("affiliations", []) or [],
        notable_works=expanded_data.get("notable_works", []) or [],
        awards=expanded_data.get("awards", []) or [],
        identifiers=identifiers_list,
        image=image_list,
        updated_at=current_time,
    )

