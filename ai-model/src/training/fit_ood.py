"""Fit an out-of-distribution detector for the intensity model.

Motivation, from a real failure: fed a wide-area VIIRS true-colour image — a
different modality from the IR frames it trained on — the model confidently
returned "Deep Depression, 30 kt" for a clear-sky scene with no storm in it. A
threshold on cloud fraction was not enough to catch that.

This fits a Gaussian to the training feature distribution and scores new images
by Mahalanobis distance. Anything far outside the training manifold is reported
as out-of-distribution instead of being given an authoritative-looking number.

    python -m src.training.fit_ood
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import tarfile
from pathlib import Path

import joblib
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.features.image_features import extract  # noqa: E402

RAW = Path("data/raw/nasa_tc")
CHECKPOINTS = Path("models/checkpoints")


def collect_features(sample: int) -> np.ndarray:
    source = RAW / "nasa_tropical_storm_competition_train_source.tar.gz"
    if not source.exists():
        raise SystemExit(f"Missing {source}")

    feats = []
    with tarfile.open(source) as tf:
        for m in tf:
            if not m.name.endswith(".jpg"):
                continue
            f = tf.extractfile(m)
            if f is None:
                continue
            try:
                feats.append(extract(np.array(Image.open(io.BytesIO(f.read())))))
            except Exception:
                continue
            if len(feats) >= sample:
                break
    return np.vstack(feats)


def fit(sample: int, out_dir: Path) -> dict:
    print(f"Extracting features from up to {sample} training frames…")
    x = collect_features(sample)
    print(f"  {x.shape[0]} frames · {x.shape[1]} features")

    mean = x.mean(axis=0)
    # Shrinkage keeps the covariance invertible when features are collinear
    cov = np.cov(x, rowvar=False) + np.eye(x.shape[1]) * 1e-4
    inv_cov = np.linalg.pinv(cov)

    d = x - mean
    dist = np.sqrt(np.einsum("ij,jk,ik->i", d, inv_cov, d))

    # Calibrate the threshold on the training distances themselves
    threshold = float(np.percentile(dist, 99.0))
    stats = {
        "mean": mean,
        "inv_cov": inv_cov,
        "threshold": threshold,
        "train_p50": float(np.percentile(dist, 50)),
        "train_p99": threshold,
        "train_max": float(dist.max()),
        "n_frames": int(x.shape[0]),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(stats, out_dir / "ood_stats.joblib")
    (out_dir / "ood_report.json").write_text(
        json.dumps({k: v for k, v in stats.items() if k not in ("mean", "inv_cov")}, indent=2)
    )

    print(
        f"  median distance {stats['train_p50']:.2f} · p99 {threshold:.2f} · max {stats['train_max']:.2f}"
    )
    print(f"Saved to {out_dir}/ood_stats.joblib")
    return stats


def main() -> None:
    p = argparse.ArgumentParser(description="Fit OOD detector for intensity model")
    p.add_argument("--sample", type=int, default=6000)
    p.add_argument("--out", default=str(CHECKPOINTS))
    args = p.parse_args()
    fit(args.sample, Path(args.out))


if __name__ == "__main__":
    main()
