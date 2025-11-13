from typing import Optional, Set, Dict, Any

class FieldParser:
    """Parses and filters field parameters."""
    
    @staticmethod
    def parse_fields_param(fields: Optional[str]) -> Optional[Set[str]]:
        """Parse comma-separated fields parameter into a set of field names."""
        if not fields:
            return None
        return {f.strip() for f in fields.split(',') if f.strip()}
    
    @staticmethod
    def filter_fields(
        data: Dict[str, Any],
        requested_fields: Set[str],
        entity_kind: str
    ) -> Dict[str, Any]:
        """Filter response data to only include requested fields.
        
        Always includes 'id' and 'entity_kind' regardless of fields parameter.
        Supports nested field access with dot notation (e.g., 'website.url', 'accounts.handle').
        
        Args:
            data: Full entity data dictionary
            requested_fields: Set of field names to include
            entity_kind: Type of entity ('public_figure' or 'public_institution')
        
        Returns:
            Filtered dictionary with only requested fields
        """
        if not requested_fields:
            return data
        
        # Always include required fields
        required_fields = {'id', 'entity_kind'}
        filtered = {}
        
        # Add required fields first
        for field in required_fields:
            if field in data:
                filtered[field] = data[field]
        
        # Process requested fields
        for field in requested_fields:
            if '.' in field:
                # Handle nested fields (e.g., 'website.url', 'accounts.handle')
                parts = field.split('.')
                if len(parts) == 2:
                    parent_field, child_field = parts
                    if parent_field in data:
                        parent_data = data[parent_field]
                        if isinstance(parent_data, list):
                            # Filter list items to only include requested child field
                            filtered[parent_field] = []
                            for item in parent_data:
                                if isinstance(item, dict) and child_field in item:
                                    filtered_item = {child_field: item[child_field]}
                                    # Always include 'source' and 'retrieved_at' for nested objects
                                    if 'source' in item:
                                        filtered_item['source'] = item['source']
                                    if 'retrieved_at' in item:
                                        filtered_item['retrieved_at'] = item['retrieved_at']
                                    filtered[parent_field].append(filtered_item)
                                elif isinstance(item, dict):
                                    # If child field not found, include whole item
                                    filtered[parent_field].append(item)
                        elif isinstance(parent_data, dict) and child_field in parent_data:
                            filtered[parent_field] = {child_field: parent_data[child_field]}
                # For deeper nesting (3+ levels), include the full parent object
                elif len(parts) > 2:
                    parent_field = parts[0]
                    if parent_field in data:
                        filtered[parent_field] = data[parent_field]
            else:
                # Simple top-level field
                if field in data:
                    filtered[field] = data[field]
        
        return filtered

