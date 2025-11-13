from functools import lru_cache
from fastapi import Depends
from core.wiki_service import WikiService
from api.services.entity_service import EntityService
from api.services.list_processor import ListProcessor


@lru_cache(maxsize=1)
def get_wiki_service() -> WikiService:
    """Get WikiService instance (cached singleton).
    
    Uses functools.lru_cache to ensure a single WikiService instance is created
    and reused across requests. This provides thread-safe singleton behavior
    without global mutable state.
    
    For testing, use get_wiki_service.cache_clear() to reset the singleton,
    or use FastAPI's dependency override mechanism: 
    app.dependency_overrides[get_wiki_service] = lambda: mock_service
    
    Returns:
        WikiService instance
    """
    return WikiService()

def get_entity_service(
    wiki_service: WikiService = Depends(get_wiki_service)
) -> EntityService:
    """Get EntityService instance.
    
    Args:
        wiki_service: WikiService instance (injected)
        
    Returns:
        EntityService instance
    """
    return EntityService(wiki_service)

def get_list_processor(
    wiki_service: WikiService = Depends(get_wiki_service)
) -> ListProcessor:
    """Get ListProcessor instance.
    
    Args:
        wiki_service: WikiService instance (injected)
        
    Returns:
        ListProcessor instance
    """
    return ListProcessor(wiki_service)

