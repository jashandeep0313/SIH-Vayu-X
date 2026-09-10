"""Satellite image upload → cyclone classification.

Real by default: the upload is forwarded to the model service, which runs
`intensity_from_image_v2` (trained on ~70k labelled IR frames) and returns a
genuine estimate, prediction interval and category probabilities.

`_mock_result` is now only a fallback for when that service is unreachable —
the UI stays usable during a restart instead of showing an error page. Anything
it produces carries `"mock": true` and a `warning`, and the UI renders a MOCK
RESULT badge, so a generated number can never be mistaken for a predicted one.
"""

import hashlib
import random

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import settings
from app.services.wind_field import wind_field

router = APIRouter()

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp", "image/tiff"}

PATTERNS = ["eye", "banding_eye", "CDO", "curved_band", "shear", "central_cold_cover"]
CATEGORIES = ["LPA", "D", "DD", "CS", "SCS", "VSCS", "ESCS", "SuCS"]

CATEGORY_WIND = {
    "LPA": (10, 16),
    "D": (17, 27),
    "DD": (28, 33),
    "CS": (34, 47),
    "SCS": (48, 63),
    "VSCS": (64, 89),
    "ESCS": (90, 119),
    "SuCS": (120, 150),
}


def _pressure_for(wind_kt: float) -> float:
    return round(max(870.0, 1010 - (wind_kt / 6.7) ** (1 / 0.644)), 1)


def _mock_result(digest: str, filename: str, size: int) -> dict:
    """Deterministic pseudo-random result.

    Seeded from the file's own hash so the same image always returns the same
    answer — random output would make it impossible to tell a UI bug from a
    changed prediction while testing.
    """
    rng = random.Random(digest)

    is_cyclone = rng.random() > 0.2
    if not is_cyclone:
        return {
            "mock": True,
            "warning": "MOCK RESULT — no model is trained yet. Numbers are generated.",
            "filename": filename,
            "size_bytes": size,
            "sha256": digest[:16],
            "cyclone_detected": False,
            "detection_probability": round(rng.uniform(2, 24), 1),
            "message": "No organised cyclonic system identified in this frame.",
            "model_versions": {"identification": "mock-v0", "classification": "mock-v0"},
        }

    category = rng.choices(CATEGORIES, weights=[4, 10, 10, 18, 18, 20, 14, 6], k=1)[0]
    lo, hi = CATEGORY_WIND[category]
    wind = round(rng.uniform(lo, hi), 1)
    pressure = _pressure_for(wind)
    rmw = round(max(15.0, 70 - wind * 0.35), 1)

    # Probabilities that actually sum to 100
    dominant = (
        "eye"
        if wind >= 85
        else "banding_eye"
        if wind >= 64
        else "CDO"
        if wind >= 45
        else "curved_band"
        if wind >= 30
        else "shear"
    )
    raw = {p: rng.uniform(0.5, 8.0) for p in PATTERNS}
    raw[dominant] = rng.uniform(45, 80)
    total = sum(raw.values())
    probabilities = {p: round(v / total * 100, 1) for p, v in raw.items()}
    # absorb rounding drift into the dominant class so the total reads 100.0
    probabilities[dominant] = round(
        probabilities[dominant] + (100 - sum(probabilities.values())), 1
    )

    return {
        "mock": True,
        "warning": "MOCK RESULT — no model is trained yet. Numbers are generated.",
        "filename": filename,
        "size_bytes": size,
        "sha256": digest[:16],
        "cyclone_detected": True,
        "detection_probability": round(rng.uniform(72, 99), 1),
        "classification": {
            "intensity_category": category,
            "pattern_type": dominant,
            "est_wind_kt": wind,
            "est_wind_kmph": round(wind * 1.852, 1),
            "est_pressure_hpa": pressure,
            "dvorak_t_number": round(min(8.0, 1.0 + wind / 21.0), 1),
            "radius_max_wind_km": rmw,
            "pattern_probabilities": probabilities,
        },
        "wind_field": wind_field(wind, pressure, rmw),
        "confidence": round(rng.uniform(0.61, 0.96), 2),
        "out_of_distribution_score": round(rng.uniform(0.02, 0.30), 2),
        "explanation_uri": None,
        "model_versions": {"identification": "mock-v0", "classification": "mock-v0"},
    }


