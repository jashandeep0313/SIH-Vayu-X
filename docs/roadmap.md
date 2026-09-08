# Roadmap — Team Vayu-X (152)

Build order is chosen so that an **end-to-end demo exists early** and improves, rather than three
perfect pieces that integrate the night before.

---

## Phase 0 — Foundation ✅

- [x] Repository scaffold, service boundaries
- [x] Architecture documented
- [x] Service contracts in `shared/schemas/`
- [x] Docker Compose local stack
- [x] CI skeleton
- [ ] Team roles assigned, data-source accounts registered (MOSDAC, Earthdata, CDS)

## Phase 1 — Data pipeline 🔄

**Goal: a labelled, model-ready dataset.** Everything downstream is blocked on this — start here.

- [ ] MOSDAC fetcher for INSAT-3D/3DR TIR-1, TIR-2, WV
- [ ] IMD best-track parser → labels in PostGIS
- [ ] Calibration, reprojection, NIO crop, normalization
- [ ] Storm-centred cropping using best-track positions
- [ ] ERA5 environmental feature extraction
- [ ] Chronological train/val/test split
- [ ] Dataset statistics + EDA notebook
- [ ] Negative (non-cyclonic) sample set

**Exit criterion:** `dataset.py` yields `(image_stack, env_features, labels)` tensors for training.

## Phase 2 — Identification + classification ⬜

- [ ] M0 classical CV baseline (sanity floor)
- [ ] M1 ResNet intensity classifier
- [ ] M2 CenterNet-style centre detector
- [ ] M3 multi-task pattern + intensity model
- [ ] Evaluation vs best track: POD, FAR, centre error, wind RMSE
- [ ] ONNX export + `/identify`, `/classify` endpoints live

**Exit criterion:** POST an INSAT frame, get back centre + category + confidence.

## Phase 3 — Prediction ⬜

- [ ] Sequence dataset builder (sliding window)
- [ ] ConvLSTM track + intensity model
- [ ] Uncertainty estimation → cone radii
- [ ] Landfall time/location estimator
- [ ] Benchmark vs persistence and CLIPER baselines
- [ ] `/predict` and `/infer` endpoints live

**Exit criterion:** 24 h track forecast with a quantified error figure we can defend.

## Phase 4 — Backend + dashboard ⬜

- [ ] Database schema + migrations (PostGIS + TimescaleDB hypertables)
- [ ] REST endpoints per `api-contract.md`
- [ ] WebSocket live push
- [ ] JWT auth + roles
- [ ] Dashboard: live map, track, cone, intensity charts
- [ ] Grad-CAM explainability overlay in the UI
- [ ] Historical case-study replay mode

**Exit criterion:** open the dashboard, watch a cyclone move and intensify live.

## Phase 5 — Alert system ⬜

- [ ] Rule engine + YAML rules
- [ ] Geofencing against district boundaries
- [ ] Dedup, cooldown, escalation logic
- [ ] SMS / email / push / webhook channels
- [ ] Subscriber registry
- [ ] Alert console with manual override
- [ ] Delivery audit trail

**Exit criterion:** a simulated VSCS landfall produces a targeted ORANGE alert to the right districts.

## Phase 6 — Hardening & presentation ⬜

- [ ] Full evaluation report vs IMD best track on held-out seasons
- [ ] Case studies: Amphan / Fani / Biparjoy / Tauktae replays
- [ ] Performance: inference latency, pipeline throughput
- [ ] Failure-mode testing (feed outage, model down, channel failure)
- [ ] Demo script rehearsed end-to-end with a fallback recording
- [ ] Presentation deck + architecture diagrams
- [ ] README screenshots / GIFs

---

## Parallelization

These tracks run simultaneously — nobody waits:

| Track | Owner | Depends on |
|---|---|---|
| Data pipeline | ML/Data | Nothing — start immediately |
| Models | ML | Phase 1 output (use synthetic/sample data to build scaffolding meanwhile) |
| Backend + DB | Backend | Contracts only — mock the model service |
| Dashboard | Frontend | Contracts only — mock the API |
| Alert system | Alerts | Contracts only — mock events |
| Infra/CI | DevOps | Nothing |

**The contracts in `shared/schemas/` are what make this parallelism possible.** Every team mocks
against the schema and integrates late with low risk.

---

## Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| MOSDAC data access delayed or throttled | Blocks everything | Register accounts on day 1; keep IBTrACS + public satellite archives as fallback training data |
| No GPU available for training | Slow iteration | Colab / Kaggle free GPUs; smaller input resolution; pre-trained backbones |
| Severe-cyclone samples too few | Poor performance on the cases that matter most | Global IBTrACS pre-training, augmentation, class-weighted loss |
| Integration left too late | Demo fails | Contract-first mocks from week 1; weekly full-stack integration checkpoint |
| Scope creep | Nothing finished | Phases 1–4 are the minimum viable demo; 5–6 are the differentiators; anything else is out of scope |
| Demo depends on live internet/feeds | Single point of failure on presentation day | Pre-loaded historical case-study replay mode + recorded backup video |

---

## Definition of done (for the submission)

1. `docker compose up` brings the whole system up on a clean machine.
2. A historical cyclone can be replayed end-to-end: frames → detection → classification →
   forecast → geofenced alert → dashboard.
3. Accuracy numbers are measured against IMD best track on held-out data, not claimed.
4. Every prediction shows a confidence value and an explainability overlay.
5. README, architecture, and API docs are current with the code.
