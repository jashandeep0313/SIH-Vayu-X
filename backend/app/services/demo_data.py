"""Synthetic cyclone data for development and offline demos.

Served only when DEMO_MODE is enabled. Every event is tagged `synthetic: true`
in its metadata and the dashboard renders a DEMO banner, so demo output can
never be mistaken for a real IMD product.

This is also the presentation fallback: it lets the full stack be demonstrated
end-to-end without depending on live satellite feeds.
"""

import math
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.services.wind_field import wind_field

EARTH_RADIUS_KM = 6371.0
KM_PER_DEG_LAT = 111.32

# Stable UUIDs so links and selections survive a server restart
STORM_A = UUID("b1f7c2de-3a4e-4b21-9f0c-7d8e2a1b5c34")
STORM_B = UUID("c2a8d3ef-4b5f-4c32-8a1d-6e9f3b2c7d45")
STORM_C = UUID("d3b9e4f0-5c60-4d43-9b2e-7f0a4c3d8e56")


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def wind_to_category(wind_kt: float) -> str:
    """IMD North Indian Ocean intensity scale."""
    for limit, code in [
        (17, "LPA"),
        (28, "D"),
        (34, "DD"),
        (48, "CS"),
        (64, "SCS"),
        (90, "VSCS"),
        (120, "ESCS"),
    ]:
        if wind_kt < limit:
            return code
    return "SuCS"


def _pattern_for(wind_kt: float) -> str:
    if wind_kt >= 85:
        return "eye"
    if wind_kt >= 64:
        return "banding_eye"
    if wind_kt >= 45:
        return "CDO"
    if wind_kt >= 30:
        return "curved_band"
    return "shear"


def _pressure_for(wind_kt: float) -> float:
    """Central pressure via the Atkinson-Holliday wind-pressure relationship.

    Vmax = 6.7 * (1010 - Pc)^0.644, inverted. The exponent is 1/0.644; getting it
    wrong produces pressures below the world record for an ordinary storm.

    Floored at 870 hPa (Typhoon Tip, 1979) because the empirical relation keeps
    extrapolating past the lowest pressure ever observed on Earth.
    """
    return round(max(870.0, 1010 - (wind_kt / 6.7) ** (1 / 0.644)), 1)


# Standard Dvorak CI number → maximum sustained wind (kt)
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


def _t_number(wind_kt: float) -> float:
    """Dvorak-equivalent T-number, interpolated from the standard CI table.

    Included so an IMD analyst can cross-check the model against the method
    they already trust.
    """
    if wind_kt <= _DVORAK_CI[0][1]:
        return _DVORAK_CI[0][0]
    for (t_lo, v_lo), (t_hi, v_hi) in zip(_DVORAK_CI, _DVORAK_CI[1:], strict=False):
        if wind_kt <= v_hi:
            frac = (wind_kt - v_lo) / (v_hi - v_lo)
            return round(t_lo + frac * (t_hi - t_lo), 1)
    return 8.0


