"""Forecast endpoints — proxies the model service and persists issued forecasts.

Contract: docs/api-contract.md §1  ·  Payloads: shared/schemas/forecast.schema.json
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.schemas.cyclone import Forecast
from app.services import event_source, real_data
from app.services.model_client import ModelServiceClient

router = APIRouter()

_NOT_IMPLEMENTED = "Not implemented — Phase 4. Set DEMO_MODE=true for synthetic data."


async def _forecast_for(event: dict) -> dict:
    """Get a forecast for an event from the trained model service.

    Falls back to whatever forecast the event already carries if the model
    service is unreachable — a stale forecast is better than a blank dashboard
    during an event, and the payload records which path was taken.
    """
    observations = event.get("observations") or []
    if len(observations) >= 2:
        try:
            forecast = await ModelServiceClient().predict_track(observations)
            forecast["cyclone_id"] = event["id"]
            forecast["source"] = "model"

            # For replayed storms the real outcome is known, so score the
            # forecast against it rather than only asserting accuracy.
            if event.get("metadata", {}).get("verification"):
                forecast["verification"] = real_data.verification_for(event, forecast)
            return forecast
        except Exception as exc:  # noqa: BLE001 - degrade, don't fail the request
            fallback = event.get("latest_forecast")
            if fallback:
                return {**fallback, "source": "cached", "model_error": str(exc)}
            raise HTTPException(
                status_code=503, detail=f"Model service unavailable: {exc}"
            ) from exc

    fallback = event.get("latest_forecast")
    if fallback:
        return fallback
    raise HTTPException(status_code=422, detail="Not enough observations to forecast")


@router.get("/{cyclone_id}", response_model=Forecast)
async def get_latest_prediction(cyclone_id: UUID) -> Forecast:
    """Most recently issued forecast for this event."""
    if not settings.DEMO_MODE:
        # TODO(backend): SELECT latest forecast by issued_at
        raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)

    event = event_source.event_by_id(cyclone_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"No cyclone event with id {cyclone_id}")

    forecast = await _forecast_for(event)
    return Forecast(**forecast)


@router.get("/{cyclone_id}/history")
async def get_prediction_history(cyclone_id: UUID) -> dict:
    """Every forecast issued for this event.

    Forecasts are immutable, so this history is what makes retrospective
    verification against IMD best track possible.
    """
    if not settings.DEMO_MODE:
        # TODO(backend): return all forecasts ordered by issued_at
        raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)

    event = event_source.event_by_id(cyclone_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"No cyclone event with id {cyclone_id}")
    forecast = await _forecast_for(event)
    return {"count": 1, "items": [forecast]}


@router.post("/run", status_code=202)
async def run_prediction(cyclone_id: UUID | None = None, frame_id: str | None = None) -> dict:
    """Trigger inference on demand (analyst+ role)."""
    if cyclone_id is None and frame_id is None:
        raise HTTPException(status_code=400, detail="Provide either cyclone_id or frame_id")

    client = ModelServiceClient()
    # TODO(backend): resolve frame URIs, call client.infer(), persist, broadcast over WS
    _ = client
    raise HTTPException(status_code=501, detail="Not implemented — Phase 4")
