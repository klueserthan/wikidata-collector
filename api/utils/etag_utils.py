import json
import hashlib
from typing import Dict, Any

class ETagGenerator:
    """Generates ETags for responses."""
    
    @staticmethod
    def generate(data: Dict[str, Any]) -> str:
        """Generate ETag from data dictionary.
        
        Args:
            data: Dictionary to generate ETag from
            
        Returns:
            Quoted ETag string (e.g., "abc123...")
        """
        etag_content = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
        etag = hashlib.md5(etag_content.encode('utf-8')).hexdigest()
        return f'"{etag}"'  # ETags should be quoted

