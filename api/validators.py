from api.exceptions import InvalidQIDException
from api.constants import EntityType

class QIDValidator:
    """Validates Wikidata QIDs."""
    
    @staticmethod
    def validate(qid: str) -> None:
        """Validate QID format.
        
        Raises:
            InvalidQIDException: If QID format is invalid
        """
        if not qid or not qid.startswith('Q'):
            raise InvalidQIDException()
    
    @staticmethod
    def is_valid(qid: str) -> bool:
        """Check if QID is valid without raising exception.
        
        Args:
            qid: QID to validate
            
        Returns:
            True if valid, False otherwise
        """
        return bool(qid and qid.startswith('Q'))

class EntityTypeValidator:
    """Validates entity types."""
    
    @staticmethod
    def validate(entity_type: str) -> EntityType:
        """Validate and convert entity type string to enum.
        
        Args:
            entity_type: Entity type string
            
        Returns:
            EntityType enum
            
        Raises:
            ValueError: If entity type is invalid
        """
        try:
            return EntityType(entity_type)
        except ValueError:
            raise ValueError(f"Invalid entity type: {entity_type}")

