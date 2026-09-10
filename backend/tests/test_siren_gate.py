"""Guards on the one alert path that fires without a human.

The siren is the only channel allowed to trigger itself, so the conditions
under which it does are worth pinning down. Each test here corresponds to a way
a physical siren could go off when it should not — or stay silent when it
should not — and both failures are expensive: one erodes the trust that makes
people evacuate, the other leaves them unwarned.
"""

import asyncio

import pytest
from app.api.v1.routes.inference import _maybe_sound_siren
from app.core.config import settings


def sound(result: dict) -> dict:
    return asyncio.run(_maybe_sound_siren(result))


@pytest.fixture(autouse=True)
def _enable_auto(monkeypatch):
    """Tests below assume the automatic path is on; it ships off."""
    monkeypatch.setattr(settings, "SIREN_AUTO_ON_UPLOAD", True)
    monkeypatch.setattr(settings, "SIREN_MIN_CONFIDENCE_PCT", 70)


def test_disabled_by_default_never_attempts(monkeypatch):
    monkeypatch.setattr(settings, "SIREN_AUTO_ON_UPLOAD", False)
    out = sound({"classification": {"intensity_category": "ESCS"}, "confidence_pct": 99})
    assert out["attempted"] is False
    assert "disabled" in out["reason"]


def test_refused_image_never_sounds():
    """An out-of-distribution frame has no classification. It must not alert.

    This is the dangerous one: a colour or wide-area image the model declined to
    score must not fall through into a siren.
    """
    out = sound({"classification": None, "confidence_pct": None})
    assert out["attempted"] is False
    assert "not scored" in out["reason"]


def test_below_scs_does_not_sound():
    out = sound({"classification": {"intensity_category": "CS"}, "confidence_pct": 95})
    assert out["attempted"] is False
    assert out["category"] == "CS"


def test_low_confidence_does_not_sound_automatically():
    """A severe category the model is unsure about waits for an operator.

    On the labelled frames confidence tracked error closely — 96% where the
    estimate was 0.5 kt out, 29% where it was 33 kt out — so this gate keeps a
    shaky read from sounding a siren by itself.
    """
    out = sound({"classification": {"intensity_category": "ESCS"}, "confidence_pct": 42})
    assert out["attempted"] is False
    assert out["confidence_pct"] == 42
    assert "below" in out["reason"]
    # The operator must still be told they can trigger it themselves.
    assert "manually" in out["reason"]


def test_missing_confidence_is_treated_as_insufficient():
    """Absent evidence is not evidence. No confidence value must not sound."""
    out = sound({"classification": {"intensity_category": "SuCS"}, "confidence_pct": None})
    assert out["attempted"] is False


@pytest.mark.parametrize("category", ["SCS", "VSCS", "ESCS", "SuCS"])
def test_alertable_categories_attempt_to_sound(category, monkeypatch):
    """At or above SCS with confidence, it reaches the tower.

    The call itself will fail in CI with no hardware attached — what is asserted
    is that the gate let it through, not that a siren physically sounded.
    """
    out = sound({"classification": {"intensity_category": category}, "confidence_pct": 88})
    assert out["attempted"] is True


def test_tower_unreachable_does_not_break_the_analysis(monkeypatch):
    """Losing the siren must not also lose the intensity estimate."""
    monkeypatch.setattr(settings, "ALERT_SERVICE_URL", "http://127.0.0.1:9")
    out = sound({"classification": {"intensity_category": "ESCS"}, "confidence_pct": 95})
    assert out["attempted"] is True
    assert out["sounded"] is False
    assert "unreachable" in out["reason"] or "reason" in out


def test_replay_seasons_do_not_overlap_track_training():
    """Every storm on the map must come from the model's test window.

    Replaying a storm the track model trained on and scoring the forecast
    against its outcome measures memory, not skill. This caught TAUKTAE (2021)
    sitting on the dashboard while the model trained on 2012-2022.
    """
    import json
    from pathlib import Path

    report = json.loads(
        (Path(__file__).resolve().parents[2] / "ai-model" / "models" / "checkpoints"
         / "track_model_report.json").read_text()
    )
    train_lo, train_hi = report["train_seasons"]
    assert train_hi < settings.REPLAY_MIN_SEASON, (
        f"replay starts at {settings.REPLAY_MIN_SEASON} but the track model "
        f"trained through {train_hi} — the map would show storms it has seen"
    )
    assert report["test_seasons"][0] == settings.REPLAY_MIN_SEASON
    assert train_lo < train_hi
