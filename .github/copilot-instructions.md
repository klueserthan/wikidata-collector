# Copilot Instructions: Wikidata Fetch Microservice

Concise guidance for AI agents working in this repo. Focus on SPARQL keyset pagination, streaming NDJSON, proxy rotation, and observability.

## Architecture & Flow
- `api/`: Routes + orchestration. `routes/*` parse/validate; `services/list_processor.py` builds queries, executes, normalizes, and returns responses; `services/response_builder.py` sets headers/ETags; `utils/field_utils.py` parses sparse fields.
- `core/`: `wiki_service.py` runs SPARQL with caching/retries/proxies and entity expansion; `models.py` Pydantic schemas; `normalizers/*` turn raw results into `PublicFigure`/`PublicInstitution` models.
- `sparql/builders/`: Deterministic query builders for figures/institutions with keyset (QID) and OFFSET fallback.
- `infrastructure/`: `cache.py` (TTL LRU by MD5 query), `proxy_service.py` (round-robin with cooldown), `observability.py` (JSON logs, metrics, request IDs).
- `app/`: `main.py` FastAPI app, `server.py` runner.

## Patterns That Matter
- Pagination: Prefer keyset with QID cursors (`cursor=Q12345` → `after_qid`) over OFFSET (numeric cursor). `list_processor._deduplicate_and_paginate()` sorts QIDs and trims to `limit`.
- Filters: Prefer QIDs for speed (e.g., `nationality=Q30`, `type=Q327333`). Label filters imply extra patterns in SPARQL.
- Sparse fieldsets: `FieldParser` supports dot notation (e.g., `website.url`, `accounts.handle`) and always includes `id` and `entity_kind`. For lists, keep metadata `source` and `retrieved_at`.
- Entity expansions: People → affiliations (P102/P463), awards, socials, identifiers; Institutions → types/country/jurisdiction/website/socials. Expansion results cached via `entity_expansion_cache`.

## Streaming NDJSON
- When `stream=ndjson`, `list_processor._build_streaming_response()` yields one JSON line per entity, capped by `config.STREAMING_PAGE_SIZE` (default 50), then emits a final `{"stats": {total_returned, has_more, next_cursor}}` line.
- Concurrency: `ThreadPoolExecutor(max_workers=config.MAX_WORKERS)` expands entities in parallel; per-item timeout `config.ENTITY_EXPANSION_TIMEOUT`.
- Headers: `X-Proxy-Used`, `X-Next-Cursor` (if `has_more`), `X-Request-ID`.

## Caching & Proxies
- Caching: `infrastructure/cache.TTLCache` (default 5-min TTL, size-limited). Keys are MD5 of the full SPARQL query. `WikiService.execute_sparql_query()` returns `used_proxy="cached"` on hits.
- Proxy rotation: `ProxyManager` supports per-request override via `X-Proxy-List`, round-robin selection, 5-min cooldown on failure, and 3 retry attempts with backoff and 429 Retry-After handling.

## Observability
- Context vars in `infrastructure/observability.py`: `request_id_ctx`, `sparql_latency_ctx`, `proxy_used_ctx` etc. Middleware adds `X-Request-ID` to responses.
- Metrics: `metrics` collector provides `/v1/metrics` (JSON) and `/metrics` (Prometheus). Use `log_request_info()` from `list_processor` for structured logs.

## Developer Workflow
- Env: set `CONTACT_EMAIL` (User-Agent requirement); optional `PROXY_LIST`.
- Run: `python -m app.server` or `uvicorn app.main:app --reload --port 8000`.
- Docker: `docker build -t wikidata-fetch:latest .` then `docker run -p 8000:8000 -e CONTACT_EMAIL=you@example.com wikidata-fetch:latest`.

## Tests
- Structure: unit (`tests/unit/*`), integration mocked (`tests/integration/test_integration.py`), live optional (`tests/integration/test_integration_live.py`), plus streaming (`tests/unit/test_streaming.py`).
- Commands: `pytest`; with coverage `pytest --cov=. --cov-report=html`.
- Conventions: always mock `requests.get` for integration; fixtures clear caches (`clear_caches`), provide `wiki_service`, and mock `Request`.

## Key Files
- Routes: `api/routes/{figures.py,institutions.py,entities.py,meta.py,metrics.py}`
- Orchestrator: `api/services/list_processor.py`
- SPARQL builders: `sparql/builders/{figures_query_builder.py,institutions_query_builder.py}`
- Service: `core/wiki_service.py`
- Normalizers: `core/normalizers/*`
- Infra: `infrastructure/{cache.py,proxy_service.py,observability.py}`
- Models: `core/models.py`

If anything here is unclear or incomplete, tell me what you’re building and I’ll refine these instructions for your workflow.
