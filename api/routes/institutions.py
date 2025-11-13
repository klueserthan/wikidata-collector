from fastapi import APIRouter, Query, Request, Depends
from typing import List, Optional
from api.services.list_processor import ListProcessor
from api.dependencies import get_list_processor
from api.constants import EntityType
from api.config import config

router = APIRouter()

@router.get("/v1/public-institutions")
async def get_public_institutions(
    request: Request,
    country: Optional[str] = Query(None, description="Country filter (ISO-3166 alpha-3 code, label, or QID)"),
    type: Optional[List[str]] = Query(None, description="Type filter (repeatable)"),
    jurisdiction: Optional[str] = Query(None, description="Jurisdiction filter"),
    fields: Optional[str] = Query(None, description="Comma-separated sparse fieldset"),
    lang: str = Query(config.DEFAULT_LANG, description="Language code"),
    stream: Optional[str] = Query(None, description="Set to 'ndjson' for streaming"),
    limit: int = Query(config.DEFAULT_LIMIT, le=config.MAX_LIMIT, description=f"Limit results (max {config.MAX_LIMIT})"),
    cursor: Optional[str] = Query(None, description="Keyset cursor: last QID (e.g., Q12345). Integer values use OFFSET fallback."),
    list_processor: ListProcessor = Depends(get_list_processor)
):
    """Fetch public institutions from Wikidata with optional filters and proxy support."""
    filters = {
        'country': country,
        'type': type,
        'jurisdiction': jurisdiction,
        'lang': lang
    }
    pagination = {
        'limit': limit,
        'cursor': cursor
    }
    
    return await list_processor.process_list(
        entity_type=EntityType.PUBLIC_INSTITUTION.value,
        request=request,
        filters=filters,
        pagination=pagination,
        fields=fields,
        stream=stream,
        route="/v1/public-institutions"
    )

