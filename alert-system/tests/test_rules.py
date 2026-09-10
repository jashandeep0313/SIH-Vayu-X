"""Rule engine tests.

The engine decides whether people get warned, so its logic is worth testing before
any of it is wired to a real SMS gateway.
"""

import pytest
from src.rules.engine import SEVERITY_ORDER, RuleEngine


@pytest.fixture
def engine(tmp_path):
    rules_file = tmp_path / "rules.yaml"
    rules_file.write_text(
        """
defaults:
  min_confidence: 0.65
rules:
  - id: red_rule
    severity: RED
    conditions:
      intensity_category: [ESCS, SuCS]
      hours_to_landfall: { max: 24 }
    channels: [sms, email]
    audience: [citizen]
    cooldown_minutes: 60
  - id: yellow_rule
    severity: YELLOW
    conditions:
      intensity_category: [CS, SCS, VSCS, ESCS, SuCS]
      hours_to_landfall: { max: 72 }
    channels: [email]
    audience: [analyst]
    cooldown_minutes: 360
escalation:
  on_severity_increase: true
  on_same_severity: false
"""
    )
    eng = RuleEngine(rules_file)
    eng.load()
    return eng


def test_loads_rules(engine):
    assert engine.rule_count == 2


def test_matches_highest_severity_rule(engine):
    """Both rules match this event; only the most severe should fire."""
    match = engine.evaluate({"intensity_category": "ESCS", "hours_to_landfall": 12})
    assert match is not None
    assert match.severity == "RED"
    assert match.rule_id == "red_rule"


def test_weaker_storm_matches_only_yellow(engine):
    match = engine.evaluate({"intensity_category": "CS", "hours_to_landfall": 48})
    assert match is not None
    assert match.severity == "YELLOW"


def test_no_match_when_far_from_landfall(engine):
    match = engine.evaluate({"intensity_category": "ESCS", "hours_to_landfall": 200})
    assert match is None


def test_missing_field_does_not_match(engine):
    """An event lacking a condition field must not silently satisfy the rule."""
    assert engine.evaluate({"intensity_category": "ESCS"}) is None


def test_cooldown_suppresses_repeat(engine):
    event = {"intensity_category": "ESCS", "hours_to_landfall": 12}
    assert engine.evaluate(event) is not None
    # Immediately re-evaluating falls inside the cooldown; RED is suppressed and
    # the next-best rule outside cooldown (YELLOW) fires instead.
    second = engine.evaluate(event)
    assert second is None or second.severity != "RED"


def test_escalation_only_on_increase(engine):
    assert engine.should_escalate("YELLOW", "RED") is True
    assert engine.should_escalate("RED", "RED") is False
    assert engine.should_escalate("RED", "YELLOW") is False


def test_severity_ordering_is_total():
    assert (
        SEVERITY_ORDER["RED"]
        > SEVERITY_ORDER["ORANGE"]
        > SEVERITY_ORDER["YELLOW"]
        > SEVERITY_ORDER["GREEN"]
    )


def test_min_confidence_is_a_threshold_not_a_field(tmp_path):
    """`min_confidence` gates on the event's `confidence`.

    Regression: it was previously compared as a literal field named
    `min_confidence`, which no event carries — so every rule using it silently
    never fired, disabling the entire alert system.
    """
    rules = tmp_path / "r.yaml"
    rules.write_text(
        """
rules:
  - id: needs_confidence
    severity: RED
    conditions:
      intensity_category: [ESCS]
      min_confidence: 0.70
    channels: [sms]
    audience: [citizen]
    cooldown_minutes: 60
"""
    )
    eng = RuleEngine(rules)
    eng.load()

    assert eng.evaluate({"intensity_category": "ESCS", "confidence": 0.85}) is not None

    eng2 = RuleEngine(rules)
    eng2.load()
    assert eng2.evaluate({"intensity_category": "ESCS", "confidence": 0.50}) is None

    eng3 = RuleEngine(rules)
    eng3.load()
    assert eng3.evaluate({"intensity_category": "ESCS"}) is None


def test_real_rulebook_fires_on_a_severe_landfall():
    """The shipped alert_rules.yaml must actually produce an alert."""
    eng = RuleEngine("config/alert_rules.yaml")
    eng.load()
    assert eng.rule_count > 0

    match = eng.evaluate(
        {
            "intensity_category": "ESCS",
            "hours_to_landfall": 18,
            "confidence": 0.82,
        }
    )
    assert match is not None
    assert match.severity == "RED"


def test_missing_rules_path_falls_back_to_packaged_rules():
    """ALERT_RULES_PATH holds the container path; a local run must not silently
    end up with a dead engine that still reports healthy."""
    engine = RuleEngine("/app/config/alert_rules.yaml")
    engine.load()
    assert engine.rule_count > 0
    assert engine.load_error is not None
    assert "fell back" in engine.load_error


def test_load_error_is_none_when_path_is_correct():
    engine = RuleEngine("config/alert_rules.yaml")
    engine.load()
    assert engine.rule_count > 0
    assert engine.load_error is None
