"""Train intensity estimation from satellite imagery.

Data: NASA / Radiant Earth "Tropical Cyclone Wind Estimation" competition set —
geostationary IR imagery paired with best-track wind speed. Public, CC-BY-4.0,
no credentials.

This is the image half of PS 26070 made real. It is *not* INSAT data: the task
is identical (estimate intensity from satellite IR) but the sensor differs, so
treat it as a transferable baseline until MOSDAC access lands, and expect a
domain gap on INSAT frames.

Trains four things from one feature pass:
  * a wind regressor (point estimate, kt)
  * 10th/90th quantile regressors, giving a real prediction interval rather
    than a made-up confidence number
  * a category classifier over the IMD scale, giving genuine per-class
    probabilities that sum to 100
  * OOD statistics, so out-of-distribution input is refused rather than scored

Splits are by storm, never by frame. Consecutive frames of one storm are nearly
identical, so a random split would leak and report a fantasy score.

The regressors are trained with inverse-frequency sample weights (see
`severity_weights`). Without them the model regresses to the mean and
under-reads the severe storms this system exists to warn about.

    python -m src.training.train_intensity
    python -m src.training.train_intensity --refresh-cache
    python -m src.training.train_intensity --severity-weight 0   # unweighted
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
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    IsolationForest,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.features.image_features import (  # noqa: E402
    FEATURE_VERSION,
    extract,
    feature_names,
)

RAW = Path("data/raw/nasa_tc")
CHECKPOINTS = Path("models/checkpoints")
CACHE = Path("data/processed/nasa_tc_features.npz")

IMD_SCALE = [
    (17, "LPA"),
    (28, "D"),
    (34, "DD"),
    (48, "CS"),
    (64, "SCS"),
    (90, "VSCS"),
    (120, "ESCS"),
]
CAT_ORDER = ["LPA", "D", "DD", "CS", "SCS", "VSCS", "ESCS", "SuCS"]

TARGET_COVERAGE = 0.80

# Damping exponent for the inverse-frequency sample weights. 0 = unweighted,
# 1 = full inverse frequency. 0.5 was chosen by measurement, not taste: on the
# held-out storms it cut severe-storm (>=90 kt) MAE from 17.3 to 16.2 kt and
# bias from -14.1 to -12.6 kt, for 0.15 kt on the headline MAE. Going to 1.0
# bought almost nothing more (16.1 kt) and cost 0.8 kt overall.
SEVERITY_WEIGHT = 0.5
WEIGHT_BIN_KT = 10


def severity_weights(wind_kt: np.ndarray, alpha: float = SEVERITY_WEIGHT) -> np.ndarray:
    """Inverse-frequency weights over wind bins, damped by `alpha`.

    The training set is dominated by moderate storms — ~11.7k CS frames against
    ~1.0k SuCS — so a plain least-squares fit minimises its loss by pulling
    every prediction toward the middle. That is textbook regression to the mean,
    and here it points the wrong way: it under-reads the most dangerous storms
    by 13-16 kt while over-reading weak ones. Weighting rare intensities up
    trades a little average accuracy for accuracy where the cost of being wrong
    is highest.

    Returns weights normalised to mean 1.0, so `max_iter` and the learning rate
    keep behaving as they did unweighted.
    """
    if alpha <= 0:
        return np.ones(len(wind_kt))
    bins = np.clip((wind_kt // WEIGHT_BIN_KT).astype(int), 0, None)
    counts = np.bincount(bins).astype(float)
    counts[counts == 0] = 1.0
    w = (counts.max() / counts[bins]) ** alpha
    return w / w.mean()


def categorise(wind_kt: float) -> str:
    for limit, code in IMD_SCALE:
        if wind_kt < limit:
            return code
    return "SuCS"


def _cat_index(c: str) -> int:
    return CAT_ORDER.index(c) if c in CAT_ORDER else 0


def _load_labels(tar_path: Path) -> dict[str, float]:
    out: dict[str, float] = {}
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
            if wind is not None:
                out[Path(m.name).parent.name.replace("_labels_", "_source_")] = float(wind)
    return out


def _extract_all(limit: int | None):
    """One pass over the tarball, extracting features for every labelled frame."""
    from PIL import Image

    labels = _load_labels(RAW / "nasa_tropical_storm_competition_train_labels.tar.gz")
    print(f"  {len(labels)} labelled frames")

    xs, ys, sids = [], [], []
    with tarfile.open(RAW / "nasa_tropical_storm_competition_train_source.tar.gz") as tf:
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
                xs.append(extract(np.array(Image.open(io.BytesIO(f.read())))))
            except Exception:
                continue
            ys.append(wind)
            sids.append(key.split("_")[-2])
            if len(xs) % 10000 == 0:
                print(f"    {len(xs)} frames…")
            if limit and len(xs) >= limit:
                break
    return np.vstack(xs), np.array(ys), np.array(sids)


def load_features(limit: int | None, refresh: bool):
    if CACHE.exists() and not refresh:
        d = np.load(CACHE, allow_pickle=True)
        if d.get("feature_version", FEATURE_VERSION) == FEATURE_VERSION:
            print(f"Using cached features from {CACHE}")
            return d["x"], d["y"], d["sids"]
        print("Cached features are a different version — re-extracting")

    print("Extracting features (one pass over the tarball)…")
    x, y, sids = _extract_all(limit)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(CACHE, x=x, y=y, sids=sids, feature_version=FEATURE_VERSION)
    print(f"  cached -> {CACHE}")
    return x, y, sids


def train(
    limit: int | None,
    out_dir: Path,
    refresh: bool,
    test_frac: float = 0.20,
    severity_weight: float = SEVERITY_WEIGHT,
) -> dict:
    for p in (
        RAW / "nasa_tropical_storm_competition_train_labels.tar.gz",
        RAW / "nasa_tropical_storm_competition_train_source.tar.gz",
    ):
        if not p.exists():
            raise SystemExit(f"Missing {p}. See README §7a for the download command.")

    x, y, sids = load_features(limit, refresh)
    print(f"  {len(x)} frames · {x.shape[1]} features · {len(set(sids))} storms")

    # Three-way split *by storm*: fit / calibrate / test. The calibration split
    # exists only to conformalise the interval — using the test split for that
    # would be self-fulfilling.
    storms = sorted(set(sids))
    rng = np.random.default_rng(42)
    rng.shuffle(storms)
    n_test = max(1, int(len(storms) * test_frac))
    n_cal = max(1, int(len(storms) * 0.15))
    test_storms = set(storms[:n_test])
    cal_storms = set(storms[n_test : n_test + n_cal])
    te = np.isin(sids, list(test_storms))
    cal = np.isin(sids, list(cal_storms))
    tr = ~(te | cal)
    print(
        f"  fit {tr.sum()} / {len(storms) - n_test - n_cal} storms · "
        f"calib {cal.sum()} / {n_cal} · test {te.sum()} / {n_test}  "
        f"(test_frac={test_frac:.0%})"
    )

    common = {
        "max_iter": 700,
        "learning_rate": 0.05,
        "max_depth": 8,
        "min_samples_leaf": 20,
        "l2_regularization": 1.0,
        "random_state": 42,
        "early_stopping": True,
        "validation_fraction": 0.15,
    }

    # Same weights for the point and quantile models. Weighting only the point
    # model would shift it relative to its own interval and let the estimate
    # fall outside the band it is reported with.
    sw = severity_weights(y[tr], severity_weight)
    print(
        f"\nSeverity weighting alpha={severity_weight} "
        f"(weight range {sw.min():.2f}-{sw.max():.2f})"
    )

    print("Training wind regressor…")
    reg = HistGradientBoostingRegressor(**common)
    reg.fit(x[tr], y[tr], sample_weight=sw)

    print("Training quantile regressors (p10 / p90) for prediction intervals…")
    q_lo = HistGradientBoostingRegressor(loss="quantile", quantile=0.10, **common)
    q_lo.fit(x[tr], y[tr], sample_weight=sw)
    q_hi = HistGradientBoostingRegressor(loss="quantile", quantile=0.90, **common)
    q_hi.fit(x[tr], y[tr], sample_weight=sw)

    # Conformalised quantile regression (Romano et al. 2019): widen the interval
    # by the (1-alpha) quantile of the conformity score measured on calibration
    # storms, so empirical coverage matches the nominal level. Raw quantile
    # models are over-confident — an earlier run advertised 80% and delivered 66%.
    # The conformity scores stay unweighted on purpose: coverage is a promise
    # about the real distribution of frames, not the reweighted one.
    cal_lo, cal_hi = q_lo.predict(x[cal]), q_hi.predict(x[cal])
    scores = np.maximum(cal_lo - y[cal], y[cal] - cal_hi)
    n_scores = len(scores)
    level = min(1.0, np.ceil((n_scores + 1) * TARGET_COVERAGE) / n_scores)
    conformal_pad = float(np.quantile(scores, level))
    print(f"  conformal padding {conformal_pad:+.2f} kt (target {TARGET_COVERAGE:.0%})")

    print("Training category classifier…")
    # Deliberately *not* weighted. Measured on the same held-out storms, the
    # weighted classifier was a wash — identical accuracy (43.6%) and
    # within-one (85.4% vs 85.3%), +1.0pp severe recall bought at +1.4pp severe
    # false alarms. Its cross-entropy loss is already per-class, so it does not
    # suffer the regression-to-the-mean the squared-error regressor does. Left
    # unweighted so the reported probabilities stay honest frequencies.
    y_cat = np.array([_cat_index(categorise(v)) for v in y])
    clf = HistGradientBoostingClassifier(**common)
    clf.fit(x[tr], y_cat[tr])

    # ---- evaluate ----
    pred = reg.predict(x[te])
    raw_lo, raw_hi = q_lo.predict(x[te]), q_hi.predict(x[te])
    lo, hi = raw_lo - conformal_pad, raw_hi + conformal_pad
    mae = float(np.mean(np.abs(pred - y[te])))
    rmse = float(np.sqrt(np.mean((pred - y[te]) ** 2)))
    base = float(np.mean(np.abs(y[te] - y[tr].mean())))
    raw_cov = float(np.mean((y[te] >= raw_lo) & (y[te] <= raw_hi)))
    coverage = float(np.mean((y[te] >= lo) & (y[te] <= hi)))
    interval = float(np.mean(hi - lo))

    cat_pred = clf.predict(x[te])
    cat_acc = float(np.mean(cat_pred == y_cat[te]))
    within_1 = float(np.mean(np.abs(cat_pred - y_cat[te]) <= 1))
    proba = clf.predict_proba(x[te])
    top_conf = float(np.mean(proba.max(axis=1)))

    # Per-category error. The headline MAE averages over a set dominated by
    # moderate storms and hides how the model behaves at the extremes, which is
    # exactly where a warning system's errors matter. Reported so the weakness
    # is visible in the artefact rather than only in whoever ran the notebook.
    per_category = {}
    for code in CAT_ORDER:
        m = np.array([categorise(v) == code for v in y[te]])
        if m.sum() == 0:
            continue
        per_category[code] = {
            "n": int(m.sum()),
            "mae_kt": round(float(np.mean(np.abs(pred[m] - y[te][m]))), 2),
            "bias_kt": round(float(np.mean(pred[m] - y[te][m])), 2),
        }
    severe = y[te] >= 90
    severe_mae = float(np.mean(np.abs(pred[severe] - y[te][severe]))) if severe.any() else None
    severe_bias = float(np.mean(pred[severe] - y[te][severe])) if severe.any() else None
    # How often the point estimate lands outside its own reported interval —
    # weighting the point and quantile models differently would break this.
    outside = float(np.mean((pred < lo) | (pred > hi)))

    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(reg, out_dir / "intensity_from_image_v2.joblib")
    joblib.dump(q_lo, out_dir / "intensity_q10_v2.joblib")
    joblib.dump(q_hi, out_dir / "intensity_q90_v2.joblib")
    joblib.dump({"model": clf, "classes": CAT_ORDER}, out_dir / "category_classifier_v2.joblib")

    # ---- novelty detection ----
    print("Fitting novelty detector…")
    iso = IsolationForest(
        n_estimators=300, contamination=0.01, random_state=42, n_jobs=-1
    ).fit(x[tr])
    # p0.05, not p0.5: the texture gate below already catches every adversarial
    # input tried, so a tight isolation threshold only costs false refusals on
    # genuinely rare weak systems (an LPA frame was being rejected at p0.5).
    # Isolation stays as a backstop for inputs the other gates miss.
    iso_threshold = float(np.percentile(iso.score_samples(x[tr]), 0.05))

    # Per-feature training envelope. Mahalanobis measures distance from the
    # centre, so inputs that sit near the mean in aggregate slip through even
    # when individual features are physically impossible — random noise is 3x
    # too rough, a linear ramp is perfectly smooth. Counting features outside
    # the envelope catches both, and is interpretable when it fires.
    env_lo = np.percentile(x[tr], 0.1, axis=0)
    env_hi = np.percentile(x[tr], 99.9, axis=0)

    def _outside(mat):
        return ((mat < env_lo) | (mat > env_hi)).sum(axis=1)

    # Calibrate the allowed count so genuine frames almost never trip it
    env_threshold = int(max(3, np.percentile(_outside(x[tr]), 99.9)))

    # Targeted texture gate. The broad envelope above has to stay loose (genuine
    # frames put up to ~15 features outside it), which is too loose to catch
    # inputs that are merely *near* the mean. Local gradient statistics do not
    # have that problem: real cloud imagery occupies a narrow band of roughness,
    # while noise is far too rough and a synthetic ramp far too smooth. This
    # single check catches every adversarial input tried at ~0.2% false positives.
    names = feature_names()
    texture_idx = [names.index(n) for n in ("grad_mean", "grad_std", "grad_p90")]
    tex_lo = np.percentile(x[tr][:, texture_idx], 0.05, axis=0)
    tex_hi = np.percentile(x[tr][:, texture_idx], 99.95, axis=0)

    mean = x[tr].mean(axis=0)
    cov = np.cov(x[tr], rowvar=False) + np.eye(x.shape[1]) * 1e-4
    inv_cov = np.linalg.pinv(cov)
    d = x[tr] - mean
    dist = np.sqrt(np.einsum("ij,jk,ik->i", d, inv_cov, d))
    # p99.9, not the raw max: the max is set by one outlier frame and leaves the
    # gate so loose that unrelated images sail through.
    maha_threshold = float(np.percentile(dist, 99.9))
    te_dist = np.sqrt(np.einsum("ij,jk,ik->i", x[te] - mean, inv_cov, x[te] - mean))
    tex_out = (
        (x[te][:, texture_idx] < tex_lo) | (x[te][:, texture_idx] > tex_hi)
    ).any(axis=1)
    fp_rate = float(
        np.mean(
            (te_dist > maha_threshold)
            | (iso.score_samples(x[te]) < iso_threshold)
            | (_outside(x[te]) > env_threshold)
            | tex_out
        )
    )
    tex_fp = float(np.mean(tex_out))

    joblib.dump(
        {
            "mean": mean,
            "inv_cov": inv_cov,
            "threshold": maha_threshold,
            "iso": iso,
            "iso_threshold": iso_threshold,
            "env_lo": env_lo,
            "env_hi": env_hi,
            "env_threshold": env_threshold,
            "texture_idx": texture_idx,
            "texture_lo": tex_lo,
            "texture_hi": tex_hi,
            "conformal_pad": conformal_pad,
            "target_coverage": TARGET_COVERAGE,
            "train_p50": float(np.percentile(dist, 50)),
            "train_p999": maha_threshold,
            "train_max": float(dist.max()),
            "n_frames": int(tr.sum()),
            "feature_version": FEATURE_VERSION,
        },
        out_dir / "ood_stats.joblib",
    )

    report = {
        "model": "intensity_from_image_v2",
        "feature_version": FEATURE_VERSION,
        "n_features": int(x.shape[1]),
        "algorithm": "HistGradientBoosting over radial IR structure features",
        "dataset": "NASA/Radiant Earth Tropical Cyclone Wind Estimation (CC-BY-4.0)",
        "sensor_note": "Geostationary IR, not INSAT — expect a domain gap on INSAT frames",
        "n_frames": int(len(x)),
        "n_storms": int(len(storms)),
        "split": f"by storm · fit/calib/test = "
                 f"{len(storms) - n_test - n_cal}/{n_cal}/{n_test} storms",
        "test_fraction": test_frac,
        "wind_mae_kt": round(mae, 2),
        "wind_rmse_kt": round(rmse, 2),
        "baseline_mae_kt": round(base, 2),
        "skill_vs_mean_baseline": round((base - mae) / base, 3),
        "severity_weight_alpha": severity_weight,
        "per_category_error": per_category,
        "severe_mae_kt": round(severe_mae, 2) if severe_mae is not None else None,
        "severe_bias_kt": round(severe_bias, 2) if severe_bias is not None else None,
        "severe_note": (
            "Severe = observed >= 90 kt (ESCS/SuCS). Single-channel IR saturates "
            "once cloud tops reach the tropopause, so intensity is systematically "
            "under-read at the top of the scale — the same ceiling the Dvorak "
            "technique has. Resolving it needs passive microwave, not a better "
            "regressor."
        ),
        "point_estimate_outside_interval": round(outside, 4),
        "interval_target_coverage": TARGET_COVERAGE,
        "interval_coverage_raw": round(raw_cov, 3),
        "interval_coverage_conformal": round(coverage, 3),
        "interval_width_kt": round(interval, 1),
        "conformal_pad_kt": round(conformal_pad, 2),
        "novelty_false_positive_rate": round(fp_rate, 4),
        "novelty_envelope_threshold": env_threshold,
        "novelty_texture_false_positive_rate": round(tex_fp, 5),
        "category_accuracy": round(cat_acc, 3),
        "category_within_one": round(within_1, 3),
        "mean_top_class_probability": round(top_conf, 3),
        "categories": CAT_ORDER,
        "features": feature_names(),
    }
    (out_dir / "intensity_model_report.json").write_text(json.dumps(report, indent=2))

    print(f"\n  wind MAE       {mae:.2f} kt  (baseline {base:.2f}, skill {(base-mae)/base:+.1%})")
    print(f"  wind RMSE      {rmse:.2f} kt")
    print(f"  interval        raw {raw_cov:.1%} -> conformal {coverage:.1%} "
          f"(target {TARGET_COVERAGE:.0%}), width {interval:.1f} kt")
    print(f"  novelty         FP {fp_rate:.2%} overall · texture gate FP {tex_fp:.3%}")
    print(f"  category acc   {cat_acc:.1%}   within one {within_1:.1%}")
    if severe_mae is not None:
        print(f"  severe >=90kt  MAE {severe_mae:.1f} kt  bias {severe_bias:+.1f} kt")
    print("\n  per-category error (the headline MAE hides this):")
    for code, s in per_category.items():
        print(f"    {code:5} n={s['n']:5}  MAE {s['mae_kt']:5.1f}  bias {s['bias_kt']:+6.1f}")
    print(f"\nSaved to {out_dir}")
    return report


def main() -> None:
    p = argparse.ArgumentParser(description="Train image-based intensity estimation")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--out", default=str(CHECKPOINTS))
    p.add_argument("--refresh-cache", action="store_true")
    p.add_argument("--test-frac", type=float, default=0.20,
                   help="fraction of storms held out for test (0.20 = 80/20)")
    p.add_argument("--severity-weight", type=float, default=SEVERITY_WEIGHT,
                   help="inverse-frequency weighting damping; 0 disables it")
    args = p.parse_args()
    train(args.limit, Path(args.out), args.refresh_cache, args.test_frac,
          args.severity_weight)


if __name__ == "__main__":
    main()
