"""Features for estimating cyclone intensity from a satellite IR image.

Deliberately not raw pixels. The Dvorak technique reads *structure* — how cold
the core is, how tightly organised the cloud shield is, whether an eye has
cleared — so the features here are radial statistics about the storm centre,
which is the same information in numeric form.

That choice also means a gradient-boosted model can learn this from a few
thousand images on a CPU, instead of needing a GPU and a large CNN.
"""

from __future__ import annotations

import numpy as np

N_RINGS = 8
IMAGE_SIZE = 128


def _to_gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 3:
        img = img.mean(axis=2)
    return img.astype(np.float32)


def chroma(img: np.ndarray) -> float:
    """Mean colour saturation, 0 for greyscale.

    Not a model feature — a modality check. The intensity model is trained on
    single-channel infrared, which is greyscale by construction. Any appreciable
    chroma means the caller supplied true-colour or a composite, which the model
    cannot interpret. Kept outside `extract()` because that per-image normalises
    to [0,1] and so destroys exactly this signal.
    """
    if img.ndim != 3 or img.shape[2] < 3:
        return 0.0
    rgb = img[:, :, :3].astype(np.float32)
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    return float(np.mean((mx - mn) / (mx + 1e-6)))


def _resize(img: np.ndarray, size: int = IMAGE_SIZE) -> np.ndarray:
    """Nearest-neighbour resize — no SciPy/PIL dependency in the hot path."""
    h, w = img.shape
    yi = (np.arange(size) * h / size).astype(int).clip(0, h - 1)
    xi = (np.arange(size) * w / size).astype(int).clip(0, w - 1)
    return img[yi][:, xi]


_RING_CACHE: dict[int, list[np.ndarray]] = {}


def _ring_masks(size: int) -> list[np.ndarray]:
    """Concentric annuli around the image centre, cached per size."""
    if size in _RING_CACHE:
        return _RING_CACHE[size]
    yy, xx = np.mgrid[0:size, 0:size]
    cy = cx = (size - 1) / 2.0
    r = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    r_max = size / 2.0
    edges = np.linspace(0, r_max, N_RINGS + 1)
    masks = [(r >= edges[i]) & (r < edges[i + 1]) for i in range(N_RINGS)]
    _RING_CACHE[size] = masks
    return masks


def feature_names() -> list[str]:
    names = ["global_mean", "global_std", "global_min", "global_max", "p05", "p25", "p75", "p95"]
    for i in range(N_RINGS):
        names += [f"ring{i}_mean", f"ring{i}_std", f"ring{i}_min"]
    names += [
        "core_minus_env",     # eye/eyewall contrast — the core Dvorak signal
        "core_gradient",      # how sharply the core warms outward
        "asymmetry",          # sheared storms are lopsided
        "cold_fraction",      # extent of deep convection
        "very_cold_fraction",
    ]
    return names


def extract(img: np.ndarray) -> np.ndarray:
    """Feature vector for one image. Input may be any size, grey or RGB."""
    g = _resize(_to_gray(img), IMAGE_SIZE)

    # Scale to [0,1] per image: absolute brightness varies by sensor and
    # normalisation, structure does not.
    lo, hi = float(g.min()), float(g.max())
    g = (g - lo) / (hi - lo) if hi > lo else np.zeros_like(g)

    feats = [
        g.mean(), g.std(), g.min(), g.max(),
        *np.percentile(g, [5, 25, 75, 95]),
    ]

    masks = _ring_masks(IMAGE_SIZE)
    ring_means = []
    for m in masks:
        vals = g[m]
        if vals.size == 0:
            feats += [0.0, 0.0, 0.0]
            ring_means.append(0.0)
        else:
            feats += [float(vals.mean()), float(vals.std()), float(vals.min())]
            ring_means.append(float(vals.mean()))

    core = float(np.mean(ring_means[:2]))
    env = float(np.mean(ring_means[-2:]))
    feats.append(core - env)
    feats.append(float(ring_means[2] - ring_means[0]))

    # Left/right asymmetry about the centre
    half = IMAGE_SIZE // 2
    feats.append(float(abs(g[:, :half].mean() - g[:, half:].mean())))

    # In IR, cold tops are the deep convection; these images are normalised so
    # that dark == cold.
    feats.append(float((g < 0.25).mean()))
    feats.append(float((g < 0.10).mean()))

    return np.array(feats, dtype=np.float32)


def extract_batch(images) -> np.ndarray:
    return np.vstack([extract(im) for im in images])
