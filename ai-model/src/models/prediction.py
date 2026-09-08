"""Task 3 — Prediction: track and intensity forecasting.

Pure image extrapolation plateaus quickly; the environmental features (SST, shear,
steering flow) are what let this beat a persistence baseline at longer leads.

See docs/ml-approach.md §4.
"""

import torch
import torch.nn as nn

FORECAST_LEADS = [6, 12, 24, 48, 72]  # hours


class ConvLSTMCell(nn.Module):
    """Single ConvLSTM cell — convolutional gates preserve spatial structure."""

    def __init__(self, in_channels: int, hidden_channels: int, kernel_size: int = 3) -> None:
        super().__init__()
        padding = kernel_size // 2
        self.hidden_channels = hidden_channels
        self.conv = nn.Conv2d(
            in_channels + hidden_channels,
            4 * hidden_channels,  # i, f, o, g gates
            kernel_size,
            padding=padding,
        )

    def forward(
        self, x: torch.Tensor, state: tuple[torch.Tensor, torch.Tensor]
    ) -> tuple[torch.Tensor, torch.Tensor]:
        h, c = state
        gates = self.conv(torch.cat([x, h], dim=1))
        i, f, o, g = gates.chunk(4, dim=1)
        i, f, o = torch.sigmoid(i), torch.sigmoid(f), torch.sigmoid(o)
        g = torch.tanh(g)
        c_next = f * c + i * g
        h_next = o * torch.tanh(c_next)
        return h_next, c_next

    def init_state(self, batch: int, height: int, width: int, device) -> tuple:
        shape = (batch, self.hidden_channels, height, width)
        return torch.zeros(shape, device=device), torch.zeros(shape, device=device)


class TrackIntensityPredictor(nn.Module):
    """ConvLSTM encoder over past frames + environment features -> forecast heads.

    Outputs one (lat, lon, wind, pressure, uncertainty) tuple per lead time.
    Uncertainty comes from MC-dropout spread and becomes the cone of uncertainty
    drawn on the dashboard.
    """

    def __init__(
        self,
        in_channels: int = 4,
        hidden_channels: list[int] | None = None,
        sequence_length: int = 8,
        n_env_features: int = 6,
        forecast_leads: list[int] | None = None,
        dropout: float = 0.3,
    ) -> None:
        super().__init__()
        self.forecast_leads = forecast_leads or FORECAST_LEADS
        self.sequence_length = sequence_length
        # TODO(ml): stack ConvLSTM cells, fuse env features, per-lead forecast heads
        raise NotImplementedError("Phase 3 — see docs/roadmap.md")

    def forward(self, frames: torch.Tensor, env: torch.Tensor) -> dict[str, torch.Tensor]:
        """
        Args:
            frames: [B, T, C, H, W] sequence of storm-centred crops
            env:    [B, F] environmental predictors
        Returns:
            {"track": [B, L, 2], "intensity": [B, L, 2], "uncertainty": [B, L]}
        """
        raise NotImplementedError

    @torch.no_grad()
    def predict_with_uncertainty(
        self, frames: torch.Tensor, env: torch.Tensor, n_samples: int = 20
    ) -> dict[str, torch.Tensor]:
        """MC-dropout: keep dropout active at inference and take the ensemble spread."""
        # TODO(ml): enable dropout, run n_samples passes, return mean + std
        raise NotImplementedError


def haversine_loss(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """Great-circle distance loss in km.

    Plain MSE on (lat, lon) misweights errors by latitude — a degree of longitude
    is not a fixed distance. This loss optimizes the metric we actually report.
    """
    earth_radius_km = 6371.0
    lat1, lon1 = torch.deg2rad(pred[..., 0]), torch.deg2rad(pred[..., 1])
    lat2, lon2 = torch.deg2rad(target[..., 0]), torch.deg2rad(target[..., 1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = torch.sin(dlat / 2) ** 2 + torch.cos(lat1) * torch.cos(lat2) * torch.sin(dlon / 2) ** 2
    return (2 * earth_radius_km * torch.asin(torch.sqrt(torch.clamp(a, 0, 1)))).mean()
