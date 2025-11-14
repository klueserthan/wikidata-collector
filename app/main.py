import logging

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from api.routes import meta, router
from infrastructure.observability import JSONFormatter, RequestIDMiddleware, metrics as obs_metrics

# Configure structured JSON logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.handlers.clear()
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)

app = FastAPI(
    title="Wikidata Fetch Microservice",
    description="A microservice that fetches public figures and institutions from Wikidata via SPARQL with proxy support",
    version="1.0.0",
)

# Add request ID middleware
app.add_middleware(RequestIDMiddleware)

# Initialize route services (meta needs app instance)
meta.init_app(app)

# Include routers
app.include_router(router)


@app.on_event("shutdown")
async def shutdown_event():
    """Save metrics on server shutdown."""
    obs_metrics.save()
    logger.info("Metrics saved to disk on shutdown")

