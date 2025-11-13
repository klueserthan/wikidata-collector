from api.constants import EntityType

class CacheKeyGenerator:
    """Generates cache keys for different contexts."""
    
    @staticmethod
    def entity_expansion(qid: str, lang: str, entity_type: EntityType) -> str:
        """Generate cache key for entity expansion.
        
        Args:
            qid: Entity QID
            lang: Language code
            entity_type: Entity type enum
            
        Returns:
            Cache key string
        """
        suffix = "" if entity_type == EntityType.PUBLIC_FIGURE else ":institution"
        return f"{qid}:{lang}{suffix}"
    
    @staticmethod
    def sparql_query(query_hash: str) -> str:
        """Generate cache key for SPARQL query.
        
        Args:
            query_hash: Hash of the SPARQL query
            
        Returns:
            Cache key string
        """
        return f"sparql:{query_hash}"

