from typing import Dict, Any, List, Optional
from api.constants import WikidataProperty, EntityQID

# Supported institution type mappings (exposed via /v1/meta)
TYPE_MAPPINGS = {
    'political_party': EntityQID.POLITICAL_PARTY.value,
    'government_agency': EntityQID.GOVERNMENT_AGENCY.value,
    'municipality': EntityQID.MUNICIPALITY.value,
    'media_outlet': EntityQID.MEDIA_OUTLET.value,
    'ngo': EntityQID.NGO.value,
    'ministry': EntityQID.MINISTRY.value
}

class EntityTypeDetector:
    """Detects entity type from Wikidata data."""
    
    def __init__(self):
        self.type_mappings = TYPE_MAPPINGS
    
    def determine_type(self, ent: Dict[str, Any]) -> Dict[str, Any]:
        """Determine entity type from Wikidata entity data.
        
        Args:
            ent: Wikidata entity dictionary
            
        Returns:
            Dictionary with 'is_person', 'is_institution', and 'p31_vals' keys
        """
        # Get instance-of (P31) QIDs
        p31_vals = []
        for claim in ent.get('claims', {}).get(WikidataProperty.INSTANCE_OF.value, []):
            dv = claim.get('mainsnak', {}).get('datavalue', {})
            if dv and dv.get('type') == 'wikibase-entityid':
                pid = dv.get('value', {}).get('id')
                if pid:
                    p31_vals.append(pid)
        
        is_person = EntityQID.PERSON.value in p31_vals
        is_institution = (
            any(v == self.type_mappings.get(k) or v in self.type_mappings.values() 
                for v in p31_vals for k in self.type_mappings) or 
            (not is_person and len(p31_vals) > 0)
        )
        
        return {
            'is_person': is_person,
            'is_institution': is_institution,
            'p31_vals': p31_vals
        }
    
    @staticmethod
    def pick_text(mapping: Dict[str, Dict[str, str]], prefer: str = "en") -> Optional[str]:
        """Get label/description in preferred language with fallback.
        
        Args:
            mapping: Dictionary mapping language codes to text objects
            prefer: Preferred language code
            
        Returns:
            Text value or None
        """
        if prefer in mapping:
            return mapping[prefer].get('value')
        # Fallback to any available
        for v in mapping.values():
            return v.get('value')
        return None
    
    @staticmethod
    def first_claim_value(claims_dict: Dict[str, Any], prop: str, extract_qid: bool = False):
        """Get first claim value from Wikidata claims.
        
        Args:
            claims_dict: Dictionary of claims
            prop: Property ID (e.g., 'P569' for birth date)
            extract_qid: If True, extract QID from entityid type
            
        Returns:
            Claim value or None
        """
        vals = claims_dict.get(prop)
        if not vals:
            return None
        dv = vals[0].get('mainsnak', {}).get('datavalue')
        if not dv:
            return None
        dv_type = dv.get('type')
        dv_value = dv.get('value')
        
        if dv_type == 'wikibase-entityid':
            return dv_value.get('id') if extract_qid else dv_value
        elif dv_type == 'time':
            # For time datatypes, extract the time string (e.g., "+1997-02-10T00:00:00Z")
            if isinstance(dv_value, dict) and 'time' in dv_value:
                # Remove the '+' prefix if present and return ISO format
                time_str = dv_value['time']
                if time_str.startswith('+'):
                    return time_str[1:]  # Remove leading '+'
                return time_str
            return None
        elif dv_type == 'string' or dv_type == 'commonsMedia':
            return dv_value
        # For other types, return the value as-is
        return dv_value
    
    @staticmethod
    def extract_qids_from_claims(claims_dict: Dict[str, Any], prop: str) -> List[str]:
        """Extract all QIDs from a claim property (e.g., P102, P463 for affiliations).
        
        Args:
            claims_dict: Dictionary of claims
            prop: Property ID
            
        Returns:
            List of QIDs
        """
        qids = []
        if claims_dict.get(prop):
            for claim in claims_dict[prop]:
                dv = claim.get('mainsnak', {}).get('datavalue', {})
                if dv and dv.get('type') == 'wikibase-entityid':
                    qid_val = dv.get('value', {}).get('id')
                    if qid_val and qid_val not in qids:
                        qids.append(qid_val)
        return qids

