"""Alert service.

Deliberately separate from the backend so warnings keep flowing even if the
dashboard or model service is down.

Contract: docs/api-contract.md §3  ·  Design: docs/alerting.md
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.manual_sms import build_message, is_alertable, send_alert
from src.rendering import render_alert
from src.rules.engine import RuleEngine
from src.siren_device import sound_async, tower

rule_engine = RuleEngine(os.getenv("ALERT_RULES_PATH", "config/alert_rules.yaml"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    rule_engine.load()
    yield
    # Leave no tower sounding when the service stops.
    tower.close()


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
    # An engine with zero rules matches nothing and dispatches nothing. Calling
    # that "ok" is how a dead alert system passes a health check.
    return {
        "status": "ok" if rule_engine.rule_count else "degraded",
        "service": "vayux-alert-system",
        "dry_run": os.getenv("ALERT_DRY_RUN", "true").lower() == "true",
        "rules_loaded": rule_engine.rule_count,
        "rules_source": rule_engine.source,
        "rules_warning": rule_engine.load_error,
        "channels": {
            "sms": bool(os.getenv("TWILIO_ACCOUNT_SID")),
            "email": bool(os.getenv("SMTP_HOST")),
            "push": bool(os.getenv("FCM_SERVER_KEY")),
            "webhook": bool(os.getenv("ALERT_WEBHOOK_URL")),
            # The one channel that does not need a network to reach anybody.
            "siren": os.getenv("SIREN_ENABLED", "false").lower() == "true",
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


class SmsRequest(BaseModel):
    number: str
    message: str | None = None
    confirm: bool = False
    flash: bool = True
    region: str | None = None
    analysis: dict | None = None


@app.post("/alert/preview", tags=["alerts"])
async def preview_sms(payload: SmsRequest) -> dict:
    """Compose the SMS an analysis would produce, without sending anything."""
    if not payload.analysis:
        raise HTTPException(status_code=400, detail="analysis is required")
    return {
        "alertable": is_alertable(payload.analysis),
        "message": build_message(payload.analysis, payload.region),
    }


@app.post("/alert/sms", tags=["alerts"])
async def send_sms(payload: SmsRequest) -> dict:
    """Send one SMS alert. Requires confirm=true; never fires automatically.

    Manual by design: dispatch costs credits, and an unreviewed model output
    should not be able to text the public on its own.
    """
    message = payload.message
    if not message:
        if not payload.analysis:
            raise HTTPException(status_code=400, detail="message or analysis is required")
        message = build_message(payload.analysis, payload.region)["text"]

    return await send_alert(payload.number, message, payload.confirm, payload.flash)


# ------------------------------------------------ last-mile siren tower
class SirenRequest(BaseModel):
    intensity_category: str
    seconds: int = 10
    confirm: bool = False
    auto: bool = False


@app.get("/alert/siren/status", tags=["siren"])
async def siren_status() -> dict:
    """Is the tower reachable? Lists every serial port so a bad cable is obvious.

    Worth calling before a demo: it is the difference between finding out now
    and finding out in front of judges.
    """
    return tower.status()


@app.post("/alert/siren/test", tags=["siren"])
async def siren_test() -> dict:
    """Cycle the lamps and chirp once. Proves the hardware works end to end."""
    return tower.self_test()


@app.post("/alert/siren", tags=["siren"])
async def siren_sound(payload: SirenRequest) -> dict:
    """Sound the tower.

    Unlike SMS this may fire automatically (`auto=true`) — a siren costs nothing
    per sounding and a tower that waits for a human defeats its purpose. It is
    still off unless SIREN_ENABLED=true, and every sounding is duration-capped.
    """
    return await sound_async(
        payload.intensity_category,
        payload.seconds,
        confirm=payload.confirm,
        auto=payload.auto,
    )


@app.post("/alert/siren/stop", tags=["siren"])
async def siren_stop() -> dict:
    """All clear — silence the siren and return the lamps to green."""
    return tower.all_clear()


@app.post("/alert/siren/release", tags=["siren"])
async def siren_release() -> dict:
    """Let go of the serial port.

    The connection is deliberately held open (reopening resets the board), but
    that also means this service owns the port and reflashing the ESP32 fails
    with "access denied". Rather than making people stop the whole service to
    upload firmware, hand the port back. The next siren call reconnects.
    """
    tower.close()
    return {"released": True, "note": "port free — reflash now; next alert reconnects"}


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
