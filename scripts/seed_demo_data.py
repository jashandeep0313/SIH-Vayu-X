"""Seed a synthetic cyclone event for UI development and demos.

Lets the frontend and alert teams build against realistic data before the model
or the satellite pipeline produce anything. It is also the fallback demo path if
live feeds are unavailable on presentation day.

    python scripts/seed_demo_data.py
"""

import json
import math
import uuid
from datetime import datetime, timedelta, timezone

FORECAST_LEADS = [6, 12, 24, 48, 72]


def wind_to_category(wind_kt: float) -> str:
    thresholds = [
        (17, "LPA"), (28, "D"), (34, "DD"), (48, "CS"),
        (64, "SCS"), (90, "VSCS"), (120, "ESCS"),
    ]
    for limit, code in thresholds:
        if wind_kt < limit:
            return code
    return "SuCS"


def build_demo_event() -> dict:
    """A Bay of Bengal system intensifying on approach to the Odisha coast."""
    cyclone_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # 24 hours of history at 3-hourly steps, tracking north-west and intensifying
    observations = []
    for step in range(8):
        observed_at = now - timedelta(hours=(7 - step) * 3)
        wind = 35 + step * 6.5
        observations.append(
            {
                "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
                "lat": round(13.2 + step * 0.38, 2),
                "lon": round(89.4 - step * 0.31, 2),
                "pattern_type": "eye" if wind > 70 else "CDO" if wind > 50 else "curved_band",
                "intensity_category": wind_to_category(wind),
                "est_wind_kt": round(wind, 1),
                "est_pressure_hpa": round(1004 - (wind - 35) * 0.95, 1),
                "dvorak_t_number": round(2.0 + step * 0.35, 1),
                "confidence": round(0.72 + step * 0.025, 2),
                "source_frame": f"insat3d_tir1_{observed_at:%Y%m%dT%H%M}Z",
                "model_versions": {
                    "identification": "cyclone_detector_v1",
                    "classification": "pattern_classifier_v1",
                },
            }
        )

    last = observations[-1]

    # Forecast continues north-west, peaks, then weakens after landfall
    points = []
    for lead in FORECAST_LEADS:
        # Intensity rises to ~36h then decays as the system moves inland
        wind = last["est_wind_kt"] + 14 * math.sin(min(lead, 36) / 36 * math.pi / 2)
        if lead > 36:
            wind -= (lead - 36) * 1.15
        wind = max(wind, 25.0)

        points.append(
            {
                "lead_hours": lead,
                "valid_at": (now + timedelta(hours=lead)).isoformat().replace("+00:00", "Z"),
                "lat": round(last["lat"] + lead * 0.062, 2),
                "lon": round(last["lon"] - lead * 0.048, 2),
                "est_wind_kt": round(wind, 1),
                "est_pressure_hpa": round(1004 - (wind - 35) * 0.95, 1),
                "intensity_category": wind_to_category(wind),
                # Uncertainty grows with lead time — this becomes the cone
                "radius_uncertainty_km": round(28 + lead * 3.4, 0),
                "confidence": round(max(0.45, 0.92 - lead * 0.006), 2),
            }
        )

    return {
        "id": cyclone_id,
        "name": "DEMO-VAYUX-01",
        "basin": "BOB",
        "status": "active",
        "first_seen": observations[0]["observed_at"],
        "last_seen": last["observed_at"],
        "peak_intensity_category": last["intensity_category"],
        "observations": observations,
        "latest_forecast": {
            "cyclone_id": cyclone_id,
            "issued_at": now.isoformat().replace("+00:00", "Z"),
            "model_version": "track_convlstm_v1",
            "points": points,
            "landfall_estimate": {
                "expected_at": (now + timedelta(hours=38)).isoformat().replace("+00:00", "Z"),
                "lat": 19.8,
                "lon": 85.0,
                "region": "Odisha coast (Puri-Paradip)",
                "confidence": 0.74,
            },
            "rapid_intensification_risk": 0.38,
        },
        "metadata": {"synthetic": True, "purpose": "UI development and demo fallback"},
    }


def main() -> None:
    event = build_demo_event()
    output = "demo_cyclone_event.json"
    with open(output, "w") as f:
        json.dump(event, f, indent=2)

    print(f"Wrote {output}")
    print(f"  {event['name']} — {len(event['observations'])} observations, "
          f"{len(event['latest_forecast']['points'])} forecast points")
    print(f"  Peak: {event['peak_intensity_category']}, "
          f"landfall {event['latest_forecast']['landfall_estimate']['region']}")
    print("\nPOST it to the backend once /cyclones accepts writes, or serve it "
          "from a frontend mock while the API is still stubbed.")


if __name__ == "__main__":
    main()
