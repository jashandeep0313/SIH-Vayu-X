"""Frame preprocessing — raw satellite product to model-ready tensor.

Chain: calibrate -> reproject -> crop -> normalize -> tile / storm-centre crop.
See docs/data-sources.md §7.
"""

from pathlib import Path

import numpy as np

# North Indian Ocean domain
NIO_BBOX = {"lat_min": 0.0, "lat_max": 30.0, "lon_min": 55.0, "lon_max": 100.0}

# Physical range of cloud-top brightness temperature, used for normalization
BT_MIN_K = 180.0
BT_MAX_K = 320.0


def counts_to_brightness_temperature(counts: np.ndarray, calibration: dict) -> np.ndarray:
    """Radiometric calibration: raw counts -> radiance -> brightness temperature (K)."""
    # TODO(ml): apply the lookup table / Planck inversion from the product metadata
    raise NotImplementedError


def reproject_to_grid(
    data: np.ndarray,
    src_geotransform: dict,
    target_resolution_km: float = 4.0,
    bbox: dict | None = None,
) -> tuple[np.ndarray, dict]:
    """Reproject onto a common grid so all sources co-register.

    Includes parallax correction — at high satellite zenith angles, tall convective
    cloud tops are displaced from their true ground position, which shifts the
    apparent centre by tens of km near the edge of the disk.
    """
    # TODO(ml): pyproj/rasterio warp to the target grid, apply parallax correction
    raise NotImplementedError


def normalize_channel(
    data: np.ndarray, vmin: float = BT_MIN_K, vmax: float = BT_MAX_K
) -> np.ndarray:
    """Clip to the physical range and scale to [0, 1]."""
    return np.clip((data - vmin) / (vmax - vmin), 0.0, 1.0)


def storm_centered_crop(
    frame: np.ndarray,
    center_lat: float,
    center_lon: float,
    geotransform: dict,
    crop_size: int = 224,
) -> np.ndarray:
    """Crop a fixed-size window around a storm centre, edge-padded if it runs off the frame."""
    # TODO(ml): lat/lon -> pixel via geotransform, slice, pad
    raise NotImplementedError


def stack_channels(
    channel_arrays: dict[str, np.ndarray],
    channels: list[str],
    night_mask_vis: bool = True,
) -> np.ndarray:
    """Stack channels into [C, H, W].

    VIS is unusable at night. Rather than dropping the channel entirely (which would
    require two model variants), it is zero-filled and flagged so the model learns to
    rely on IR/WV when it is absent.
    """
    # TODO(ml): stack in the given order; zero-fill VIS when solar zenith says night
    raise NotImplementedError


def load_insat_frame(path: str | Path, channels: list[str]) -> dict[str, np.ndarray]:
    """Read an INSAT-3D/3DR HDF5 product and return calibrated channel arrays."""
    # TODO(ml): h5py read, per-channel calibration
    raise NotImplementedError