def _build_cone(points: list[dict]) -> dict:
    """Cone of uncertainty polygon from forecast points and their radii.

    Offsets each point perpendicular to the local track heading, then walks up
    one side and back down the other to close the ring.
    """
    left, right = [], []
    for i, p in enumerate(points):
        nxt = points[min(i + 1, len(points) - 1)]
        prv = points[max(i - 1, 0)]
        dlat = nxt["lat"] - prv["lat"]
        dlon = nxt["lon"] - prv["lon"]
        norm = math.hypot(dlat, dlon) or 1.0

        radius_deg = p["radius_uncertainty_km"] / KM_PER_DEG_LAT
        lon_scale = max(math.cos(math.radians(p["lat"])), 0.1)

        # Perpendicular to the heading
        perp_lat = -dlon / norm * radius_deg
        perp_lon = dlat / norm * radius_deg / lon_scale

        left.append([round(p["lon"] + perp_lon, 4), round(p["lat"] + perp_lat, 4)])
        right.append([round(p["lon"] - perp_lon, 4), round(p["lat"] - perp_lat, 4)])

    ring = left + list(reversed(right))
    ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def _make_track(
    start_lat: float,
    start_lon: float,
    d_lat: float,
    d_lon: float,
    start_wind: float,
    wind_step: float,
    steps: int,
    now: datetime,
    step_hours: int = 3,
    curvature: float = 0.0,
) -> list[dict]:
    """Generate an observation history ending at `now`."""
    observations = []
    for i in range(steps):
        observed_at = now - timedelta(hours=(steps - 1 - i) * step_hours)
        wind = max(15.0, start_wind + wind_step * i)
        lat = start_lat + d_lat * i + curvature * (i**2) * 0.01
        lon = start_lon + d_lon * i - curvature * (i**2) * 0.008
        pressure = _pressure_for(wind)
        rmw = round(max(15.0, 70 - wind * 0.35), 1)

        observations.append(
            {
                "observed_at": _iso(observed_at),
                "lat": round(lat, 2),
                "lon": round(lon, 2),
                "pattern_type": _pattern_for(wind),
                "intensity_category": wind_to_category(wind),
                "est_wind_kt": round(wind, 1),
                "est_pressure_hpa": pressure,
                "dvorak_t_number": _t_number(wind),
                "radius_max_wind_km": rmw,
                "wind_field": wind_field(wind, pressure, rmw),
                "confidence": round(min(0.96, 0.68 + i * 0.02), 2),
                "class_probabilities": _class_probabilities(wind),
                "source_frame": f"insat3d_tir1_{observed_at:%Y%m%dT%H%M}Z",
                "source_channels": ["TIR1", "TIR2", "WV", "MIR"],
                "model_versions": {
                    "identification": "cyclone_detector_v1",
                    "classification": "pattern_classifier_v1",
                },
                "explanation_uri": f"s3://vayux-processed/explain/gradcam_{observed_at:%Y%m%dT%H%M}Z.png",
            }
        )
    return observations


def _class_probabilities(wind_kt: float) -> dict[str, float]:
    """Plausible softmax output, peaked on the dominant pattern."""
    dominant = _pattern_for(wind_kt)
    base = {
        "eye": 0.03,
        "banding_eye": 0.05,
        "CDO": 0.06,
        "curved_band": 0.04,
        "shear": 0.02,
        "central_cold_cover": 0.01,
    }
    base[dominant] = 0.0
    remainder = round(1.0 - sum(base.values()), 2)
    base[dominant] = remainder
    return {k: round(v, 3) for k, v in base.items()}


def _make_forecast(
    cyclone_id: UUID,
    last_obs: dict,
    now: datetime,
    d_lat: float,
    d_lon: float,
    peak_gain: float,
    decay_after_h: int,
    landfall: dict | None,
) -> dict:
    leads = [6, 12, 24, 48, 72]
    points = []
    for lead in leads:
        wind = last_obs["est_wind_kt"] + peak_gain * math.sin(
            min(lead, decay_after_h) / decay_after_h * math.pi / 2
        )
        if lead > decay_after_h:
            wind -= (lead - decay_after_h) * 1.4
        wind = max(18.0, wind)

        points.append(
            {
                "lead_hours": lead,
                "valid_at": _iso(now + timedelta(hours=lead)),
                "lat": round(last_obs["lat"] + d_lat * lead, 2),
                "lon": round(last_obs["lon"] + d_lon * lead, 2),
                "est_wind_kt": round(wind, 1),
                "est_pressure_hpa": _pressure_for(wind),
                "intensity_category": wind_to_category(wind),
                "radius_uncertainty_km": round(30 + lead * 3.6, 0),
                "confidence": round(max(0.42, 0.93 - lead * 0.0065), 2),
            }
        )

    return {
        "cyclone_id": str(cyclone_id),
        "issued_at": _iso(now),
        "model_version": "track_convlstm_v1",
        "points": points,
        "landfall_estimate": landfall,
        "cone_geojson": _build_cone(points),
        "environment_inputs": {
            "sst_c": 29.6,
            "shear_kt": 7.4,
            "rh_mid_pct": 71.0,
            "vorticity_850": 4.6e-5,
            "steering_u": -3.1,
            "steering_v": 4.9,
            "ocean_heat_content": 82.0,
        },
        "rapid_intensification_risk": 0.41,
    }


