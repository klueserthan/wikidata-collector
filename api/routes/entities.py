from fastapi import APIRouter, Query, Request, Depends
from typing import Optional
from api.services.entity_service import EntityService
from api.dependencies import get_entity_service
from api.config import config

router = APIRouter()

@router.get("/v1/entities/{qid}")
async def get_entity(
    qid: str,
    request: Request,
    lang: str = Query(config.DEFAULT_LANG, description="Language code"),
    expand: Optional[str] = Query(None, description="Comma-separated expansions (e.g., sub_institutions, affiliations)"),
    entity_service: EntityService = Depends(get_entity_service)
):
    """Point lookup for a Wikidata QID. Returns a compact representation of the entity (labels, descriptions, claims).

    This uses the Wikidata EntityData JSON endpoint and supports proxying via the same ProxyManager.
    """
    return await entity_service.get_entity(qid, request, lang, expand)

