from typing import Optional, Dict
from fastapi import HTTPException, Request, Response

from core.wiki_service import WikiService
from api.services.response_builder import ResponseBuilder
from api.services.expansion_handler import ExpansionHandler
from api.utils.entity_utils import EntityTypeDetector
from api.utils.cache_utils import CacheKeyGenerator
from api.exceptions import InternalErrorException
from api.validators import QIDValidator
from api.constants import EntityType, WikidataProperty
from infrastructure.observability import get_request_id
from infrastructure.cache import entity_expansion_cache
import logging

logger = logging.getLogger(__name__)

class EntityService:
    """Handles entity lookup operations."""
    
    def __init__(self, wiki_service: WikiService):
        self.wiki_service = wiki_service
        self.response_builder = ResponseBuilder()
        self.expansion_handler = ExpansionHandler(wiki_service)
        self.type_detector = EntityTypeDetector()
    
    async def get_entity(
        self,
        qid: str,
        request: Request,
        lang: str,
        expand: Optional[str]
    ) -> Response:
        """Get entity by QID with expansion support.
        
        Args:
            qid: Wikidata QID
            request: FastAPI request object
            lang: Language code
            expand: Comma-separated expansion types
            
        Returns:
            HTTP Response with entity data
        """
        request_id = get_request_id()
        cache_hit = False
        
        # Validate QID format
        QIDValidator.validate(qid)
        
        try:
            # Fetch entity data from Wikidata
            ent, used_proxy = self.wiki_service.get_entity_by_qid(qid, lang=lang, request=request)
            
            # Determine entity type
            entity_type_info = self.type_detector.determine_type(ent)
            is_person = entity_type_info['is_person']
            is_institution = entity_type_info['is_institution']
            
            # Determine entity type enum
            entity_type = EntityType.PUBLIC_FIGURE if is_person else EntityType.PUBLIC_INSTITUTION
            
            # Check cache
            expansion_cache_key = CacheKeyGenerator.entity_expansion(qid, lang, entity_type)
            if entity_expansion_cache.get(expansion_cache_key):
                cache_hit = True
            
            # Expand entity data
            if is_person:
                expanded_data = self.wiki_service.expand_entity_data(qid, lang=lang, request=request)
                ent_claims = ent.get('claims', {})
                
                # Create minimal SPARQL-like item structure for normalization
                person_item = self._build_person_item(ent, ent_claims, qid, lang)
                result = self.wiki_service.normalize_public_figure(person_item, expanded_data, lang=lang)
            else:
                expanded_data = self.wiki_service.expand_entity_data_institution(qid, lang=lang, request=request)
                ent_claims = ent.get('claims', {})
                
                # Create minimal SPARQL-like item structure for normalization
                institution_item = self._build_institution_item(ent, ent_claims, qid, lang)
                result = self.wiki_service.normalize_public_institution(
                    institution_item, expanded_data, lang=lang, request=request
                )
            
            # Handle expand parameter
            if expand:
                result = self.expansion_handler.apply_expansions(
                    result, expand, qid, lang, ent, request
                )
            
            # Convert to dict
            result_dict = result.model_dump()
            
            # Build response
            return self.response_builder.build_entity_response(
                result_dict, request_id, used_proxy, cache_hit
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching entity {qid}: {e}")
            raise InternalErrorException()
    
    def _build_person_item(self, ent: Dict, ent_claims: Dict, qid: str, lang: str) -> Dict:
        """Build person item structure for normalization."""
        return {
            "person": {"value": f"http://www.wikidata.org/entity/{qid}"},
            "personLabel": {"value": self.type_detector.pick_text(ent.get('labels', {}), lang)},
            "description": {"value": self.type_detector.pick_text(ent.get('descriptions', {}), lang)},
            "birthDate": {"value": self.type_detector.first_claim_value(ent_claims, WikidataProperty.BIRTH_DATE.value)},
            "deathDate": {"value": self.type_detector.first_claim_value(ent_claims, WikidataProperty.DEATH_DATE.value)},
            "genderLabel": {"value": None},
            "image": {"value": self.type_detector.first_claim_value(ent_claims, WikidataProperty.IMAGE.value)},
            "countryLabel": {"value": None},
            "occupationLabel": {"value": None}
        }
    
    def _build_institution_item(self, ent: Dict, ent_claims: Dict, qid: str, lang: str) -> Dict:
        """Build institution item structure for normalization."""
        item = {
            "institution": {"value": f"http://www.wikidata.org/entity/{qid}"},
            "institutionLabel": {"value": self.type_detector.pick_text(ent.get('labels', {}), lang)},
            "description": {"value": self.type_detector.pick_text(ent.get('descriptions', {}), lang)},
            "type": None,
            "foundedDate": {"value": self.type_detector.first_claim_value(ent_claims, WikidataProperty.FOUNDED_DATE.value)},
            "image": {"value": self.type_detector.first_claim_value(ent_claims, WikidataProperty.IMAGE.value)},
            "countryLabel": {"value": None},
            "jurisdictionLabel": {"value": None}
        }
        
        # Get type from P31
        if ent_claims.get(WikidataProperty.INSTANCE_OF.value):
            first_type = ent_claims[WikidataProperty.INSTANCE_OF.value][0].get('mainsnak', {}).get('datavalue', {}).get('value', {}).get('id')
            if first_type:
                item["type"] = {"value": f"http://www.wikidata.org/entity/{first_type}"}
        
        return item