SIREN_CATEGORIES = {"SCS", "VSCS", "ESCS", "SuCS"}


async def _maybe_sound_siren(result: dict) -> dict:
    """Fire the physical tower when a classification clears the bar.

    This is the one alert path that runs without a human. SMS does not, because
    it costs credits and messages real people; a siren costs nothing per
    sounding and a tower that waits for an operator is no use at 03:00 when the
    control room link is down.

    Four things must all hold, and every refusal says which one failed:
      * the automatic path is switched on
      * the image was actually scored (a refused/out-of-distribution frame has
        no classification, and must never sound anything)
      * the category is at or above SCS
      * the model is confident enough

    Never raises and never blocks the upload. If the tower is unreachable the
    analysis still returns — losing the siren must not also lose the estimate.
    """
    if not settings.SIREN_AUTO_ON_UPLOAD:
        return {"attempted": False, "reason": "automatic siren disabled (SIREN_AUTO_ON_UPLOAD)"}

    classification = result.get("classification")
    if not classification:
        return {"attempted": False, "reason": "image was not scored — nothing to alert on"}

    category = classification.get("intensity_category")
    if category not in SIREN_CATEGORIES:
        return {"attempted": False, "category": category, "reason": f"{category} is below SCS"}

    confidence = result.get("confidence_pct")
    if confidence is None or confidence < settings.SIREN_MIN_CONFIDENCE_PCT:
        return {
            "attempted": False,
            "category": category,
            "confidence_pct": confidence,
            "reason": (
                f"confidence {confidence}% is below the "
                f"{settings.SIREN_MIN_CONFIDENCE_PCT}% required to sound automatically — "
                "an operator can still trigger it manually"
            ),
        }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{settings.ALERT_SERVICE_URL}/alert/siren",
                json={
                    "intensity_category": category,
                    "seconds": settings.SIREN_AUTO_SECONDS,
                    "auto": True,
                },
            )
        if r.status_code != 200:
            return {"attempted": True, "sounded": False, "reason": r.text[:200]}
        return {"attempted": True, **r.json()}
    except httpx.HTTPError as exc:
        return {"attempted": True, "sounded": False, "reason": f"tower unreachable: {exc}"}


@router.post("/upload")
async def analyse_upload(file: UploadFile = File(...)) -> dict:
    """Upload a satellite image and get a (currently mocked) classification."""
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported type {file.content_type}. Use PNG, JPEG, WebP or TIFF.",
        )

    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(payload) // 1024} KB). Limit is 15 MB.",
        )

    digest = hashlib.sha256(payload).hexdigest()

    # Real model first; the mock exists only so the UI still works when the
    # model service is down or the checkpoint has not been trained yet.
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.MODEL_SERVICE_URL}/classify/image",
                files={"file": (file.filename or "upload", payload, file.content_type)},
            )
        if response.status_code == 200:
            result = response.json()
            result.update(
                {
                    "mock": False,
                    "filename": file.filename or "upload",
                    "size_bytes": len(payload),
                    "sha256": digest[:16],
                }
            )
            result["siren"] = await _maybe_sound_siren(result)
            return result
        detail = response.text[:200]
    except httpx.HTTPError as exc:
        detail = str(exc)

    fallback = _mock_result(digest, file.filename or "upload", len(payload))
    fallback["warning"] = (
        "MOCK RESULT — the trained model was unreachable, so these numbers are "
        f"generated. ({detail})"
    )
    return fallback
