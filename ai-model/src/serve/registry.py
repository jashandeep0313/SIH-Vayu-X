"""Checkpoint registry for the inference service.

Loads models once at startup rather than per request, and records which version
answered each call so every prediction is traceable to a specific checkpoint.
"""

import os
from typing import Any


class ModelRegistry:
    def __init__(self) -> None:
        self.device: str = os.getenv("MODEL_DEVICE", "cpu")
        self.checkpoint_dir: str = os.getenv("MODEL_CHECKPOINT_DIR", "models/checkpoints")
        self._models: dict[str, Any] = {}
        self._versions: dict[str, str] = {
            "identification": os.getenv("IDENTIFICATION_MODEL", "cyclone_detector_v1"),
            "classification": os.getenv("CLASSIFICATION_MODEL", "pattern_classifier_v1"),
            "prediction": os.getenv("PREDICTION_MODEL", "track_convlstm_v1"),
        }

    def load_all(self) -> None:
        """Load every configured checkpoint.

        A missing checkpoint is logged and skipped rather than fatal — the service
        must still start so that /health can report which tasks are unavailable.
        """
        # TODO(ml): load ONNX/TorchScript checkpoints into self._models
        pass

    def unload_all(self) -> None:
        self._models.clear()

    def get(self, task: str) -> Any:
        if task not in self._models:
            raise KeyError(f"Model for task '{task}' is not loaded")
        return self._models[task]

    def loaded_names(self) -> list[str]:
        return list(self._models.keys())

    def describe(self) -> dict:
        return {
            "device": self.device,
            "checkpoint_dir": self.checkpoint_dir,
            "versions": self._versions,
            "loaded": self.loaded_names(),
            "input_specs": {
                "identification": {
                    "shape": [None, 4, 256, 256],
                    "channels": ["TIR1", "TIR2", "WV", "MIR"],
                },
                "classification": {
                    "shape": [None, 4, 224, 224],
                    "channels": ["TIR1", "TIR2", "WV", "MIR"],
                },
                "prediction": {"shape": [None, 8, 4, 224, 224], "extra": "environment features"},
            },
        }
