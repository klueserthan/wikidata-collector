from fastapi import APIRouter, Depends
from fastapi import FastAPI
from api.utils.entity_utils import TYPE_MAPPINGS
from api.config import config
from api.constants import EntityType

router = APIRouter()

# This will be set from main.py
app = None

def init_app(fastapi_app: FastAPI):
    """Initialize with FastAPI app instance."""
    global app
    app = fastapi_app

@router.get("/v1/meta")
async def get_meta():
    """Return metadata about the service: version, supported filters/types, defaults, and Wikidata endpoints used."""
    meta = {
        "service_version": app.version,
        "wikidata_sparql": config.WIKIDATA_SPARQL_URL,
        "wikidata_entity_api": config.WIKIDATA_ENTITY_API_URL,
        "defaults": {
            "limit": config.DEFAULT_LIMIT,
            "max_limit": config.MAX_LIMIT,
            "lang": config.DEFAULT_LANG
        },
        "supported_filters": {
            "public_figures": ["birthday_from", "birthday_to", "nationality", "profession", "fields", "lang", "stream", "limit", "cursor"],
            "public_institutions": ["country", "type", "jurisdiction", "fields", "lang", "stream", "limit", "cursor"]
        },
        "supported_institution_types": list(TYPE_MAPPINGS.keys())
    }
    return meta

@router.get("/v1/health")
async def root():
    return {"ok": True, "version": "1.0.0"}

