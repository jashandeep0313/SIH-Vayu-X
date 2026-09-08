"""Evaluation metrics, measured against IMD best track.

A model is only interesting if it beats persistence and CLIPER — those baselines
are computed here alongside the model scores.

See docs/ml-approach.md §7.
"""

import numpy as np

EARTH_RADIUS_KM = 6371.0


def haversine_km(
    lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray
) -> np.ndarray:
    """Great-circle distance between predicted and actual positions."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


# ------------------------------------------------------------- identification
def detection_scores(tp: int, fp: int, fn: int) -> dict[str, float]:
    """POD, FAR and CSI — the standard triple in operational meteorology."""
    pod = tp / (tp + fn) if (tp + fn) else 0.0  # probability of detection
    far = fp / (tp + fp) if (tp + fp) else 0.0  # false alarm ratio
    csi = tp / (tp + fp + fn) if (tp + fp + fn) else 0.0  # critical success index
    return {"pod": pod, "far": far, "csi": csi}


def mean_center_error_km(pred_lat, pred_lon, true_lat, true_lon) -> float:
    return float(np.mean(haversine_km(pred_lat, pred_lon, true_lat, true_lon)))


# ------------------------------------------------------------- classification
def wind_rmse_kt(pred: np.ndarray, true: np.ndarray) -> float:
    return float(np.sqrt(np.mean((pred - true) ** 2)))


def pressure_mae_hpa(pred: np.ndarray, true: np.ndarray) -> float:
    return float(np.mean(np.abs(pred - true)))


# ---------------------------------------------------------------- prediction
def track_error_by_lead(
    pred_lat: np.ndarray,
    pred_lon: np.ndarray,
    true_lat: np.ndarray,
    true_lon: np.ndarray,
    leads: list[int],
) -> dict[int, float]:
    """Mean track error in km at each forecast lead time.

    Shapes: [N, L] where L == len(leads).
    """
    errors = haversine_km(pred_lat, pred_lon, true_lat, true_lon)
    return {lead: float(np.mean(errors[:, i])) for i, lead in enumerate(leads)}


def skill_score(model_error: float, baseline_error: float) -> float:
    """Fractional improvement over a baseline. Positive means the model helps.

    A negative skill score against persistence means the model is worse than
    assuming nothing changes — worth knowing before claiming anything.
    """
    if baseline_error == 0:
        return 0.0
    return (baseline_error - model_error) / baseline_error


def persistence_baseline(
    current_lat: np.ndarray,
    current_lon: np.ndarray,
    prev_lat: np.ndarray,
    prev_lon: np.ndarray,
    leads: list[int],
    step_hours: int = 6,
) -> tuple[np.ndarray, np.ndarray]:
    """Extrapolate the current motion vector forward — the floor any model must clear."""
    dlat = (current_lat - prev_lat) / step_hours
    dlon = (current_lon - prev_lon) / step_hours
    pred_lat = np.stack([current_lat + dlat * lead for lead in leads], axis=1)
    pred_lon = np.stack([current_lon + dlon * lead for lead in leads], axis=1)
    return pred_lat, pred_lon
