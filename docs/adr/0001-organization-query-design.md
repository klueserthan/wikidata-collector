# ADR 0001: Organization query design

## Status

Accepted (2026-08-18)

## Context

`build_public_organizations_query` and `iterate_public_organizations` needed a
concrete design for how to filter and page through Wikidata organizations. The
decisions below were live-benchmarked against the real WDQS endpoint
(https://query.wikidata.org/sparql) on 2026-08-18, not assumed from
documentation.

### `types` must be required

An unfiltered "all organizations" scan — `?organization wdt:P31/wdt:P279*
wd:Q43229` (the organization umbrella, ~51k subclasses) — times out (504) on
WDQS in every query shape tested: with and without a country filter, with and
without `SELECT DISTINCT`, with and without optimizer hints. There is no safe
default query that returns "organizations in general." Callers must instead
name one or more concrete types from the curated 15-key vocabulary, or a raw
QID. The query builder raises `ValueError` (wrapped as `InvalidFilterError` at
the client boundary) before building any SPARQL when `types` is missing or
empty.

### OR semantics via one `VALUES` + one property-path triple

Multiple type values are combined with a single `VALUES ?orgClass {...}`
clause feeding one `?organization wdt:P31/wdt:P279* ?orgClass` triple, never
AND-joined `;`-chained `wdt:P31` triples (an entity cannot simultaneously be a
direct `P31` instance of two different classes, so that shape returns nothing
on real data). The `P279*` subclass closure is what gives useful recall: e.g.
"daily newspaper" is a subclass of, not a direct instance of, `newspaper`, and
only matches through the closure.

Benchmarked latency for a single type + country query: roughly 1–34 seconds
cold, sub-second warm.

### `SELECT DISTINCT` in the subquery is mandatory

The multi-class property path produces duplicate `?organization` rows for any
entity that matches more than one `VALUES` class. Keyset pagination decides
end-of-results by comparing the count of *unique* QIDs in a page against the
limit — without `SELECT DISTINCT`, duplicate rows would inflate that count and
the pipeline would silently truncate a page's results, believing a partial
page was a full one.

### Iteration decomposes multi-type into one keyset stream per type

A single combined multi-type `VALUES`-OR query degrades fast as the type count
grows: 3 types measured around 35 seconds, and roughly 16 types is a
guaranteed 504. `iterate_public_organizations` therefore decomposes a
multi-type filter into one keyset-paginated query stream per type
(`_decompose_organization_filters`), sharing one `seen_qids` de-dupe set and
one global `max_results` budget across every stream — an entity matching more
than one type is yielded once, not once per matching stream.

`get_public_organizations` (a single, caller-bounded page) keeps the combined
`VALUES`-OR query instead: it never paginates past the caller's own `limit`,
so the degradation above does not apply, and a single query is simpler for a
single-page caller.

### Excluded from the type vocabulary

- `political_organization` (Q7210356, ~13k subclasses) times out the same way
  the organization umbrella does.
- `company` was considered and rejected: it is too broad to be a useful filter
  and pulls in the same class of unbounded-scan risk.

### Optimizer hints are not used

`hint:Prior hint:gearing` and similar WDQS optimizer hints were benchmarked
against the single-type and multi-type shapes above and measured
neutral-to-harmful — no consistent improvement, and occasional regressions.
They are not used anywhere in the organization query.

## Decision

1. `types` is a required, non-empty filter on both `build_public_organizations_query`
   and `iterate_public_organizations` / `get_public_organizations`.
2. Multiple types combine via one `VALUES ?orgClass {...}` clause and one
   `wdt:P31/wdt:P279* ?orgClass` triple (OR semantics, subclass closure).
3. The pagination subquery always uses `SELECT DISTINCT`.
4. `iterate_public_organizations` decomposes multi-type filters into one
   keyset stream per type with shared de-duplication and a shared
   `max_results` budget; `get_public_organizations` does not decompose.
5. `political_organization` and `company` are excluded from
   `ORGANIZATION_TYPE_MAPPINGS`.
6. No WDQS optimizer hints are used in the organization query.

## Consequences

- Callers cannot request "all organizations" — they must name types, which is
  a real usability cost but the only option that does not time out.
- Multi-type iteration issues more HTTP round trips than a single combined
  query would (one per type), trading request count for reliability.
- The curated vocabulary is deliberately smaller than the full space of
  Wikidata organization subclasses; broadening it later requires the same
  live-benchmarking discipline used here, not just adding a QID.
