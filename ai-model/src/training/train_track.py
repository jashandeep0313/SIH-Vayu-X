"""Train the track and intensity forecast models on IBTrACS best-track data.

This is a real model on real data — no synthetic inputs. Gradient-boosted trees
over CLIPER-style causal features, one model per (lead time, target).

Every result is reported against a persistence baseline on a held-out set of
seasons the model has never seen. A model that cannot beat persistence is not a
result, so the skill score is printed alongside the raw error.

    python -m src.training.train_track
    python -m src.training.train_track --data data/raw/ibtracs/ibtracs_NI_v04r01.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.features.track_features import (  # noqa: E402
    FEATURE_COLUMNS,
    FORECAST_LEADS,
    build_dataset,
    chronological_split,
    haversine_km,
    xy_for_lead,
)

DEFAULT_DATA = "data/raw/ibtracs/ibtracs_NI_v04r01.csv"
CHECKPOINT_DIR = Path("models/checkpoints")


def _load(path: str) -> pd.DataFrame:
    """Load best track, reusing the data-pipeline parser as the single source of truth.

    Imported by file path rather than package: both services root their code at
    `src`, so a normal import would collide.
    """
    import importlib.util

    module_path = (
        Path(__file__).resolve().parents[3]
        / "data-pipeline"
        / "src"
        / "ingest"
        / "best_track_parsing.py"
    )
    spec = importlib.util.spec_from_file_location("vayux_best_track", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load_best_track(path)


def persistence_forecast(df: pd.DataFrame, lead: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Extrapolate the current 12-hour motion and hold intensity constant.

    This is the floor every operational forecast is measured against.
    """
    lat = df["LAT"].to_numpy() + df["v_deg_h"].to_numpy() * lead
    lon = df["LON"].to_numpy() + df["u_deg_h"].to_numpy() * lead
    wind = df["wind_kt"].to_numpy()
    return lat, lon, wind


def train(
    data_path: str,
    out_dir: Path,
    train_max: int = 2022,
    val_max: int = 2022,
    min_season: int | None = 2012,
) -> dict:
    print(f"Loading best track from {data_path}")
    raw = _load(data_path)
    if min_season:
        raw = raw[raw["SEASON"] >= min_season]
    ds = build_dataset(raw)
    parts = chronological_split(ds, train_max_season=train_max, val_max_season=val_max)

    for name, part in parts.items():
        seasons = f"{int(part['SEASON'].min())}-{int(part['SEASON'].max())}" if len(part) else "—"
        print(f"  {name:5} {len(part):6} rows  {part['SID'].nunique():4} storms  seasons {seasons}")

    out_dir.mkdir(parents=True, exist_ok=True)
    report: dict = {"leads": {}, "features": FEATURE_COLUMNS}

    for lead in FORECAST_LEADS:
        models = {}
        for target in ("dlat", "dlon", "dwind"):
            x_tr, y_tr = xy_for_lead(parts["train"], lead, target)
            if len(x_tr) < 200:
                print(f"  [+{lead}h/{target}] too few samples ({len(x_tr)}), skipped")
                continue
            model = HistGradientBoostingRegressor(
                max_iter=400,
                learning_rate=0.06,
                max_depth=6,
                min_samples_leaf=25,
                l2_regularization=1.0,
                random_state=42,
                early_stopping=True,
                validation_fraction=0.15,
            )
            model.fit(x_tr, y_tr)
            models[target] = model

        if len(models) < 3:
            continue

        # ---- evaluate on held-out seasons ----
        test = parts["test"].dropna(
            subset=[f"y_lat_{lead}", f"y_lon_{lead}", f"y_wind_{lead}", "u_deg_h", "v_deg_h"]
        )
        if test.empty:
            continue

        x_te = test[FEATURE_COLUMNS].fillna(0.0)
        pred_lat = test["LAT"].to_numpy() + models["dlat"].predict(x_te)
        pred_lon = test["LON"].to_numpy() + models["dlon"].predict(x_te)
        pred_wind = test["wind_kt"].to_numpy() + models["dwind"].predict(x_te)

        true_lat = test[f"y_lat_{lead}"].to_numpy()
        true_lon = test[f"y_lon_{lead}"].to_numpy()
        true_wind = test[f"y_wind_{lead}"].to_numpy()

        p_lat, p_lon, p_wind = persistence_forecast(test, lead)

        model_km = float(np.mean(haversine_km(pred_lat, pred_lon, true_lat, true_lon)))
        persist_km = float(np.mean(haversine_km(p_lat, p_lon, true_lat, true_lon)))
        model_mae = float(np.mean(np.abs(pred_wind - true_wind)))
        persist_mae = float(np.mean(np.abs(p_wind - true_wind)))

        skill_track = (persist_km - model_km) / persist_km if persist_km else 0.0
        skill_int = (persist_mae - model_mae) / persist_mae if persist_mae else 0.0

        for target, m in models.items():
            joblib.dump(m, out_dir / f"track_{target}_{lead}h.joblib")

        report["leads"][lead] = {
            "n_test": int(len(test)),
            "track_error_km": round(model_km, 1),
            "track_error_km_persistence": round(persist_km, 1),
            "track_skill_vs_persistence": round(skill_track, 3),
            "intensity_mae_kt": round(model_mae, 2),
            "intensity_mae_kt_persistence": round(persist_mae, 2),
            "intensity_skill_vs_persistence": round(skill_int, 3),
        }
        print(
            f"  [+{lead:2}h] track {model_km:6.1f} km (persist {persist_km:6.1f}, "
            f"skill {skill_track:+.1%})   intensity {model_mae:5.2f} kt "
            f"(persist {persist_mae:5.2f}, skill {skill_int:+.1%})   n={len(test)}"
        )

    report["train_seasons"] = [
        int(parts["train"]["SEASON"].min()),
        int(parts["train"]["SEASON"].max()),
    ]
    report["test_seasons"] = [
        int(parts["test"]["SEASON"].min()),
        int(parts["test"]["SEASON"].max()),
    ]
    report["n_storms_total"] = int(ds["SID"].nunique())

    (out_dir / "track_model_report.json").write_text(json.dumps(report, indent=2))
    print(f"\nSaved models and report to {out_dir}")
    return report


def main() -> None:
    p = argparse.ArgumentParser(description="Train Vayu-X track/intensity models")
    p.add_argument("--data", default=DEFAULT_DATA)
    p.add_argument("--out", default=str(CHECKPOINT_DIR))
    p.add_argument("--min-season", type=int, default=2012,
                   help="earliest season to use at all")
    p.add_argument("--train-max", type=int, default=2022,
                   help="last season used for training")
    p.add_argument("--val-max", type=int, default=2022,
                   help="last season used for validation; test is everything after")
    args = p.parse_args()
    train(args.data, Path(args.out), args.train_max, args.val_max, args.min_season)


if __name__ == "__main__":
    main()
