"""Task 1 — Identification: detect and locate cyclonic systems.

A cyclone centre is a *point*, not a box, so we regress a centre heatmap
(CenterNet-style) rather than using generic object detection. Peak of the heatmap
= centre; a local offset head recovers sub-pixel position.

See docs/ml-approach.md §2.
"""

import torch
import torch.nn as nn


class CycloneDetector(nn.Module):
    """CNN backbone + centre-heatmap head.

    Args:
        in_channels: number of satellite channels stacked (e.g. TIR1, TIR2, WV, MIR)
        backbone: torchvision backbone name
        heatmap_stride: output stride of the heatmap relative to the input
    """

    def __init__(
        self,
        in_channels: int = 4,
        backbone: str = "resnet50",
        heatmap_stride: int = 4,
        pretrained: bool = True,
    ) -> None:
        super().__init__()
        self.in_channels = in_channels
        self.heatmap_stride = heatmap_stride
        # TODO(ml): build backbone (adapt first conv to in_channels), upsampling neck,
        # and three heads: centre heatmap, sub-pixel offset, extent/size.
        raise NotImplementedError("Phase 2 — see docs/roadmap.md")

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        """
        Args:
            x: [B, C, H, W] normalized multi-channel satellite tile
        Returns:
            {"heatmap": [B, 1, H/s, W/s], "offset": [B, 2, H/s, W/s], "size": [B, 2, H/s, W/s]}
        """
        raise NotImplementedError


def decode_detections(
    outputs: dict[str, torch.Tensor],
    min_confidence: float = 0.65,
    top_k: int = 10,
) -> list[dict]:
    """Turn heatmap peaks into detections in pixel space.

    Caller converts pixel coordinates to lat/lon using the frame's geo-transform.
    """
    # TODO(ml): 3x3 max-pool NMS on the heatmap, top-k peaks, apply offsets
    raise NotImplementedError
