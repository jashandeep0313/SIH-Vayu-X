"""Checkpoint registry for the inference service.

Loads models once at startup rather than per request, and records which version
answered each call so every prediction is traceable to a specific checkpoint.

The track/intensity predictor is real: gradient-boosted models fitted to IBTrACS
best-track data by src.training.train_track. The identification and
classification models are still unbuilt — they need INSAT imagery, which needs
MOSDAC credentials.
"""

import os
from pathlib import Path
from typing import Any


class ModelRegistry:
    def __init__(self) -> None:
        self.device: str = os.getenv("MODEL_DEVICE", "cpu")
        self.checkpoint_dir: str = os.getenv("MODEL_CHECKPOINT_DIR", "models/checkpoints")
        self._models: dict[str, Any] = {}
        self._versions: dict[str, str] = {
            "identification": os.getenv("IDENTIFICATION_MODEL", "not-trained"),
            "classification": os.getenv("CLASSIFICATION_MODEL", "not-trained"),
            "prediction": os.getenv("PREDICTION_MODEL", "track_hgbr_ibtracs_v1"),
        }

    def load_all(self) -> None:
        """Load every available checkpoint.

        A missing checkpoint is skipped rather than fatal — the service must still
        start so /health can report which tasks are unavailable.
        """
        try:
            from src.inference.track_predictor import TrackPredictor

            predictor = TrackPredictor(self.checkpoint_dir)
            if predictor.load():
                self._models["prediction"] = predictor
        except Exception as exc:  # noqa: BLE001 - degraded start beats no start
            print(f"[registry] track predictor unavailable: {exc}")

        try:
            from src.inference.intensity_estimator import IntensityEstimator

            estimator = IntensityEstimator(self.checkpoint_dir)
            if estimator.load():
                self._models["intensity"] = estimator
        except Exception as exc:  # noqa: BLE001
            print(f"[registry] intensity estimator unavailable: {exc}")

        # TODO(ml): cyclone *localisation* still needs INSAT full-disk frames

    def unload_all(self) -> None:
        self._models.clear()

    def get(self, task: str) -> Any:
        if task not in self._models:
            raise KeyError(f"Model for task '{task}' is not loaded")
        return self._models[task]

    def has(self, task: str) -> bool:
        return task in self._models

    def loaded_names(self) -> list[str]:
        return list(self._models.keys())

    def describe(self) -> dict:
        predictor = self._models.get("prediction")
        report = getattr(predictor, "report", {}) if predictor else {}
        return {
            "device": self.device,
            "checkpoint_dir": self.checkpoint_dir,
            "versions": self._versions,
            "loaded": self.loaded_names(),
            "prediction": {
                "trained": bool(predictor),
                "leads": getattr(predictor, "available_leads", []),
                "training_data": "IBTrACS v04r01 (North Indian Ocean)",
                "train_seasons": report.get("train_seasons"),
                "test_seasons": report.get("test_seasons"),
                "storms": report.get("n_storms_total"),
                "skill": report.get("leads", {}),
            },
            "identification": {
                "trained": False,
                "blocked_on": "INSAT imagery — requires MOSDAC credentials",
            },
            "classification": {
                "trained": "intensity" in self._models,
                "model": "intensity_from_image_v1",
                "training_data": "NASA/Radiant Earth Tropical Cyclone Wind Estimation",
                "skill": getattr(self._models.get("intensity"), "report", {}),
                "note": "Geostationary IR, not INSAT — expect a domain gap",
            },
        }


def checkpoint_dir_exists() -> bool:
    return Path(os.getenv("MODEL_CHECKPOINT_DIR", "models/checkpoints")).exists()
