# Data Model: Wikidata Public Entities ETL Package

## Overview

The data model is implemented using Pydantic v2 and is designed to represent public figures and
public institutions as normalized Python objects suitable for ETL pipelines. The models expand on
`wikidata_collector/models.py` and align with the feature specification.

## Core Entities

### PublicFigureNormalizedRecord

Represents an individual public figure after aggregating multiple SPARQL rows by QID.

**Note on Architecture**: SPARQL queries return one row per multi-valued field (e.g., each profession, award, or nationality). The library aggregates these rows by QID into normalized record objects.

Key fields (all strings are UTF-8 text unless otherwise noted):

- `qid: str` — stable Wikidata identifier (e.g., `Q42`).
- `id: str` — compatibility alias for `qid`.
- `entity_kind: Literal["public_figure"] | None` — entity discriminator for downstream code.
- `name: str | None` — primary label in the requested language.
- `aliases: list[str]` — alternative names and spellings.
- `description: str | None` — short description from Wikidata.
- `birth_date: str | None` — ISO-8601 datetime string for date of birth.
- `birthday: str` — formatted date string (YYYY-MM-DD) extracted from `birth_date`.
- `death_date: str | None` — ISO-8601 datetime string for date of death (if applicable).
- `gender: str | None` — human-readable gender label or code.
- `nationalities: list[str]` — list of nationalities (aggregated from multiple SPARQL rows).
- `professions: list[str]` — list of professions or occupations (aggregated).
- `website: list[WebsiteEntry]` — normalized website entries.
- `accounts: list[AccountEntry]` — social media accounts (Twitter/X, Instagram, Facebook, TikTok, etc.).
- `identifiers: list[Identifier]` — external identifiers such as GND or VIAF.
- `image: list[str]` — image URLs.
- `retrieved_at: str | None` — timestamp when this record was retrieved.

### PublicInstitutionNormalizedRecord

Represents a public institution such as a government agency, NGO, municipality, or media outlet, after aggregating multiple SPARQL rows by QID.

Key fields:

- `qid: str` — stable Wikidata identifier.
- `id: str` — compatibility alias for `qid`.
- `entity_kind: Literal["public_institution"] | None` — entity discriminator.
- `name: str | None` — primary label.
- `aliases: list[str]` — alternative names.
- `description: str | None` — short description.
- `founded: str | None` — ISO-8601 date/datetime for founding date.
- `country: list[str]` — countries associated with the institution (aggregated).
- `types: list[str]` — institution types (e.g., government agency, NGO) (aggregated).
- `headquarters: list[str]` — headquarters locations (labels or identifiers).
- `website: list[WebsiteEntry]` — official websites.
- `logo: list[str]` — logo image URLs.
- `accounts: list[AccountEntry]` — social media accounts.
- `sub_institutions: list[SubInstitution]` — subsidiary organizations.
- `retrieved_at: str | None` — last refresh timestamp.

### Supporting Types

- `WebsiteEntry` — `{ url: str, source: str, retrieved_at: str }`.
- `AccountEntry` — `{ platform: str, handle: str, source: str, retrieved_at: str }`.
- `Identifier` — `{ scheme: str, id: str }` for external identifier systems.

## Result and Filter Representations

### Result Set (Public API)

Iterator-based public APIs (`iterate_public_figures`, `iterate_public_institutions`) yield individual `PublicFigureNormalizedRecord` or `PublicInstitutionNormalizedRecord` instances.

Lower-level methods (`get_public_figures`, `get_public_institutions`) return `(List[NormalizedRecord], proxy)` tuples, where the list contains aggregated normalized records from a single SPARQL query page.

**Internal Architecture**: The library uses a three-layer pattern:
1. **Page fetch layer**: `get_public_*` executes SPARQL, aggregates rows by QID, returns list of normalized records
2. **Stream iterator layer**: `iter_public_*` wraps page fetch with automatic pagination using keyset cursors
3. **High-level wrapper**: `iterate_public_*` adds validation, logging, and `max_results` control

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
