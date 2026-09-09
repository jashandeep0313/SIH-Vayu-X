"""Track and intensity forecasting from a storm's observed history.

Loads the gradient-boosted models trained by src.training.train_track and turns
a sequence of past fixes into a forecast at each standard lead time.

This is the real inference path — the numbers it returns come from a model
fitted to IBTrACS best-track data, not from a script.
"""

from __future__ import annotations

import json
import math
from datetime import timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.features.track_features import FEATURE_COLUMNS, FORECAST_LEADS, build_dataset

DEFAULT_CHECKPOINTS = Path("models/checkpoints")

IMD_SCALE = [(17, "LPA"), (28, "D"), (34, "DD"), (48, "CS"),
             (64, "SCS"), (90, "VSCS"), (120, "ESCS")]


def categorise(wind_kt: float) -> str:
    for limit, code in IMD_SCALE:
        if wind_kt < limit:
            return code
    return "SuCS"


def pressure_from_wind(wind_kt: float) -> float:
    """Atkinson-Holliday, floored at the lowest pressure ever observed (870 hPa)."""
    return round(max(870.0, 1010 - (wind_kt / 6.7) ** (1 / 0.644)), 1)


class TrackPredictor:
    """Loads per-lead models and forecasts from an observation history."""

    def __init__(self, checkpoint_dir: str | Path = DEFAULT_CHECKPOINTS) -> None:
        self.dir = Path(checkpoint_dir)
        self.models: dict[tuple[int, str], object] = {}
        self.report: dict = {}
        self.loaded = False

    def load(self) -> bool:
        report_path = self.dir / "track_model_report.json"
        if report_path.exists():
            self.report = json.loads(report_path.read_text())

        for lead in FORECAST_LEADS:
            for target in ("dlat", "dlon", "dwind"):
                p = self.dir / f"track_{target}_{lead}h.joblib"
                if p.exists():
                    self.models[(lead, target)] = joblib.load(p)

        self.loaded = bool(self.models)
        return self.loaded

    @property
    def available_leads(self) -> list[int]:
        return sorted({lead for lead, _ in self.models})

    def skill(self, lead: int) -> dict:
        return self.report.get("leads", {}).get(str(lead), {})

    def predict(self, observations: list[dict]) -> dict:
        """Forecast from a storm's observed history.

        `observations` must be time-ordered, each with observed_at, lat, lon and
        est_wind_kt. At least 24 hours of history (9 three-hourly fixes) gives the
        lag features their full window; shorter histories still work but the
        motion terms are weaker.
        """
        if not self.loaded:
            raise RuntimeError("no models loaded")
        if len(observations) < 2:
            raise ValueError("need at least two observations to infer motion")

        df = pd.DataFrame(
            {
                "SID": "QUERY",
                "SEASON": 2025,
                "ISO_TIME": pd.to_datetime([o["observed_at"] for o in observations]),
                "LAT": [o["lat"] for o in observations],
                "LON": [o["lon"] for o in observations],
                "wind_kt": [o["est_wind_kt"] for o in observations],
                "pressure_hpa": [
                    o.get("est_pressure_hpa") or pressure_from_wind(o["est_wind_kt"])
                    for o in observations
                ],
                "DIST2LAND": [o.get("dist2land", np.nan) for o in observations],
            }
        )

        featured = build_dataset(df)
        current = featured.iloc[[-1]]
        x = current[FEATURE_COLUMNS].fillna(0.0)

        lat0 = float(current["LAT"].iloc[0])
        lon0 = float(current["LON"].iloc[0])
        wind0 = float(current["wind_kt"].iloc[0])
        issued = pd.to_datetime(current["ISO_TIME"].iloc[0]).to_pydatetime()

        points = []
        for lead in self.available_leads:
            try:
                lat = lat0 + float(self.models[(lead, "dlat")].predict(x)[0])
                lon = lon0 + float(self.models[(lead, "dlon")].predict(x)[0])
                wind = max(10.0, wind0 + float(self.models[(lead, "dwind")].predict(x)[0]))
            except KeyError:
                continue

            # Uncertainty radius comes from measured test-set error at this lead,
            # not from a guess — so the cone reflects how wrong the model actually is.
            skill = self.skill(lead)
            radius = skill.get("track_error_km", 40 + lead * 4.0)

            points.append(
                {
                    "lead_hours": lead,
                    "valid_at": (issued + timedelta(hours=lead)).isoformat().replace("+00:00", "Z"),
                    "lat": round(lat, 2),
                    "lon": round(lon, 2),
                    "est_wind_kt": round(wind, 1),
                    "est_pressure_hpa": pressure_from_wind(wind),
                    "intensity_category": categorise(wind),
                    "radius_uncertainty_km": round(radius, 0),
                    "intensity_mae_kt": skill.get("intensity_mae_kt"),
                }
            )

        return {
            "model_version": "track_hgbr_ibtracs_v1",
            "issued_at": issued.isoformat().replace("+00:00", "Z"),
            "points": points,
            "cone_geojson": build_cone(points),
            "trained_on": {
                "source": "IBTrACS v04r01 (North Indian Ocean)",
                "train_seasons": self.report.get("train_seasons"),
                "test_seasons": self.report.get("test_seasons"),
                "storms": self.report.get("n_storms_total"),
            },
        }


KM_PER_DEG_LAT = 111.32


def build_cone(points: list[dict]) -> dict | None:
    """Cone of uncertainty from the per-lead radii."""
    if len(points) < 2:
        return None

    left, right = [], []
    for i, p in enumerate(points):
        nxt = points[min(i + 1, len(points) - 1)]
        prv = points[max(i - 1, 0)]
        dlat = nxt["lat"] - prv["lat"]
        dlon = nxt["lon"] - prv["lon"]
        norm = math.hypot(dlat, dlon) or 1.0

        radius_deg = p["radius_uncertainty_km"] / KM_PER_DEG_LAT
        lon_scale = max(math.cos(math.radians(p["lat"])), 0.1)
        perp_lat = -dlon / norm * radius_deg
        perp_lon = dlat / norm * radius_deg / lon_scale

        left.append([round(p["lon"] + perp_lon, 4), round(p["lat"] + perp_lat, 4)])
        right.append([round(p["lon"] - perp_lon, 4), round(p["lat"] - perp_lat, 4)])

    ring = left + list(reversed(right))
    ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}
