# Data Model: Wikidata Public Entities ETL Package

## Overview

The data model is implemented using Pydantic v2 and is designed to represent public figures and
public institutions as normalized Python objects suitable for ETL pipelines. The models expand on
`wikidata_collector/models.py` and align with the feature specification.

## Core Entities

### PublicFigure

Represents an individual public figure. Fields mirror the SELECT clause in
`build_public_figures_query`.

Key fields (all strings are UTF-8 text unless otherwise noted):

- `id: str | None` — stable Wikidata identifier (QID extracted from `?person`).
- `entity_kind: Literal["public_figure"] | None` — entity discriminator for downstream code.
- `name: str | None` — primary label (`?personLabel`).
- `description: str | None` — short description (`?description`).
- `birth_date: str | None` — ISO-8601 date/datetime (`?birthDate`).
- `death_date: str | None` — ISO-8601 date/datetime (`?deathDate`).
- `gender: str | None` — gender label (`?genderLabel`).
- `countries: list[str]` — country labels (`?countryLabel`), possibly multi-valued.
- `occupations: list[str]` — occupation labels (`?occupationLabel`), possibly multi-valued.
- `image: str | None` — image URL (`?image`).
- `instagram_handle: str | None` — `?instagramHandle`.
- `twitter_handle: str | None` — `?twitterHandle`.
- `facebook_handle: str | None` — `?facebookHandle`.
- `youtube_handle: str | None` — `?youtubeHandle`.
- `updated_at: str | None` — timestamp when this record was last refreshed.

### PublicInstitution

Represents a public institution such as a government agency, NGO, municipality, or media outlet.
Fields mirror the SELECT clause in `build_public_institutions_query`.

Key fields:

- `id: str | None` — stable Wikidata identifier (QID extracted from `?institution`).
- `entity_kind: Literal["public_institution"] | None` — entity discriminator.
- `name: str | None` — primary label (`?institutionLabel`).
- `description: str | None` — short description (`?description`).
- `founded_date: str | None` — ISO-8601 date/datetime (`?foundedDate`).
- `dissolved_date: str | None` — ISO-8601 date/datetime (`?dissolvedDate`).
- `countries: list[str]` — country labels (`?countryLabel`), possibly multi-valued.
- `types: list[str]` — institution type labels (`?typeLabel`), possibly multi-valued.
- `image: str | None` — image URL (`?image`).
- `instagram_handle: str | None` — `?instagramHandle`.
- `twitter_handle: str | None` — `?twitterHandle`.
- `facebook_handle: str | None` — `?facebookHandle`.
- `youtube_handle: str | None` — `?youtubeHandle`.
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
