"""Satellite frame metadata, map overlays, and explainability images."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response

from app.services.ir_imagery import enhanced_ir_tile
from app.services.ir_imagery import legend as ir_legend

router = APIRouter()


@router.get("/frames")
async def list_frames(
    source: str | None = Query(None, description="insat3d | insat3dr | scatsat | imerg"),
    channel: str | None = Query(None, description="TIR1 | TIR2 | WV | VIS | MIR"),
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    """Available satellite frames — powers the dashboard's time slider."""
    # TODO(backend): query frame metadata table
    raise HTTPException(status_code=501, detail="Not implemented — Phase 4")


@router.get("/frames/{frame_id}")
async def get_frame(frame_id: str) -> dict:
    """Frame metadata plus a signed MinIO/S3 tile URL."""
    # TODO(backend): fetch metadata, generate presigned URL
    raise HTTPException(status_code=501, detail="Not implemented — Phase 4")


@router.get("/overlay/{cyclone_id}")
async def get_overlay(cyclone_id: UUID) -> dict:
    """Latest storm-centred image overlay for the map."""
    # TODO(backend): return presigned URL + geographic bounds for map placement
    raise HTTPException(status_code=501, detail="Not implemented — Phase 4")


@router.get("/explain/{observation_id}")
async def get_explanation(observation_id: UUID) -> dict:
    """Grad-CAM / attention overlay showing which cloud features drove the estimate.

    Explainability is not optional here — meteorologists will not act on a black box.
    """
    # TODO(backend): return explanation_uri recorded with the observation
    raise HTTPException(status_code=501, detail="Not implemented — Phase 4")


# ------------------------------------------------- colour-enhanced IR tiles
@router.get("/ir/{z}/{x}/{y}.png")
async def enhanced_ir(z: int, x: int, y: int, time: str | None = Query(None)) -> Response:
    """Meteosat IODC infrared, colour-enhanced, as an XYZ tile.

    `time` accepts an ISO timestamp so the map can follow a storm through its
    lifetime; it is snapped to the nearest published 15-minute slot.
    """
    png = await enhanced_ir_tile(z, x, y, time)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=900"},
    )


@router.get("/ir/legend")
async def enhanced_ir_legend() -> dict:
    return {
        "layer": "msg_iodc:ir108",
        "source": "EUMETSAT EUMETView · Meteosat Indian Ocean Data Coverage",
        "enhancement": "cloud-top temperature curve; warm pixels transparent",
        "stops": ir_legend(),
    }
