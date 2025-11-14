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


class PublicFigure(BaseModel):
    id: Optional[str] = None
    entity_kind: Optional[str] = "public_figure"
    name: Optional[str] = None
    aliases: List[str] = []
    description: Optional[str] = None
    birthday: Optional[str] = None
    deathday: Optional[str] = None
    gender: Optional[str] = None
    nationalities: List[str] = []
    professions: List[str] = []
    place_of_birth: Optional[str] = None
    place_of_death: Optional[str] = None
    residence: List[str] = []
    website: List[WebsiteEntry] = []
    accounts: List[AccountEntry] = []
    affiliations: List[str] = []
    notable_works: List[str] = []
    awards: List[str] = []
    identifiers: List[Identifier] = []
    image: List[str] = []
    updated_at: Optional[str] = None


class PublicInstitution(BaseModel):
    id: str
    entity_kind: Optional[str] = "public_institution"
    name: Optional[str] = None
    aliases: List[str] = []
    description: Optional[str] = None
    founded: Optional[str] = None
    country: List[str] = []
    jurisdiction: List[str] = []
    types: List[str] = []
    legal_form: List[str] = []
    headquarters: List[str] = []
    headquarters_coords: List[Coordinates] = []
    website: List[WebsiteEntry] = []
    official_language: List[str] = []
    logo: List[str] = []
    budget: List[str] = []
    parent_institution: List[str] = []
    sub_institutions: List[SubInstitution] = []
    sector: List[str] = []
    affiliations: List[str] = []
    accounts: List[AccountEntry] = []
    updated_at: Optional[str] = None


class PaginatedResponse(BaseModel):
    data: List[Dict[str, Any]]
    next_cursor: Optional[str] = None
    has_more: bool = False

