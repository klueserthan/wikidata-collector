# CONTEXT.md — Domain Glossary

Shared vocabulary for wikidata-collector. Use these terms exactly in code, docs, and reviews.

## Entities

- **Public figure** — a human Wikidata entity (`wdt:P31 wd:Q5`), filterable by birthday range,
  nationality (P27, country of citizenship), occupations (P106), and gender (P21).
- **Public organization** — an organizational Wikidata entity, filterable by country (P17,
  optional) and types (P31 with P279\* subclass closure, required — Wikidata has no bounded
  "organization" umbrella class a query can scan without it).
- **Entity kind** — the discriminator string on every model (`"public_figure"` /
  `"public_organization"`).

## Records

- **Record family** — the pair of Pydantic models describing one entity kind: a **Wiki record**
  (one raw SPARQL result row) and a **Normalized record** (one entity, multi-valued fields
  aggregated into lists). Lives in `models.py`.
- **Normalization** — folding consecutive same-QID SPARQL rows into one Normalized record via the
  record family's `from_wikidata` / `from_wikidata_record` / `add_from_wikidata_record` protocol.
  The single entry point is `models.normalize_bindings`.

## Pipeline

- **Entity pipeline** — the deep module inside `WikidataClient` that turns filters into an
  iterator of Normalized records: validate filters → build query → fetch page → normalize →
  keyset-paginate → honor `max_results`. One implementation, parameterized by Entity spec.
- **Entity spec** (`_EntitySpec`) — the frozen per-entity row the pipeline consumes: entity kind,
  query type, query builder, normalizer, filter validator. Adding an entity kind means adding a
  spec row, a record family, and a query builder — not a new pipeline.
- **Fetch seam** (`_fetch_page`) — the substitution point where tests feed fake pages into the
  pipeline; production fetches via SPARQL + proxy.
- **Keyset pagination** — paging ordered by numeric QID with an `after_qid` filter; end-of-results
  is decided on *unique* QIDs per page (rows are expanded per value combination).
- **Filter decomposition** (`_EntitySpec.decompose_filters`) — splitting one call's filters into
  several sub-streams run sequentially through the same pipeline, sharing one keyset-pagination
  loop and one `seen_qids` de-dupe set. Default is identity (one sub-stream, filters unchanged).
  Multi-type organization iteration decomposes into one keyset stream per `types` value, because a
  single combined multi-type query degrades badly on WDQS; a duplicate entity across streams is
  yielded once and does not count twice toward `max_results`, which is a global budget spanning
  every sub-stream. `get_public_organizations` (a single page) never decomposes.

## Filter vocabulary

One name per concept, end to end (public method → pipeline → query builder):

| Concept | Name | Applies to |
|---|---|---|
| Country of citizenship (P27) | `nationality` | public figures |
| Occupations (P106) | `occupations` | public figures |
| Gender (P21) | `gender` | public figures |
| Birth date range (P569) | `birthday_from` / `birthday_to` | public figures |
| Country (P17) | `country` | public organizations |
| Organization types (P31, with P279\* subclass closure, OR across values) | `types` (required) | public organizations |

Human-readable filter labels resolve to QIDs only via the mappings in `constants.py`; unknown
labels are rejected (never interpolated into SPARQL).
