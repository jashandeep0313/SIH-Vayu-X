"""Rule engine — decides whether a cyclone event warrants an alert, and how severe.

Rules live in YAML so meteorologists can tune thresholds without touching code.
See docs/alerting.md §3.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

SEVERITY_ORDER = {"GREEN": 0, "YELLOW": 1, "ORANGE": 2, "RED": 3}


@dataclass
class MatchedRule:
    rule_id: str
    severity: str
    channels: list[str]
    audience: list[str]
    recommended_actions: list[str] = field(default_factory=list)
    review_required: bool = False


# The rule file as it sits in the repo. ALERT_RULES_PATH points at the
# container path (/app/config/...) which does not exist when the service is run
# directly, so a configured-but-missing path must fall back to this rather than
# leaving the engine empty.
PACKAGED_RULES = Path(__file__).resolve().parents[2] / "config" / "alert_rules.yaml"


class RuleEngine:
    def __init__(self, rules_path: str | Path) -> None:
        self.rules_path = Path(rules_path)
        self.rules: list[dict] = []
        self.defaults: dict = {}
        self.escalation: dict = {}
        self.geofence_config: dict = {}
        self.source: str | None = None
        self.load_error: str | None = None
        self._last_fired: dict[str, datetime] = {}

    @property
    def rule_count(self) -> int:
        return len(self.rules)

    def load(self) -> None:
        """Load (or hot-reload) the rule file.

        An alert engine with no rules is not "quiet", it is broken — it accepts
        every event and dispatches nothing. Silently returning an empty list on
        a missing file hid exactly that: ALERT_RULES_PATH holds the container
        path, so every local run had a dead engine and reported healthy. So a
        missing path now falls back to the packaged rules and records why.
        """
        self.load_error = None
        path = self.rules_path

        if not path.exists():
            if PACKAGED_RULES.exists():
                self.load_error = (
                    f"{path} not found — fell back to packaged rules at {PACKAGED_RULES}. "
                    "(ALERT_RULES_PATH is set to the container path.)"
                )
                path = PACKAGED_RULES
            else:
                self.rules = []
                self.source = None
                self.load_error = f"no rule file at {path} and no packaged fallback"
                return

        self.source = str(path)
        with open(path) as f:
            config = yaml.safe_load(f) or {}
        self.defaults = config.get("defaults", {})
        self.rules = config.get("rules", [])
        self.escalation = config.get("escalation", {})
        self.geofence_config = config.get("geofence", {})

    def evaluate(self, event: dict) -> MatchedRule | None:
        """Return the highest-severity matching rule, or None.

        Only the most severe match is returned — firing four rules for one storm
        would mean four messages to the same person.
        """
        matches = [rule for rule in self.rules if self._matches(rule, event)]
        matches = [rule for rule in matches if not self._in_cooldown(rule)]
        if not matches:
            return None

        best = max(matches, key=lambda r: SEVERITY_ORDER.get(r["severity"], 0))
        self._last_fired[best["id"]] = datetime.now(UTC)
        return MatchedRule(
            rule_id=best["id"],
            severity=best["severity"],
            channels=best.get("channels", []),
            audience=best.get("audience", []),
            recommended_actions=best.get("recommended_actions", []),
            review_required=best.get("review_required", False),
        )

    def _matches(self, rule: dict, event: dict) -> bool:
        """Check every condition in the rule against the event."""
        conditions = rule.get("conditions", {})
        for key, expected in conditions.items():
            # `min_confidence: 0.7` is shorthand for a floor on the event's
            # `confidence`, not a field literally named min_confidence. Without
            # this every rule carrying it would silently never fire.
            if key == "min_confidence":
                confidence = event.get("confidence")
                if confidence is None or confidence < expected:
                    return False
                continue

            actual = event.get(key)
            if actual is None:
                return False
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif isinstance(expected, dict):
                if "min" in expected and actual < expected["min"]:
                    return False
                if "max" in expected and actual > expected["max"]:
                    return False
            elif actual != expected:
                return False
        return True

    def _in_cooldown(self, rule: dict) -> bool:
        """Suppress a rule that fired recently — prevents alert loops."""
        last = self._last_fired.get(rule["id"])
        if last is None:
            return False
        cooldown = timedelta(minutes=rule.get("cooldown_minutes", 60))
        return datetime.now(UTC) - last < cooldown

    def should_escalate(self, previous_severity: str, new_severity: str) -> bool:
        """Re-alert only on a severity increase.

        Repeating an identical warning is how a population learns to ignore warnings.
        """
        if SEVERITY_ORDER.get(new_severity, 0) > SEVERITY_ORDER.get(previous_severity, 0):
            return bool(self.escalation.get("on_severity_increase", True))
        return bool(self.escalation.get("on_same_severity", False))
