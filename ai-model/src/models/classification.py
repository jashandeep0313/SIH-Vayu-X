"""Task 2 — Classification: cloud pattern + intensity.

Automates what the Dvorak technique does manually. Pattern and intensity are
physically coupled, so a shared trunk with multiple heads regularizes both and
mirrors how a human analyst actually reasons about the image.

See docs/ml-approach.md §3.
"""

import torch
import torch.nn as nn

PATTERN_CLASSES = ["curved_band", "shear", "CDO", "banding_eye", "eye", "central_cold_cover"]
INTENSITY_CLASSES = ["LPA", "D", "DD", "CS", "SCS", "VSCS", "ESCS", "SuCS"]


class CyclonePatternClassifier(nn.Module):
    """Shared CNN/ViT trunk with three heads.

    Heads:
        A — pattern class (6-way)
        B — intensity category (8-way, IMD scale)
        C — regression: wind (kt), pressure (hPa), Dvorak T-number
    """

    def __init__(
        self,
        in_channels: int = 4,
        backbone: str = "resnet50",
        pretrained: bool = True,
        dropout: float = 0.3,
    ) -> None:
        super().__init__()
        self.n_patterns = len(PATTERN_CLASSES)
        self.n_intensities = len(INTENSITY_CLASSES)
        # TODO(ml): build trunk + three heads
        raise NotImplementedError("Phase 2 — see docs/roadmap.md")

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        """
        Args:
            x: [B, C, 224, 224] storm-centred crop
        Returns:
            {"pattern_logits": [B, 6], "intensity_logits": [B, 8], "regression": [B, 3]}
        """
        raise NotImplementedError


class MultiTaskLoss(nn.Module):
    """Weighted sum of the three heads' losses.

    Class weights matter: SuCS events are rare, and an unweighted loss learns to
    ignore exactly the cases the system exists to catch.
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        pattern_class_weights: torch.Tensor | None = None,
        intensity_class_weights: torch.Tensor | None = None,
    ) -> None:
        super().__init__()
        self.weights = weights or {"pattern": 1.0, "intensity": 1.0, "wind": 0.5, "pressure": 0.3}
        # TODO(ml): CrossEntropyLoss(weight=...) for A and B, HuberLoss for C
        raise NotImplementedError

    def forward(self, outputs: dict, targets: dict) -> tuple[torch.Tensor, dict[str, float]]:
        raise NotImplementedError


def wind_to_category(wind_kt: float) -> str:
    """IMD North Indian Ocean intensity scale."""
    if wind_kt < 17:
        return "LPA"
    if wind_kt < 28:
        return "D"
    if wind_kt < 34:
        return "DD"
    if wind_kt < 48:
        return "CS"
    if wind_kt < 64:
        return "SCS"
    if wind_kt < 90:
        return "VSCS"
    if wind_kt < 120:
        return "ESCS"
    return "SuCS"
