from fastapi import APIRouter

router = APIRouter()

# Import route handlers
from . import entities, figures, institutions, metrics, meta

# Include routers
router.include_router(entities.router)
router.include_router(figures.router)
router.include_router(institutions.router)
router.include_router(metrics.router)
router.include_router(meta.router)

