# Vayu-X — AI/ML Tropical Cyclone Intelligence System

> **Smart India Hackathon 2025** · Problem Statement **26070**
> **Team No.** 152 · **Team Name** Vayu-X

An AI/ML system for **identification**, **classification**, and **prediction** of tropical
cyclone patterns over the North Indian Ocean using **multi-source satellite data**.

| | |
|---|---|
| **Problem Statement ID** | 26070 |
| **Organization** | Ministry of Earth Sciences (MoES) |
| **Department** | India Meteorological Department (IMD) |
| **Category** | Software |
| **Theme** | Disaster Management |

---

## 1. Problem in one paragraph

IMD currently relies heavily on the **Dvorak technique** — a manual, analyst-driven method of
reading cloud patterns in satellite imagery to estimate cyclone intensity. It is subjective,
slow, and inconsistent between analysts. Meanwhile INSAT-3D/3DR alone push out a half-hourly
full-disk scan, and scatterometer, microwave, and reanalysis products add several more streams.
No human team can fuse all of that in real time. **Vayu-X automates the loop**: ingest
multi-source satellite data → detect and locate cyclonic systems → classify their pattern and
intensity → forecast track and intensity → push graded alerts to responders before landfall.

## 2. What the system does

| Stage | Capability | Approach |
|---|---|---|
| **Identify** | Detect and geo-locate cyclonic systems / eye centre from full-disk imagery | CNN + attention-based detector over IR (TIR-1), WV, and VIS channels |
| **Classify** | Cloud pattern type (CDO, banding, shear, eye, curved band) + intensity category (D, DD, CS, SCS, VSCS, ESCS, SuCS) | Deep classifier trained against IMD best-track / Dvorak T-number labels |
| **Predict** | Track (lat/lon) and intensity for T+6h … T+72h | ConvLSTM / spatio-temporal transformer over image sequences + reanalysis features |
| **Alert** | Graded, geo-fenced warnings to authorities and citizens | Rule engine over predictions → multi-channel dispatch (SMS / email / push / webhook) |
| **Visualize** | Live dashboard: satellite overlay, cyclone track, cone of uncertainty, intensity timeline | React + Leaflet geospatial dashboard |

## 3. Architecture

```mermaid
flowchart TB
    subgraph SRC["Multi-Source Satellite Data"]
        S1["INSAT-3D / 3DR / 3DS<br/>IR · WV · VIS (MOSDAC)"]
        S2["SCATSAT-1 / ASCAT<br/>Ocean surface winds"]
        S3["GPM / IMERG<br/>Precipitation"]
        S4["ERA5 Reanalysis<br/>SST · Shear · Vorticity"]
        S5["IMD Best Track<br/>Ground truth labels"]
    end

    subgraph DP["data-pipeline/ · Ingestion & ETL"]
        I1["Fetchers<br/>(scheduled)"] --> I2["Reproject · Calibrate<br/>Normalize · Tile"]
        I2 --> I3["Feature store<br/>+ Object storage"]
    end

    subgraph AI["ai-model/ · ML Core"]
        M1["Identification<br/>CNN detector"]
        M2["Classification<br/>Pattern + Intensity"]
        M3["Prediction<br/>ConvLSTM / Transformer"]
        M1 --> M2 --> M3
        M4["Inference Service<br/>FastAPI :8001"]
    end

    subgraph BE["backend/ · API Gateway :8000"]
        B1["REST + WebSocket"]
        B2["Auth · RBAC"]
        B3["PostGIS + TimescaleDB"]
    end

    subgraph AL["alert-system/ · :8002"]
        A1["Rule Engine<br/>thresholds · geofence"]
        A2["Dispatcher"]
        A3["SMS · Email · Push · Webhook"]
        A1 --> A2 --> A3
    end

    subgraph FE["frontend/ · Dashboard :5173"]
        F1["Live map · Track · Cone"]
        F2["Intensity charts"]
        F3["Alert console"]
    end

    SRC --> DP --> AI
    M3 --> M4 --> BE
    BE --> AL
    BE <--> FE
    AL --> RESP["Responders · IMD · NDMA · Citizens"]
```