def _events(now: datetime) -> list[dict]:
    # --- Storm A: severe system intensifying toward the Odisha coast ---
    obs_a = _make_track(13.1, 89.6, 0.42, -0.34, 38, 6.2, 9, now, curvature=0.6)
    last_a = obs_a[-1]
    forecast_a = _make_forecast(
        STORM_A,
        last_a,
        now,
        0.061,
        -0.047,
        15.0,
        36,
        {
            "expected_at": _iso(now + timedelta(hours=37)),
            "lat": 19.9,
            "lon": 85.1,
            "region": "Odisha coast (Puri–Paradip)",
            "confidence": 0.76,
        },
    )

    # --- Storm B: Arabian Sea system, weakening, no landfall threat ---
    obs_b = _make_track(16.4, 66.2, -0.14, 0.28, 52, -2.4, 8, now)
    last_b = obs_b[-1]
    forecast_b = _make_forecast(STORM_B, last_b, now, -0.018, 0.032, 2.0, 12, None)

    # --- Storm C: newly identified depression, south Bay of Bengal ---
    obs_c = _make_track(9.2, 87.1, 0.22, -0.12, 22, 1.1, 5, now)
    last_c = obs_c[-1]
    forecast_c = _make_forecast(STORM_C, last_c, now, 0.035, -0.02, 9.0, 48, None)

    return [
        {
            "id": str(STORM_A),
            "name": "MONTHA",
            "basin": "BOB",
            "status": "active",
            "first_seen": obs_a[0]["observed_at"],
            "last_seen": last_a["observed_at"],
            "peak_intensity_category": last_a["intensity_category"],
            "observations": obs_a,
            "latest_forecast": forecast_a,
            "metadata": {"synthetic": True, "threat": "landfall_expected"},
        },
        {
            "id": str(STORM_B),
            "name": "SENYAR",
            "basin": "ARB",
            "status": "weakened",
            "first_seen": obs_b[0]["observed_at"],
            "last_seen": last_b["observed_at"],
            "peak_intensity_category": "SCS",
            "observations": obs_b,
            "latest_forecast": forecast_b,
            "metadata": {"synthetic": True, "threat": "none"},
        },
        {
            "id": str(STORM_C),
            "name": None,
            "basin": "BOB",
            "status": "active",
            "first_seen": obs_c[0]["observed_at"],
            "last_seen": last_c["observed_at"],
            "peak_intensity_category": last_c["intensity_category"],
            "observations": obs_c,
            "latest_forecast": forecast_c,
            "metadata": {"synthetic": True, "threat": "monitoring"},
        },
    ]


def active_events() -> list[dict]:
    return _events(datetime.now(UTC))


def event_by_id(cyclone_id: UUID | str) -> dict | None:
    return next((e for e in active_events() if e["id"] == str(cyclone_id)), None)


def summaries() -> list[dict]:
    """List-view rows — full observation history is omitted deliberately."""
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
        for e in active_events()
    ]


