import json
import time
from typing import Dict, Any, Optional, Union, List
from concurrent.futures import ThreadPoolExecutor
from fastapi import Request, HTTPException, Response
from fastapi.responses import StreamingResponse
from core.wiki_service import WikiService
from api.services.response_builder import ResponseBuilder
from api.utils.field_utils import FieldParser
from api.constants import EntityType, StreamFormat, ErrorType
from api.config import config
from api.exceptions import InternalErrorException
from infrastructure.observability import (
    get_request_id, sparql_latency_ctx, metrics, log_request_info
)
import logging

logger = logging.getLogger(__name__)

class ListProcessor:
    """Handles list operations for both figures and institutions."""
    
    def __init__(self, wiki_service: WikiService):
        self.wiki_service = wiki_service
        self.response_builder = ResponseBuilder()
        self.field_parser = FieldParser()
    
    async def process_list(
        self,
        entity_type: str,  # "public_figure" or "public_institution"
        request: Request,
        filters: Dict[str, Any],
        pagination: Dict[str, Any],
        fields: Optional[str],
        stream: Optional[str],
        route: str
    ) -> Union[Response, StreamingResponse]:
        """Process list request - handles both streaming and non-streaming.
        
        Args:
            entity_type: Type of entity ("public_figure" or "public_institution")
            request: FastAPI request object
            filters: Filter parameters
            pagination: Pagination parameters
            fields: Fields parameter for sparse fieldsets
            stream: Stream parameter ("ndjson" or None)
            route: Route path for logging
            
        Returns:
            Response or StreamingResponse
        """
        start_time = time.time()
        request_id = get_request_id()
        
        # Build params dict for logging
        params = {**filters, **pagination, "fields": fields, "stream": stream}
        
        used_proxy = None
        sparql_latency_ms = None
        entity_expansion_latency_ms = None
        cache_hit = False
        status_code = config.DEFAULT_STATUS_CODE
        error_type = None
        error_detail = None
        
        try:
            # Determine keyset vs offset cursor
            cursor = pagination.get('cursor')
            after_qid: Optional[str] = (
                cursor if isinstance(cursor, str) and cursor and cursor.startswith('Q') 
                else None
            )
            offset_cursor: int = (
                int(cursor) if cursor and isinstance(cursor, str) and cursor.isdigit() 
                else (cursor or 0) if isinstance(cursor, int) 
                else 0
            )
            
            # Build SPARQL query
            query = self._build_query(entity_type, filters, pagination, offset_cursor, after_qid)
            
            # Execute query with proxy support
            try:
                result, used_proxy = self.wiki_service.execute_sparql_query(
                    query, limit=pagination['limit'], request=request
                )
                sparql_latency_ms = sparql_latency_ctx.get(None)
                if used_proxy == "cached":
                    cache_hit = True
            except HTTPException as e:
                sparql_latency_ms = sparql_latency_ctx.get(None)
                status_code = getattr(e, "status_code", config.INTERNAL_ERROR_CODE)
                error_type = ErrorType.WDQS_ERROR.value
                error_detail = str(getattr(e, "detail", "error"))
                return self._handle_query_error(
                    stream, error_type, status_code, error_detail,
                    request_id, used_proxy, sparql_latency_ms, cache_hit,
                    route, params, start_time
                )
            
            bindings = result.get("results", {}).get("bindings", [])
            
            # Deduplicate and paginate
            entity_rows, page_qids = self._deduplicate_and_paginate(
                bindings, entity_type, pagination['limit']
            )
            
            # Parse fields parameter
            requested_fields = self.field_parser.parse_fields_param(fields)
            
            # Handle streaming vs non-streaming
            if stream == StreamFormat.NDJSON.value:
                return self._build_streaming_response(
                    entity_rows, page_qids, entity_type, requested_fields,
                    request_id, used_proxy, pagination['limit'], route, params,
                    sparql_latency_ms, cache_hit, status_code, request, filters.get('lang', config.DEFAULT_LANG)
                )
            else:
                return self._build_paginated_response(
                    entity_rows, page_qids, entity_type, requested_fields,
                    request_id, used_proxy, pagination['limit'], route, params,
                    sparql_latency_ms, cache_hit, status_code, start_time, request, filters.get('lang', config.DEFAULT_LANG)
                )
                
        except Exception as e:
            status_code = config.INTERNAL_ERROR_CODE
            error_type = ErrorType.INTERNAL_ERROR.value
            error_detail = str(e)
            total_latency_ms = (time.time() - start_time) * 1000
            metrics.record_request(route, status_code, total_latency_ms)
            log_request_info(
                route=route, params=params, proxy_used=used_proxy,
                sparql_latency_ms=sparql_latency_ms,
                entity_expansion_latency_ms=entity_expansion_latency_ms,
                cache_hit=cache_hit, status_code=status_code,
                error_type=error_type, error_detail=error_detail
            )
            logger.error(f"Error fetching {entity_type}: {e}", exc_info=True)
            raise InternalErrorException()
    
    def _build_query(
        self,
        entity_type: str,
        filters: Dict,
        pagination: Dict,
        offset_cursor: int,
        after_qid: Optional[str]
    ) -> str:
        """Build SPARQL query based on entity type."""
        if entity_type == EntityType.PUBLIC_FIGURE.value:
            return self.wiki_service.build_public_figures_query(
                birthday_from=filters.get('birthday_from'),
                birthday_to=filters.get('birthday_to'),
                nationality=filters.get('nationality'),
                profession=filters.get('profession'),
                lang=filters.get('lang', config.DEFAULT_LANG),
                limit=pagination['limit'],
                cursor=offset_cursor,
                after_qid=after_qid
            )
        else:
            return self.wiki_service.build_public_institutions_query(
                country=filters.get('country'),
                type=filters.get('type'),
                jurisdiction=filters.get('jurisdiction'),
                lang=filters.get('lang', config.DEFAULT_LANG),
                cursor=offset_cursor,
                limit=pagination['limit'],
                after_qid=after_qid
            )
    
    def _deduplicate_and_paginate(
        self,
        bindings: List[Dict],
        entity_type: str,
        limit: int
    ) -> tuple[Dict[str, Dict], List[str]]:
        """Deduplicate by QID and apply pagination."""
        entity_key = "person" if entity_type == EntityType.PUBLIC_FIGURE.value else "institution"
        entity_rows: Dict[str, Dict[str, Any]] = {}
        
        for item in bindings:
            qid = item.get(entity_key, {}).get("value", "").split("/")[-1]
            if qid and qid not in entity_rows:
                entity_rows[qid] = item
        
        # Trim to requested limit (query fetched limit+1)
        qids_sorted = sorted(entity_rows.keys())
        page_qids = qids_sorted[:limit]
        
        return entity_rows, page_qids
    
    def _build_streaming_response(
        self,
        entity_rows: Dict[str, Dict],
        page_qids: List[str],
        entity_type: str,
        requested_fields: Optional[set],
        request_id: str,
        used_proxy: str,
        limit: int,
        route: str,
        params: Dict,
        sparql_latency_ms: Optional[float],
        cache_hit: bool,
        status_code: int,
        request: Request,
        lang: str
    ) -> StreamingResponse:
        """Build NDJSON streaming response."""
        # Cap page size for stability
        if len(page_qids) > config.STREAMING_PAGE_SIZE:
            page_qids = page_qids[:config.STREAMING_PAGE_SIZE]
            next_cursor = page_qids[-1] if page_qids else None
            has_more = True
        else:
            has_more = len(entity_rows) > len(page_qids)
            next_cursor = page_qids[-1] if has_more and page_qids else None
        
        def stream_entities_ordered(qids_order):
            """Stream entities preserving order."""
            yielded_count = 0
            with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as pool:
                futures = {}
                for qid in qids_order:
                    item = entity_rows[qid]
                    # Capture variables in lambda closure
                    futures[qid] = pool.submit(
                        lambda q=item, qid_local=qid, et=entity_type, l=lang, req=request: 
                        self._normalize_entity(q, qid_local, et, l, req)
                    )
                for qid in qids_order:
                    try:
                        entity_data = futures[qid].result(timeout=config.ENTITY_EXPANSION_TIMEOUT)
                        # Apply field filtering if requested
                        if requested_fields:
                            entity_data = self.field_parser.filter_fields(
                                entity_data, requested_fields, entity_type
                            )
                        yield json.dumps(entity_data, ensure_ascii=False, default=str) + "\n"
                        yielded_count += 1
                    except Exception as ex:
                        yield json.dumps({
                            "error": ErrorType.ENTITY_EXPAND_ERROR.value,
                            "qid": qid,
                            "detail": str(ex)
                        }, ensure_ascii=False) + "\n"
            stats_payload = {
                "stats": {
                    "total_returned": yielded_count,
                    "has_more": has_more,
                    "next_cursor": next_cursor
                }
            }
            yield json.dumps(stats_payload, ensure_ascii=False, default=str) + "\n"
        
        response = self.response_builder.build_streaming_response(
            stream_entities_ordered(page_qids),
            request_id,
            used_proxy,
            next_cursor
        )
        
        # Log initial request info
        log_request_info(
            route=route, params=params, proxy_used=used_proxy,
            sparql_latency_ms=sparql_latency_ms, cache_hit=cache_hit,
            status_code=status_code
        )
        
        return response
    
    def _build_paginated_response(
        self,
        entity_rows: Dict[str, Dict],
        page_qids: List[str],
        entity_type: str,
        requested_fields: Optional[set],
        request_id: str,
        used_proxy: str,
        limit: int,
        route: str,
        params: Dict,
        sparql_latency_ms: Optional[float],
        cache_hit: bool,
        status_code: int,
        start_time: float,
        request: Request,
        lang: str
    ) -> Response:
        """Build paginated JSON response."""
        # Track entity expansion time
        entity_expansion_start = time.time()
        entities_list = []
        
        for qid in page_qids:
            item = entity_rows[qid]
            entity_data = self._normalize_entity(item, qid, entity_type, lang, request)
            # Apply field filtering if requested
            if requested_fields:
                entity_data = self.field_parser.filter_fields(
                    entity_data, requested_fields, entity_type
                )
            entities_list.append(entity_data)
        
        entity_expansion_latency_ms = (time.time() - entity_expansion_start) * 1000
        
        # Calculate pagination
        has_more = len(entity_rows) > len(page_qids)
        next_cursor = page_qids[-1] if has_more and page_qids else None
        
        # Calculate total latency
        total_latency_ms = (time.time() - start_time) * 1000
        
        # Record metrics
        metrics.record_request(route, status_code, total_latency_ms)
        metrics.record_cache(route, cache_hit)
        
        # Log request info
        log_request_info(
            route=route, params=params, proxy_used=used_proxy,
            sparql_latency_ms=sparql_latency_ms,
            entity_expansion_latency_ms=entity_expansion_latency_ms,
            cache_hit=cache_hit, status_code=status_code
        )
        
        return self.response_builder.build_paginated_response(
            entities_list, next_cursor, has_more, request_id, used_proxy
        )
    
    def _normalize_entity(
        self,
        item: Dict,
        qid: str,
        entity_type: str,
        lang: str,
        request: Request
    ) -> Dict:
        """Normalize entity data."""
        if entity_type == EntityType.PUBLIC_FIGURE.value:
            expanded = self.wiki_service.expand_entity_data(qid, lang=lang, request=request)
            return self.wiki_service.normalize_public_figure(item, expanded, lang=lang).model_dump()
        else:
            expanded = self.wiki_service.expand_entity_data_institution(qid, lang=lang, request=request)
            return self.wiki_service.normalize_public_institution(
                item, expanded, lang=lang, request=request
            ).model_dump()
    
    def _handle_query_error(
        self,
        stream: Optional[str],
        error_type: str,
        status_code: int,
        error_detail: str,
        request_id: str,
        used_proxy: str,
        sparql_latency_ms: Optional[float],
        cache_hit: bool,
        route: str,
        params: Dict,
        start_time: float
    ) -> Union[Response, StreamingResponse]:
        """Handle query execution errors."""
        total_latency_ms = (time.time() - start_time) * 1000
        metrics.record_request(route, status_code, total_latency_ms)
        
        if stream == StreamFormat.NDJSON.value:
            def error_ndjson():
                yield json.dumps({
                    "error": error_type,
                    "status": status_code,
                    "detail": error_detail
                }, ensure_ascii=False) + "\n"
            response = StreamingResponse(error_ndjson(), media_type="application/x-ndjson")
            response.headers["X-Request-ID"] = request_id
            log_request_info(
                route=route, params=params, proxy_used=used_proxy,
                sparql_latency_ms=sparql_latency_ms, cache_hit=cache_hit,
                status_code=status_code, error_type=error_type, error_detail=error_detail
            )
            return response
        
        # For non-streaming, log and re-raise
        log_request_info(
            route=route, params=params, proxy_used=used_proxy,
            sparql_latency_ms=sparql_latency_ms, cache_hit=cache_hit,
            status_code=status_code, error_type=error_type, error_detail=error_detail
        )
        raise HTTPException(status_code=status_code, detail=error_detail)

