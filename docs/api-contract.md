# API Contract — Vayu-X

The service boundary. Agree changes here **before** implementing on either side.
Canonical payload shapes: [`shared/schemas/`](../shared/schemas/).

| Service | Base URL (local) | Docs |
|---|---|---|
| Backend (gateway) | `http://localhost:8000/api/v1` | `/docs` |
| Model inference | `http://localhost:8001` | `/docs` |
| Alert system | `http://localhost:8002` | `/docs` |

All responses are JSON. All timestamps are **ISO-8601 UTC** (`2025-09-08T12:30:00Z`).
Coordinates are decimal degrees, WGS-84, `lat` then `lon`.

---

## 1. Backend — `:8000/api/v1`

### Health & meta

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness + downstream service status |
| `GET` | `/version` | API version, model versions in use |

### Auth

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/login` | `{username, password}` → `{access_token, token_type, role}` |
| `POST` | `/auth/refresh` | Refresh an access token |
| `GET` | `/auth/me` | Current user profile and role |

Roles: `admin`, `analyst`, `responder`, `public`.

### Cyclones

| Method | Path | Description |
|---|---|---|
| `GET` | `/cyclones` | List events. Query: `status`, `from`, `to`, `bbox`, `min_category`, `limit`, `offset` |
| `GET` | `/cyclones/{id}` | Full event: metadata, observation history, latest forecast |
| `GET` | `/cyclones/{id}/track` | Observed track as GeoJSON `LineString` |
| `GET` | `/cyclones/{id}/observations` | Time-series of observations |
| `GET` | `/cyclones/active` | Currently active systems (dashboard default view) |

<details>
<summary><code>GET /cyclones/active</code> — example response</summary>

```json
{
  "count": 1,
  "items": [
    {
      "id": "b1f7c2de-3a4e-4b21-9f0c-7d8e2a1b5c34",
      "name": "VAYU-X-2025-03",
      "basin": "NIO",
      "status": "active",
      "first_seen": "2025-09-06T03:00:00Z",
      "last_seen": "2025-09-08T12:30:00Z",
      "latest_observation": {
        "observed_at": "2025-09-08T12:30:00Z",
        "lat": 15.8,
        "lon": 87.2,
        "pattern_type": "eye",
        "intensity_category": "VSCS",
        "est_wind_kt": 78.5,
        "est_pressure_hpa": 968.0,
        "dvorak_t_number": 4.5,
        "confidence": 0.91
      }
    }
  ]
}
```
</details>

### Predictions

| Method | Path | Description |
|---|---|---|
| `GET` | `/predictions/{cyclone_id}` | Latest forecast (track points + intensity + uncertainty) |
| `GET` | `/predictions/{cyclone_id}/history` | All forecasts issued for this event (for verification) |
| `POST` | `/predictions/run` | Trigger inference on demand (`analyst`+). Body: `{cyclone_id}` or `{frame_id}` |

<details>
<summary><code>GET /predictions/{cyclone_id}</code> — example response</summary>

```json
{
  "cyclone_id": "b1f7c2de-3a4e-4b21-9f0c-7d8e2a1b5c34",
  "issued_at": "2025-09-08T12:35:00Z",
  "model_version": "track_convlstm_v1",
  "points": [
    {"lead_hours": 6,  "valid_at": "2025-09-08T18:30:00Z", "lat": 16.4, "lon": 86.5, "est_wind_kt": 83.0, "radius_uncertainty_km": 45},
    {"lead_hours": 12, "valid_at": "2025-09-09T00:30:00Z", "lat": 17.1, "lon": 85.9, "est_wind_kt": 88.0, "radius_uncertainty_km": 70},
    {"lead_hours": 24, "valid_at": "2025-09-09T12:30:00Z", "lat": 18.6, "lon": 85.1, "est_wind_kt": 92.0, "radius_uncertainty_km": 110},
    {"lead_hours": 48, "valid_at": "2025-09-10T12:30:00Z", "lat": 20.9, "lon": 84.6, "est_wind_kt": 61.0, "radius_uncertainty_km": 190},
    {"lead_hours": 72, "valid_at": "2025-09-11T12:30:00Z", "lat": 22.4, "lon": 84.9, "est_wind_kt": 30.0, "radius_uncertainty_km": 280}
  ],
  "landfall_estimate": {
    "expected_at": "2025-09-09T21:00:00Z",
    "lat": 19.8, "lon": 85.0,
    "region": "Odisha coast (Puri–Paradip)",
    "confidence": 0.74
  }
}
```
</details>

### Alerts

| Method | Path | Description |
|---|---|---|
| `GET` | `/alerts` | List alerts. Query: `severity`, `status`, `from`, `to`, `region` |
| `GET` | `/alerts/{id}` | Alert detail incl. per-channel dispatch status |
| `POST` | `/alerts/{id}/acknowledge` | Responder acknowledges receipt |
| `POST` | `/alerts/manual` | Analyst-issued manual alert (`analyst`+) |
| `POST` | `/alerts/{id}/cancel` | Cancel/withdraw an alert (`admin`) |

### Imagery

| Method | Path | Description |
|---|---|---|
| `GET` | `/imagery/frames` | Available frames. Query: `source`, `channel`, `from`, `to` |
| `GET` | `/imagery/frames/{id}` | Frame metadata + signed tile URL |
| `GET` | `/imagery/overlay/{cyclone_id}` | Latest storm-centred overlay (PNG) for the map |
| `GET` | `/imagery/explain/{observation_id}` | Grad-CAM attention overlay for that inference |

### WebSocket — `ws://localhost:8000/ws`

