from typing import Any, Dict, List, Optional

from pydantic import BaseModel


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


class PublicFigureWikiRecord(BaseModel):
    """Normalized view of fields returned by build_public_figures_query."""

    qid: str  # QID, derived from ?person URI
    entity_kind: Optional[str] = "public_figure"
    name: Optional[str] = None  # ?personLabel
    description: Optional[str] = None  # ?description
    birth_date: Optional[str] = None  # ?birthDate
    death_date: Optional[str] = None  # ?deathDate
    gender: Optional[str] = None  # ?genderLabel
    countries: Optional[str] = None  # ?countryLabel
    occupations: Optional[str] = None  # ?occupationLabel
    image: Optional[str] = None  # ?image
    instagram_handle: Optional[str] = None  # ?instagramHandle
    twitter_handle: Optional[str] = None  # ?twitterHandle
    facebook_handle: Optional[str] = None  # ?facebookHandle
    youtube_handle: Optional[str] = None  # ?youtubeHandle


class PublicInstitutionWikiRecord(BaseModel):
    """Normalized view of fields returned by build_public_institutions_query."""

    qid: str  # QID, derived from ?institution URI
    entity_kind: Optional[str] = "public_institution"
    name: Optional[str] = None  # ?institutionLabel
    description: Optional[str] = None  # ?description
    founded_date: Optional[str] = None  # ?foundedDate
    dissolved_date: Optional[str] = None  # ?dissolvedDate
    countries: Optional[str] = None  # ?countryLabel
    types: Optional[str] = None  # ?typeLabel
    image: Optional[str] = None  # ?image
    instagram_handle: Optional[str] = None  # ?instagramHandle
    twitter_handle: Optional[str] = None  # ?twitterHandle
    facebook_handle: Optional[str] = None  # ?facebookHandle
    youtube_handle: Optional[str] = None  # ?youtubeHandle


class PaginatedResponse(BaseModel):
    data: List[Dict[str, Any]]
    next_cursor: Optional[str] = None
    has_more: bool = False
