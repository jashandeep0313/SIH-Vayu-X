"""Alert endpoints — read alert state, acknowledge, and issue manual alerts.

Dispatch itself lives in the separate alert-system service so that warnings keep
flowing even if this gateway is down.

Contract: docs/api-contract.md §1  ·  Payloads: shared/schemas/alert.schema.json
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.services import demo_data

router = APIRouter()

_NOT_IMPLEMENTED = "Not implemented — Phase 5. Set DEMO_MODE=true for synthetic data."


@router.get("")
async def list_alerts(
    severity: str | None = Query(None, description="GREEN | YELLOW | ORANGE | RED"),
    status: str | None = Query(None),
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = Query(None),
    region: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    """List alerts for the alert console."""
    if not settings.DEMO_MODE:
        # TODO(backend): query alerts table with filters
        raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)

    items = demo_data.alerts()
    if severity:
        items = [a for a in items if a["severity"] == severity]
    if status:
        items = [a for a in items if a["status"] == status]
    return {
        "count": len(items),
        "limit": limit,
        "offset": offset,
        "items": items[offset : offset + limit],
    }


@router.get("/{alert_id}")
async def get_alert(alert_id: UUID) -> dict:
    """Alert detail including per-channel dispatch status."""
    if not settings.DEMO_MODE:
        # TODO(backend): join alerts + dispatches
        raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)

    alert = next((a for a in demo_data.alerts() if a["id"] == str(alert_id)), None)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"No alert with id {alert_id}")
    return alert


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: UUID) -> dict:
    """Responder confirms receipt — closes the loop on the warning chain."""
    # TODO(backend): record acknowledgement, broadcast alert.acknowledged over WS
    raise HTTPException(status_code=501, detail="Not implemented — Phase 5")


@router.post("/manual", status_code=201)
async def create_manual_alert() -> dict:
    """Analyst-issued alert, bypassing the rule engine (analyst+ role).

    Needed when a human sees something the model does not, and for the
    pending_review queue where confidence was below the auto-dispatch threshold.
    """
    # TODO(backend): validate payload, forward to alert-system /dispatch
    raise HTTPException(status_code=501, detail="Not implemented — Phase 5")


@router.post("/{alert_id}/cancel")
async def cancel_alert(alert_id: UUID) -> dict:
    """Withdraw an alert and send an all-clear to the same recipients (admin role)."""
    # TODO(backend): mark cancelled, trigger all-clear dispatch
    raise HTTPException(status_code=501, detail="Not implemented — Phase 5")
