# ADR 0002: Social handles fetched by a second, WAF-safe query

## Status

Accepted (2026-09-04)

## Context

`build_public_figures_query` and `build_public_organizations_query` both embed
five `OPTIONAL` clauses for social-media handles (Instagram, Twitter,
Facebook, YouTube, TikTok — `P2003`/`P2002`/`P2013`/`P2397`/`P7085`) in the
outer query, alongside the label/date/image/description fields. In production
this query is rejected outright by Wikidata's edge WAF: an instant 403 on
every GET, from any IP, any User-Agent, reproducible on two unrelated
networks. It is not IP reputation, User-Agent, or URL length — bisection
against the live endpoint on 2026-09-04 narrowed it to the query text itself:

| Query | GET |
|---|---|
| `build_public_figures_query(...)` as emitted | **403 in 0.14 s** |
| same, minus the five social-handle `OPTIONAL`s | 200 in 15.8 s |
| same via POST | 504 after 65 s |
| `VALUES ?entity { 15 QIDs }` + the five social `OPTIONAL`s | **200 in 0.33 s** |

The rule matches the *combination* of the five social-handle properties
inside this particular `SELECT` shape, not any single clause, and not the
transport. `organizations_query_builder.py` emits the identical block, so
both entity kinds are affected identically.

### Why not just switch to POST

POST does get past the edge WAF, but the underlying query — a birth-date
range scan plus five extra `OPTIONAL` joins — is genuinely too expensive for
public WDQS: it times out with a 504 after 65 s. Switching transport alone
just trades a fast 403 for a slow 5xx; it does not address why the query is
expensive in the first place. The page query (without the five handles)
already passes on GET, so nothing forces a transport change — POST is
deliberately out of scope here (tracked separately, alongside 403-specific
retry handling).

## Decision

Split every page fetch into two SPARQL requests:

1. **Page query** — the existing builder output, with the five social-handle
   `OPTIONAL`s and their outer-`SELECT` variables removed. This is the query
   shape that measured 200 in 15.8 s above.
2. **Social-handles query** (`build_social_handles_query`) — a small,
   `VALUES ?entity { ... }`-keyed lookup against exactly the page's QIDs, with
   the five `OPTIONAL`s and no `SERVICE wikibase:label`, no `ORDER BY`. This
   is the shape that measured 200 in 0.33 s above. Run only when the page is
   non-empty — an empty page has no QIDs to key it on.

The two result sets are merged **at the bindings level, before
`spec.normalize`**, by `_merge_social_bindings`: a pure function that
reproduces the row cross-product the single combined query used to produce
(each page row is paired with every social row sharing its QID; page order,
and therefore same-QID row adjacency, is preserved). `normalize_bindings`,
the record classes, `_collect_accounts`, `_merge_accounts`, and every public
record shape are untouched — the split is invisible above `_fetch_page`.

`_EntitySpec` gains an `entity_var` field (`"person"` for public figures,
`"organization"` for public organizations) naming the page binding's entity
variable, since the social-handles query always binds `?entity` regardless of
entity kind.

No chunking of the social-handles query's `VALUES` list: page sizes are
small, and the 15-QID benchmark above already returns in well under a second.

## Consequences

- Every non-empty page now costs two HTTP round trips instead of one. This is
  the trade made deliberately: two fast, WAF-safe requests instead of one
  request that is either rejected (GET) or times out (POST).
- `_fetch_page`'s contract changes from "one query" to "one query, plus a
  conditional second one" — callers of `_fetch_page` are unaffected, since the
  seam still returns `(records, used_proxy)`; `used_proxy` reports the page
  query's proxy, not the social-handles query's.
- Adding a sixth social-media property means adding one entry to
  `SOCIAL_HANDLE_PROPERTIES` in `constants.py` — the query builder generates
  its `OPTIONAL` and `SELECT` clauses from that mapping, not from hand-written
  property lists.
