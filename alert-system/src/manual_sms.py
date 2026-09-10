"""Operator-triggered SMS alerts.

Deliberately manual. Automatic dispatch on every classification would burn
Fast2SMS credits and, more importantly, an unreviewed model output should not be
able to text the public by itself. An analyst presses send.

Guards, in order:
  * `confirm: true` must be present — no accidental sends from a stray request
  * a cooldown between sends to the same number
  * a per-process send cap
  * dry-run whenever no API key is configured, so nothing leaves the machine
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

from src.channels.fast2sms import Fast2SMSChannel

COOLDOWN_SECONDS = int(os.getenv("SMS_COOLDOWN_SECONDS", "60"))
MAX_SENDS = int(os.getenv("SMS_MAX_SENDS_PER_RUN", "25"))

CATEGORY_NAMES = {
    "LPA": "Low Pressure Area",
    "D": "Depression",
    "DD": "Deep Depression",
    "CS": "Cyclonic Storm",
    "SCS": "Severe Cyclonic Storm",
    "VSCS": "Very Severe Cyclonic Storm",
    "ESCS": "Extremely Severe Cyclonic Storm",
    "SuCS": "Super Cyclonic Storm",
}

# Categories at or above which an alert is offered at all
ALERTABLE = {"SCS", "VSCS", "ESCS", "SuCS"}

SEVERITY_FOR = {
    "SCS": "YELLOW",
    "VSCS": "ORANGE",
    "ESCS": "RED",
    "SuCS": "RED",
}


@dataclass
class SendLedger:
    """In-process record of what has been sent, to protect credits."""

    sends: int = 0
    last_by_number: dict[str, float] = field(default_factory=dict)

    def blocked(self, number: str) -> str | None:
        if self.sends >= MAX_SENDS:
            return f"send cap reached ({MAX_SENDS} this run)"
        last = self.last_by_number.get(number)
        if last and time.time() - last < COOLDOWN_SECONDS:
            wait = int(COOLDOWN_SECONDS - (time.time() - last))
            return f"cooldown active for this number, {wait}s remaining"
        return None

    def record(self, number: str) -> None:
        self.sends += 1
        self.last_by_number[number] = time.time()


ledger = SendLedger()


def build_message(analysis: dict, region: str | None = None) -> dict:
    """Compose the SMS text from a classification result.

    Action first, then the specifics — a warning nobody acts on is wasted.
    """
    cls = analysis.get("classification", {}) or {}
    category = cls.get("intensity_category", "D")
    wind_kt = cls.get("est_wind_kt")
    wind_kmph = round(wind_kt * 1.852) if wind_kt else None
    confidence = analysis.get("confidence_pct")
    severity = SEVERITY_FOR.get(category, "GREEN")
    full_name = CATEGORY_NAMES.get(category, category)
    place = region or "the coast"

    action = (
        "Move to a safe shelter now."
        if severity == "RED"
        else "Prepare to move to safety."
        if severity == "ORANGE"
        else "Stay alert and follow updates."
    )

    parts = [f"IMD/Vayu-X {severity} ALERT:", full_name]
    if wind_kmph:
        parts.append(f"winds ~{wind_kmph} kmph")
    parts.append(f"near {place}.")
    parts.append(action)
    parts.append("Do not venture into the sea.")
    text = " ".join(parts)

    if len(text) > 160:
        text = text[:159].rsplit(" ", 1)[0] + "…"

    return {
        "severity": severity,
        "category": category,
        "category_name": full_name,
        "text": text,
        "length": len(text),
        "confidence_pct": confidence,
    }


def is_alertable(analysis: dict) -> bool:
    """Only offer to alert on genuinely severe, in-distribution results."""
    if analysis.get("out_of_distribution", {}).get("flagged"):
        return False
    if not analysis.get("cyclone_detected"):
        return False
    category = (analysis.get("classification") or {}).get("intensity_category")
    return category in ALERTABLE


async def send_alert(number: str, message: str, confirm: bool, flash: bool = True) -> dict:
    """Send one SMS. Refuses unless `confirm` is true."""
    if not confirm:
        return {
            "sent": False,
            "reason": "confirmation required — pass confirm=true to actually send",
            "would_send": {"number": number, "message": message},
        }

    channel = Fast2SMSChannel()
    normalised = channel._normalise(number)

    blocked = ledger.blocked(normalised)
    if blocked:
        return {"sent": False, "reason": blocked, "number": normalised}

    if not channel.is_configured():
        return {
            "sent": False,
            "dry_run": True,
            "reason": "FAST2SMS_API_KEY not set — nothing was sent",
            "would_send": {"number": normalised, "message": message, "flash": flash},
        }

    result = await channel.send([normalised], "Cyclone Alert", message, flash=flash)
    if result.status == "sent":
        ledger.record(normalised)

    return {
        "sent": result.status == "sent",
        "status": result.status,
        "number": normalised,
        "message": message,
        "provider_message_id": result.provider_message_id,
        "error": result.error,
        "sends_this_run": ledger.sends,
        "cap": MAX_SENDS,
    }
