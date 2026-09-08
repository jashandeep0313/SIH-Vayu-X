"""Forecast endpoints — proxies the model service and persists issued forecasts.

Contract: docs/api-contract.md §1  ·  Payloads: shared/schemas/forecast.schema.json
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.schemas.cyclone import Forecast
from app.services import demo_data
from app.services.model_client import ModelServiceClient

router = APIRouter()

_NOT_IMPLEMENTED = "Not implemented — Phase 4. Set DEMO_MODE=true for synthetic data."


@router.get("/{cyclone_id}", response_model=Forecast)
async def get_latest_prediction(cyclone_id: UUID) -> Forecast:
    """Most recently issued forecast for this event."""
    if not settings.DEMO_MODE:
        # TODO(backend): SELECT latest forecast by issued_at
        raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)

    event = demo_data.event_by_id(cyclone_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"No cyclone event with id {cyclone_id}")
    return Forecast(**event["latest_forecast"])


@router.get("/{cyclone_id}/history")
async def get_prediction_history(cyclone_id: UUID) -> dict:
    """Every forecast issued for this event.

    Forecasts are immutable, so this history is what makes retrospective
    verification against IMD best track possible.
    """
    if not settings.DEMO_MODE:
        # TODO(backend): return all forecasts ordered by issued_at
        raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)

    event = demo_data.event_by_id(cyclone_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"No cyclone event with id {cyclone_id}")
    return {"count": 1, "items": [event["latest_forecast"]]}


@router.post("/run", status_code=202)
async def run_prediction(cyclone_id: UUID | None = None, frame_id: str | None = None) -> dict:
    """Trigger inference on demand (analyst+ role)."""
    if cyclone_id is None and frame_id is None:
        raise HTTPException(status_code=400, detail="Provide either cyclone_id or frame_id")

    client = ModelServiceClient()
    # TODO(backend): resolve frame URIs, call client.infer(), persist, broadcast over WS
    _ = client
    raise HTTPException(status_code=501, detail="Not implemented — Phase 4")
