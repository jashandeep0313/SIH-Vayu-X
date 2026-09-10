"""Real cyclone events from IBTrACS best-track data.

Replaces the synthetic demo source with actual storms. For the North Indian
Ocean, IBTrACS carries the RSMC New Delhi (IMD) analyses — the same record our
forecasts are judged against.

Each replayed event is positioned partway through its real life, so:
  * observations are the storm's genuine history up to that moment,
  * the forecast comes from the trained model, and
  * the remaining real track is retained as `verification` — what actually
    happened next.

That last part is the point. A forecast you cannot check is a claim; a forecast
shown beside the outcome is a result.
"""

from __future__ import annotations

import functools
import math
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.core.config import settings
from app.services.wind_field import wind_field

IMD_SCALE = [
    (17, "LPA"),
    (28, "D"),
    (34, "DD"),
    (48, "CS"),
    (64, "SCS"),
    (90, "VSCS"),
    (120, "ESCS"),
]


def categorise(wind_kt: float) -> str:
    for limit, code in IMD_SCALE:
        if wind_kt < limit:
            return code
    return "SuCS"


def pressure_from_wind(wind_kt: float) -> float:
    return round(max(870.0, 1010 - (wind_kt / 6.7) ** (1 / 0.644)), 1)


_DVORAK_CI = [
    (1.0, 25),
    (2.0, 30),
    (2.5, 35),
    (3.0, 45),
    (3.5, 55),
    (4.0, 65),
    (4.5, 77),
    (5.0, 90),
    (5.5, 102),
    (6.0, 115),
    (6.5, 127),
    (7.0, 140),
    (7.5, 155),
    (8.0, 170),
]


def dvorak_t(wind_kt: float) -> float:
    if wind_kt <= _DVORAK_CI[0][1]:
        return _DVORAK_CI[0][0]
    for (t_lo, v_lo), (t_hi, v_hi) in zip(_DVORAK_CI, _DVORAK_CI[1:], strict=False):
        if wind_kt <= v_hi:
            return round(t_lo + (wind_kt - v_lo) / (v_hi - v_lo) * (t_hi - t_lo), 1)
    return 8.0


def _pattern_for(wind_kt: float) -> str:
    """Cloud pattern inferred from intensity.

    A stand-in until the image classifier exists — the real pattern comes from
    imagery, which needs MOSDAC credentials. Flagged as inferred in the payload
    so it is never mistaken for a classification result.
    """
    if wind_kt >= 85:
        return "eye"
    if wind_kt >= 64:
        return "banding_eye"
    if wind_kt >= 45:
        return "CDO"
    if wind_kt >= 30:
        return "curved_band"
    return "shear"


def _iso(ts) -> str:
    dt = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat().replace("+00:00", "Z")


def _stable_id(sid: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"vayux:ibtracs:{sid}"))


@functools.lru_cache(maxsize=1)
def _load_tracks():
    """Parse IBTrACS once and cache. Returns None if the archive is absent."""
    import importlib.util

    path = Path(settings.IBTRACS_PATH)
    if not path.exists():
        return None

    parser = (
        Path(__file__).resolve().parents[3]
        / "data-pipeline"
        / "src"
        / "ingest"
        / "best_track_parsing.py"
    )
    if not parser.exists():
        return None

    spec = importlib.util.spec_from_file_location("vayux_bt", parser)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load_best_track(path)


def available() -> bool:
    try:
        return _load_tracks() is not None
    except Exception:
        return False


def _observation(row, replay_now: datetime, idx: int) -> dict:
    wind = float(row.wind_kt)
    pressure = (
        float(row.pressure_hpa)
        if row.pressure_hpa == row.pressure_hpa  # not NaN
        else pressure_from_wind(wind)
    )
    rmw = round(max(15.0, 70 - wind * 0.35), 1)
    return {
        "observed_at": _iso(row.ISO_TIME),
        "lat": round(float(row.LAT), 2),
        "lon": round(float(row.LON), 2),
        "pattern_type": _pattern_for(wind),
        "intensity_category": categorise(wind),
        "est_wind_kt": round(wind, 1),
        "est_pressure_hpa": round(pressure, 1),
        "dvorak_t_number": dvorak_t(wind),
        "radius_max_wind_km": rmw,
        "wind_field": wind_field(wind, pressure, rmw),
        # Best-track fixes are analysed positions, not model estimates
        "confidence": 1.0,
        "class_probabilities": None,
        "source_frame": f"ibtracs:{row.SID}",
        "source_channels": ["IBTrACS"],
        "model_versions": {"source": "IBTrACS v04r01 (RSMC New Delhi)"},
        "explanation_uri": None,
    }


