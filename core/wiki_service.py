import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from fastapi import HTTPException, Request

from api.config import config
from core.models import PublicFigure, PublicInstitution, SubInstitution
from core.normalizers.figure_normalizer import normalize_public_figure as normalize_figure
from core.normalizers.institution_normalizer import (
    normalize_public_institution as normalize_institution,
)
from infrastructure.cache import entity_expansion_cache, sparql_cache
from infrastructure.observability import (
    get_request_id,
    hash_query,
    metrics,
    proxy_used_ctx,
    sparql_latency_ctx,
)
from infrastructure.proxy_service import ProxyManager
# Use secure query builders from wikidata_retriever module
from wikidata_retriever.query_builders.figures_query_builder import (
    build_public_figures_query as build_figures_query,
)
from wikidata_retriever.query_builders.institutions_query_builder import (
    build_public_institutions_query as build_institutions_query,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# User agent for Wikidata requests (Wikidata requires a descriptive UA)
USER_AGENT = (
    "WikidataFetchMicroservice/1.0.0 "
    f"(https://github.com/, contact: {config.CONTACT_EMAIL or 'not-provided'})"
)

class WikiService:
    def __init__(self):
        self.proxy_manager = ProxyManager()
    def execute_sparql_query(self,query: str, limit: int = 500, request: Optional[Request] = None) -> tuple[Dict[str, Any], str]:
        """Execute SPARQL query against Wikidata with proxy support and caching."""
        request_id = get_request_id()
        query_hash = hash_query(query)
        
        # Check cache first
        cached_result = sparql_cache.get(query)
        if cached_result:
            logger.info(
                f"SPARQL query cache hit",
                extra={
                    'request_id': request_id,
                    'query_hash': query_hash,
                    'cache_hit': True,
                }
            )
            # Return cached result with "cached" as proxy indicator
            sparql_latency_ctx.set(0.0)  # Cache hit = 0 latency
            return cached_result, "cached"
        
        # Cache miss - execute query
        query_snippet = query[:500] if query else ""

        logger.info(
            f"SPARQL query cache miss",
            extra={
                'request_id': request_id,
                'query_hash': query_hash,
                'cache_hit': False,
                'query': query_snippet,
            }
        )

        logger.debug(
            "Executing SPARQL query",
            extra={
                "request_id": request_id,
                "query_hash": query_hash,
                "query": query_snippet,
            },
        )
        
        # Track total SPARQL latency (including all retries)
        sparql_start_time = time.time()
        
        headers = {
            "Accept": "application/sparql-results+json"
        }
        
        params = {
            'query': query# + f"\nLIMIT {limit}"
        }
        
        used_proxy = "direct"
        max_retries = 3
        
        for attempt in range(max_retries):
            proxy = None
            try:
                # Get proxy for this attempt
                proxy = self.proxy_manager.get_next_proxy(request)
                proxy_dict = None
                
                if proxy:
                    proxy_dict =self.proxy_manager.get_proxy_dict(proxy)
                    used_proxy = proxy
                
                # Make request with timeout
                response = requests.get(
                    config.WIKIDATA_SPARQL_URL,
                    params=params, 
                    headers=headers, 
                    proxies=proxy_dict,
                    timeout=self.proxy_manager.timeout_per_hop
                )
                # Handle throttling gracefully
                if response.status_code == 429:
                    error_type = "wdqs_429_throttled"
                    metrics.record_sparql_error(error_type)
                    retry_after = response.headers.get("Retry-After")
                    wait_s = int(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
                    logger.warning(
                        f"WDQS 429 received. Waiting {wait_s}s before retry…",
                        extra={
                            'request_id': request_id,
                            'query_hash': query_hash,
                            'query': query_snippet,
                            'error_type': error_type,
                            'proxy_used': proxy or 'direct',
                            'attempt': attempt + 1,
                        }
                    )
                    time.sleep(wait_s)
                    raise requests.exceptions.RequestException("Throttled 429")

                if response.status_code in (502, 503, 504):
                    error_type = f"wdqs_{response.status_code}"
                    metrics.record_sparql_error(error_type)
                    wait_s = min(10, 2 ** attempt)
                    logger.warning(
                        f"WDQS {response.status_code} transient error. Backing off {wait_s}s…",
                        extra={
                            'request_id': request_id,
                            'query_hash': query_hash,
                            'query': query_snippet,
                            'error_type': error_type,
                            'proxy_used': proxy or 'direct',
                            'attempt': attempt + 1,
                        }
                    )
                    time.sleep(wait_s)
                    raise requests.exceptions.RequestException(f"Transient {response.status_code}")

                response.raise_for_status()
                
                # Calculate total SPARQL latency (including all retries and waits)
                sparql_latency_ms = (time.time() - sparql_start_time) * 1000
                sparql_latency_ctx.set(sparql_latency_ms)
                proxy_used_ctx.set(used_proxy)
                
                result = response.json()
                
                # Store in cache
                sparql_cache.set(query, result)
                
                logger.info(
                    f"SPARQL query executed successfully",
                    extra={
                        'request_id': request_id,
                        'query_hash': query_hash,
                        'proxy_used': used_proxy,
                        'sparql_latency_ms': sparql_latency_ms,
                        'status_code': response.status_code,
                        'cache_hit': False,
                    }
                )
                
                return result, used_proxy
                
            except requests.exceptions.RequestException as e:
                logger.error(
                    f"SPARQL request failed (attempt {attempt + 1})",
                    extra={
                        'request_id': request_id,
                        'query_hash': query_hash,
                        'query': query_snippet,
                        'error_type': type(e).__name__,
                        'proxy_used': proxy or 'direct',
                        'attempt': attempt + 1,
                    },
                    exc_info=True
                )
                
                if proxy:
                    self.proxy_manager.mark_proxy_failed(proxy)
                
                # If this was the last attempt, calculate total latency and raise
                if attempt == max_retries - 1:
                    sparql_latency_ms = (time.time() - sparql_start_time) * 1000
                    sparql_latency_ctx.set(sparql_latency_ms)
                    proxy_used_ctx.set(used_proxy)
                    raise HTTPException(status_code=500, detail="Failed to fetch data from Wikidata")
                
                # Short jitter before retry if not already slept
                time.sleep(0.5 + 0.2 * attempt)
        # Should never reach here because function either returns or raises, but add explicit raise for static check
        raise HTTPException(status_code=500, detail="Failed to fetch data from Wikidata")

    def build_public_figures_query(
        self,
        birthday_from: Optional[str] = None,
        birthday_to: Optional[str] = None,
        nationality: Optional[List[str]] = None,
        profession: Optional[List[str]] = None,
        lang: str = "en",
        limit: int = 100,
        cursor: int = 0,
        after_qid: Optional[str] = None,
    ) -> str:
        """Build SPARQL query for public figures with filters."""
        
        return build_figures_query(
            birthday_from=birthday_from,
            birthday_to=birthday_to,
            nationality=nationality,
            profession=profession,
            lang=lang,
            limit=limit,
            cursor=cursor,
            after_qid=after_qid,
        )

    def build_public_institutions_query(
        self,
        country: Optional[str] = None,
        type: Optional[List[str]] = None,
        jurisdiction: Optional[str] = None,
        lang: str = "en",
        limit: int = 100,
        cursor: int = 0,
        after_qid: Optional[str] = None,
    ) -> str:
        """Build SPARQL query for public institutions with filters."""
        
        return build_institutions_query(
            country=country,
            type=type,
            jurisdiction=jurisdiction,
            lang=lang,
            limit=limit,
            cursor=cursor,
            after_qid=after_qid,
        )

    def build_entity_expansion_query(self, qid: str, lang: str = "en") -> str:
        """Build comprehensive SPARQL query to fetch all entity properties with labels directly.
        Includes: _id (?entity), gender label, aliases (alt labels), and common identifiers.
        """
        parts = []
        parts.append("""
        SELECT DISTINCT 
            ?entity
            ?gender ?genderLabel
            ?entityAltLabel
            ?nationality ?nationalityLabel
            ?profession ?professionLabel
            ?placeOfBirth ?placeOfBirthLabel
            ?placeOfDeath ?placeOfDeathLabel
            ?residence ?residenceLabel
            ?affiliation ?affiliationLabel
            ?notableWork ?notableWorkLabel
            ?award ?awardLabel
            ?website
            ?twitterHandle ?instagramHandle ?facebookHandle ?youtubeHandle ?tiktokHandle
            ?gnd ?viaf ?isni ?lc ?bnf
        WHERE {
        """)
        parts.append(f"  BIND(wd:{qid} AS ?entity)\n")
        parts.append("  ?entity wdt:P31 wd:Q5.  # instance of human\n\n")
        parts.append("  # Gender (P21)\n  OPTIONAL { ?entity wdt:P21 ?gender. }\n\n")
        parts.append("  # Nationalities (P27)\n  OPTIONAL { ?entity wdt:P27 ?nationality. }\n\n")
        parts.append("  # Professions (P106)\n  OPTIONAL { ?entity wdt:P106 ?profession. }\n\n")
        parts.append("  # Place of birth (P19)\n  OPTIONAL { ?entity wdt:P19 ?placeOfBirth. }\n\n")
        parts.append("  # Place of death (P20)\n  OPTIONAL { ?entity wdt:P20 ?placeOfDeath. }\n\n")
        parts.append("  # Residence (P551)\n  OPTIONAL { ?entity wdt:P551 ?residence. }\n\n")
        parts.append("  # Affiliations (P102 - member of political party, P463 - member of)\n  OPTIONAL { ?entity wdt:P102 ?affiliation. }\n  OPTIONAL { ?entity wdt:P463 ?affiliation. }\n\n")
        parts.append("  # Notable works (P800)\n  OPTIONAL { ?entity wdt:P800 ?notableWork. }\n\n")
        parts.append("  # Awards (P166)\n  OPTIONAL { ?entity wdt:P166 ?award. }\n\n")
        parts.append("  # Website (P856)\n  OPTIONAL { ?entity wdt:P856 ?website. }\n\n")
        parts.append("  # Identifiers\n  OPTIONAL { ?entity wdt:P227 ?gnd. }   # GND\n  OPTIONAL { ?entity wdt:P214 ?viaf. }  # VIAF\n  OPTIONAL { ?entity wdt:P213 ?isni. }  # ISNI\n  OPTIONAL { ?entity wdt:P244 ?lc. }    # LC\n  OPTIONAL { ?entity wdt:P268 ?bnf. }   # BNF\n\n")
        parts.append("  # Social media handles\n  OPTIONAL { ?entity wdt:P2002 ?twitterHandle. }  # Twitter\n  OPTIONAL { ?entity wdt:P2003 ?instagramHandle. }  # Instagram\n  OPTIONAL { ?entity wdt:P2013 ?facebookHandle. }  # Facebook\n  OPTIONAL { ?entity wdt:P2397 ?youtubeHandle. }  # YouTube\n  OPTIONAL { ?entity wdt:P7083 ?tiktokHandle. }  # TikTok\n\n")
        parts.append("  SERVICE wikibase:label {\n")
        parts.append(f"    bd:serviceParam wikibase:language \"{lang}\".\n")
        parts.append("    ?gender rdfs:label ?genderLabel.\n")
        parts.append("    ?nationality rdfs:label ?nationalityLabel.\n")
        parts.append("    ?profession rdfs:label ?professionLabel.\n")
        parts.append("    ?placeOfBirth rdfs:label ?placeOfBirthLabel.\n")
        parts.append("    ?placeOfDeath rdfs:label ?placeOfDeathLabel.\n")
        parts.append("    ?residence rdfs:label ?residenceLabel.\n")
        parts.append("    ?affiliation rdfs:label ?affiliationLabel.\n")
        parts.append("    ?notableWork rdfs:label ?notableWorkLabel.\n")
        parts.append("    ?award rdfs:label ?awardLabel.\n")
        parts.append("    ?entity skos:altLabel ?entityAltLabel.\n")
        parts.append("  }\n")
        parts.append("}" )
        return "".join(parts)

    def build_institution_expansion_query(self, qid: str, lang: str = "en") -> str:
        """Build SPARQL to fetch institution properties with labels directly."""
        parts: List[str] = []
        parts.append("""
        SELECT DISTINCT
            ?entity
            ?type ?typeLabel
            ?country ?countryLabel
            ?jurisdiction ?jurisdictionLabel
            ?foundedDate
            ?legalForm ?legalFormLabel
            ?headquarters ?headquartersLabel
            ?officialLanguage ?officialLanguageLabel
            ?parentInstitution ?parentInstitutionLabel
            ?affiliation ?affiliationLabel
            ?website
            ?logo
            ?budget
            ?twitterHandle ?instagramHandle ?facebookHandle ?youtubeHandle ?tiktokHandle
        WHERE {
        """)
        parts.append(f"  BIND(wd:{qid} AS ?entity)\n")
        parts.append("  ?entity wdt:P31 ?type.\n\n")
        parts.append("  OPTIONAL { ?entity wdt:P17 ?country. }\n")
        parts.append("  OPTIONAL { ?entity wdt:P1001 ?jurisdiction. }\n")
        parts.append("  OPTIONAL { ?entity wdt:P571 ?foundedDate. }\n")
        parts.append("  OPTIONAL { ?entity wdt:P1454 ?legalForm. }\n")
        parts.append("  OPTIONAL { ?entity wdt:P159 ?headquarters. }\n")
        parts.append("  OPTIONAL { ?entity wdt:P2936 ?officialLanguage. }\n")
        parts.append("  OPTIONAL { ?entity wdt:P749 ?parentInstitution. }\n")
        parts.append("  OPTIONAL { ?entity wdt:P361 ?parentInstitution. }\n")
        parts.append("  OPTIONAL { ?entity wdt:P463 ?affiliation. }\n")
        parts.append("  OPTIONAL { ?entity wdt:P856 ?website. }\n")
        parts.append("  OPTIONAL { ?entity wdt:P154 ?logo. }\n")
        parts.append("  OPTIONAL { ?entity wdt:P2130 ?budget. }\n")
        parts.append("  OPTIONAL { ?entity wdt:P2002 ?twitterHandle. }\n")
        parts.append("  OPTIONAL { ?entity wdt:P2003 ?instagramHandle. }\n")
        parts.append("  OPTIONAL { ?entity wdt:P2013 ?facebookHandle. }\n")
        parts.append("  OPTIONAL { ?entity wdt:P2397 ?youtubeHandle. }\n")
        parts.append("  OPTIONAL { ?entity wdt:P7083 ?tiktokHandle. }\n\n")
        parts.append("  SERVICE wikibase:label {\n")
        parts.append(f"    bd:serviceParam wikibase:language \"{lang}\".\n")
        parts.append("    ?type rdfs:label ?typeLabel.\n")
        parts.append("    ?country rdfs:label ?countryLabel.\n")
        parts.append("    ?jurisdiction rdfs:label ?jurisdictionLabel.\n")
        parts.append("    ?legalForm rdfs:label ?legalFormLabel.\n")
        parts.append("    ?headquarters rdfs:label ?headquartersLabel.\n")
        parts.append("    ?officialLanguage rdfs:label ?officialLanguageLabel.\n")
        parts.append("    ?parentInstitution rdfs:label ?parentInstitutionLabel.\n")
        parts.append("    ?affiliation rdfs:label ?affiliationLabel.\n")
        parts.append("  }\n")
        parts.append("}" )
        return "".join(parts)

    def get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()

    def get_entity_by_qid(self, qid: str, lang: str = "en", request: Optional[Request] = None) -> tuple[Dict[str, Any], str]:
        """Fetch raw entity data from Wikidata EntityData API.
        
        Args:
            qid: Wikidata entity QID (e.g., 'Q42')
            lang: Language code for labels
            request: FastAPI Request object for proxy management
            
        Returns:
            Tuple of (entity_dict, used_proxy) where entity_dict is the full entity object from EntityData JSON
            
        Raises:
            HTTPException: If entity cannot be fetched after retries
        """
        entity_url = config.WIKIDATA_ENTITY_API_URL.format(qid=qid)
        used_proxy = "direct"
        max_retries = 3
        
        for attempt in range(max_retries):
            proxy = None
            try:
                # On final attempt force a direct connection (no proxy) as a fallback
                if attempt < max_retries - 1:
                    proxy = self.proxy_manager.get_next_proxy(request)
                proxy_dict = self.proxy_manager.get_proxy_dict(proxy) if proxy else None
                
                headers = {
                    "Accept": "application/json",
                    "User-Agent": USER_AGENT
                }
                resp = requests.get(entity_url, params={"language": lang}, headers=headers, proxies=proxy_dict, timeout=self.proxy_manager.timeout_per_hop)
                resp.raise_for_status()
                used_proxy = proxy or "direct"
                data = resp.json()
                
                entities = data.get("entities", {})
                ent = entities.get(qid)
                if not ent:
                    raise HTTPException(status_code=404, detail="Entity not found")
                
                return ent, used_proxy
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Entity lookup failed (attempt {attempt + 1}): {e}")
                if proxy:
                    self.proxy_manager.mark_proxy_failed(proxy)
                if attempt == max_retries - 1:
                    raise HTTPException(status_code=502, detail="Failed to fetch entity from Wikidata")
                time.sleep(1)
        
        # Should never reach here
        raise HTTPException(status_code=502, detail="Failed to fetch entity from Wikidata")

    def expand_entity_data(self,qid: str, lang: str = "en", request: Optional[Request] = None) -> Dict[str, Any]:
        """Fetch additional entity data using SPARQL query with direct label resolution and caching."""
        # Check entity expansion cache
        cache_key = f"{qid}:{lang}"
        cached_data = entity_expansion_cache.get(cache_key)
        if cached_data:
            return cached_data
        
        expanded_data = {
            "aliases": [],
            "nationalities": [],
            "gender": None,
            "professions": [],
            "place_of_birth": [],
            "place_of_death": [],
            "residence": [],
            "website": [],
            "accounts": [],
            "affiliations": [],
            "notable_works": [],
            "awards": [],
            "identifiers": []
        }
        
        try:
            # Try SPARQL approach first
            sparql_query = self.build_entity_expansion_query(qid, lang)
            result, _ = self.execute_sparql_query(sparql_query, limit=1000, request=request)
            #print (result)
            # Process SPARQL results
            bindings = result.get("results", {}).get("bindings", [])
            if bindings:
                current_time = self.get_current_timestamp()
                
                for binding in bindings:
                    # Process aliases (entity alt labels)
                    if binding.get("entityAltLabel"):
                        alt_label = binding["entityAltLabel"]["value"]
                        if alt_label:
                            # Some endpoints may return comma-separated aliases; split conservatively
                            parts = [p.strip() for p in alt_label.split(",") if p.strip()]
                            if parts:
                                for alias in parts:
                                    if alias not in expanded_data["aliases"]:
                                        expanded_data["aliases"].append(alias)
                            elif alt_label not in expanded_data["aliases"]:
                                expanded_data["aliases"].append(alt_label)
                    
                    # Process gender label
                    if binding.get("genderLabel"):
                        gender_label = binding["genderLabel"]["value"]
                        #print (gender_label)
                        if gender_label: #and "gender" not in expanded_data:
                            #print (gender_label)
                            expanded_data["gender"] = gender_label.lower()
                    # Process nationalities (P27)
                    if binding.get("nationality") and binding.get("nationalityLabel"):
                        nationality = binding["nationalityLabel"]["value"]
                        if nationality not in expanded_data["nationalities"]:
                            expanded_data["nationalities"].append(nationality)
                    
                    # Process professions (P106)
                    if binding.get("profession") and binding.get("professionLabel"):
                        profession = binding["professionLabel"]["value"]
                        if profession not in expanded_data["professions"]:
                            expanded_data["professions"].append(profession)
                    
                    # Process place of birth (P19)
                    if binding.get("placeOfBirth") and binding.get("placeOfBirthLabel"):
                        place = binding["placeOfBirthLabel"]["value"]
                        if place not in expanded_data["place_of_birth"]:
                            expanded_data["place_of_birth"].append(place)
                    
                    # Process place of death (P20)
                    if binding.get("placeOfDeath") and binding.get("placeOfDeathLabel"):
                        place = binding["placeOfDeathLabel"]["value"]
                        if place not in expanded_data["place_of_death"]:
                            expanded_data["place_of_death"].append(place)
                    
                    # Process residence (P551)
                    if binding.get("residence") and binding.get("residenceLabel"):
                        residence = binding["residenceLabel"]["value"]
                        if residence not in expanded_data["residence"]:
                            expanded_data["residence"].append(residence)
                    
                    # Process affiliations (P102, P463)
                    if binding.get("affiliation") and binding.get("affiliationLabel"):
                        affiliation = binding["affiliationLabel"]["value"]
                        if affiliation not in expanded_data["affiliations"]:
                            expanded_data["affiliations"].append(affiliation)
                    
                    # Process notable works (P800)
                    if binding.get("notableWork") and binding.get("notableWorkLabel"):
                        work = binding["notableWorkLabel"]["value"]
                        if work not in expanded_data["notable_works"]:
                            expanded_data["notable_works"].append(work)
                    
                    # Process awards (P166)
                    if binding.get("award") and binding.get("awardLabel"):
                        award = binding["awardLabel"]["value"]
                        if award not in expanded_data["awards"]:
                            expanded_data["awards"].append(award)
                    
                    # Process website (P856)
                    if binding.get("website"):
                        url = binding["website"]["value"]
                        if url:
                            website_entry = {
                                "url": url,
                                "source": "wikidata",
                                "retrieved_at": current_time
                            }
                            if website_entry not in expanded_data["website"]:
                                expanded_data["website"].append(website_entry)
                    
                    # Process social media handles
                    for platform, prop in [("twitter", "twitterHandle"), ("instagram", "instagramHandle"), 
                                         ("facebook", "facebookHandle"), ("youtube", "youtubeHandle"), 
                                         ("tiktok", "tiktokHandle")]:
                        if binding.get(prop):
                            handle = binding[prop]["value"]
                            if handle:
                                account_entry = {
                                    "platform": platform,
                                    "handle": handle,
                                    "source": "wikidata",
                                    "retrieved_at": current_time
                                }
                                if account_entry not in expanded_data["accounts"]:
                                    expanded_data["accounts"].append(account_entry)

                    # Process identifiers
                    for var_name, scheme in [("gnd", "GND"), ("viaf", "VIAF"), ("isni", "ISNI"), ("lc", "LC"), ("bnf", "BNF")]:
                        if binding.get(var_name):
                            id_val = binding[var_name]["value"]
                            if id_val:
                                identifier_entry = {"scheme": scheme, "id": id_val}
                                if identifier_entry not in expanded_data["identifiers"]:
                                    expanded_data["identifiers"].append(identifier_entry)
                
                # Cache the result before returning
                entity_expansion_cache.set(cache_key, expanded_data)
                return expanded_data
            
        except Exception as e:
            logger.warning(f"SPARQL approach failed for {qid}: {e}")
        
        # Fallback to EntityData API approach
        try:
            entity_url = config.WIKIDATA_ENTITY_API_URL.format(qid=qid)
            logger.warning(f"Falling back to EntityData API approach for {qid}")
            max_retries = 3
            for attempt in range(max_retries):
                proxy = None
                try:
                    if attempt < max_retries - 1:
                        proxy = self.proxy_manager.get_next_proxy(request)
                    proxy_dict = self.proxy_manager.get_proxy_dict(proxy) if proxy else None
                    
                    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
                    resp = requests.get(entity_url, headers=headers, proxies=proxy_dict, timeout=self.proxy_manager.timeout_per_hop)
                    resp.raise_for_status()
                    data = resp.json()
                    
                    entities = data.get("entities", {})
                    ent = entities.get(qid)
                    if not ent:
                        return expanded_data
                    
                    claims = ent.get("claims", {})
                    current_time = self.get_current_timestamp()
                    
                    # Get aliases
                    aliases_data = ent.get("aliases", {})
                    for lang_aliases in aliases_data.values():
                        for alias in lang_aliases:
                            alias_val = alias.get("value")
                            if alias_val:
                                expanded_data["aliases"].append(alias_val)
                    
                    # Get website (P856)
                    if claims.get("P856"):
                        for claim in claims["P856"]:
                            dv = claim.get("mainsnak", {}).get("datavalue")
                            if dv and dv.get("type") == "string":
                                url = dv.get("value")
                                if url:
                                    expanded_data["website"].append({
                                        "url": url,
                                        "source": "wikidata",
                                        "retrieved_at": current_time
                                    })
                    
                    # Get social media handles
                    for platform, prop in [("twitter", "P2002"), ("instagram", "P2003"), 
                                         ("facebook", "P2013"), ("youtube", "P2397"), 
                                         ("tiktok", "P7083")]:
                        if claims.get(prop):
                            for claim in claims[prop]:
                                dv = claim.get("mainsnak", {}).get("datavalue")
                                if dv and dv.get("type") == "string":
                                    handle = dv.get("value")
                                    if handle:
                                        account_entry = {
                                            "platform": platform,
                                            "handle": handle,
                                            "source": "wikidata",
                                            "retrieved_at": current_time
                                        }
                                        if account_entry not in expanded_data["accounts"]:
                                            expanded_data["accounts"].append(account_entry)
                    
                    # Get identifiers
                    identifier_mappings = {
                        "P227": "GND",
                        "P214": "VIAF",
                        "P213": "ISNI",
                        "P244": "LC",
                        "P268": "BNF"
                    }
                    for prop, scheme in identifier_mappings.items():
                        if claims.get(prop):
                            for claim in claims[prop]:
                                dv = claim.get("mainsnak", {}).get("datavalue")
                                if dv and (dv.get("type") == "string" or dv.get("type") == "external-id"):
                                    id_val = dv.get("value")
                                    if id_val:
                                        expanded_data["identifiers"].append({
                                            "scheme": scheme,
                                            "id": id_val
                                        })
                    
                    # Cache the result before returning
                    entity_expansion_cache.set(cache_key, expanded_data)
                    return expanded_data
                    
                except requests.exceptions.RequestException as e:
                    if proxy:
                        self.proxy_manager.mark_proxy_failed(proxy)
                    if attempt == max_retries - 1:
                        logger.warning(f"Failed to expand entity data for {qid}: {e}")
                        # Don't cache partial/failed results
                        return expanded_data
                    time.sleep(0.5)
            
        except Exception as e:
            logger.warning(f"Error expanding entity data for {qid}: {e}")
        
        # Don't cache if we get here (error/empty case)
        return expanded_data

    def normalize_public_figure(
        self,
        item: Dict[str, Any],
        expanded_data: Optional[Dict[str, Any]] = None,
        lang: str = "en",
    ) -> PublicFigure:
        """Normalize Wikidata result to the public figure schema."""

        return normalize_figure(item, expanded_data, lang, self)

    def get_labels_from_qids(self, qids: List[str], lang: str = "en", request: Optional[Request] = None) -> Dict[str, str]:
        """Get labels for multiple QIDs from Wikidata EntityData API.
        
        Args:
            qids: List of Wikidata entity QIDs
            lang: Language code for labels
            request: FastAPI Request object for proxy management
            
        Returns:
            Dictionary mapping QID to label (e.g., {"Q42": "Douglas Adams"})
        """
        if not qids:
            return {}
        
        labels = {}
        # Process each QID individually since EntityData API processes one at a time
        for qid in qids:
            if not qid or not qid.startswith('Q'):
                continue
                
            entity_url = config.WIKIDATA_ENTITY_API_URL.format(qid=qid)
            
            try:
                max_retries = 2
                for attempt in range(max_retries):
                    proxy = None
                    try:
                        if attempt < max_retries - 1:
                            proxy = self.proxy_manager.get_next_proxy(request)
                        proxy_dict = self.proxy_manager.get_proxy_dict(proxy) if proxy else None
                        
                        headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
                        resp = requests.get(entity_url, params={"language": lang}, headers=headers, proxies=proxy_dict, timeout=self.proxy_manager.timeout_per_hop)
                        resp.raise_for_status()
                        data = resp.json()
                        entities = data.get("entities", {})
                        ent = entities.get(qid)
                        if ent:
                            labels_data = ent.get("labels", {})
                            # Try preferred language first, then fallback to any
                            if lang in labels_data:
                                labels[qid] = labels_data[lang].get("value", "")
                            elif labels_data:
                                # Fallback to first available label
                                first_label = next(iter(labels_data.values()))
                                labels[qid] = first_label.get("value", "")
                        
                        break  # Success, move to next QID
                        
                    except requests.exceptions.RequestException:
                        if attempt == max_retries - 1:
                            logger.warning(f"Failed to get label for QID: {qid}")
                        else:
                            time.sleep(0.3)
            except Exception as e:
                logger.warning(f"Error getting label for QID {qid}: {e}")
        
        return labels

    def get_country_code_from_qid(self,country_qid: str, request: Optional[Request] = None) -> Optional[str]:
        """Get ISO 3166-1 alpha-3 country code from Wikidata QID."""
        if not country_qid or not country_qid.startswith('Q'):
            return None
        
        entity_url = config.WIKIDATA_ENTITY_API_URL.format(qid=country_qid)
        try:
            max_retries = 2
            for attempt in range(max_retries):
                proxy = None
                try:
                    if attempt < max_retries - 1:
                        proxy = self.proxy_manager.get_next_proxy(request)
                    proxy_dict = self.proxy_manager.get_proxy_dict(proxy) if proxy else None
                    
                    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
                    resp = requests.get(entity_url, headers=headers, proxies=proxy_dict, timeout=30)
                    resp.raise_for_status()
                    data = resp.json()
                    
                    entities = data.get("entities", {})
                    ent = entities.get(country_qid)
                    if not ent:
                        return None
                    
                    claims = ent.get("claims", {})
                    # P298 is ISO 3166-1 alpha-3 code
                    if claims.get("P298"):
                        dv = claims["P298"][0].get("mainsnak", {}).get("datavalue")
                        if dv and dv.get("type") == "string":
                            return dv.get("value")
                    
                    return None
                    
                except requests.exceptions.RequestException:
                    if attempt == max_retries - 1:
                        return None
                    time.sleep(0.3)
            
        except Exception:
            pass
        
        return None

    def expand_entity_data_institution(self,qid: str, lang: str = "en", request: Optional[Request] = None) -> Dict[str, Any]:
        """Fetch additional institution data via SPARQL (labels directly), fallback to EntityData."""
        # Check entity expansion cache
        cache_key = f"{qid}:{lang}:institution"
        cached_data = entity_expansion_cache.get(cache_key)
        if cached_data:
            return cached_data
        
        # SPARQL-first approach
        try:
            expanded_data = {
                "aliases": [],
                "types": [],
                "country": [],
                "country_code": [],
                "jurisdiction": [],
                "founded": [],
                "legal_form": [],
                "headquarters": [],
                "headquarters_coords": [],
                "website": [],
                "official_language": [],
                "logo": [],
                "budget": [],
                "parent_institution": [],
                "sector": [],
                "affiliations": [],
                "accounts": []
            }

            query = self.build_institution_expansion_query(qid, lang)
            result, _ = self.execute_sparql_query(query, limit=1000, request=request)
            bindings = result.get("results", {}).get("bindings", [])
            if bindings:
                current_time = self.get_current_timestamp()
                for b in bindings:
                    # Types
                    if b.get("typeLabel"):
                        val = b["typeLabel"]["value"]
                        if val and val not in expanded_data["types"]:
                            expanded_data["types"].append(val)
                    # Country and code
                    if b.get("countryLabel"):
                        val = b["countryLabel"]["value"]
                        if val and val not in expanded_data["country"]:
                            expanded_data["country"].append(val)
                        # country code from QID
                        if b.get("country"):
                            quri = b["country"]["value"]
                            q = quri.split("/")[-1]
                            if q.startswith("Q"):
                                code = self.get_country_code_from_qid(q, request)
                                if code and code not in expanded_data["country_code"]:
                                    expanded_data["country_code"].append(code)
                    # Jurisdiction
                    if b.get("jurisdictionLabel"):
                        val = b["jurisdictionLabel"]["value"]
                        if val and val not in expanded_data["jurisdiction"]:
                            expanded_data["jurisdiction"].append(val)
                    # Founded
                    if b.get("foundedDate"):
                        fval = b["foundedDate"]["value"]
                        if fval and fval not in expanded_data["founded"]:
                            expanded_data["founded"].append(fval)
                    # Legal form
                    if b.get("legalFormLabel"):
                        val = b["legalFormLabel"]["value"]
                        if val and val not in expanded_data["legal_form"]:
                            expanded_data["legal_form"].append(val)
                    # Headquarters (labels)
                    if b.get("headquartersLabel"):
                        val = b["headquartersLabel"]["value"]
                        if val and val not in expanded_data["headquarters"]:
                            expanded_data["headquarters"].append(val)
                    # Official language
                    if b.get("officialLanguageLabel"):
                        val = b["officialLanguageLabel"]["value"]
                        if val and val not in expanded_data["official_language"]:
                            expanded_data["official_language"].append(val)
                    # Parent institution
                    if b.get("parentInstitutionLabel"):
                        val = b["parentInstitutionLabel"]["value"]
                        if val and val not in expanded_data["parent_institution"]:
                            expanded_data["parent_institution"].append(val)
                    # Affiliations
                    if b.get("affiliationLabel"):
                        val = b["affiliationLabel"]["value"]
                        if val and val not in expanded_data["affiliations"]:
                            expanded_data["affiliations"].append(val)
                    # Website
                    if b.get("website"):
                        url = b["website"]["value"]
                        if url:
                            entry = {"url": url, "source": "wikidata", "retrieved_at": current_time}
                            if entry not in expanded_data["website"]:
                                expanded_data["website"].append(entry)
                    # Logo
                    if b.get("logo"):
                        logo = b["logo"]["value"]
                        if logo and logo not in expanded_data["logo"]:
                            expanded_data["logo"].append(logo)
                    # Budget (stringify)
                    if b.get("budget"):
                        bud = b["budget"]["value"]
                        if bud and bud not in expanded_data["budget"]:
                            expanded_data["budget"].append(str(bud))
                    # Social accounts
                    for platform, var in [("twitter", "twitterHandle"), ("instagram", "instagramHandle"),
                                          ("facebook", "facebookHandle"), ("youtube", "youtubeHandle"),
                                          ("tiktok", "tiktokHandle")]:
                        if b.get(var):
                            handle = b[var]["value"]
                            if handle:
                                acc = {"platform": platform, "handle": handle, "source": "wikidata", "retrieved_at": current_time}
                                if acc not in expanded_data["accounts"]:
                                    expanded_data["accounts"].append(acc)

                # Cache the result before returning
                entity_expansion_cache.set(cache_key, expanded_data)
                return expanded_data
        except Exception as e:
            logger.warning(f"SPARQL institution expansion failed for {qid}: {e}")

        # Fallback to existing EntityData approach below
        entity_url = config.WIKIDATA_ENTITY_API_URL.format(qid=qid)
        expanded_data = {
            "aliases": [],
            "types": [],
            "country": [],
            "country_code": [],
            "jurisdiction": [],
            "founded": [],
            "legal_form": [],
            "headquarters": [],
            "headquarters_coords": [],
            "website": [],
            "official_language": [],
            "logo": [],
            "budget": [],
            "parent_institution": [],
            "sector": [],
            "affiliations": [],
            "accounts": []
        }
        
        try:
            max_retries = 3
            for attempt in range(max_retries):
                proxy = None
                try:
                    if attempt < max_retries - 1:
                        proxy = self.proxy_manager.get_next_proxy(request)
                    proxy_dict = self.proxy_manager.get_proxy_dict(proxy) if proxy else None
                    
                    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
                    resp = requests.get(entity_url, headers=headers, proxies=proxy_dict, timeout=self.proxy_manager.timeout_per_hop)
                    resp.raise_for_status()
                    data = resp.json()
                    
                    entities = data.get("entities", {})
                    ent = entities.get(qid)
                    if not ent:
                        return expanded_data
                    
                    claims = ent.get("claims", {})
                    current_time = self.get_current_timestamp()
                    
                    # Get aliases (language-specific)
                    aliases_data = ent.get("aliases", {})
                    if lang in aliases_data:
                        for alias in aliases_data[lang]:
                            alias_val = alias.get("value")
                            if alias_val:
                                expanded_data["aliases"].append(alias_val)
                    # Fallback to English if lang not available
                    elif "en" in aliases_data and lang != "en":
                        for alias in aliases_data["en"]:
                            alias_val = alias.get("value")
                            if alias_val:
                                expanded_data["aliases"].append(alias_val)
                    
                    # Collect QIDs that need label resolution
                    qids_to_resolve = []
                    
                    # Get types (P31 - instance of) - collect all types as QIDs
                    type_qids = []
                    if claims.get("P31"):
                        for claim in claims["P31"]:
                            dv = claim.get("mainsnak", {}).get("datavalue")
                            if dv and dv.get("type") == "wikibase-entityid":
                                type_qid = dv.get("value", {}).get("id")
                                if type_qid:
                                    type_qids.append(type_qid)
                                    qids_to_resolve.append(type_qid)
                    
                    # Get country (P17) - collect all countries (can have multiple)
                    country_qids = []
                    if claims.get("P17"):
                        for claim in claims["P17"]:
                            dv = claim.get("mainsnak", {}).get("datavalue")
                            if dv and dv.get("type") == "wikibase-entityid":
                                country_qid = dv.get("value", {}).get("id")
                        if country_qid:
                                    country_qids.append(country_qid)
                                    qids_to_resolve.append(country_qid)
                    
                    # Get jurisdiction (P1001) - collect all
                    jurisdiction_qids = []
                    if claims.get("P1001"):
                        for claim in claims["P1001"]:
                            dv = claim.get("mainsnak", {}).get("datavalue")
                        if dv and dv.get("type") == "wikibase-entityid":
                            jurisdiction_qid = dv.get("value", {}).get("id")
                            if jurisdiction_qid:
                                    jurisdiction_qids.append(jurisdiction_qid)
                                    qids_to_resolve.append(jurisdiction_qid)
                    
                    # Get founded date (P571) - collect all as list
                    founded_dates = []
                    if claims.get("P571"):
                        for claim in claims["P571"]:
                            dv = claim.get("mainsnak", {}).get("datavalue")
                        if dv and dv.get("type") == "time":
                            founded = dv.get("value", {}).get("time")
                            if founded:
                                founded_date = founded.split("T")[0] if "T" in founded else founded
                                if founded_date.startswith("+") or founded_date.startswith("-"):
                                        founded_dates.append(founded_date[1:])
                                else:
                                        founded_dates.append(founded_date)
                    
                    # Get legal form (P1454) - collect all
                    legal_form_qids = []
                    if claims.get("P1454"):
                        for claim in claims["P1454"]:
                            dv = claim.get("mainsnak", {}).get("datavalue")
                        if dv and dv.get("type") == "wikibase-entityid":
                            legal_form_qid = dv.get("value", {}).get("id")
                            if legal_form_qid:
                                    legal_form_qids.append(legal_form_qid)
                                    qids_to_resolve.append(legal_form_qid)
                    
                    # Get headquarters (P159) - collect all
                    headquarters_qids = []
                    if claims.get("P159"):
                        for claim in claims["P159"]:
                            dv = claim.get("mainsnak", {}).get("datavalue")
                        if dv and dv.get("type") == "wikibase-entityid":
                            hq_qid = dv.get("value", {}).get("id")
                            if hq_qid:
                                    headquarters_qids.append(hq_qid)
                                    qids_to_resolve.append(hq_qid)
                    
                    # Get headquarters coordinates (P625) - collect all
                    headquarters_coords_list = []
                    if claims.get("P625"):
                        for claim in claims["P625"]:
                            dv = claim.get("mainsnak", {}).get("datavalue")
                            if dv and dv.get("type") == "globecoordinate":
                                coord = dv.get("value", {})
                                if coord and coord.get("latitude") is not None and coord.get("longitude") is not None:
                                    headquarters_coords_list.append({
                                        "lat": coord.get("latitude"),
                                        "lon": coord.get("longitude")
                                    })
                    
                    # Get website (P856)
                    if claims.get("P856"):
                        for claim in claims["P856"]:
                            dv = claim.get("mainsnak", {}).get("datavalue")
                            if dv and dv.get("type") == "string":
                                url = dv.get("value")
                                if url:
                                    expanded_data["website"].append({
                                        "url": url,
                                        "source": "wikidata",
                                        "retrieved_at": current_time
                                    })
                    
                    # Get official language (P2936) - collect QIDs
                    official_language_qids = []
                    if claims.get("P2936"):
                        for claim in claims["P2936"]:
                            dv = claim.get("mainsnak", {}).get("datavalue")
                            if dv and dv.get("type") == "wikibase-entityid":
                                lang_qid = dv.get("value", {}).get("id")
                                if lang_qid:
                                    official_language_qids.append(lang_qid)
                                    qids_to_resolve.append(lang_qid)
                    
                    # Get logo (P154) - collect all
                    logos = []
                    if claims.get("P154"):
                        for claim in claims["P154"]:
                            dv = claim.get("mainsnak", {}).get("datavalue")
                        if dv and dv.get("type") == "string":
                            logo = dv.get("value")
                            if logo:
                                    logos.append(logo)
                    
                    # Get budget (P2130) - collect all
                    budgets = []
                    if claims.get("P2130"):
                        for claim in claims["P2130"]:
                            dv = claim.get("mainsnak", {}).get("datavalue")
                        if dv:
                            if dv.get("type") == "quantity":
                                budget_val = dv.get("value", {}).get("amount")
                                if budget_val:
                                        budgets.append(str(budget_val))
                            elif dv.get("type") == "string":
                                    budget_str = dv.get("value")
                                    if budget_str:
                                        budgets.append(budget_str)
                    
                    # Get parent institution (P749 - founded by, or P361 - part of) - collect QIDs
                    parent_institution_qids = []
                    for prop in ["P749", "P361"]:
                        if claims.get(prop):
                            for claim in claims[prop]:
                                dv = claim.get("mainsnak", {}).get("datavalue")
                        if dv and dv.get("type") == "wikibase-entityid":
                            parent_qid = dv.get("value", {}).get("id")
                            if parent_qid:
                                        parent_institution_qids.append(parent_qid)
                                        qids_to_resolve.append(parent_qid)
                    
                    # Sector - leave blank for now as per user request (empty list)
                    
                    # Get affiliations (P463 - member of) - collect QIDs
                    affiliation_qids = []
                    if claims.get("P463"):
                        for claim in claims["P463"]:
                            dv = claim.get("mainsnak", {}).get("datavalue")
                            if dv and dv.get("type") == "wikibase-entityid":
                                aff_qid = dv.get("value", {}).get("id")
                                if aff_qid:
                                    affiliation_qids.append(aff_qid)
                                    qids_to_resolve.append(aff_qid)
                    
                    # Resolve QIDs to labels
                    if qids_to_resolve:
                        labels_map = self.get_labels_from_qids(list(set(qids_to_resolve)), lang=lang, request=request)
                        
                        # Resolve types
                        for qid in type_qids:
                            label = labels_map.get(qid, qid)
                            if label:
                                expanded_data["types"].append(label)
                        
                        # Resolve countries
                        for qid in country_qids:
                            label = labels_map.get(qid, qid)
                            if label:
                                expanded_data["country"].append(label)
                            # Get country code
                            country_code = self.get_country_code_from_qid(qid, request)
                            if country_code:
                                expanded_data["country_code"].append(country_code)
                        
                        # Resolve jurisdictions
                        for qid in jurisdiction_qids:
                            label = labels_map.get(qid, qid)
                            if label:
                                expanded_data["jurisdiction"].append(label)
                        
                        # Resolve legal forms
                        for qid in legal_form_qids:
                            label = labels_map.get(qid, qid)
                            if label:
                                expanded_data["legal_form"].append(label)
                        
                        # Resolve headquarters
                        for qid in headquarters_qids:
                            label = labels_map.get(qid, qid)
                            if label:
                                expanded_data["headquarters"].append(label)
                        
                        # Resolve official languages
                        for qid in official_language_qids:
                            label = labels_map.get(qid, qid)
                            if label:
                                expanded_data["official_language"].append(label)
                        
                        # Resolve parent institutions
                        for qid in parent_institution_qids:
                            label = labels_map.get(qid, qid)
                            if label:
                                expanded_data["parent_institution"].append(label)
                        
                        # Resolve affiliations
                        for qid in affiliation_qids:
                            label = labels_map.get(qid, qid)
                            if label:
                                expanded_data["affiliations"].append(label)
                    
                    # Set founded dates, logos, budgets, coordinates
                    expanded_data["founded"] = founded_dates
                    expanded_data["logo"] = logos
                    expanded_data["budget"] = budgets
                    expanded_data["headquarters_coords"] = headquarters_coords_list
                    
                    # Get social media handles (same as for persons)
                    # Social media accounts (P2002, P2003, P2013, P2397, P7083)
                    property_map = {
                        "P2002": "twitter",
                        "P2003": "instagram",
                        "P2013": "facebook",
                        "P2397": "youtube",
                        "P7083": "tiktok"
                    }
                    for prop, platform in property_map.items():
                        if claims.get(prop):
                            for claim in claims[prop]:
                                dv = claim.get("mainsnak", {}).get("datavalue")
                                if dv and dv.get("type") == "string":
                                    handle = dv.get("value")
                                    if handle:
                                        account_entry = {
                                            "platform": platform,
                                            "handle": handle,
                                            "source": "wikidata",
                                            "retrieved_at": current_time
                                        }
                                        if account_entry not in expanded_data["accounts"]:
                                            expanded_data["accounts"].append(account_entry)
                    
                    # Cache the result before returning
                    entity_expansion_cache.set(cache_key, expanded_data)
                    return expanded_data
                    
                except requests.exceptions.RequestException as e:
                    if proxy:
                        self.proxy_manager.mark_proxy_failed(proxy)
                    if attempt == max_retries - 1:
                        logger.warning(f"Failed to expand institution entity data for {qid}: {e}")
                        # Don't cache partial/failed results
                        return expanded_data
                    time.sleep(0.5)
            
        except Exception as e:
            logger.warning(f"Error expanding institution entity data for {qid}: {e}")
        
        # Don't cache if we get here (error/empty case)
        return expanded_data

    def normalize_public_institution(
        self,
        item: Dict[str, Any],
        expanded_data: Optional[Dict[str, Any]] = None,
        lang: str = "en",
        request: Optional[Request] = None,
    ) -> PublicInstitution:
        """Normalize Wikidata result to the public institution schema."""

        return normalize_institution(item, expanded_data, lang, request, self)

    def expand_sub_institutions(self, qid: str, lang: str = "en", request: Optional[Request] = None) -> List[SubInstitution]:
        """Fetch sub-institutions for a given institution QID via SPARQL query.
        
        Finds institutions whose parent (P749) or part of (P361) is this QID.
        
        Args:
            qid: Wikidata institution QID
            lang: Language code for labels
            request: FastAPI Request object for proxy management
            
        Returns:
            List of SubInstitution models with _id, name, description, image
        """
        query = f"""SELECT DISTINCT ?inst ?instLabel ?description ?image WHERE {{
            ?inst (wdt:P749|wdt:P361) wd:{qid}.
            OPTIONAL {{ ?inst wdt:P18 ?image. }}
            SERVICE wikibase:label {{
                bd:serviceParam wikibase:language "{lang}".
                ?inst rdfs:label ?instLabel.
                ?inst schema:description ?description.
            }}
        }}"""
        
        try:
            result, _ = self.execute_sparql_query(query, limit=500, request=request)
            subs = []
            for item in result.get('results', {}).get('bindings', []):
                name_value = None
                if item.get('instLabel', {}).get('value'):
                    name_value = item['instLabel']['value']
                
                description_value = None
                if item.get('description', {}).get('value'):
                    description_value = item['description']['value']
                
                image_value = None
                if item.get('image', {}).get('value'):
                    image_value = item['image']['value']
                
                subs.append(SubInstitution(
                    _id=item.get('inst', {}).get('value', '').split('/')[-1],
                    name=name_value,
                    description=description_value,
                    image=image_value
                ))
            return subs
        except Exception as e:
            logger.warning(f"Failed to expand sub_institutions for {qid}: {e}")
            return []