def alerts() -> list[dict]:
    now = datetime.now(UTC)
    return [
        {
            "id": "a7c3e1b9-5d2f-4a80-b6c1-9e3f7d2a4b58",
            "cyclone_id": str(STORM_A),
            "cyclone_name": "MONTHA",
            "severity": "ORANGE",
            "status": "issued",
            "headline": "Very Severe Cyclonic Storm expected to cross Odisha coast within 36 hours",
            "body": (
                "MONTHA is forecast to make landfall near Puri between 21:00 and 23:00 IST "
                "on 10 September with sustained winds of 90–100 kmph, gusting to 115 kmph. "
                "Prepare to evacuate low-lying coastal areas."
            ),
            "matched_rule": "vscs_landfall_36h",
            "issued_at": _iso(now - timedelta(minutes=24)),
            "valid_from": _iso(now - timedelta(minutes=24)),
            "valid_until": _iso(now + timedelta(hours=36)),
            "affected_regions": ["Puri", "Khordha", "Jagatsinghpur", "Kendrapara", "Ganjam"],
            "intensity_summary": {"category": "VSCS", "max_wind_kt": 94.0, "max_wind_kmph": 174.0},
            "recommended_actions": [
                "Prepare to evacuate low-lying and coastal areas",
                "Secure loose objects, livestock and fishing boats",
                "Charge phones and store drinking water",
            ],
            "channels": ["sms", "email", "push", "webhook"],
            "audience": ["district_admin", "responder", "citizen"],
            "dispatches": [
                {"channel": "sms", "recipient_count": 1240, "status": "sent", "attempts": 1},
                {"channel": "email", "recipient_count": 86, "status": "sent", "attempts": 1},
                {"channel": "push", "recipient_count": 5310, "status": "sent", "attempts": 1},
                {"channel": "webhook", "recipient_count": 3, "status": "partial", "attempts": 2},
            ],
            "issued_by": "system",
            "dry_run": True,
        },
        {
            "id": "b8d4f2ca-6e3a-4b91-c7d2-0f4a8e3b5c69",
            "cyclone_id": str(STORM_A),
            "cyclone_name": "MONTHA",
            "severity": "YELLOW",
            "status": "acknowledged",
            "headline": "Cyclonic Storm within 72 hours of the Odisha–Andhra coast",
            "body": "Fishermen advised not to venture into the sea. Monitor official updates.",
            "matched_rule": "cs_approaching_72h",
            "issued_at": _iso(now - timedelta(hours=9)),
            "valid_from": _iso(now - timedelta(hours=9)),
            "valid_until": _iso(now + timedelta(hours=63)),
            "affected_regions": ["Ganjam", "Srikakulam", "Vizianagaram"],
            "intensity_summary": {"category": "SCS", "max_wind_kt": 58.0, "max_wind_kmph": 107.0},
            "recommended_actions": [
                "Monitor official updates",
                "Fishermen advised not to venture into the sea",
            ],
            "channels": ["email", "push"],
            "audience": ["district_admin", "analyst"],
            "dispatches": [
                {"channel": "email", "recipient_count": 64, "status": "sent", "attempts": 1},
                {"channel": "push", "recipient_count": 2870, "status": "sent", "attempts": 1},
            ],
            "issued_by": "system",
            "dry_run": True,
        },
        {
            "id": "c9e5a3db-7f4b-4ca2-d8e3-1a5b9f4c6d70",
            "cyclone_id": str(STORM_C),
            "cyclone_name": None,
            "severity": "GREEN",
            "status": "issued",
            "headline": "New depression identified in the south Bay of Bengal",
            "body": "System under observation. No coastal threat at present.",
            "matched_rule": "depression_formed",
            "issued_at": _iso(now - timedelta(hours=2, minutes=40)),
            "valid_from": _iso(now - timedelta(hours=2, minutes=40)),
            "valid_until": _iso(now + timedelta(hours=21)),
            "affected_regions": [],
            "intensity_summary": {"category": "D", "max_wind_kt": 26.0, "max_wind_kmph": 48.0},
            "recommended_actions": ["Continue monitoring"],
            "channels": ["email"],
            "audience": ["analyst"],
            "dispatches": [
                {"channel": "email", "recipient_count": 12, "status": "sent", "attempts": 1},
            ],
            "issued_by": "system",
            "dry_run": True,
        },
    ]


def pipeline_status() -> dict:
    """Ingestion heartbeat. Data staleness is the single most important
    operational signal — a stalled pipeline looks exactly like calm weather."""
    now = datetime.now(UTC)
    return {
        "last_frame_at": _iso(now - timedelta(minutes=7)),
        "staleness_minutes": 7,
        "expected_cadence_minutes": 30,
        "healthy": True,
        "sources": [
            {"id": "insat3d", "status": "ok", "last_seen_minutes": 7},
            {"id": "insat3dr", "status": "ok", "last_seen_minutes": 22},
            {"id": "scatsat1", "status": "ok", "last_seen_minutes": 184},
            {"id": "era5", "status": "lagging", "last_seen_minutes": 310},
        ],
    }