Full detail: [`docs/architecture.md`](docs/architecture.md)

## 4. Repository structure

```
SIH_Project/
├── frontend/          React + Vite dashboard (map, tracks, charts, alert console)
├── backend/           FastAPI API gateway — auth, orchestration, persistence, WebSocket
├── ai-model/          ML core — datasets, training, evaluation, inference microservice
├── alert-system/      Rule engine + multi-channel alert dispatcher
├── data-pipeline/     Satellite ingestion, ETL, feature store loading, scheduler
├── shared/            Cross-service JSON schemas (the service contract)
├── infra/             nginx, k8s manifests, monitoring configs
├── scripts/           Setup / bootstrap / sample-data helpers
├── docs/              Architecture, data sources, ML approach, API contract, roadmap
├── .github/           CI workflows, PR template
└── docker-compose.yml One-command local stack
```

Each service has its own `README.md` explaining its internals.

## 5. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | React 18 + Vite, TailwindCSS, Leaflet, Recharts | Fast HMR, mature geospatial mapping, small bundle |
| Backend | FastAPI (Python 3.11), Pydantic, SQLAlchemy | Async, auto OpenAPI docs, same language as ML |
| Database | PostgreSQL + PostGIS + TimescaleDB | Geospatial queries + time-series cyclone tracks |
| Cache / Queue | Redis | Live state, pub/sub for WebSocket fan-out, task queue |
| ML | PyTorch, torchvision, xarray, rasterio, scikit-learn | Standard for satellite raster + deep learning |
| Serving | FastAPI + ONNX Runtime | Low-latency inference, framework-agnostic export |
| Object store | MinIO (S3-compatible) | Raw/processed satellite tiles |
| Alerts | Twilio (SMS), SMTP (email), FCM (push), webhooks | Redundant channels for disaster reliability |
| Orchestration | Docker Compose (dev) → Kubernetes (prod) | Portable, judge-friendly one-command demo |
| CI | GitHub Actions | Lint + test on every push |

> Every choice is swappable — services talk over HTTP using the contracts in `shared/schemas/`.

## 6. Data sources

| Source | Product | Use |
|---|---|---|
| **MOSDAC / ISRO** | INSAT-3D & 3DR — TIR-1, TIR-2, WV, VIS, MIR | Primary imagery for identification & classification |
| **ISRO / EUMETSAT** | SCATSAT-1, ASCAT ocean surface winds | Wind field, intensity cross-validation |
| **NASA / JAXA** | GPM IMERG precipitation | Rain-band structure |
| **ECMWF** | ERA5 reanalysis (SST, wind shear, vorticity, RH) | Environmental predictors for track/intensity |
| **IMD** | Best Track Data (RSMC New Delhi) | Ground-truth labels for supervised training |
| **NOAA** | IBTrACS global best track | Augmented training data, benchmarking |

Details, access notes, and licensing: [`docs/data-sources.md`](docs/data-sources.md)

## 7. Quick start

### Option A — Docker (recommended)

```bash
git clone https://github.com/<your-org>/SIH_Project.git
cd SIH_Project
cp .env.example .env
docker compose up --build
```

| Service | URL |
|---|---|
| Dashboard | http://localhost:5173 |
| Backend API + Swagger | http://localhost:8000/docs |
| Model inference API | http://localhost:8001/docs |
| Alert service | http://localhost:8002/docs |
| MinIO console | http://localhost:9001 |

### Option B — Manual (no Docker)

Run each in its **own terminal**, from the repo root.

```bash
cp .env.example .env      # Windows: copy .env.example .env
```

**1 · Backend API — port 8000**
```bash
cd backend && python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000
```

**2 · Model service — port 8001**
```bash
cd ai-model && python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt && uvicorn src.serve.app:app --reload --port 8001
```

