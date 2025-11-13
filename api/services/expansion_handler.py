from typing import Union, Dict
from fastapi import Request
from core.models import PublicFigure, PublicInstitution
from core.wiki_service import WikiService
from api.constants import ExpansionType, WikidataProperty

class ExpansionHandler:
    """Handles entity expansions (sub_institutions, affiliations, etc.)."""
    
    def __init__(self, wiki_service: WikiService):
        self.wiki_service = wiki_service
    
    def apply_expansions(
        self,
        entity: Union[PublicFigure, PublicInstitution],
        expand: str,
        qid: str,
        lang: str,
        ent: Dict,
        request: Request
    ) -> Union[PublicFigure, PublicInstitution]:
        """Apply requested expansions to entity.
        
        Args:
            entity: Entity to expand
            expand: Comma-separated expansion types
            qid: Entity QID
            lang: Language code
            ent: Raw Wikidata entity data
            request: FastAPI request object
            
        Returns:
            Entity with expansions applied
        """
        expand_list = [e.strip() for e in expand.split(',')]
        ent_claims = ent.get('claims', {})
        
        if ExpansionType.SUB_INSTITUTIONS.value in expand_list and hasattr(entity, 'sub_institutions'):
            # Fetch sub-institutions
            subs = self.wiki_service.expand_sub_institutions(qid, lang=lang, request=request)
            entity.sub_institutions = subs
        
        if ExpansionType.AFFILIATIONS.value in expand_list and hasattr(entity, 'affiliations'):
            # Extract affiliation QIDs from claims (P102: member of political party, P463: member of)
            from api.utils.entity_utils import EntityTypeDetector
            
            affiliation_qids = []
            affiliation_qids.extend(EntityTypeDetector.extract_qids_from_claims(ent_claims, WikidataProperty.MEMBER_OF_PARTY.value))
            affiliation_qids.extend(EntityTypeDetector.extract_qids_from_claims(ent_claims, WikidataProperty.MEMBER_OF.value))
            
            # Remove duplicates while preserving order
            seen = set()
            unique_qids = []
            for q in affiliation_qids:
                if q not in seen:
                    seen.add(q)
                    unique_qids.append(q)
            
            # Resolve QIDs to labels
            if unique_qids:
                labels_map = self.wiki_service.get_labels_from_qids(unique_qids, lang=lang, request=request)
                # Convert to list of labels, preserving order, fallback to QID if label not found
                affiliation_labels = [labels_map.get(qid, qid) for qid in unique_qids]
                entity.affiliations = affiliation_labels
            else:
                entity.affiliations = []
        
        return entity

