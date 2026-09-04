"""SPARQL query builder for social-media handles, keyed by a page's QIDs.

Split out from the page queries (`build_public_figures_query`,
`build_public_organizations_query`) because Wikidata's edge WAF rejects the
five social-handle `OPTIONAL`s combined with those queries' `SELECT` shape
with an instant 403. Keyed by `VALUES ?entity { ... }` against a small page
of QIDs, the same handles fetch cleanly and cheaply. See
docs/adr/0002-social-handles-second-query.md.
"""

from typing import List

from ..constants import SOCIAL_HANDLE_PROPERTIES
from ..security import validate_qid


def build_social_handles_query(qids: List[str]) -> str:
    """Build a SPARQL query fetching social-media handles for a set of QIDs.

    Args:
        qids: The page's entity QIDs (e.g. ``["Q42", "Q1"]``). Order does not
            matter — results are merged back onto the page bindings by QID.

    Returns:
        SPARQL query string binding ``?entity`` plus one ``?<platform>Handle``
        variable per entry in ``SOCIAL_HANDLE_PROPERTIES``.

    Raises:
        ValueError: If ``qids`` is empty, or if any QID fails validation.
    """
    if not qids:
        raise ValueError("qids must not be empty")

    validated_qids = [validate_qid(qid) for qid in qids]
    # ponytail: unchunked VALUES list, sized by the caller's page limit;
    # chunk if pages grow past a few hundred QIDs.
    values_clause = " ".join(f"wd:{qid}" for qid in validated_qids)

    select_vars = " ".join(f"?{platform}Handle" for platform in SOCIAL_HANDLE_PROPERTIES)
    optional_lines = "\n".join(
        f"  OPTIONAL {{ ?entity wdt:{pid} ?{platform}Handle. }}"
        for platform, pid in SOCIAL_HANDLE_PROPERTIES.items()
    )

    return (
        f"SELECT ?entity {select_vars} WHERE {{\n"
        f"  VALUES ?entity {{ {values_clause} }}\n"
        f"{optional_lines}\n"
        "}"
    )