**3 · Alert service — port 8002**
```bash
cd alert-system && python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt && uvicorn src.main:app --reload --port 8002
```

**4 · Frontend — port 5173**
```bash
cd frontend && npm install && npm run dev
```

On macOS/Linux use `source .venv/bin/activate` instead of `.venv/Scripts/activate`.

> **Minimal install.** `ai-model/requirements.txt` pulls ~2.5 GB of PyTorch. Until Phase 2
> there is nothing to infer, so for UI/alert work you can skip it and install only:
> `pip install fastapi uvicorn[standard] pydantic pydantic-settings httpx tenacity pyyaml python-multipart`

Bootstrap helpers: `scripts/setup.sh` (Linux/macOS) · `scripts/setup.ps1` (Windows)

### If a port is already in use

```bash
npx kill-port 8000 8001 8002 5173
```

Or run the backend elsewhere and point the frontend proxy at it:

```bash
cd backend && uvicorn app.main:app --reload --port 8010
```
```bash
cd frontend && VITE_PROXY_TARGET=http://127.0.0.1:8010 npm run dev
```

## 7a. The trained model — real data, measured results

The forecast model is **real and trained**, not a placeholder.

| | |
|---|---|
| **Training data** | IBTrACS v04r01, North Indian Ocean — 366 storms, 13,002 fixes, 1990–2025. Public, no credentials. For this basin it carries the RSMC New Delhi (IMD) analyses |
| **Model** | Gradient-boosted trees (`HistGradientBoostingRegressor`), one per lead time × target (Δlat, Δlon, Δwind) |
| **Features** | CLIPER-style and strictly causal — position, intensity, 6/12/24h motion and intensity trends, storm age, seasonality. Nothing from the future leaks in |
| **Split** | Chronological. Train ≤2016 · validate 2017–2020 · **test 2021–2025**, never seen in training |

### Measured skill on held-out seasons

| Lead | Track error | Persistence | Skill | Intensity MAE | Persistence | Skill |
|---|---|---|---|---|---|---|
| +6h | 41.7 km | 42.1 km | +1.0% | 3.40 kt | 3.58 kt | +5.1% |
| +12h | 82.9 km | 81.5 km | **−1.7%** | 5.93 kt | 6.31 kt | +6.1% |
| +24h | 163.1 km | 173.9 km | +6.2% | 9.09 kt | 10.97 kt | +17.1% |
| +48h | 327.9 km | 379.5 km | +13.6% | 14.26 kt | 16.98 kt | +16.0% |
| +72h | 478.5 km | 598.5 km | +20.1% | 17.19 kt | 19.21 kt | +10.5% |

Reproduce with `python -m src.training.train_track`; numbers are written to
`models/checkpoints/track_model_report.json`.

**Read these honestly.** The model beats persistence at 24h and beyond, and the advantage
grows with lead time — which is the useful direction. But:

- **At +12h it is slightly worse than persistence.** At short range a storm's current motion is
  very hard to improve on. Reported rather than hidden.
- **IMD's operational 24h track error is roughly 100–120 km.** Ours is 163 km. It beats the
  statistical baseline; it does not beat the operational forecast.
- **Intensity is under-forecast near peak.** Replaying Cyclone MOCHA (2023) the model called
  89 kt against an actual 115 kt. This is the rapid-intensification blind spot — the case that
  matters most, and the clearest target for the next iteration.

### Verification is in the product

`DATA_SOURCE=ibtracs` (default) replays real storms from held-out seasons. Each forecast is
scored against what actually happened and shown in a **Forecast vs Actual** panel on the
dashboard. A forecast you cannot check is a claim; beside the outcome it is a result.

## 7b. Intensity from satellite imagery — also real

A second trained model estimates intensity directly from a satellite image.

