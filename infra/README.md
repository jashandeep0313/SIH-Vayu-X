# infra/ — Deployment & Operations

| Environment | How |
|---|---|
| **Local / demo** | `docker compose up` from the repo root — everything on one machine |
| **Staging** | Same compose file on a cloud VM, behind `nginx/vayux.conf` |
| **Production sketch** | Kubernetes manifests in `k8s/`, Prometheus + Grafana in `monitoring/` |

## Contents

```
infra/
├── nginx/vayux.conf     Reverse proxy: /api, /ws, and the dashboard on one origin
├── k8s/                 Kubernetes manifests (Phase 6)
└── monitoring/          Prometheus scrape config, Grafana dashboards
```

## Production topology (sketch)

| Component | Scaling | Notes |
|---|---|---|
| `frontend` | Static build behind a CDN | No server-side state |
| `backend` | Horizontal, stateless | Sticky sessions not needed; WebSocket fan-out via Redis pub/sub |
| `ai-model` | GPU node pool, scale on queue depth | The expensive component — batch inference where possible |
| `alert-system` | Horizontal, low replica count | Must stay available even when everything else is degraded |
| `data-pipeline` | Single scheduled worker (CronJob) | Duplicate ingestion is wasteful, not harmful — cycles are idempotent |
| PostgreSQL | Managed (PostGIS + TimescaleDB) | Point-in-time recovery on |
| Object storage | S3 / managed MinIO | Lifecycle rule: raw expires at 30 days |
| Redis | Managed | Cache + pub/sub |

## What to monitor

Beyond the usual CPU/memory:

| Signal | Why it matters |
|---|---|
| **Data staleness** — minutes since the last ingested frame | The most important metric in the system. A silently stalled pipeline looks identical to calm weather |
| Inference latency (p50/p95) | Determines how quickly a new frame becomes a warning |
| Alert delivery latency and success rate per channel | A queued alert is an undelivered alert |
| Model confidence distribution drift | Sudden drops suggest input data changed (new satellite, calibration shift) |
| WebSocket connection count | Detects dashboards that dropped off without anyone noticing |

## Alerting on the system itself

The irony is worth stating: a cyclone warning system needs its own monitoring alerts.
Page someone if ingestion stalls for more than two scan cycles (60 min), if the model service
health check fails, or if any alert channel reports repeated delivery failure.
