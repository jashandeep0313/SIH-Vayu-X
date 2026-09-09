"""Feature engineering for track and intensity forecasting.

Builds a CLIPER-style feature set (CLImatology and PERsistence) from best-track
history. CLIPER is the standard operational baseline: any model that cannot beat
it is not adding value, so we build it as a real model rather than a strawman.

Features are strictly causal — every one is computable at forecast time from the
storm's past. Nothing from the future leaks in.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

EARTH_RADIUS_KM = 6371.0
FORECAST_LEADS = [6, 12, 24, 48, 72]
STEP_HOURS = 3  # best-track cadence


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def _storm_features(g: pd.DataFrame) -> pd.DataFrame:
    """Per-storm causal features. `g` must be time-ordered for one SID."""
    g = g.sort_values("ISO_TIME").copy()

    for lag_h in (6, 12, 24):
        n = lag_h // STEP_HOURS
        g[f"dlat_{lag_h}h"] = g["LAT"] - g["LAT"].shift(n)
        g[f"dlon_{lag_h}h"] = g["LON"] - g["LON"].shift(n)
        g[f"dwind_{lag_h}h"] = g["wind_kt"] - g["wind_kt"].shift(n)

    # Motion vector in degrees/hour — the dominant control on short-range track
    g["u_deg_h"] = g["dlon_12h"] / 12.0
    g["v_deg_h"] = g["dlat_12h"] / 12.0
    g["speed_kmh"] = (
        haversine_km(g["LAT"].shift(4), g["LON"].shift(4), g["LAT"], g["LON"]) / 12.0
    )
    g["heading_deg"] = (np.degrees(np.arctan2(g["dlon_12h"], g["dlat_12h"])) + 360) % 360

    g["age_h"] = (g["ISO_TIME"] - g["ISO_TIME"].iloc[0]).dt.total_seconds() / 3600.0
    g["wind_max_so_far"] = g["wind_kt"].cummax()
    g["wind_rate_6h"] = g["dwind_6h"] / 6.0

    # Targets: displacement and intensity change at each lead time
    for lead in FORECAST_LEADS:
        n = lead // STEP_HOURS
        g[f"y_dlat_{lead}"] = g["LAT"].shift(-n) - g["LAT"]
        g[f"y_dlon_{lead}"] = g["LON"].shift(-n) - g["LON"]
        g[f"y_dwind_{lead}"] = g["wind_kt"].shift(-n) - g["wind_kt"]
        g[f"y_lat_{lead}"] = g["LAT"].shift(-n)
        g[f"y_lon_{lead}"] = g["LON"].shift(-n)
        g[f"y_wind_{lead}"] = g["wind_kt"].shift(-n)

    return g


FEATURE_COLUMNS = [
    "LAT", "LON", "wind_kt", "pressure_hpa",
    "dlat_6h", "dlon_6h", "dwind_6h",
    "dlat_12h", "dlon_12h", "dwind_12h",
    "dlat_24h", "dlon_24h", "dwind_24h",
    "u_deg_h", "v_deg_h", "speed_kmh", "heading_deg",
    "age_h", "wind_max_so_far", "wind_rate_6h",
    "day_of_year_sin", "day_of_year_cos", "DIST2LAND",
]


def build_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Attach causal features and forecast targets to a best-track table.

    Built storm-by-storm rather than via groupby.apply: the identifier column
    must stay on the frame, and pandas has changed that behaviour across
    versions. An explicit loop is stable and no slower at this size.
    """
    out = pd.concat(
        [_storm_features(g) for _, g in df.groupby("SID", sort=False)],
        ignore_index=True,
    )

    doy = out["ISO_TIME"].dt.dayofyear
    out["day_of_year_sin"] = np.sin(2 * np.pi * doy / 365.25)
    out["day_of_year_cos"] = np.cos(2 * np.pi * doy / 365.25)

    if "DIST2LAND" not in out.columns:
        out["DIST2LAND"] = np.nan

    return out.reset_index(drop=True)


def chronological_split(
    df: pd.DataFrame,
    train_max_season: int = 2016,
    val_max_season: int = 2020,
) -> dict[str, pd.DataFrame]:
    """Split by season, never at random.

    Consecutive best-track rows of one storm are near-identical; a random split
    puts them on both sides and inflates every score. Splitting by season also
    matches how the system would actually be deployed — trained on the past,
    judged on seasons it has never seen.
    """
    return {
        "train": df[df["SEASON"] <= train_max_season],
        "val": df[(df["SEASON"] > train_max_season) & (df["SEASON"] <= val_max_season)],
        "test": df[df["SEASON"] > val_max_season],
    }


def xy_for_lead(df: pd.DataFrame, lead: int, target: str) -> tuple[pd.DataFrame, pd.Series]:
    """Feature matrix and target vector for one lead time.

    target: 'dlat' | 'dlon' | 'dwind'
    """
    col = f"y_{target}_{lead}"
    needed = FEATURE_COLUMNS + [col]
    sub = df.dropna(subset=[c for c in needed if c != "DIST2LAND"])
    x = sub[FEATURE_COLUMNS].fillna(0.0)
    return x, sub[col]
