"""Guards on the intensity model's calibration behaviour.

Two things here are easy to break silently and expensive to get wrong in a
warning system, so they are pinned by tests rather than left to review:

  * the severity weighting that stops the regressor collapsing toward the mean
    and under-reading severe storms
  * the guarantee that a reported wind estimate lies inside the wind range
    reported next to it
"""

import numpy as np
from src.training.train_intensity import SEVERITY_WEIGHT, severity_weights


def test_weights_are_disabled_at_alpha_zero():
    y = np.array([20.0, 30.0, 40.0, 130.0])
    assert np.allclose(severity_weights(y, 0.0), 1.0)


def test_weights_average_to_one():
    """Normalisation keeps learning rate and max_iter behaving as they did."""
    rng = np.random.default_rng(0)
    y = np.concatenate([rng.uniform(30, 60, 5000), rng.uniform(110, 150, 200)])
    assert np.isclose(severity_weights(y, SEVERITY_WEIGHT).mean(), 1.0)


def test_rare_high_intensities_outweigh_common_moderate_ones():
    """The whole point: a 140 kt frame must count for more than a 45 kt one."""
    rng = np.random.default_rng(0)
    y = np.concatenate([rng.uniform(40, 50, 4000), rng.uniform(135, 145, 50)])
    w = severity_weights(y, SEVERITY_WEIGHT)
    assert w[y > 130].mean() > 5 * w[y < 55].mean()


def test_weighting_is_monotone_in_alpha():
    rng = np.random.default_rng(0)
    y = np.concatenate([rng.uniform(40, 50, 4000), rng.uniform(135, 145, 50)])
    rare = y > 130
    ratios = [
        severity_weights(y, a)[rare].mean() / severity_weights(y, a)[~rare].mean()
        for a in (0.25, 0.5, 1.0)
    ]
    assert ratios[0] < ratios[1] < ratios[2]


def test_uniform_distribution_gets_near_uniform_weights():
    """No free lunch: balanced data should not be reweighted much."""
    y = np.repeat(np.arange(20.0, 140.0, 10.0), 100)
    w = severity_weights(y, SEVERITY_WEIGHT)
    assert w.max() / w.min() < 1.2


def test_estimate_lies_inside_its_reported_range():
    """A bulletin reading '92 kt (range 60-88)' is indefensible.

    The point and quantile models are separate fits, so the estimator has to
    reconcile them. Exercised through the real class with stub models rather
    than by re-implementing the arithmetic the test is meant to check.
    """
    from src.inference.intensity_estimator import IntensityEstimator

    class _Stub:
        def __init__(self, value):
            self.value = value

        def predict(self, _x):
            return np.array([self.value])

    est = IntensityEstimator()
    est.version = "test"
    # Quantile band deliberately placed entirely below the point estimate.
    est.model, est.q_lo, est.q_hi = _Stub(92.0), _Stub(60.0), _Stub(88.0)
    est.ood = None
    est.classifier = None

    rng = np.random.default_rng(0)
    result = est.estimate(rng.integers(0, 255, (128, 128, 3), dtype=np.uint8))

    cls = result["classification"]
    if cls is None:  # novelty gates may refuse random noise, which is correct
        assert result["out_of_distribution"]["flagged"]
        return
    lo, hi = cls["wind_range_kt"]
    assert lo <= cls["est_wind_kt"] <= hi
