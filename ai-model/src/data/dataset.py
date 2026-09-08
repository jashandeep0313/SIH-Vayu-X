"""Dataset construction — pairs satellite frames with IMD best-track labels.

Splits are chronological by design. A random split puts near-identical adjacent
frames of the same storm in both train and test, which inflates every metric.

See docs/ml-approach.md §5.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import torch
from torch.utils.data import Dataset


@dataclass
class CycloneSample:
    """One training example."""

    timestamp: datetime
    frame_paths: dict[str, Path]  # channel -> file
    lat: float
    lon: float
    intensity_category: str
    wind_kt: float
    pressure_hpa: float
    pattern_type: str | None
    environment: dict[str, float]
    future_track: list[tuple[int, float, float, float]]  # (lead_h, lat, lon, wind_kt)


class CycloneDataset(Dataset):
    """Storm-centred crops with classification labels.

    Args:
        root: processed data directory
        split: train | val | test
        channels: satellite channels to stack
        crop_size: output crop edge length in pixels
        include_negatives: include non-cyclonic frames. Required for the detector —
            without them it never learns what is *not* a cyclone.
    """

    def __init__(
        self,
        root: str | Path,
        split: str = "train",
        channels: list[str] | None = None,
        crop_size: int = 224,
        augment: bool = False,
        include_negatives: bool = True,
    ) -> None:
        self.root = Path(root)
        self.split = split
        self.channels = channels or ["TIR1", "TIR2", "WV", "MIR"]
        self.crop_size = crop_size
        self.augment = augment
        self.include_negatives = include_negatives
        self.samples: list[CycloneSample] = []
        # TODO(ml): load the split manifest and populate self.samples
        raise NotImplementedError("Phase 1 — see docs/roadmap.md")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        """Returns {'image': [C,H,W], 'env': [F], 'pattern': int, 'intensity': int, 'regression': [3]}."""
        raise NotImplementedError


class CycloneSequenceDataset(CycloneDataset):
    """Sliding-window sequences for the prediction model.

    Yields N past frames plus the future track points at each forecast lead.
    """

    def __init__(
        self,
        root: str | Path,
        split: str = "train",
        sequence_length: int = 8,
        forecast_leads: list[int] | None = None,
        **kwargs,
    ) -> None:
        self.sequence_length = sequence_length
        self.forecast_leads = forecast_leads or [6, 12, 24, 48, 72]
        super().__init__(root, split, **kwargs)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        """Returns {'frames': [T,C,H,W], 'env': [F], 'track_target': [L,2], 'intensity_target': [L,2]}."""
        raise NotImplementedError


def build_splits(
    manifest_path: str | Path,
    train_years: tuple[int, int],
    val_years: tuple[int, int],
    test_years: tuple[int, int],
    holdout_cases: list[str] | None = None,
) -> dict[str, list[CycloneSample]]:
    """Chronological split, with named storms held out entirely for case studies."""
    # TODO(ml): partition the manifest by season; remove holdout cases from train/val
    raise NotImplementedError
