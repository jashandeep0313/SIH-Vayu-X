"""Pure IBTrACS parsing — no framework dependencies.

Deliberately free of any intra-package import so ai-model can load this module
by file path for training. Both services root their code at `src`, so a normal
cross-service import collides; keeping the parsing pure avoids duplicating the
column handling in two places.

IBTrACS (NOAA NCEI) is the merged global best-track archive. For the North
Indian Ocean it carries the RSMC New Delhi (IMD) analyses, so these are the same
labels our forecasts will ultimately be judged against.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# IMD North Indian Ocean intensity scale (sustained wind, knots)
IMD_SCALE = [
    (17, "LPA"), (28, "D"), (34, "DD"), (48, "CS"),
    (64, "SCS"), (90, "VSCS"), (120, "ESCS"),
]


def categorise(wind_kt: float) -> str:
    if pd.isna(wind_kt):
        return "UNK"
    for limit, code in IMD_SCALE:
        if wind_kt < limit:
            return code
    return "SuCS"


def load_best_track(path: str | Path, min_season: int = 1990) -> pd.DataFrame:
    """Read an IBTrACS CSV into a clean, typed track table.

    IBTrACS puts a units row directly under the header, and uses a mix of blanks
    and sentinel strings for missing values — both are stripped here.
    """
    df = pd.read_csv(path, skiprows=[1], low_memory=False, na_values=[" ", "", "NOT_NAMED"])

    keep = ["SID", "SEASON", "BASIN", "SUBBASIN", "NAME", "ISO_TIME", "LAT", "LON",
            "WMO_WIND", "WMO_PRES", "USA_WIND", "USA_PRES", "DIST2LAND", "STORM_SPEED"]
    df = df[[c for c in keep if c in df.columns]].copy()

    df["ISO_TIME"] = pd.to_datetime(df["ISO_TIME"], errors="coerce")
    for col in ["LAT", "LON", "WMO_WIND", "WMO_PRES", "USA_WIND", "USA_PRES",
                "DIST2LAND", "STORM_SPEED"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["SEASON"] = pd.to_numeric(df["SEASON"], errors="coerce")
    df = df[df["SEASON"] >= min_season]

    # Prefer the WMO agency value (RSMC New Delhi for this basin); fall back to JTWC
    df["wind_kt"] = df["WMO_WIND"].fillna(df.get("USA_WIND"))
    df["pressure_hpa"] = df["WMO_PRES"].fillna(df.get("USA_PRES"))

    df = df.dropna(subset=["ISO_TIME", "LAT", "LON", "wind_kt"])
    df = df.sort_values(["SID", "ISO_TIME"]).reset_index(drop=True)

    # Best tracks are 3-hourly but carry extra synoptic rows; keep the main cycle
    df = df[df["ISO_TIME"].dt.hour % 3 == 0].reset_index(drop=True)

    df["category"] = df["wind_kt"].apply(categorise)
    return df


def track_summary(df: pd.DataFrame) -> dict:
    return {
        "storms": int(df["SID"].nunique()),
        "observations": int(len(df)),
        "seasons": f"{int(df['SEASON'].min())}-{int(df['SEASON'].max())}",
        "by_category": df.groupby("category")["SID"].nunique().to_dict(),
        "max_wind_kt": float(np.nanmax(df["wind_kt"])),
    }