| | |
|---|---|
| **Training data** | NASA / Radiant Earth *Tropical Cyclone Wind Estimation* — 70,257 labelled IR frames, 494 storms. Public, CC-BY-4.0, no credentials |
| **Model** | `intensity_from_image_v1` — gradient boosting over **radial IR structure** features (concentric-ring brightness statistics, core-minus-environment contrast, asymmetry, cold-cloud fraction). That is the Dvorak signal expressed numerically, which is why it trains on a CPU in minutes instead of needing a GPU |
| **Split** | By storm — no storm appears in both train and test |

| Metric | Value |
|---|---|
| Wind MAE | **11.2 kt** (mean baseline 20.8 kt → **+46% skill**) |
| Wind RMSE | 15.5 kt |
| Exact IMD category | 43.1% |
| Within one category | **86.8%** |

For scale, trained-analyst Dvorak spread is around 10 kt.

### The domain gap is real — read this before demoing

The model expects **storm-centred infrared crops**, because that is what it was trained on.
Measured behaviour on out-of-domain input:

| Input | Predicted | Actual | Error |
|---|---|---|---|
| In-domain IR crop (severe) | 106.6 kt | 103 kt | **+3.6** |
| In-domain IR crop (extreme) | 120.4 kt | 128 kt | −7.6 |
| Wide-area VIIRS true-colour, Cyclone MOCHA | 39.7 kt | 115 kt | **−75** |
| Wide-area VIIRS true-colour, clear sky | 30.1 kt | 0 kt | **+30** |

Mean error across five in-domain samples was 11.6 kt, matching the 11.2 kt test MAE — so the
model is sound; wide-area true-colour images are simply the wrong input. **Do not demo it on a
screenshot from Google.** INSAT frames will also differ until it is retrained on MOSDAC data.

### Test images included

```
data/test_images/in_domain/     5 IR crops, ground truth in the filename — use these
data/test_images/               5 real VIIRS frames (MOCHA, BIPARJOY, TAUKTAE, REMAL,
                                plus a clear-sky negative control) — for the map, not the model
```

Regenerate the wide-area set with `python scripts/fetch_test_images.py`.

### What is still not real

| Capability | State |
|---|---|
| Track & intensity forecasting | **Real** — trained on IBTrACS, evaluated, serving |
| Intensity from imagery | **Real** — trained on NASA/Radiant Earth, 11.2 kt MAE |
| Cyclone *localisation* in a full-disk frame | Not built — needs INSAT full-disk frames |
| Pattern classification (Dvorak classes) | Not built — the datasets carry wind speed, not pattern labels. Pattern shown anywhere is *inferred from intensity* and labelled as such |
| Alert dispatch | Rules and message rendering real; geofencing and delivery not built |

To close the domain gap and unlock localisation, put your MOSDAC credentials in `.env` and
retrain on INSAT frames.

### Train both models

```bash
cd ai-model && python -m src.training.train_track && python -m src.training.train_intensity
```

## 7b. Testing without a trained model

`DEMO_MODE=true` (the default) makes the whole system demonstrable before Phase 2.

Set `DATA_SOURCE=synthetic` to fall back to generated events (no data files needed).

**Train the forecast model** (downloads ~28 MB of IBTrACS, trains in about a minute on CPU):

```bash
cd data-pipeline && python -c "from src.ingest.best_track import BestTrackFetcher; from datetime import datetime,UTC; from pathlib import Path; print(BestTrackFetcher({'id':'ibtracs','basin':'NI'}).fetch(datetime.now(UTC), Path('../ai-model/data/raw/ibtracs')).status)"
```
```bash
cd ai-model && python -m src.training.train_track
```

**Image analysis** — Sidebar → **Image Analysis**, drop in any image.

```bash
curl -F "file=@frame.png" http://localhost:8000/api/v1/inference/upload
```

Returns an intensity category, wind, pressure, and pattern probabilities that sum to 100.
**Every number is generated, not predicted** — the response carries `"mock": true` and the UI
shows a MOCK RESULT badge. Output is seeded from the file hash, so the same image always gives
the same answer. Swap `_mock_result` in `backend/app/api/v1/routes/inference.py` for a model
call when the classifier lands.

