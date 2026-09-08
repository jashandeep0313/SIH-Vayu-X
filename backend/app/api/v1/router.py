"""Aggregates all v1 route modules."""

from fastapi import APIRouter

from app.api.v1.routes import (
    alerts,
    auth,
    cyclones,
    health,
    imagery,
    inference,
    predictions,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["meta"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(cyclones.router, prefix="/cyclones", tags=["cyclones"])
api_router.include_router(predictions.router, prefix="/predictions", tags=["predictions"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(imagery.router, prefix="/imagery", tags=["imagery"])
api_router.include_router(inference.router, prefix="/inference", tags=["inference"])
