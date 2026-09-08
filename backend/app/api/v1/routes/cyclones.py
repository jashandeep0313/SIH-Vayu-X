"""Cyclone event endpoints.

Contract: docs/api-contract.md §1  ·  Payloads: shared/schemas/cyclone_event.schema.json

While DEMO_MODE is on these serve synthetic events from app.services.demo_data.
Turning it off restores the 501s that mark the real Phase 4 work.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.schemas.cyclone import CycloneEvent, CycloneListResponse
from app.services import demo_data

router = APIRouter()

_NOT_IMPLEMENTED = "Not implemented — Phase 4. Set DEMO_MODE=true for synthetic data."


@router.get("", response_model=CycloneListResponse)
async def list_cyclones(
    status: str | None = Query(None, description="active | weakened | dissipated | landfall"),
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = Query(None),
    bbox: str | None = Query(None, description="lat_min,lon_min,lat_max,lon_max"),
    min_category: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> CycloneListResponse:
    """List cyclone events with filtering and pagination."""
    if not settings.DEMO_MODE:
        # TODO(backend): query PostGIS with the supplied filters
        raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)

    items = demo_data.summaries()
    if status:
        items = [i for i in items if i["status"] == status]
    return CycloneListResponse(
        count=len(items), limit=limit, offset=offset, items=items[offset : offset + limit]
    )


@router.get("/active", response_model=CycloneListResponse)
async def list_active_cyclones() -> CycloneListResponse:
    """Currently active systems. This is the dashboard's default view."""
    if not settings.DEMO_MODE:
        # TODO(backend): SELECT ... WHERE status = 'active'
        raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)

    items = demo_data.summaries()
    return CycloneListResponse(count=len(items), items=items)


@router.get("/{cyclone_id}", response_model=CycloneEvent)
async def get_cyclone(cyclone_id: UUID) -> CycloneEvent:
    """Full event: metadata, observation history, latest forecast."""
    if not settings.DEMO_MODE:
        # TODO(backend): fetch event + observations + latest forecast
        raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)

    event = demo_data.event_by_id(cyclone_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"No cyclone event with id {cyclone_id}")
    return CycloneEvent(**event)


@router.get("/{cyclone_id}/track")
async def get_track(cyclone_id: UUID) -> dict:
    """Observed track as a GeoJSON LineString, ready to drop onto the map."""
    if not settings.DEMO_MODE:
        # TODO(backend): build LineString from ordered observations
        raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)

    event = demo_data.event_by_id(cyclone_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"No cyclone event with id {cyclone_id}")
    return {
        "type": "Feature",
        "properties": {"cyclone_id": str(cyclone_id), "name": event["name"]},
        "geometry": {
            "type": "LineString",
            "coordinates": [[o["lon"], o["lat"]] for o in event["observations"]],
        },
    }


@router.get("/{cyclone_id}/observations")
async def get_observations(
    cyclone_id: UUID,
    limit: int = Query(200, ge=1, le=1000),
) -> dict:
    """Time-series of observations for intensity charts."""
    if not settings.DEMO_MODE:
        # TODO(backend): query TimescaleDB hypertable
        raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)

    event = demo_data.event_by_id(cyclone_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"No cyclone event with id {cyclone_id}")
    items = event["observations"][-limit:]
    return {"count": len(items), "items": items}
