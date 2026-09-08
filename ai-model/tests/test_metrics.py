"""Tests for evaluation metrics — these guard the numbers we report."""

import numpy as np
from src.evaluation.metrics import (
    detection_scores,
    haversine_km,
    mean_center_error_km,
    skill_score,
)


def test_haversine_zero_distance():
    d = haversine_km(np.array([15.0]), np.array([80.0]), np.array([15.0]), np.array([80.0]))
    assert np.allclose(d, 0.0)


def test_haversine_one_degree_latitude_is_about_111km():
    d = haversine_km(np.array([15.0]), np.array([80.0]), np.array([16.0]), np.array([80.0]))
    assert 110.0 < d[0] < 112.0


def test_detection_scores_perfect():
    scores = detection_scores(tp=10, fp=0, fn=0)
    assert scores["pod"] == 1.0
    assert scores["far"] == 0.0
    assert scores["csi"] == 1.0


def test_detection_scores_no_predictions():
    scores = detection_scores(tp=0, fp=0, fn=5)
    assert scores["pod"] == 0.0
    assert scores["csi"] == 0.0


def test_skill_score_positive_when_model_beats_baseline():
    assert skill_score(model_error=80.0, baseline_error=100.0) == 0.2


def test_skill_score_negative_when_worse_than_baseline():
    assert skill_score(model_error=120.0, baseline_error=100.0) < 0


def test_mean_center_error():
    error = mean_center_error_km(
        np.array([15.0, 16.0]),
        np.array([80.0, 81.0]),
        np.array([15.0, 16.0]),
        np.array([80.0, 81.0]),
    )
    assert error == 0.0
