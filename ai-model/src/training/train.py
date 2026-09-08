"""Training entry point.

Config-driven so a run is fully reproducible from its YAML file plus the logged
git SHA:

    python -m src.training.train --config configs/config.yaml
    python -m src.training.train --config configs/config.yaml --task prediction
"""

import argparse
import random
from pathlib import Path

import numpy as np
import torch
import yaml


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True


def load_config(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def build_model(config: dict) -> torch.nn.Module:
    task = config["model"]["task"]
    if task == "identification":
        from src.models.identification import CycloneDetector

        return CycloneDetector(
            in_channels=len(config["data"]["channels"]),
            backbone=config["model"]["backbone"],
            heatmap_stride=config["model"]["identification"]["heatmap_stride"],
        )
    if task == "classification":
        from src.models.classification import CyclonePatternClassifier

        return CyclonePatternClassifier(
            in_channels=len(config["data"]["channels"]),
            backbone=config["model"]["backbone"],
            dropout=config["model"]["dropout"],
        )
    if task == "prediction":
        from src.models.prediction import TrackIntensityPredictor

        return TrackIntensityPredictor(
            in_channels=len(config["data"]["channels"]),
            hidden_channels=config["model"]["prediction"]["hidden_channels"],
            sequence_length=config["data"]["sequence_length"],
            forecast_leads=config["data"]["forecast_leads"],
        )
    raise ValueError(f"Unknown task: {task}")


def train(config: dict) -> None:
    set_seed(config["seed"])
    device = torch.device(config["device"] if torch.cuda.is_available() else "cpu")

    model = build_model(config).to(device)
    _ = model
    # TODO(ml): dataloaders, optimizer, scheduler, AMP loop, validation,
    # early stopping, checkpointing, MLflow logging, ONNX export
    raise NotImplementedError("Phase 2/3 — see docs/roadmap.md")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a Vayu-X cyclone model")
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--task", choices=["identification", "classification", "prediction"])
    parser.add_argument("--resume", help="Path to a checkpoint to resume from")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.task:
        config["model"]["task"] = args.task
    train(config)


if __name__ == "__main__":
    main()
