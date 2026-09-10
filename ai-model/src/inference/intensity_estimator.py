"""Estimate cyclone intensity from a satellite image.

Wraps the models trained by src.training.train_intensity. Real inference — every
number comes from a model fitted to ~70k labelled satellite frames.

Where each number in the response comes from:
  * `est_wind_kt`      — regression over radial IR structure features
  * `wind_range_kt`    — 10th/90th quantile models, a real prediction interval
  * `category_probabilities` — a trained classifier over the IMD scale, reported
    0-100 and summing to 100
  * `confidence_pct`   — top class probability, tempered by how wide the
    prediction interval is. Not a decorative number.
  * `out_of_distribution` — greyscale modality check plus Mahalanobis distance

Known limits, surfaced rather than buried:
  * Trained on geostationary IR (NASA/Radiant Earth), not INSAT, so a sensor
    domain gap remains until MOSDAC access lands.
  * Intense storms are under-read. IR brightness saturates once cloud tops hit
    the tropopause, so a 100 kt and a 140 kt eyewall look much alike — the same
    ceiling the Dvorak technique has had since the 1970s, which is why
    operational centres bring in passive microwave. Inverse-frequency training
    weights reduce it; they cannot remove it. Estimates at VSCS and above carry
    an explicit `intensity_caveat` saying so.
  * The frame is assumed roughly storm-centred, as the training frames were.
  * Pattern type is inferred from intensity and eye signature, not learned — the
    dataset carries wind speed, not Dvorak pattern labels.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np

from src.features.image_features import chroma, extract

DEFAULT_CHECKPOINTS = Path("models/checkpoints")

# Above this mean saturation an image is colour, not infrared. IR frames measure
# ~0.00-0.02; the VIIRS true-colour scenes that fooled an earlier gate measure >0.09.
CHROMA_LIMIT = 0.06

IMD_SCALE = [(17, "LPA"), (28, "D"), (34, "DD"), (48, "CS"),
             (64, "SCS"), (90, "VSCS"), (120, "ESCS")]
CAT_ORDER = ["LPA", "D", "DD", "CS", "SCS", "VSCS", "ESCS", "SuCS"]

_DVORAK_CI = [(1.0, 25), (2.0, 30), (2.5, 35), (3.0, 45), (3.5, 55), (4.0, 65),
              (4.5, 77), (5.0, 90), (5.5, 102), (6.0, 115), (6.5, 127), (7.0, 140),
              (7.5, 155), (8.0, 170)]


def categorise(wind_kt: float) -> str:
    for limit, code in IMD_SCALE:
        if wind_kt < limit:
            return code
    return "SuCS"


def dvorak_t(wind_kt: float) -> float:
    if wind_kt <= _DVORAK_CI[0][1]:
        return _DVORAK_CI[0][0]
    for (t_lo, v_lo), (t_hi, v_hi) in zip(_DVORAK_CI, _DVORAK_CI[1:], strict=False):
        if wind_kt <= v_hi:
            return round(t_lo + (wind_kt - v_lo) / (v_hi - v_lo) * (t_hi - t_lo), 1)
    return 8.0


def pressure_from_wind(wind_kt: float) -> float:
    return round(max(870.0, 1010 - (wind_kt / 6.7) ** (1 / 0.644)), 1)


def _pattern_for(wind_kt: float, eye_signature: float) -> str:
    """Pattern label from intensity plus the eye-signature feature.

    Not a trained classifier — the dataset carries wind speed, not Dvorak pattern
    labels. Always reported with `pattern_source` so it cannot be mistaken for one.
    """
    if wind_kt >= 85 and eye_signature > 0.02:
        return "eye"
    if wind_kt >= 64:
        return "banding_eye"
    if wind_kt >= 45:
        return "CDO"
    if wind_kt >= 30:
        return "curved_band"
    return "shear"


class IntensityEstimator:
    def __init__(self, checkpoint_dir: str | Path = DEFAULT_CHECKPOINTS) -> None:
        self.dir = Path(checkpoint_dir)
        self.model = None
        self.q_lo = None
        self.q_hi = None
        self.classifier = None
        self.classes: list[str] = CAT_ORDER
        self.report: dict = {}
        self.ood: dict | None = None
        self.version = "none"

    def load(self) -> bool:
        """Load v2 if present, else fall back to the v1 regressor."""
        v2 = self.dir / "intensity_from_image_v2.joblib"
        v1 = self.dir / "intensity_from_image_v1.joblib"

        if v2.exists():
            self.model = joblib.load(v2)
            self.version = "intensity_from_image_v2"
            for attr, name in (("q_lo", "intensity_q10_v2.joblib"),
                               ("q_hi", "intensity_q90_v2.joblib")):
                p = self.dir / name
                if p.exists():
                    setattr(self, attr, joblib.load(p))
            clf_path = self.dir / "category_classifier_v2.joblib"
            if clf_path.exists():
                bundle = joblib.load(clf_path)
                self.classifier = bundle["model"]
                self.classes = bundle.get("classes", CAT_ORDER)
        elif v1.exists():
            self.model = joblib.load(v1)
            self.version = "intensity_from_image_v1"
        else:
            return False

        report = self.dir / "intensity_model_report.json"
        if report.exists():
            self.report = json.loads(report.read_text())
        ood_path = self.dir / "ood_stats.joblib"
        if ood_path.exists():
            self.ood = joblib.load(ood_path)
        return True

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def _novelty(self, feats: np.ndarray) -> dict:
        """Is this frame anything like the training data?

        Two independent detectors, because either alone lets things through:
        Mahalanobis catches frames far from the distribution's centre, and an
        IsolationForest catches ones that sit in a hole inside it. Either firing
        is enough to refuse the image.
        """
        if not self.ood or len(self.ood["mean"]) != len(feats):
            return {"distance": None, "iso_score": None, "flagged": False}

        d = feats - self.ood["mean"]
        dist = float(np.sqrt(d @ self.ood["inv_cov"] @ d))
        too_far = dist > self.ood["threshold"]

        iso_score = None
        iso_flag = False
        iso = self.ood.get("iso")
        if iso is not None:
            iso_score = float(iso.score_samples(feats.reshape(1, -1))[0])
            iso_flag = iso_score < self.ood.get("iso_threshold", -np.inf)

        # Texture gate: real cloud imagery occupies a narrow band of local
        # roughness. Noise is far too rough, a synthetic ramp far too smooth —
        # and both sit near the distribution mean, so distance alone misses them.
        tex_flag = False
        idx = self.ood.get("texture_idx")
        if idx is not None:
            v = feats[idx]
            tex_flag = bool(
                ((v < self.ood["texture_lo"]) | (v > self.ood["texture_hi"])).any()
            )

        return {
            "distance": dist,
            "iso_score": iso_score,
            "flagged": bool(too_far or iso_flag or tex_flag),
            "by_distance": bool(too_far),
            "by_isolation": bool(iso_flag),
            "by_texture": tex_flag,
        }

    def estimate(self, image: np.ndarray) -> dict:
        if not self.loaded:
            raise RuntimeError("intensity model not loaded")

        feats = extract(image)
        wind = max(5.0, float(self.model.predict(feats.reshape(1, -1))[0]))
        pressure = pressure_from_wind(wind)

        # Prediction interval from the quantile models, falling back to the
        # reported test MAE when they are unavailable.
        mae = self.report.get("wind_mae_kt", 11.0)
        if self.q_lo is not None and self.q_hi is not None:
            lo = float(self.q_lo.predict(feats.reshape(1, -1))[0])
            hi = float(self.q_hi.predict(feats.reshape(1, -1))[0])
            lo, hi = min(lo, hi), max(lo, hi)
            # Conformal padding calibrated on held-out storms, so the advertised
            # coverage is the coverage actually delivered.
            pad = (self.ood or {}).get("conformal_pad", 0.0)
            lo, hi = lo - pad, hi + pad
        else:
            lo, hi = wind - mae, wind + mae
        lo = max(0.0, lo)
        # The point and quantile models are separate fits, so nothing forces the
        # estimate inside its own band. It is rare, but "92 kt (range 60-88)" is
        # indefensible on a bulletin, so widen the band rather than move the
        # estimate — the interval is the softer claim of the two.
        lo, hi = min(lo, wind), max(hi, wind)
        interval = hi - lo

        if self.classifier is not None:
            proba = self.classifier.predict_proba(feats.reshape(1, -1))[0]
            probs = {c: 0.0 for c in self.classes}
            for slot, cls_idx in enumerate(self.classifier.classes_):
                probs[self.classes[int(cls_idx)]] = float(proba[slot]) * 100.0
            top_category = max(probs, key=probs.get)
        else:
            top_category = categorise(wind)
            probs = {c: 0.0 for c in self.classes}
            probs[top_category] = 100.0

        # Round to 0.1 and absorb drift into the top class so the set reads 100.0
        probs = {k: round(v, 1) for k, v in probs.items()}
        probs[top_category] = round(probs[top_category] + (100.0 - sum(probs.values())), 1)
        top_prob = probs[top_category]

        # Confidence: the classifier's own certainty, tempered by how wide the
        # regression interval is. A wide interval means an ambiguous image even
        # when one class happens to lead.
        spread_penalty = min(1.0, interval / 60.0)
        confidence_pct = int(round(min(99.0, max(1.0, top_prob * (1.0 - 0.35 * spread_penalty)))))

        eye_sig = float(feats[-11]) if len(feats) > 11 else 0.0
        nov = self._novelty(feats)
        distance = nov["distance"]
        image_chroma = chroma(image)
        wrong_modality = image_chroma > CHROMA_LIMIT
        is_ood = bool(wrong_modality or nov["flagged"])

        result = {
            "model": self.version,
            "cyclone_detected": not is_ood,
            "confidence_pct": confidence_pct,
            "out_of_distribution": {
                "flagged": is_ood,
                "reason": (
                    "colour imagery — model expects single-channel infrared"
                    if wrong_modality
                    else "image texture is unlike satellite cloud imagery"
                    if nov.get("by_texture")
                    else "does not resemble a satellite cyclone frame"
                    if nov["flagged"]
                    else None
                ),
                "chroma": round(image_chroma, 3),
                "chroma_limit": CHROMA_LIMIT,
                "mahalanobis_distance": round(distance, 2) if distance is not None else None,
                "threshold": round(self.ood["threshold"], 2) if self.ood else None,
                "isolation_score": round(nov["iso_score"], 3) if nov["iso_score"] is not None else None,
                "triggered_by": [
                    k for k, v in (
                        ("chroma", wrong_modality),
                        ("distance", nov.get("by_distance")),
                        ("isolation", nov.get("by_isolation")),
                        ("texture", nov.get("by_texture")),
                    ) if v
                ],
                "detector": "greyscale modality check + Mahalanobis + IsolationForest",
            },
            "classification": {
                "intensity_category": top_category,
                "category_probability_pct": top_prob,
                "category_probabilities": probs,
                "pattern_type": _pattern_for(wind, eye_sig),
                "pattern_source": "inferred from intensity and eye signature — not a trained classifier",
                "est_wind_kt": round(wind, 1),
                "est_wind_kmph": round(wind * 1.852, 1),
                "est_pressure_hpa": pressure,
                "dvorak_t_number": dvorak_t(wind),
                "wind_range_kt": [round(lo, 1), round(hi, 1)],
                "interval_width_kt": round(interval, 1),
                "interval_source": "p10/p90 quantile models"
                if self.q_lo is not None
                else "test-set MAE",
            },
            "trained_on": {
                "dataset": self.report.get("dataset"),
                "frames": self.report.get("n_frames"),
                "storms": self.report.get("n_storms"),
                "wind_mae_kt": self.report.get("wind_mae_kt"),
                "category_accuracy": self.report.get("category_accuracy"),
                "category_within_one": self.report.get("category_within_one"),
                "interval_coverage": self.report.get("interval_coverage_p10_p90"),
                "sensor_note": self.report.get("sensor_note"),
                # Per-category error travels with the estimate: a 10 kt headline
                # MAE is an average over a set dominated by moderate storms and
                # overstates accuracy at both ends of the scale.
                "per_category_error": self.report.get("per_category_error"),
                "severe_mae_kt": self.report.get("severe_mae_kt"),
                "severe_bias_kt": self.report.get("severe_bias_kt"),
            },
        }

        # Known directional error, surfaced on the reading it applies to. IR
        # brightness saturates once cloud tops reach the tropopause, so the top
        # of the scale is compressed and intense storms are under-read — on the
        # held-out storms, by ~13 kt at ESCS and ~16 kt at SuCS. For a warning
        # system that is the dangerous direction, so it is stated rather than
        # silently absorbed into the interval.
        if not is_ood and wind >= 64:
            band = self.report.get("per_category_error", {}).get(top_category, {})
            result["classification"]["intensity_caveat"] = (
                "Infrared saturates at the top of the scale, so the model tends to "
                "under-read intense systems. Treat this estimate as a lower bound; "
                "the true intensity may sit above the upper end of the range."
                + (
                    f" Measured bias for {top_category} on held-out storms: "
                    f"{band['bias_kt']:+.1f} kt (MAE {band['mae_kt']:.1f} kt)."
                    if band
                    else ""
                )
            )

        if wrong_modality:
            result["warning"] = (
                f"This looks like colour imagery (chroma {image_chroma:.2f} > {CHROMA_LIMIT}). "
                "The model reads storm-centred single-channel infrared. The estimate below is "
                "not meaningful — treat this as 'cannot assess', not as a low-intensity reading."
            )
        elif nov["flagged"]:
            result["warning"] = (
                "This image does not resemble a satellite cyclone frame "
                f"(distance {distance:.1f} vs threshold {self.ood['threshold']:.1f}). "
                "No intensity is reported — the model declined to score it rather than "
                "returning a confident-looking guess."
            )

        # When refused, strip the estimate. Returning a category and a wind speed
        # alongside "cannot assess" invites someone to read the number anyway.
        if is_ood:
            result["confidence_pct"] = None
            result["classification"] = None

        return result
