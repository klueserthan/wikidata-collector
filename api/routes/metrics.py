from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from infrastructure.observability import get_prometheus_metrics, metrics

router = APIRouter()

@router.get("/v1/metrics")
async def get_metrics():
    """Get current metrics in JSON format."""
    return metrics.get_metrics()

@router.get("/metrics")
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    return PlainTextResponse(get_prometheus_metrics(), media_type="text/plain")

