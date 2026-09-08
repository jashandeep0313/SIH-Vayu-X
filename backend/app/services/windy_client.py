"""Windy Point Forecast API client.

Returns a GFS forecast time-series (wind, pressure, precipitation) at a single
lat/lon. This is a *point* service — it returns numbers, not map tiles. The
animated weather map layers are a separate product (Map Forecast API) requiring
its own key.

Used as an independent cross-check on conditions at the forecast landfall point:
our intensity estimate comes from satellite imagery, this comes from a numerical
weather model, and disagreement between them is information worth surfacing.

Docs: https://api.windy.com/point-forecast/docs
"""

import math
from datetime import UTC, datetime

import httpx

from app.core.config import settings

ENDPOINT = "https://api.windy.com/api/point-forecast/v2"
MS_TO_KT = 1.94384


class WindyClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.WINDY_POINT_API_KEY

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def point_forecast(
        self, lat: float, lon: float, model: str = "gfs", hours: int = 72
    ) -> dict:
        """Forecast at one location, normalised to the units used elsewhere here.

        Windy returns wind as u/v components in m/s and pressure in pascals; the
        rest of this system speaks knots and hectopascals.
        """
        if not self.configured:
            raise RuntimeError("WINDY_POINT_API_KEY is not set")

        payload = {
            "lat": lat,
            "lon": lon,
            "model": model,
            "parameters": ["wind", "pressure", "precip"],
            "levels": ["surface"],
            "key": self.api_key,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(ENDPOINT, json=payload)
            response.raise_for_status()
            raw = response.json()

        timestamps = raw.get("ts", [])
        u = raw.get("wind_u-surface", [])
        v = raw.get("wind_v-surface", [])
        pressure = raw.get("pressure-surface", [])
        precip = raw.get("past3hprecip-surface", [])

        now = datetime.now(UTC).timestamp() * 1000
        cutoff = now + hours * 3600 * 1000

        points = []
        for i, ts in enumerate(timestamps):
            if ts > cutoff:
                break
            wind_ms = (
                math.hypot(u[i], v[i]) if i < len(u) and i < len(v) and u[i] is not None else None
            )
            points.append(
                {
                    "valid_at": datetime.fromtimestamp(ts / 1000, tz=UTC)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "wind_kt": round(wind_ms * MS_TO_KT, 1) if wind_ms is not None else None,
                    "wind_dir_deg": (
                        round((math.degrees(math.atan2(-u[i], -v[i])) + 360) % 360)
                        if i < len(u) and u[i] is not None
                        else None
                    ),
                    "pressure_hpa": (
                        round(pressure[i] / 100, 1)
                        if i < len(pressure) and pressure[i] is not None
                        else None
                    ),
                    "precip_mm_3h": (
                        round(precip[i] * 1000, 2)
                        if i < len(precip) and precip[i] is not None
                        else None
                    ),
                }
            )

        winds = [p["wind_kt"] for p in points if p["wind_kt"] is not None]
        pressures = [p["pressure_hpa"] for p in points if p["pressure_hpa"] is not None]

        return {
            "source": "Windy Point Forecast",
            "model": model.upper(),
            "lat": lat,
            "lon": lon,
            "fetched_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "summary": {
                "max_wind_kt": max(winds) if winds else None,
                "min_pressure_hpa": min(pressures) if pressures else None,
                "total_precip_mm": round(sum(p["precip_mm_3h"] or 0 for p in points), 1),
            },
            "points": points,
        }
