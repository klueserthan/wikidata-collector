# Data Model: Wikidata Public Entities ETL Package

## Overview

The data model is implemented using Pydantic v2 and is designed to represent public figures and
public institutions as normalized Python objects suitable for ETL pipelines. The models expand on
`wikidata_collector/models.py` and align with the feature specification.

## Core Entities

### PublicFigure

Represents an individual public figure.

Key fields (all strings are UTF-8 text unless otherwise noted):

- `id: str` — stable Wikidata identifier (e.g., `Q42`).
- `entity_kind: Literal["public_figure"] | None` — entity discriminator for downstream code.
- `name: str | None` — primary label in the requested language.
- `aliases: list[str]` — alternative names and spellings.
- `description: str | None` — short description from Wikidata.
- `birthday: str | None` — ISO-8601 date or datetime string for date of birth.
- `deathday: str | None` — ISO-8601 date or datetime string for date of death (if applicable).
- `gender: str | None` — human-readable gender label or code.
- `nationalities: list[str]` — list of nationalities (multi-valued by design).
- `professions: list[str]` — list of professions or occupations.
- `website: list[WebsiteEntry]` — normalized website entries.
- `accounts: list[AccountEntry]` — social media accounts (Twitter/X, Instagram, Facebook, TikTok, etc.).
- `identifiers: list[Identifier]` — external identifiers such as GND or VIAF.
- `image: list[str]` — image URLs.
- `updated_at: str | None` — timestamp when this record was last refreshed.

### PublicInstitution

Represents a public institution such as a government agency, NGO, municipality, or media outlet.

Key fields:

- `id: str` — stable Wikidata identifier.
- `entity_kind: Literal["public_institution"] | None` — entity discriminator.
- `name: str | None` — primary label.
- `aliases: list[str]` — alternative names.
- `description: str | None` — short description.
- `founded: str | None` — ISO-8601 date/datetime for founding date.
- `country: list[str]` — countries associated with the institution.
- `types: list[str]` — institution types (e.g., government agency, NGO).
- `headquarters: list[str]` — headquarters locations (labels or identifiers).
- `website: list[WebsiteEntry]` — official websites.
- `logo: list[str]` — logo image URLs.
- `accounts: list[AccountEntry]` — social media accounts.
- `updated_at: str | None` — last refresh timestamp.

### Supporting Types

- `WebsiteEntry` — `{ url: str, source: str, retrieved_at: str }`.
- `AccountEntry` — `{ platform: str, handle: str, source: str, retrieved_at: str }`.
- `Identifier` — `{ scheme: str, id: str }` for external identifier systems.

## Result and Filter Representations

### Result Set (Public API)

Iterator-based public APIs yield individual `PublicFigure` or `PublicInstitution` instances.
Internally, the library may still construct transient `PaginatedResponse`-like structures to
handle SPARQL result pages, but these are not exposed to callers.

### Filter Set

Filters are represented as simple, typed inputs to iterator functions (e.g., keyword arguments or
small settings objects). They cover:

- Public figures: `birthday` (range or single value), `nationality` (one or more human-readable
	labels or codes, such as ISO country codes like "US"/"DE").
- Public institutions: `founded` (range or single value), `country`, `types`, `headquarter`, all
	expressed as human-readable labels or codes (for example, country codes or type labels such as
	"public broadcaster").

Internally, the library translates these labels or codes into appropriate SPARQL constraints
(including any required Wikidata identifiers), but callers do not provide or handle QIDs directly.
The exact Python representation of filters is captured in the API contracts document.
