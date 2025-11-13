from fastapi import Depends
from core.wiki_service import WikiService
from api.services.entity_service import EntityService
from api.services.list_processor import ListProcessor

# Global WikiService instance (singleton pattern)
_wiki_service_instance = None

def get_wiki_service() -> WikiService:
    """Get WikiService instance (singleton).
    
    Returns:
        WikiService instance
    """
    global _wiki_service_instance
    if _wiki_service_instance is None:
        _wiki_service_instance = WikiService()
    return _wiki_service_instance

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