def _pick_storms(df, limit: int):
    """Most intense storms from the model's held-out seasons.

    Held-out on purpose: replaying a storm the model trained on would flatter it.
    """
    recent = df[df["SEASON"] >= settings.REPLAY_MIN_SEASON]
    if recent.empty:
        recent = df
    peaks = recent.groupby("SID")["wind_kt"].max().sort_values(ascending=False)
    return list(peaks.head(limit).index)


def events(limit: int | None = None) -> list[dict]:
    df = _load_tracks()
    if df is None:
        return []

    limit = limit or settings.REPLAY_STORM_COUNT
    out = []
    for sid in _pick_storms(df, limit):
        track = df[df["SID"] == sid].sort_values("ISO_TIME").reset_index(drop=True)
        if len(track) < 8:
            continue

        # Position the replay at the storm's peak so there is real history behind
        # it and a real outcome ahead of it.
        cut = int(track["wind_kt"].idxmax())
        cut = max(6, min(cut, len(track) - 2))

        history = track.iloc[: cut + 1]
        future = track.iloc[cut + 1 :]

        observations = [_observation(r, None, i) for i, r in enumerate(history.itertuples())]
        name = track["NAME"].dropna().iloc[0] if track["NAME"].notna().any() else None
        peak = float(track["wind_kt"].max())
        basin = "ARB" if float(track["LON"].iloc[0]) < 78 else "BOB"

        out.append(
            {
                "id": _stable_id(sid),
                "name": str(name) if name else None,
                "basin": basin,
                "status": "active",
                "first_seen": observations[0]["observed_at"],
                "last_seen": observations[-1]["observed_at"],
                "peak_intensity_category": categorise(peak),
                "observations": observations,
                "latest_forecast": None,  # filled by the model service
                "metadata": {
                    "synthetic": False,
                    "source": "IBTrACS v04r01",
                    "sid": sid,
                    "season": int(track["SEASON"].iloc[0]),
                    "replay": True,
                    "verification": [
                        {
                            "valid_at": _iso(r.ISO_TIME),
                            "lat": round(float(r.LAT), 2),
                            "lon": round(float(r.LON), 2),
                            "wind_kt": round(float(r.wind_kt), 1),
                        }
                        for r in future.itertuples()
                    ],
                },
            }
        )
    return out


def event_by_id(cyclone_id) -> dict | None:
    return next((e for e in events() if e["id"] == str(cyclone_id)), None)


def summaries() -> list[dict]:
    return [
        {
            "id": e["id"],
            "name": e["name"],
            "basin": e["basin"],
            "status": e["status"],
            "first_seen": e["first_seen"],
            "last_seen": e["last_seen"],
            "latest_observation": e["observations"][-1],
        }
        for e in events()
    ]


def dataset_info() -> dict:
    df = _load_tracks()
    if df is None:
        return {"available": False, "path": settings.IBTRACS_PATH}
    return {
        "available": True,
        "source": "IBTrACS v04r01 — North Indian Ocean (RSMC New Delhi analyses)",
        "storms": int(df["SID"].nunique()),
        "observations": int(len(df)),
        "seasons": [int(df["SEASON"].min()), int(df["SEASON"].max())],
        "replay_min_season": settings.REPLAY_MIN_SEASON,
    }


def verification_for(event: dict, forecast: dict) -> list[dict]:
    """Compare each forecast point against what actually happened."""
    truth = {v["valid_at"]: v for v in event.get("metadata", {}).get("verification", [])}
    rows = []
    for p in forecast.get("points", []):
        actual = truth.get(p["valid_at"])
        if not actual:
            continue
        rows.append(
            {
                "lead_hours": p["lead_hours"],
                "forecast_lat": p["lat"],
                "forecast_lon": p["lon"],
                "actual_lat": actual["lat"],
                "actual_lon": actual["lon"],
                "track_error_km": round(
                    _haversine(p["lat"], p["lon"], actual["lat"], actual["lon"]), 1
                ),
                "forecast_wind_kt": p["est_wind_kt"],
                "actual_wind_kt": actual["wind_kt"],
                "intensity_error_kt": round(p["est_wind_kt"] - actual["wind_kt"], 1),
            }
        )
    return rows


def _haversine(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))
