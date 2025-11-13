import json
from typing import Optional, List, Dict, Any
from fastapi import Response
from fastapi.responses import StreamingResponse
from core.models import PaginatedResponse
from api.utils.etag_utils import ETagGenerator

class ResponseBuilder:
    """Builds HTTP responses with headers, ETags, etc."""
    
    def __init__(self):
        self.etag_generator = ETagGenerator()
    
    def build_entity_response(
        self,
        entity_dict: Dict[str, Any],
        request_id: str,
        used_proxy: str,
        cache_hit: bool
    ) -> Response:
        """Build entity lookup response."""
        response = Response(
            content=json.dumps(entity_dict, ensure_ascii=False, default=str),
            media_type="application/json"
        )
        
        # Add headers
        self._add_standard_headers(response, request_id, used_proxy, cache_hit)
        response.headers["ETag"] = self.etag_generator.generate(entity_dict)
        
        return response
    
    def build_paginated_response(
        self,
        data: List[Dict[str, Any]],
        next_cursor: Optional[str],
        has_more: bool,
        request_id: str,
        used_proxy: str
    ) -> Response:
        """Build paginated list response."""
        response_data = PaginatedResponse(
            data=data,
            next_cursor=next_cursor,
            has_more=has_more
        )
        
        response = Response(
            content=response_data.model_dump_json(),
            media_type="application/json"
        )
        
        self._add_standard_headers(response, request_id, used_proxy, False)
        response.headers["ETag"] = self.etag_generator.generate(
            response_data.model_dump()
        )
        
        return response
    
    def build_streaming_response(
        self,
        stream_generator,
        request_id: str,
        used_proxy: str,
        next_cursor: Optional[str]
    ) -> StreamingResponse:
        """Build NDJSON streaming response."""
        response = StreamingResponse(
            stream_generator,
            media_type="application/x-ndjson"
        )
        
        response.headers["X-Proxy-Used"] = used_proxy
        response.headers["X-Request-ID"] = request_id
        if next_cursor:
            response.headers["X-Next-Cursor"] = next_cursor
        
        return response
    
    def _add_standard_headers(
        self,
        response: Response,
        request_id: str,
        used_proxy: str,
        cache_hit: bool
    ):
        """Add standard response headers."""
        response.headers["X-Proxy-Used"] = used_proxy
        response.headers["X-Cache"] = "HIT" if cache_hit else "MISS"
        if request_id:
            response.headers["X-Request-ID"] = request_id

