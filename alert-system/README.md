# alert-system/ — Warning Dispatch

Turns model output into a **graded, geofenced, delivered** warning. A cyclone prediction
nobody acts on saves nobody.

Design and rationale: [`../docs/alerting.md`](../docs/alerting.md)

## Run

```bash
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8002
```

Docs: http://localhost:8002/docs

## Why it is a separate service

If the dashboard crashes or the model service is reloading, **warnings must still go out**.
Isolating dispatch from the rest of the stack is a reliability decision, not an architectural
preference.

## Layout

```
src/
├── main.py              FastAPI app — /evaluate, /dispatch, /rules
├── dispatcher.py        Concurrent fan-out across channels
├── rules/
│   ├── engine.py        YAML-driven rule matching, cooldown, escalation
│   └── geofence.py      Cone of uncertainty → affected districts
├── channels/
│   ├── base.py          Common interface, dry-run + config guards
│   ├── sms.py           Twilio — works without internet
│   ├── email.py         SMTP — district admin, formal record
│   ├── push.py          FCM — citizen app
│   └── webhook.py       HMAC-signed — NDMA / state EOC
└── templates/           Per-channel, per-language message templates
config/alert_rules.yaml  The rules themselves
```

## Severity ladder

| | Meaning | Typical trigger |
|---|---|---|
| 🟢 GREEN | Monitor | Depression, no coastal threat |
| 🟡 YELLOW | Watch | CS/SCS within 72 h of coast |
| 🟠 ORANGE | Prepare | SCS/VSCS within 36 h |
| 🔴 RED | Act now | VSCS+ within 24 h of landfall |

Severity = intensity × proximity × time-to-landfall × confidence. **Never intensity alone** —
a Super Cyclone heading out to sea is not a red alert.

## Rules are data, not code

Edit `config/alert_rules.yaml`, then:

```bash
curl -X POST http://localhost:8002/rules/reload
```

Meteorologists tune thresholds without a redeploy.

## Safety defaults

| Guard | Behaviour |
|---|---|
| `ALERT_DRY_RUN=true` | **Default.** Alerts are generated and logged, never sent. A bug during a demo must not reach real people |
| Confidence gate | Below threshold → analyst review queue, never auto-dispatch |
| Dedup window | Same event + same severity does not re-alert |
| Cooldown per rule | Rules cannot fire in a loop |
| Escalation only | Repeat messages only when severity *increases* |
| Manual override | Analysts can issue, upgrade, or cancel any alert |

Set `ALERT_DRY_RUN=false` only when you intend real delivery.

## Test

```bash
pytest -q
```

`tests/test_rules.py` covers severity selection, cooldown, and escalation — the logic that
decides whether people get warned.