Client subscribes; server pushes. Message envelope:

```json
{ "type": "<event_type>", "timestamp": "2025-09-08T12:30:00Z", "payload": { } }
```

| `type` | Fired when |
|---|---|
| `cyclone.detected` | A new system is identified |
| `cyclone.updated` | New observation for an existing system |
| `prediction.issued` | New forecast generated |
| `alert.issued` | Alert dispatched |
| `alert.acknowledged` | Responder acknowledged |
| `pipeline.status` | Ingestion heartbeat / data staleness warning |

---

## 2. Model service — `:8001`

Stateless. Takes imagery, returns inference. No database.

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness + which checkpoints are loaded |
| `GET` | `/models` | Loaded model names, versions, input specs |
| `POST` | `/identify` | Detect cyclone centres in a frame |
| `POST` | `/classify` | Pattern + intensity for a storm-centred crop |
| `POST` | `/predict` | Track + intensity forecast from a frame sequence |
| `POST` | `/infer` | Full chain: identify → classify → predict |

<details>
<summary><code>POST /infer</code> — request / response</summary>

**Request**
```json
{
  "frame_id": "insat3d_tir1_20250908T1230Z",
  "frame_uri": "s3://vayux-processed/2025/09/08/insat3d_tir1_1230.npy",
  "sequence_uris": ["s3://.../1130.npy", "s3://.../1200.npy", "s3://.../1230.npy"],
  "environment": {
    "sst_c": 29.4, "shear_kt": 8.2, "rh_mid_pct": 68.0,
    "vorticity_850": 4.1e-5, "steering_u": -3.2, "steering_v": 4.8
  },
  "options": { "min_confidence": 0.65, "return_explanation": true }
}
```

**Response**
```json
{
  "frame_id": "insat3d_tir1_20250908T1230Z",
  "processed_at": "2025-09-08T12:34:12Z",
  "detections": [
    {
      "lat": 15.8, "lon": 87.2,
      "bbox": [14.2, 85.6, 17.4, 88.8],
      "confidence": 0.91,
      "classification": {
        "pattern_type": "eye",
        "intensity_category": "VSCS",
        "est_wind_kt": 78.5,
        "est_pressure_hpa": 968.0,
        "dvorak_t_number": 4.5,
        "class_probabilities": {"eye": 0.78, "CDO": 0.14, "banding_eye": 0.06, "shear": 0.02}
      },
      "forecast": { "model_version": "track_convlstm_v1", "points": [] },
      "explanation_uri": "s3://vayux-processed/explain/gradcam_20250908T1230Z.png"
    }
  ],
  "model_versions": {
    "identification": "cyclone_detector_v1",
    "classification": "pattern_classifier_v1",
    "prediction": "track_convlstm_v1"
  }
}
```
</details>

---

## 3. Alert service — `:8002`

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness + channel readiness (Twilio/SMTP/FCM reachable) |
| `POST` | `/evaluate` | Evaluate a `CycloneEvent` against alert rules; dispatch if triggered |
| `POST` | `/dispatch` | Force-send a specific alert (`admin`) |
| `GET` | `/rules` | Currently loaded alert rules |
| `POST` | `/rules/reload` | Hot-reload `alert_rules.yaml` |
| `GET` | `/dispatches/{alert_id}` | Per-channel delivery status |
| `POST` | `/subscribers` | Register a recipient (channel, address, region, role) |

<details>
<summary><code>POST /evaluate</code> — response</summary>

```json
{
  "evaluated_at": "2025-09-08T12:36:00Z",
  "triggered": true,
  "alert": {
    "id": "a7c3e1b9-5d2f-4a80-b6c1-9e3f7d2a4b58",
    "severity": "ORANGE",
    "cyclone_id": "b1f7c2de-3a4e-4b21-9f0c-7d8e2a1b5c34",
    "headline": "VSCS expected to cross Odisha coast within 36 hours",
    "matched_rule": "vscs_landfall_36h",
    "geofence": { "type": "Polygon", "coordinates": [] },
    "affected_regions": ["Puri", "Khordha", "Jagatsinghpur", "Kendrapara"],
    "valid_from": "2025-09-08T12:36:00Z",
    "valid_until": "2025-09-10T00:00:00Z",
    "channels": ["sms", "email", "push", "webhook"]
  },
  "dispatch_summary": { "sms": 1240, "email": 86, "push": 5310, "webhook": 3 }
}
```
</details>

---

## 4. Conventions

**Errors** — consistent envelope across all services:

```json
{
  "error": {
    "code": "CYCLONE_NOT_FOUND",
    "message": "No cyclone event with id b1f7c2de-…",
    "details": {},
    "request_id": "req_01J8ZQ4K"
  }
}
```

| Status | Meaning |
|---|---|
| `200` | OK |
| `201` | Created |
| `202` | Accepted (async job queued) |
| `400` | Validation error |
| `401` / `403` | Unauthenticated / unauthorized |
| `404` | Not found |
| `409` | Conflict (e.g. duplicate alert within dedup window) |
| `422` | Semantically invalid payload |
| `503` | Downstream dependency unavailable |

**Pagination** — `?limit=50&offset=0`, response includes `{count, limit, offset, items}`.
**Versioning** — path-based (`/api/v1`). Breaking changes require a new version.
**Auth** — `Authorization: Bearer <jwt>` on all non-public endpoints.
**Geometry** — GeoJSON for anything spatial (`Point`, `LineString`, `Polygon`).
