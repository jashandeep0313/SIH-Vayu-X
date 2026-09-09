"""Liveness and version endpoints, including downstream service status."""

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.services import demo_data, event_source
from app.services.windy_client import WindyClient

router = APIRouter()


async def _probe(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{url}/health")
        return "up" if response.status_code == 200 else "degraded"
    except httpx.HTTPError:
        return "down"


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "vayux-backend",
        "environment": settings.ENV,
        "downstream": {
            "model_service": await _probe(settings.MODEL_SERVICE_URL),
            "alert_service": await _probe(settings.ALERT_SERVICE_URL),
        },
    }


@router.get("/version")
async def version() -> dict:
    return {
        "api_version": settings.VERSION,
        "problem_statement": "26070",
        "team": "Vayu-X (152)",
        "demo_mode": settings.DEMO_MODE,
        "data_source": event_source.describe(),
    }


@router.get("/environment/point")
async def environment_point(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    hours: int = Query(72, ge=6, le=240),
) -> dict:
    """Numerical-model forecast at a point, via Windy.

    Independent of our satellite-derived estimate on purpose: ours comes from
    imagery, this comes from GFS, and where they disagree that is worth seeing.
    """
    client = WindyClient()
    if not client.configured:
        raise HTTPException(
            status_code=503,
            detail="WINDY_POINT_API_KEY not configured",
        )
    try:
        return await client.point_forecast(lat, lon, hours=hours)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Windy request failed: {exc}") from exc


@router.get("/pipeline/status")
async def pipeline_status() -> dict:
    """Ingestion heartbeat and per-source freshness.

    Data staleness is the signal that matters most operationally: a stalled
    pipeline is indistinguishable from calm weather unless it is surfaced.
    """
    if not settings.DEMO_MODE:
        # TODO(backend): read last-ingested timestamps from the frames table
        raise HTTPException(status_code=501, detail="Not implemented — Phase 4")
    return demo_data.pipeline_status()
