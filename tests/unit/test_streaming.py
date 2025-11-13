import asyncio
import json
from typing import Optional, Dict, Any
from unittest.mock import Mock

from fastapi import Request

from api.constants import EntityType
from api.services.list_processor import ListProcessor
from core.models import PublicFigure


class StubWikiService:
    """Minimal wiki service stub for streaming tests."""

    def expand_entity_data(self, qid: str, lang: str, request: Optional[Request] = None):
        return {}

    def normalize_public_figure(
        self,
        item: Dict[str, Any],
        expanded_data: Optional[Dict[str, Any]],
        lang: str = "en",
    ) -> PublicFigure:
        return PublicFigure(
            id=item["person"]["value"].split("/")[-1],
            entity_kind="public_figure",
            name=item.get("personLabel", {}).get("value"),
            website=[],
            accounts=[],
            identifiers=[],
        )

    # Methods required by ListProcessor but unused in this test
    def expand_entity_data_institution(self, *args, **kwargs):  # pragma: no cover - not used
        raise NotImplementedError

    def normalize_public_institution(self, *args, **kwargs):  # pragma: no cover - not used
        raise NotImplementedError


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


async def _collect_chunks(streaming_response):
    chunks = []
    async for chunk in streaming_response.body_iterator:
        if isinstance(chunk, bytes):
            chunk = chunk.decode()
        chunks.append(chunk)
    return chunks


def test_streaming_appends_final_stats_line():
    wiki_service = StubWikiService()
    processor = ListProcessor(wiki_service)

    entity_rows = {
        "Q1": {
            "person": {"value": "http://www.wikidata.org/entity/Q1"},
            "personLabel": {"value": "Test Person"},
        }
    }
    page_qids = ["Q1"]
    request_id = "req-123"
    used_proxy = "direct"

    streaming_response = processor._build_streaming_response(
        entity_rows=entity_rows,
        page_qids=page_qids,
        entity_type=EntityType.PUBLIC_FIGURE.value,
        requested_fields=None,
        request_id=request_id,
        used_proxy=used_proxy,
        limit=1,
        route="/v1/public-figures",
        params={},
        sparql_latency_ms=None,
        cache_hit=False,
        status_code=200,
        request=Mock(spec=Request),
        lang="en",
    )

    chunks = _run_async(_collect_chunks(streaming_response))
    assert len(chunks) >= 1

    stats_line = json.loads(chunks[-1].strip())
    assert stats_line == {
        "stats": {
            "total_returned": 1,
            "has_more": False,
            "next_cursor": None,
        }
    }

