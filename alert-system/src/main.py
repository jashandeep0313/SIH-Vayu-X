"""Alert service.

Deliberately separate from the backend so warnings keep flowing even if the
dashboard or model service is down.

Contract: docs/api-contract.md §3  ·  Design: docs/alerting.md
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.rendering import render_alert
from src.rules.engine import RuleEngine

rule_engine = RuleEngine(os.getenv("ALERT_RULES_PATH", "config/alert_rules.yaml"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    rule_engine.load()
    yield


app = FastAPI(
    title="Vayu-X Alert Service",
    version="0.1.0",
    description="Rule-based, geofenced, multi-channel cyclone warning dispatch. "
    "SIH PS 26070 — Team Vayu-X (152).",
    lifespan=lifespan,
)


class Subscriber(BaseModel):
    channel: str  # sms | email | push | webhook
    address: str  # phone number, email, FCM token, or URL
    region: str  # district name
    role: str  # analyst | district_admin | responder | citizen
    language: str = "en"


@app.get("/health", tags=["meta"])
async def health() -> dict:
    """Liveness plus channel readiness — an alert service that cannot send is not healthy."""
    return {
        "status": "ok",
        "service": "vayux-alert-system",
        "dry_run": os.getenv("ALERT_DRY_RUN", "true").lower() == "true",
        "rules_loaded": rule_engine.rule_count,
        "channels": {
            "sms": bool(os.getenv("TWILIO_ACCOUNT_SID")),
            "email": bool(os.getenv("SMTP_HOST")),
            "push": bool(os.getenv("FCM_SERVER_KEY")),
            "webhook": bool(os.getenv("ALERT_WEBHOOK_URL")),
        },
    }


@app.post("/evaluate", tags=["alerts"])
async def evaluate(cyclone_event: dict) -> dict:
    """Run a CycloneEvent through the rule engine and render the alert it would send.

    Rule matching, severity selection, cooldown and message rendering are real.
    Geofencing and actual dispatch are still Phase 5 — nothing is delivered, and
    the response says so. This is enough to develop and test alert copy.

    Example body:
        {"intensity_category": "VSCS", "hours_to_landfall": 30,
         "confidence": 0.82, "cyclone_name": "MONTHA",
         "region": "Odisha coast (Puri-Paradip)"}
    """
    match = rule_engine.evaluate(cyclone_event)
    if match is None:
        return {
            "triggered": False,
            "reason": "no rule matched (check thresholds, or a cooldown is active)",
            "rules_loaded": rule_engine.rule_count,
            "event": cyclone_event,
        }

    rendered = render_alert(match, cyclone_event)
    return {
        "triggered": True,
        "dry_run": os.getenv("ALERT_DRY_RUN", "true").lower() == "true",
        "dispatch_implemented": False,
        "note": "Rule matching and message rendering are live. Geofencing and "
        "delivery are Phase 5 — nothing was sent.",
        "rule": {
            "id": match.rule_id,
            "severity": match.severity,
            "channels": match.channels,
            "audience": match.audience,
            "review_required": match.review_required,
        },
        "alert": rendered,
    }


@app.post("/dispatch", tags=["alerts"])
async def dispatch(alert: dict) -> dict:
    """Force-send a specific alert, bypassing the rule engine (manual/analyst path)."""
    # TODO(alerts): resolve recipients, render templates, send on each channel
    raise HTTPException(status_code=501, detail="Not implemented — Phase 5")


@app.get("/rules", tags=["rules"])
async def get_rules() -> dict:
    return {"count": rule_engine.rule_count, "rules": rule_engine.rules}


@app.post("/rules/reload", tags=["rules"])
async def reload_rules() -> dict:
    """Hot-reload alert_rules.yaml so thresholds can be tuned without a redeploy."""
    rule_engine.load()
    return {"status": "reloaded", "count": rule_engine.rule_count}


@app.get("/dispatches/{alert_id}", tags=["alerts"])
async def get_dispatches(alert_id: str) -> dict:
    """Per-channel delivery status — part of the audit trail."""
    # TODO(alerts): read dispatch records
    raise HTTPException(status_code=501, detail="Not implemented — Phase 5")


@app.post("/subscribers", status_code=201, tags=["subscribers"])
async def add_subscriber(subscriber: Subscriber) -> dict:
    """Register a recipient. Geofencing matches on `region`."""
    # TODO(alerts): persist subscriber
    raise HTTPException(status_code=501, detail="Not implemented — Phase 5")
