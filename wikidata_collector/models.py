from datetime import datetime
from logging import getLogger
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional

if TYPE_CHECKING:
    from wikidata_collector.models import AccountEntry

from pydantic import BaseModel

logger = getLogger(__name__)

SOCIAL_MEDIA_PLATFORMS = ["instagram", "twitter", "facebook", "youtube"]


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
                    retrieved_at=datetime.utcnow().isoformat(),
                )
            )
    return accounts


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


class Coordinates(BaseModel):
    lat: float
    lon: float


class SubInstitution(BaseModel):
    _id: str
    name: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None


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

    # Backwards-compatible view properties expected by existing tests
    @property
    def birthday(self) -> Optional[str]:  # pragma: no cover - formatting alias
        if not self.birth_date:
            return None
        dt = self.birth_date
        iso = dt.isoformat()
        # Normalize to trailing 'Z' when UTC
        if iso.endswith("+00:00"):
            return iso[:-6] + "Z"
        if dt.tzinfo is None:
            return iso + "Z"
        return iso

    @property
    def deathday(self) -> Optional[str]:  # pragma: no cover - formatting alias
        if not self.death_date:
            return None
        dt = self.death_date
        iso = dt.isoformat()
        if iso.endswith("+00:00"):
            return iso[:-6] + "Z"
        if dt.tzinfo is None:
            return iso + "Z"
        return iso

    @property
    def nationalities(self) -> List[str]:  # pragma: no cover - alias to countries
        return self.countries

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
        # Collect social media accounts
        accounts = existing.accounts.copy()
        new_accounts = _collect_accounts(new_record)
        for account in new_accounts:
            if all(acc.handle != account.handle for acc in accounts):
                accounts.append(account)

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


class PublicInstitutionBase(BaseModel):
    entity_kind: Literal["public_institution"] = "public_institution"
    qid: str
    name: str

    # Backwards-compatible alias used by integration tests
    @property
    def id(self) -> str:  # pragma: no cover - alias for compatibility
        return self.qid


class PublicInstitutionWikiRecord(PublicInstitutionBase):
    """Normalized view of fields returned by build_public_institutions_query."""

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

    @classmethod
    def from_wikidata(cls, item: Dict[str, Any]) -> "PublicInstitutionWikiRecord":
        """Create PublicInstitutionWikiRecord from a Wikidata item dictionary.

        Raises:
            KeyError: If required fields are missing from the item dictionary
            ValueError: If validation fails for the record data
        """
        try:
            qid = item["institution"]["value"].split("/")[-1]
        except (KeyError, IndexError) as e:
            logger.error(f"Failed to extract QID from item: {e}")
            raise KeyError(f"Missing or invalid 'institution' field in item: {e}")

        return cls(
            qid=qid,
            name=item.get("institutionLabel", {}).get("value"),
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
        )


class PublicInstitutionNormalizedRecord(PublicInstitutionBase):
    """Fully normalized public institution record that collects multiple values per field in lists.
    Uses AccountEntry, WebsiteEntry, etc."""

    description: Optional[str] = None
    founded_date: Optional[datetime] = None
    dissolved_date: Optional[datetime] = None
    image: Optional[str] = None
    countries: List[str] = []
    types: List[str] = []
    websites: List[WebsiteEntry] = []
    accounts: List[AccountEntry] = []

    @classmethod
    def from_wikidata_record(
        cls, record: PublicInstitutionWikiRecord
    ) -> "PublicInstitutionNormalizedRecord":
        """Create PublicInstitutionNormalizedRecord from a PublicInstitutionWikiRecord."""
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
        cls, existing: "PublicInstitutionNormalizedRecord", new_record: PublicInstitutionWikiRecord
    ) -> "PublicInstitutionNormalizedRecord":
        """Add data from multiple value fields to the existing PublicInstitutionNormalizedRecord."""
        # Collect social media accounts
        accounts = existing.accounts.copy()
        new_accounts = _collect_accounts(new_record)
        for account in new_accounts:
            if all(acc.handle != account.handle for acc in accounts):
                accounts.append(account)

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


# class PaginatedResponse(BaseModel):
#     data: List[Dict[str, Any]]
#     next_cursor: Optional[str] = None
#     has_more: bool = False
