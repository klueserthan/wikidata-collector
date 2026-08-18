from datetime import datetime, timezone
from logging import getLogger
from typing import Any, Dict, List, Literal, Optional, Type, overload

from pydantic import BaseModel

logger = getLogger(__name__)

SOCIAL_MEDIA_PLATFORMS = ["instagram", "twitter", "facebook", "youtube", "tiktok"]


# Helper functions
def _parse_date(date_str: Optional[str], qid: str, field_name: str) -> Optional[datetime]:
    """Parse ISO format date string to datetime object."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        logger.warning(f"Invalid {field_name} format for QID {qid}")
        return None


def _collect_accounts(record: Any) -> List["AccountEntry"]:
    """Extract social media accounts from a record."""
    accounts = []
    for platform in SOCIAL_MEDIA_PLATFORMS:
        handle = getattr(record, f"{platform}_handle", None)
        if handle:
            accounts.append(
                AccountEntry(
                    platform=platform,
                    handle=handle,
                    source="wikidata",
                    retrieved_at=datetime.now(timezone.utc).isoformat(),
                )
            )
    return accounts


def _merge_accounts(
    existing: List["AccountEntry"], new_accounts: List["AccountEntry"]
) -> List["AccountEntry"]:
    """Return a copy of existing accounts with new ones appended, deduplicated by (platform, handle)."""
    merged = existing.copy()
    seen = {(acc.platform, acc.handle) for acc in merged}
    for account in new_accounts:
        key = (account.platform, account.handle)
        if key not in seen:
            merged.append(account)
            seen.add(key)
    return merged


# Nested models for structured data
class WebsiteEntry(BaseModel):
    url: str
    source: str
    retrieved_at: str


class AccountEntry(BaseModel):
    platform: str
    handle: str
    source: str
    retrieved_at: str


class Identifier(BaseModel):
    scheme: str
    id: str


class PublicFigureBase(BaseModel):
    entity_kind: Literal["public_figure"] = "public_figure"
    qid: str
    name: str

    # Backwards-compatible alias used by integration tests
    @property
    def id(self) -> str:  # pragma: no cover - alias for compatibility
        return self.qid


class PublicFigureWikiRecord(PublicFigureBase):
    """Normalized view of fields returned by build_public_figures_query."""

    description: Optional[str] = None  # ?description
    birth_date: Optional[datetime] = None  # ?birthDate
    death_date: Optional[datetime] = None  # ?deathDate
    gender: Optional[str] = None  # ?genderLabel
    country: Optional[str] = None  # ?countryLabel
    occupation: Optional[str] = None  # ?occupationLabel
    image: Optional[str] = None  # ?image
    instagram_handle: Optional[str] = None  # ?instagramHandle
    twitter_handle: Optional[str] = None  # ?twitterHandle
    facebook_handle: Optional[str] = None  # ?facebookHandle
    youtube_handle: Optional[str] = None  # ?youtubeHandle
    tiktok_handle: Optional[str] = None  # ?tiktokHandle

    @classmethod
    def from_wikidata(cls, item: Dict[str, Any]) -> "PublicFigureWikiRecord":
        """Create PublicFigureWikiRecord from a Wikidata item dictionary.

        Raises:
            KeyError: If required fields are missing from the item dictionary
            ValueError: If validation fails for the record data
        """
        try:
            qid = item["person"]["value"].split("/")[-1]
        except (KeyError, IndexError) as e:
            logger.error(f"Failed to extract QID from item: {e}")
            raise KeyError(f"Missing or invalid 'person' field in item: {e}")

        return cls(
            qid=qid,
            name=item.get("personLabel", {}).get("value"),
            description=item.get("description", {}).get("value"),
            birth_date=_parse_date(item.get("birthDate", {}).get("value"), qid, "birth date"),
            death_date=_parse_date(item.get("deathDate", {}).get("value"), qid, "death date"),
            gender=item.get("genderLabel", {}).get("value"),
            country=item.get("countryLabel", {}).get("value"),
            occupation=item.get("occupationLabel", {}).get("value"),
            image=item.get("image", {}).get("value"),
            instagram_handle=item.get("instagramHandle", {}).get("value"),
            twitter_handle=item.get("twitterHandle", {}).get("value"),
            facebook_handle=item.get("facebookHandle", {}).get("value"),
            youtube_handle=item.get("youtubeHandle", {}).get("value"),
            tiktok_handle=item.get("tiktokHandle", {}).get("value"),
        )


class PublicFigureNormalizedRecord(PublicFigureBase):
    """Fully normalized public figure record that collects multiple values per field in lists.
    Uses AccountEntry, WebsiteEntry, etc."""

    description: Optional[str] = None
    birth_date: Optional[datetime] = None
    death_date: Optional[datetime] = None
    gender: Optional[str] = None
    image: Optional[str] = None
    countries: List[str] = []
    occupations: List[str] = []
    websites: List[WebsiteEntry] = []
    accounts: List[AccountEntry] = []

    def generate_pretty_string(self) -> str:
        """Return a pretty-printed string representation of the record."""
        lines = [f"Public Figure: {self.name} ({self.qid})"]
        if self.description:
            lines.append(f"  Description: {self.description}")
        if self.birth_date:
            lines.append(f"  Birth Date: {self.birth_date.isoformat()}")
        if self.death_date:
            lines.append(f"  Death Date: {self.death_date.isoformat()}")
        if self.gender:
            lines.append(f"  Gender: {self.gender}")
        if self.image:
            lines.append(f"  Image: {self.image}")
        if self.countries:
            lines.append(f"  Countries: {', '.join(self.countries)}")
        if self.occupations:
            lines.append(f"  Occupations: {', '.join(self.occupations)}")
        if self.websites:
            lines.append("  Websites:")
            for website in self.websites:
                lines.append(f"    - {website.url} (source: {website.source})")
        if self.accounts:
            lines.append("  Accounts:")
            for account in self.accounts:
                lines.append(
                    f"    - {account.platform}: {account.handle} (source: {account.source})"
                )
        return "\n".join(lines)

    @classmethod
    def from_wikidata_record(cls, record: PublicFigureWikiRecord) -> "PublicFigureNormalizedRecord":
        """Create PublicFigureNormalizedRecord from a PublicFigureWikiRecord."""
        return cls(
            qid=record.qid,
            name=record.name,
            description=record.description,
            birth_date=record.birth_date,
            death_date=record.death_date,
            gender=record.gender,
            image=record.image,
            countries=[record.country] if record.country else [],
            occupations=[record.occupation] if record.occupation else [],
            accounts=_collect_accounts(record),
        )

    @classmethod
    def add_from_wikidata_record(
        cls, existing: "PublicFigureNormalizedRecord", new_record: PublicFigureWikiRecord
    ) -> "PublicFigureNormalizedRecord":
        """Add data from multiple value fields to the existing PublicFigureNormalizedRecord."""
        accounts = _merge_accounts(existing.accounts, _collect_accounts(new_record))

        # Collect countries
        countries = existing.countries.copy()
        if new_record.country and new_record.country not in countries:
            countries.append(new_record.country)

        # Collect occupations
        occupations = existing.occupations.copy()
        if new_record.occupation and new_record.occupation not in occupations:
            occupations.append(new_record.occupation)

        return cls(
            qid=existing.qid,
            name=existing.name,
            description=existing.description or new_record.description,
            birth_date=existing.birth_date or new_record.birth_date,
            death_date=existing.death_date or new_record.death_date,
            gender=existing.gender or new_record.gender,
            image=existing.image or new_record.image,
            countries=countries,
            occupations=occupations,
            accounts=accounts,
        )


class PublicOrganizationBase(BaseModel):
    entity_kind: Literal["public_organization"] = "public_organization"
    qid: str
    name: str

    # Backwards-compatible alias used by integration tests
    @property
    def id(self) -> str:  # pragma: no cover - alias for compatibility
        return self.qid


class PublicOrganizationWikiRecord(PublicOrganizationBase):
    """Normalized view of fields returned by build_public_organizations_query."""

    description: Optional[str] = None  # ?description
    founded_date: Optional[datetime] = None  # ?foundedDate
    dissolved_date: Optional[datetime] = None  # ?dissolvedDate
    country: Optional[str] = None  # ?countryLabel
    type: Optional[str] = None  # ?typeLabel
    image: Optional[str] = None  # ?image
    instagram_handle: Optional[str] = None  # ?instagramHandle
    twitter_handle: Optional[str] = None  # ?twitterHandle
    facebook_handle: Optional[str] = None  # ?facebookHandle
    youtube_handle: Optional[str] = None  # ?youtubeHandle
    tiktok_handle: Optional[str] = None  # ?tiktokHandle

    @classmethod
    def from_wikidata(cls, item: Dict[str, Any]) -> "PublicOrganizationWikiRecord":
        """Create PublicOrganizationWikiRecord from a Wikidata item dictionary.

        Raises:
            KeyError: If required fields are missing from the item dictionary
            ValueError: If validation fails for the record data
        """
        try:
            qid = item["organization"]["value"].split("/")[-1]
        except (KeyError, IndexError) as e:
            logger.error(f"Failed to extract QID from item: {e}")
            raise KeyError(f"Missing or invalid 'organization' field in item: {e}")

        return cls(
            qid=qid,
            name=item.get("organizationLabel", {}).get("value"),
            description=item.get("description", {}).get("value"),
            founded_date=_parse_date(item.get("foundedDate", {}).get("value"), qid, "founded date"),
            dissolved_date=_parse_date(
                item.get("dissolvedDate", {}).get("value"), qid, "dissolved date"
            ),
            country=item.get("countryLabel", {}).get("value"),
            type=item.get("typeLabel", {}).get("value"),
            image=item.get("image", {}).get("value"),
            instagram_handle=item.get("instagramHandle", {}).get("value"),
            twitter_handle=item.get("twitterHandle", {}).get("value"),
            facebook_handle=item.get("facebookHandle", {}).get("value"),
            youtube_handle=item.get("youtubeHandle", {}).get("value"),
            tiktok_handle=item.get("tiktokHandle", {}).get("value"),
        )


class PublicOrganizationNormalizedRecord(PublicOrganizationBase):
    """Fully normalized public organization record that collects multiple values per field in lists.
    Uses AccountEntry, WebsiteEntry, etc."""

    description: Optional[str] = None
    founded_date: Optional[datetime] = None
    dissolved_date: Optional[datetime] = None
    image: Optional[str] = None
    countries: List[str] = []
    types: List[str] = []
    websites: List[WebsiteEntry] = []
    accounts: List[AccountEntry] = []

    def generate_pretty_string(self) -> str:
        """Return a pretty-printed string representation of the record."""
        lines = [f"Public Organization: {self.name} ({self.qid})"]
        if self.description:
            lines.append(f"  Description: {self.description}")
        if self.founded_date:
            lines.append(f"  Founded Date: {self.founded_date.isoformat()}")
        if self.dissolved_date:
            lines.append(f"  Dissolved Date: {self.dissolved_date.isoformat()}")
        if self.countries:
            lines.append(f"  Countries: {', '.join(self.countries)}")
        if self.types:
            lines.append(f"  Types: {', '.join(self.types)}")
        if self.websites:
            lines.append("  Websites:")
            for website in self.websites:
                lines.append(f"    - {website.url} (source: {website.source})")
        if self.accounts:
            lines.append("  Social Media Accounts:")
            for account in self.accounts:
                lines.append(f"    - {account.platform}: {account.handle}")
        return "\n".join(lines)

    @classmethod
    def from_wikidata_record(
        cls, record: PublicOrganizationWikiRecord
    ) -> "PublicOrganizationNormalizedRecord":
        """Create PublicOrganizationNormalizedRecord from a PublicOrganizationWikiRecord."""
        return cls(
            qid=record.qid,
            name=record.name,
            description=record.description,
            founded_date=record.founded_date,
            dissolved_date=record.dissolved_date,
            image=record.image,
            countries=[record.country] if record.country else [],
            types=[record.type] if record.type else [],
            accounts=_collect_accounts(record),
        )

    @classmethod
    def add_from_wikidata_record(
        cls,
        existing: "PublicOrganizationNormalizedRecord",
        new_record: PublicOrganizationWikiRecord,
    ) -> "PublicOrganizationNormalizedRecord":
        """Add data from multiple value fields to the existing PublicOrganizationNormalizedRecord."""
        accounts = _merge_accounts(existing.accounts, _collect_accounts(new_record))

        # Collect countries
        countries = existing.countries.copy()
        if new_record.country and new_record.country not in countries:
            countries.append(new_record.country)

        # Collect types
        types = existing.types.copy()
        if new_record.type and new_record.type not in types:
            types.append(new_record.type)

        return cls(
            qid=existing.qid,
            name=existing.name,
            description=existing.description or new_record.description,
            founded_date=existing.founded_date or new_record.founded_date,
            dissolved_date=existing.dissolved_date or new_record.dissolved_date,
            image=existing.image or new_record.image,
            countries=countries,
            types=types,
            accounts=accounts,
        )


@overload
def normalize_bindings(
    bindings: List[Dict[str, Any]],
    wiki_record_cls: Type[PublicFigureWikiRecord],
    normalized_record_cls: Type[PublicFigureNormalizedRecord],
) -> List[PublicFigureNormalizedRecord]: ...


@overload
def normalize_bindings(
    bindings: List[Dict[str, Any]],
    wiki_record_cls: Type[PublicOrganizationWikiRecord],
    normalized_record_cls: Type[PublicOrganizationNormalizedRecord],
) -> List[PublicOrganizationNormalizedRecord]: ...


def normalize_bindings(
    bindings: List[Dict[str, Any]],
    wiki_record_cls: Any,
    normalized_record_cls: Any,
) -> List[Any]:
    """Aggregate consecutive same-QID SPARQL bindings into normalized records.

    SPARQL row expansion yields one row per value combination, ordered by QID.
    Consecutive rows sharing a QID are folded into a single normalized record via
    the record family's ``from_wikidata`` / ``from_wikidata_record`` /
    ``add_from_wikidata_record`` protocol. Rows that fail to parse are logged and
    skipped.

    Args:
        bindings: Raw SPARQL result bindings, ordered by QID
        wiki_record_cls: Wiki record class that parses a single binding
        normalized_record_cls: Normalized record class that aggregates same-QID records

    Returns:
        One normalized record per unique QID, in binding order
    """
    results: List[Any] = []
    current: Optional[Any] = None

    for binding in bindings:
        try:
            wiki_record = wiki_record_cls.from_wikidata(binding)
        except (KeyError, ValueError) as e:
            logger.warning(f"Failed to parse record: {e}")
            continue

        if current is None:
            current = normalized_record_cls.from_wikidata_record(wiki_record)
        elif wiki_record.qid == current.qid:
            current = normalized_record_cls.add_from_wikidata_record(current, wiki_record)
        else:
            results.append(current)
            current = normalized_record_cls.from_wikidata_record(wiki_record)

    if current is not None:
        results.append(current)

    return results
