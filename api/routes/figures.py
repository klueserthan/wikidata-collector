from fastapi import APIRouter, Query, Request, Depends
from typing import List, Optional
from api.services.list_processor import ListProcessor
from api.dependencies import get_list_processor
from api.constants import EntityType, StreamFormat
from api.config import config

router = APIRouter()

@router.get("/v1/public-figures")
async def get_public_figures(
    request: Request,
    birthday_from: Optional[str] = Query(None, description="Birth date from (ISO date)"),
    birthday_to: Optional[str] = Query(None, description="Birth date to (ISO date)"),
    nationality: Optional[List[str]] = Query(None, description="Nationality filter (ISO-3166 alpha-3 code, label, or QID; repeatable)"),
    profession: Optional[List[str]] = Query(None, description="Profession filter (repeatable)"),
    fields: Optional[str] = Query(None, description="Comma-separated sparse fieldset"),
    lang: str = Query(config.DEFAULT_LANG, description="Language code"),
    stream: Optional[str] = Query(None, description="Set to 'ndjson' for streaming"),
    limit: int = Query(config.DEFAULT_LIMIT, le=config.MAX_LIMIT, description=f"Limit results (max {config.MAX_LIMIT})"),
    cursor: Optional[str] = Query(None, description="Keyset cursor: last QID (e.g., Q12345). Integer values use OFFSET fallback."),
    list_processor: ListProcessor = Depends(get_list_processor)
):
    """Fetch public figures from Wikidata with optional filters and proxy support."""
    filters = {
        'birthday_from': birthday_from,
        'birthday_to': birthday_to,
        'nationality': nationality,
        'profession': profession,
        'lang': lang
    }
    pagination = {
        'limit': limit,
        'cursor': cursor
    }
    
    return await list_processor.process_list(
        entity_type=EntityType.PUBLIC_FIGURE.value,
        request=request,
        filters=filters,
        pagination=pagination,
        fields=fields,
        stream=stream,
        route="/v1/public-figures"
    )