**Alert messages** — rule matching and message rendering are real; geofencing and delivery are
not. Nothing is ever sent (`ALERT_DRY_RUN=true`).

```bash
curl -X POST http://localhost:8002/evaluate -H "Content-Type: application/json" -d "{\"intensity_category\":\"ESCS\",\"hours_to_landfall\":18,\"confidence\":0.82,\"cyclone_name\":\"MONTHA\",\"region\":\"Odisha coast (Puri-Paradip)\",\"est_wind_kt\":95}"
```

Returns the matched rule plus rendered SMS, push, email and webhook payloads. Vary
`intensity_category`, `hours_to_landfall` and `confidence` to exercise GREEN → RED. Tune
thresholds in `alert-system/config/alert_rules.yaml`, then:

```bash
curl -X POST http://localhost:8002/rules/reload
```

### Lint and test

```bash
ruff check backend ai-model alert-system data-pipeline && cd frontend && npm run lint
```
```bash
cd backend && pytest -q && cd ../alert-system && pytest -q
```

## 8. Development workflow

```bash
git checkout -b feat/<short-description>
# work, then:
make lint && make test
git commit -m "feat(ai-model): add ConvLSTM track predictor"
git push -u origin feat/<short-description>
```

Branches: `main` (stable demo) ← `dev` (integration) ← `feat/*` · `fix/*` · `docs/*`
Conventions: [`CONTRIBUTING.md`](CONTRIBUTING.md)

## 9. Roadmap

| Phase | Deliverable | Status |
|---|---|---|
| 0 | Repo scaffold, architecture, service contracts | ✅ Done |
| 1 | Data pipeline — INSAT + best-track ingestion, labelled dataset | 🔄 In progress |
| 2 | Baseline identification + classification models | ⬜ Blocked on MOSDAC credentials |
| 3 | Track & intensity prediction | ✅ Trained on IBTrACS, beats persistence at 24h+ |
| 4 | Backend API + dashboard integration | ⬜ Planned |
| 5 | Alert engine + geofenced multi-channel dispatch | ⬜ Planned |
| 6 | Evaluation vs IMD best track, demo hardening | ⬜ Planned |

Detailed plan: [`docs/roadmap.md`](docs/roadmap.md)

## 10. Team Vayu-X — Team No. 152

| Role | Member | Owns |
|---|---|---|
| Team Lead / ML | _TBD_ | Model architecture, training |
| ML Engineer | _TBD_ | Data pipeline, feature engineering |
| Backend | _TBD_ | API gateway, database, integration |
| Frontend | _TBD_ | Dashboard, geospatial visualization |
| Alerts / DevOps | _TBD_ | Alert system, Docker, deployment |
| Research / Docs | _TBD_ | Domain research, evaluation, presentation |

## 11. Documentation index

| Doc | Contents |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | System design, data flow, component responsibilities |
| [`docs/data-sources.md`](docs/data-sources.md) | Satellite products, access, formats, preprocessing |
| [`docs/ml-approach.md`](docs/ml-approach.md) | Model designs, training strategy, evaluation metrics |
| [`docs/api-contract.md`](docs/api-contract.md) | REST/WebSocket endpoints across all services |
| [`docs/alerting.md`](docs/alerting.md) | Alert grading, thresholds, escalation, channels |
| [`docs/roadmap.md`](docs/roadmap.md) | Phase plan, milestones, ownership |

## 12. License

MIT — see [`LICENSE`](LICENSE). Satellite data remains under the licence of its respective
provider (ISRO/MOSDAC, IMD, NASA, ECMWF, NOAA); see `docs/data-sources.md`.

---

<sub>Built for Smart India Hackathon 2025 · Problem Statement 26070 · Ministry of Earth Sciences · Team Vayu-X (152)</sub>
