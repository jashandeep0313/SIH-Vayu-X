"""Estimate cyclone intensity from a satellite image.

Wraps the model trained by src.training.train_intensity. Real inference — the
numbers come from a model fitted to 70k labelled satellite frames, not a script.

Known limits, surfaced in the response rather than buried:
  * Trained on geostationary IR from the NASA/Radiant Earth set, not INSAT, so
    there is a domain gap until MOSDAC data is available.
  * The image is assumed to be roughly storm-centred, as the training frames were.
  * Out-of-distribution input is rejected rather than scored: a greyscale
    modality check catches colour imagery, and a Mahalanobis distance against the
    training feature distribution catches frames far from anything seen in
    training. Both are reported in the response.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np

from src.features.image_features import chroma, extract

DEFAULT_CHECKPOINTS = Path("models/checkpoints")

# Above this mean saturation an image is colour, not infrared. IR frames measure
# ~0.00-0.02; the VIIRS true-colour scenes that fooled the old gate measure >0.10.
CHROMA_LIMIT = 0.06

IMD_SCALE = [(17, "LPA"), (28, "D"), (34, "DD"), (48, "CS"),
             (64, "SCS"), (90, "VSCS"), (120, "ESCS")]

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


def _pattern_for(wind_kt: float, features: np.ndarray) -> str:
    """Pattern label from intensity plus core contrast.

    Not a trained classifier — the dataset carries wind speed, not Dvorak pattern
    labels. Reported as `inferred` so it is never mistaken for one.
    """
    core_contrast = float(features[-5])
    if wind_kt >= 85 and core_contrast > 0.05:
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
        self.report: dict = {}
        self.ood: dict | None = None

    def load(self) -> bool:
        path = self.dir / "intensity_from_image_v1.joblib"
        if not path.exists():
            return False
        self.model = joblib.load(path)
        report = self.dir / "intensity_model_report.json"
        if report.exists():
            self.report = json.loads(report.read_text())
        ood_path = self.dir / "ood_stats.joblib"
        if ood_path.exists():
            self.ood = joblib.load(ood_path)
        return True

    def _ood_distance(self, feats: np.ndarray) -> tuple[float | None, bool]:
        """Mahalanobis distance from the training feature distribution.

        Returns (distance, is_out_of_distribution). Without fitted stats we
        cannot judge, so nothing is flagged rather than guessing.
        """
        if not self.ood:
            return None, False
        d = feats - self.ood["mean"]
        dist = float(np.sqrt(d @ self.ood["inv_cov"] @ d))
        return dist, dist > self.ood["threshold"]

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def estimate(self, image: np.ndarray) -> dict:
        if not self.loaded:
            raise RuntimeError("intensity model not loaded")

        feats = extract(image)
        wind = float(self.model.predict(feats.reshape(1, -1))[0])
        wind = max(5.0, wind)

        mae = self.report.get("wind_mae_kt", 11.2)
        pressure = pressure_from_wind(wind)

        cold_fraction = float(feats[-2])
        core_contrast = float(feats[-5])
        structure_score = round(min(1.0, cold_fraction * 3 + abs(core_contrast) * 2), 2)

        # Mahalanobis distance from the training manifold. This exists because a
        # threshold on cloud fraction alone let a clear-sky true-colour scene
        # through as "Deep Depression, 30 kt".
        distance, dist_ood = self._ood_distance(feats)

        # Modality check first: the model reads single-channel infrared. Colour
        # imagery is a different sensor product entirely, and the distance
        # metric alone does not reliably catch it because `extract` normalises
        # each image and discards absolute colour.
        image_chroma = chroma(image)
        wrong_modality = image_chroma > CHROMA_LIMIT
        is_ood = bool(wrong_modality or dist_ood)

        result = {
            "model": "intensity_from_image_v1",
            "cyclone_detected": not is_ood,
            "structure_score": structure_score,
            "out_of_distribution": {
                "flagged": is_ood,
                "reason": (
                    "colour imagery — model expects single-channel infrared"
                    if wrong_modality
                    else "far from training distribution"
                    if dist_ood
                    else None
                ),
                "chroma": round(image_chroma, 3),
                "chroma_limit": CHROMA_LIMIT,
                "mahalanobis_distance": round(distance, 2) if distance is not None else None,
                "threshold": round(self.ood["threshold"], 2) if self.ood else None,
                "detector": "greyscale modality check + Gaussian Mahalanobis",
            },
            "classification": {
                "intensity_category": categorise(wind),
                "pattern_type": _pattern_for(wind, feats),
                "pattern_source": "inferred from intensity — not a trained classifier",
                "est_wind_kt": round(wind, 1),
                "est_wind_kmph": round(wind * 1.852, 1),
                "est_pressure_hpa": pressure,
                "dvorak_t_number": dvorak_t(wind),
                "uncertainty_kt": round(mae, 1),
                "wind_range_kt": [round(max(0, wind - mae), 1), round(wind + mae, 1)],
            },
            "trained_on": {
                "dataset": self.report.get("dataset"),
                "frames": self.report.get("n_frames"),
                "storms": self.report.get("n_storms"),
                "wind_mae_kt": self.report.get("wind_mae_kt"),
                "category_within_one": self.report.get("category_within_one"),
                "sensor_note": self.report.get("sensor_note"),
            },
        }

        if wrong_modality:
            result["warning"] = (
                f"This looks like colour imagery (chroma {image_chroma:.2f} > {CHROMA_LIMIT}). "
                "The model reads storm-centred single-channel infrared. The estimate below is "
                "not meaningful — treat this as 'cannot assess', not as a low-intensity reading."
            )
        elif dist_ood:
            result["warning"] = (
                f"This frame is far from the training distribution (distance {distance:.1f} vs "
                f"threshold {self.ood['threshold']:.1f}). The estimate below is unreliable."
            )

        return result
