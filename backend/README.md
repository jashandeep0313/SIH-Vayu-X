# backend/ — API Gateway

FastAPI service that fronts the whole system: serves the dashboard, orchestrates the model and
alert services, persists cyclone state, and pushes live updates over WebSocket.

## Run

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Swagger UI: http://localhost:8000/docs

## Layout

```
app/
├── main.py              FastAPI app, middleware, WebSocket mount
├── core/
│   ├── config.py        Settings from env/.env
│   └── security.py      JWT creation/validation, password hashing
├── api/v1/
│   ├── router.py        Aggregates route modules
│   └── routes/
│       ├── health.py        /health, /version (+ downstream probes)
│       ├── auth.py          Login, refresh, current user
│       ├── cyclones.py      Events, tracks, observations
│       ├── predictions.py   Forecasts, on-demand inference
│       ├── alerts.py        Alert console, acknowledge, manual issue
│       └── imagery.py       Frames, overlays, Grad-CAM explanations
├── schemas/             Pydantic bindings for shared/schemas/*.json
├── models/              SQLAlchemy ORM (PostGIS + TimescaleDB)
├── services/
│   ├── model_client.py  Calls ai-model service (retried)
│   ├── alert_client.py  Calls alert-system service (retried)
│   └── websocket.py     Live push fan-out
├── db/session.py        Engine + session dependency
└── utils/
```

## Responsibilities

| Does | Does not |
|---|---|
| Auth, RBAC, request validation | Run ML inference (→ `ai-model`) |
| Persist events, forecasts, alerts | Decide alert severity (→ `alert-system`) |
| Orchestrate model → alert flow | Fetch satellite data (→ `data-pipeline`) |
| Serve the dashboard's REST + WS API | Render UI (→ `frontend`) |

## Database

PostgreSQL with **PostGIS** (geometry columns for positions and geofences) and **TimescaleDB**
(`observations` and `forecast_points` as hypertables — cyclone histories are time-series and
range queries must stay fast as the archive grows).

```bash
alembic revision --autogenerate -m "add cyclone tables"
alembic upgrade head
```

Extensions are enabled by `scripts/init_db.sql` on first container start.

## Notes for implementers

- Endpoints currently return `501` with a `TODO(backend)` marker — these are the Phase 4/5 tasks.
- Every route already declares its response model; fill the body, don't change the contract.
- Contract changes go through `shared/schemas/` and `docs/api-contract.md` first.
- Never call the model service synchronously inside a request that a user is waiting on for more
  than a few seconds — queue it and push the result over WebSocket instead.

## Test

```bash
pytest -q
```
