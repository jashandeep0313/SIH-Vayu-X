"""Train intensity estimation from satellite imagery.

Data: NASA / Radiant Earth "Tropical Cyclone Wind Estimation" competition set —
geostationary IR imagery paired with best-track wind speed. Public, CC-BY-4.0,
no credentials.

This is the image half of PS 26070 made real. It is *not* INSAT data: the task
is identical (estimate intensity from satellite IR) but the sensor differs, so
treat it as a transferable baseline until MOSDAC access lands, and expect some
domain gap on INSAT frames.

Splits are by storm, never by frame. Consecutive frames of one storm are nearly
identical, so a random split would leak and report a fantasy score.

    python -m src.training.train_intensity
"""

from __future__ import annotations

import argparse
import json
import sys
import tarfile
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.features.image_features import extract, feature_names  # noqa: E402

RAW = Path("data/raw/nasa_tc")
CHECKPOINTS = Path("models/checkpoints")

IMD_SCALE = [(17, "LPA"), (28, "D"), (34, "DD"), (48, "CS"),
             (64, "SCS"), (90, "VSCS"), (120, "ESCS")]


def categorise(wind_kt: float) -> str:
    for limit, code in IMD_SCALE:
        if wind_kt < limit:
            return code
    return "SuCS"


def _load_labels(tar_path: Path) -> dict[str, float]:
    """image id -> wind speed (kt), from the labels tarball."""
    out = {}
    with tarfile.open(tar_path) as tf:
        for m in tf.getmembers():
            if not m.name.endswith(".json"):
                continue
            f = tf.extractfile(m)
            if f is None:
                continue
            try:
                data = json.loads(f.read())
            except Exception:
                continue
            wind = data.get("wind_speed")
            if wind is None:
                continue
            key = Path(m.name).parent.name.replace("_labels_", "_source_")
            out[key] = float(wind)
    return out


def _load_images(tar_path: Path, labels: dict[str, float], limit: int | None):
    """Stream images out of the source tarball, pairing each with its label."""
    import io

    from PIL import Image

    xs, ys, sids = [], [], []
    with tarfile.open(tar_path) as tf:
        for m in tf:
            if not m.name.endswith(".jpg"):
                continue
            key = Path(m.name).parent.name
            wind = labels.get(key)
            if wind is None:
                continue
            f = tf.extractfile(m)
            if f is None:
                continue
            try:
                img = np.array(Image.open(io.BytesIO(f.read())))
            except Exception:
                continue
            xs.append(extract(img))
            ys.append(wind)
            # storm id is the token before the frame number
            sids.append(key.split("_")[-2])
            if limit and len(xs) >= limit:
                break
    return np.vstack(xs), np.array(ys), np.array(sids)


def train(limit: int | None, out_dir: Path) -> dict:
    labels_tar = RAW / "nasa_tropical_storm_competition_train_labels.tar.gz"
    source_tar = RAW / "nasa_tropical_storm_competition_train_source.tar.gz"
    for p in (labels_tar, source_tar):
        if not p.exists():
            raise SystemExit(f"Missing {p}. Download it first (see README §7a).")

    print("Reading labels…")
    labels = _load_labels(labels_tar)
    print(f"  {len(labels)} labelled frames")

    print("Reading images and extracting features…")
    x, y, sids = _load_images(source_tar, labels, limit)
    print(f"  {len(x)} frames · {x.shape[1]} features · {len(set(sids))} storms")

    # Split by storm so no storm appears on both sides
    storms = sorted(set(sids))
    rng = np.random.default_rng(42)
    rng.shuffle(storms)
    n_test = max(1, int(len(storms) * 0.25))
    test_storms = set(storms[:n_test])
    te = np.isin(sids, list(test_storms))
    tr = ~te
    print(f"  train {tr.sum()} frames / {len(storms)-n_test} storms · "
          f"test {te.sum()} frames / {n_test} storms")

    model = HistGradientBoostingRegressor(
        max_iter=500, learning_rate=0.06, max_depth=7,
        min_samples_leaf=20, l2_regularization=1.0,
        random_state=42, early_stopping=True, validation_fraction=0.15,
    )
    model.fit(x[tr], y[tr])

    pred = model.predict(x[te])
    mae = float(np.mean(np.abs(pred - y[te])))
    rmse = float(np.sqrt(np.mean((pred - y[te]) ** 2)))

    # Baseline: predict the training mean for everything
    base = float(np.mean(np.abs(y[te] - y[tr].mean())))

    cat_true = [categorise(v) for v in y[te]]
    cat_pred = [categorise(v) for v in pred]
    cat_acc = float(np.mean([a == b for a, b in zip(cat_true, cat_pred, strict=True)]))
    within_1 = float(
        np.mean(
            [
                abs(_cat_index(a) - _cat_index(b)) <= 1
                for a, b in zip(cat_true, cat_pred, strict=True)
            ]
        )
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, out_dir / "intensity_from_image_v1.joblib")

    report = {
        "model": "intensity_from_image_v1",
        "algorithm": "HistGradientBoostingRegressor over radial IR structure features",
        "dataset": "NASA/Radiant Earth Tropical Cyclone Wind Estimation (CC-BY-4.0)",
        "sensor_note": "Geostationary IR, not INSAT — expect a domain gap on INSAT frames",
        "n_frames": int(len(x)),
        "n_storms": int(len(storms)),
        "split": "by storm (no storm in both train and test)",
        "wind_mae_kt": round(mae, 2),
        "wind_rmse_kt": round(rmse, 2),
        "baseline_mae_kt": round(base, 2),
        "skill_vs_mean_baseline": round((base - mae) / base, 3),
        "category_accuracy": round(cat_acc, 3),
        "category_within_one": round(within_1, 3),
        "features": feature_names(),
    }
    (out_dir / "intensity_model_report.json").write_text(json.dumps(report, indent=2))

    print(f"\n  wind MAE      {mae:.2f} kt   (mean-baseline {base:.2f} kt, "
          f"skill {(base-mae)/base:+.1%})")
    print(f"  wind RMSE     {rmse:.2f} kt")
    print(f"  category acc  {cat_acc:.1%}   within one category {within_1:.1%}")
    print(f"\nSaved to {out_dir}")
    return report


_CAT_ORDER = ["LPA", "D", "DD", "CS", "SCS", "VSCS", "ESCS", "SuCS"]


def _cat_index(c: str) -> int:
    return _CAT_ORDER.index(c) if c in _CAT_ORDER else 0


def main() -> None:
    p = argparse.ArgumentParser(description="Train image-based intensity estimation")
    p.add_argument("--limit", type=int, default=None, help="cap frames (for a quick run)")
    p.add_argument("--out", default=str(CHECKPOINTS))
    args = p.parse_args()
    train(args.limit, Path(args.out))


if __name__ == "__main__":
    main()
