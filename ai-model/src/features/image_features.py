"""Features for estimating cyclone intensity from a satellite IR image.

Deliberately not raw pixels. The Dvorak technique reads *structure* — how cold
the core is, how tightly organised the cloud shield is, whether an eye has
cleared, how symmetric the system looks — so these features encode that same
information numerically. A gradient-boosted model can then learn the mapping
from a few tens of thousands of images on a CPU, with no GPU and no large CNN.

v2 adds finer radial resolution, quadrant asymmetry, gradient/texture measures
and an explicit eye signature, roughly tripling the feature count over v1.
"""

from __future__ import annotations

import numpy as np

N_RINGS = 16
N_QUADRANTS = 4
IMAGE_SIZE = 128

FEATURE_VERSION = "v2"


def _to_gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 3:
        img = img[:, :, :3].mean(axis=2)
    return img.astype(np.float32)


def chroma(img: np.ndarray) -> float:
    """Mean colour saturation, 0 for greyscale.

    Not a model feature — a modality check. The intensity model is trained on
    single-channel infrared, which is greyscale by construction. Appreciable
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
    """Nearest-neighbour resize — avoids a SciPy/PIL dependency in the hot path."""
    h, w = img.shape
    yi = (np.arange(size) * h / size).astype(int).clip(0, h - 1)
    xi = (np.arange(size) * w / size).astype(int).clip(0, w - 1)
    return img[yi][:, xi]


_GEOM_CACHE: dict[int, tuple] = {}


def _geometry(size: int):
    """Ring and quadrant masks plus radius grid, cached per image size."""
    if size in _GEOM_CACHE:
        return _GEOM_CACHE[size]
    yy, xx = np.mgrid[0:size, 0:size]
    cy = cx = (size - 1) / 2.0
    dy, dx = yy - cy, xx - cx
    r = np.sqrt(dy**2 + dx**2)
    r_max = size / 2.0
    edges = np.linspace(0, r_max, N_RINGS + 1)
    rings = [(r >= edges[i]) & (r < edges[i + 1]) for i in range(N_RINGS)]

    theta = np.arctan2(dy, dx)
    quads = [
        (theta >= -np.pi + i * np.pi / 2) & (theta < -np.pi + (i + 1) * np.pi / 2)
        for i in range(N_QUADRANTS)
    ]
    inner = r < r_max * 0.5
    _GEOM_CACHE[size] = (rings, quads, r, inner)
    return _GEOM_CACHE[size]


def feature_names() -> list[str]:
    names = [
        "global_mean",
        "global_std",
        "global_min",
        "global_max",
        "p01",
        "p05",
        "p10",
        "p25",
        "p50",
        "p75",
        "p90",
        "p95",
        "p99",
        "skew",
        "kurtosis",
    ]
    for i in range(N_RINGS):
        names += [f"ring{i}_mean", f"ring{i}_std", f"ring{i}_min", f"ring{i}_p10"]
    for i in range(N_QUADRANTS):
        names += [f"quad{i}_mean", f"quad{i}_min"]
    names += [
        "core_minus_env",
        "core_gradient",
        "mid_gradient",
        "radial_slope",
        "radial_slope_inner",
        "asymmetry_lr",
        "asymmetry_tb",
        "quad_spread",
        "eye_signature",
        "eye_contrast",
        "grad_mean",
        "grad_std",
        "grad_p90",
        "texture_inner",
        "texture_outer",
    ]
    for t in (0.05, 0.10, 0.20, 0.30, 0.40, 0.50):
        names.append(f"cold_frac_{int(t*100)}")
    return names


def extract(img: np.ndarray) -> np.ndarray:
    """Feature vector for one image. Input may be any size, grey or RGB."""
    g = _resize(_to_gray(img), IMAGE_SIZE)

    # Per-image scale to [0,1]: absolute brightness varies by sensor and
    # normalisation, structure does not.
    lo, hi = float(g.min()), float(g.max())
    g = (g - lo) / (hi - lo) if hi > lo else np.zeros_like(g)

    flat = g.ravel()
    mean, std = float(flat.mean()), float(flat.std())
    centred = flat - mean
    denom = (std**3 * flat.size) or 1.0
    skew = float((centred**3).sum() / denom)
    kurt = float((centred**4).sum() / ((std**4 * flat.size) or 1.0) - 3.0)

    feats = [
        mean,
        std,
        float(flat.min()),
        float(flat.max()),
        *[float(v) for v in np.percentile(flat, [1, 5, 10, 25, 50, 75, 90, 95, 99])],
        skew,
        kurt,
    ]

    rings, quads, _r, inner = _geometry(IMAGE_SIZE)

    ring_means = []
    for m in rings:
        vals = g[m]
        if vals.size == 0:
            feats += [0.0, 0.0, 0.0, 0.0]
            ring_means.append(0.0)
        else:
            rm = float(vals.mean())
            feats += [rm, float(vals.std()), float(vals.min()), float(np.percentile(vals, 10))]
            ring_means.append(rm)

    quad_means = []
    for m in quads:
        vals = g[m]
        qm = float(vals.mean()) if vals.size else 0.0
        feats += [qm, float(vals.min()) if vals.size else 0.0]
        quad_means.append(qm)

    core = float(np.mean(ring_means[:3]))
    env = float(np.mean(ring_means[-3:]))
    feats.append(core - env)
    feats.append(float(ring_means[3] - ring_means[0]))
    feats.append(float(ring_means[8] - ring_means[4]))

    # Slope of the radial brightness profile — a tight, deep core gives a steep rise
    idx = np.arange(N_RINGS, dtype=np.float32)
    rm = np.array(ring_means, dtype=np.float32)
    feats.append(float(np.polyfit(idx, rm, 1)[0]))
    feats.append(float(np.polyfit(idx[:6], rm[:6], 1)[0]))

    half = IMAGE_SIZE // 2
    feats.append(float(abs(g[:, :half].mean() - g[:, half:].mean())))
    feats.append(float(abs(g[:half, :].mean() - g[half:, :].mean())))
    feats.append(float(np.std(quad_means)))

    # Eye signature: a cleared eye is a *warm* centre ringed by very cold cloud,
    # which is the single strongest visual cue of an intense storm.
    centre = float(np.mean(rm[:2]))
    eyewall = float(np.min(rm[2:6])) if N_RINGS > 6 else centre
    feats.append(float(centre - eyewall))
    feats.append(float((centre - eyewall) / (abs(eyewall) + 1e-3)))

    gy, gx = np.gradient(g)
    gm = np.sqrt(gy**2 + gx**2)
    feats += [float(gm.mean()), float(gm.std()), float(np.percentile(gm, 90))]
    feats.append(float(g[inner].std()))
    feats.append(float(g[~inner].std()))

    # In IR these frames are normalised so dark == cold == deep convection
    for t in (0.05, 0.10, 0.20, 0.30, 0.40, 0.50):
        feats.append(float((g < t).mean()))

    return np.array(feats, dtype=np.float32)


def extract_batch(images) -> np.ndarray:
    return np.vstack([extract(im) for im in images])
