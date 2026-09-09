"""Alert message rendering.

Produces the per-channel text a recipient actually sees. Kept separate from
dispatch so message copy can be developed and reviewed without any credentials
configured and without sending anything.

Copy rules (docs/alerting.md §6): lead with the action, name a specific place
and time, keep SMS to one 160-character segment, and never put a raw model
confidence in a public-facing message.
"""

from datetime import UTC, datetime, timedelta

from src.channels.sms import truncate_for_sms

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

SEVERITY_ACTION = {
    "GREEN": "No action required",
    "YELLOW": "Be updated",
    "ORANGE": "Be prepared",
    "RED": "Take action now",
}

KT_TO_KMPH = 1.852


def _ist(dt: datetime) -> str:
    return (dt + timedelta(hours=5, minutes=30)).strftime("%d %b, %H:%M IST")


def render_alert(match, event: dict) -> dict:
    """Render one alert across every channel it targets."""
    now = datetime.now(UTC)

    category = event.get("intensity_category", "D")
    category_name = CATEGORY_NAMES.get(category, category)
    name = event.get("cyclone_name") or "The system"
    region = event.get("region") or "the coast"
    hours = event.get("hours_to_landfall")
    wind_kt = event.get("est_wind_kt")
    wind_kmph = round(wind_kt * KT_TO_KMPH) if wind_kt else None

    FALLBACK_ACTION = "Follow official updates"
    eta = _ist(now + timedelta(hours=hours)) if hours is not None else None
    primary_action = (match.recommended_actions or [FALLBACK_ACTION])[0]

    if hours is not None:
        headline = f"{category_name} expected to cross {region} within {int(hours)} hours"
    else:
        headline = f"{category_name} identified — {region}"

    # Build the SMS from parts so an absent ETA doesn't read as "by shortly",
    # and the sign-off isn't repeated when it is already the primary action.
    when = f" by {eta}" if eta else ""
    wind_clause = f" Winds {wind_kmph} kmph." if wind_kmph else ""
    sign_off = "" if primary_action == FALLBACK_ACTION else f" {FALLBACK_ACTION}."
    sms = truncate_for_sms(
        f"IMD/Vayu-X {match.severity} ALERT: {category_name} near {region}{when}."
        f"{wind_clause} {primary_action}.{sign_off}"
    )

    body = (
        f"{name} is forecast to affect {region}"
        + (f" around {eta}" if eta else "")
        + (f", with sustained winds of {wind_kmph} kmph" if wind_kmph else "")
        + f". {SEVERITY_ACTION.get(match.severity, '')}."
    )

    return {
        "severity": match.severity,
        "matched_rule": match.rule_id,
        "headline": headline,
        "body": body,
        "issued_at": now.isoformat().replace("+00:00", "Z"),
        "valid_until": (now + timedelta(hours=hours if hours is not None else 24))
        .isoformat()
        .replace("+00:00", "Z"),
        "recommended_actions": match.recommended_actions,
        "audience": match.audience,
        "messages": {
            "sms": {"text": sms, "length": len(sms), "segments": 1},
            "push": {
                "title": f"{match.severity} · {category_name}",
                "body": (f"{region}" + (f" · {eta}" if eta else "") + f". {primary_action}."),
            },
            "email": {
                "subject": f"[{match.severity}] {headline}",
                "body": body
                + "\n\nRecommended actions:\n"
                + "\n".join(f"  - {a}" for a in (match.recommended_actions or [])),
            },
            "webhook": {
                "severity": match.severity,
                "headline": headline,
                "category": category,
                "region": region,
                "hours_to_landfall": hours,
            },
        },
    }
