# ai-model/ — ML Core

Datasets, training, evaluation, and the inference microservice for the three tasks in
PS 26070: **identification**, **classification**, **prediction**.

Approach and rationale: [`../docs/ml-approach.md`](../docs/ml-approach.md)

## Run the inference service

```bash
pip install -r requirements.txt
uvicorn src.serve.app:app --reload --port 8001
```

Docs: http://localhost:8001/docs

## Train

```bash
python -m src.training.train --config configs/config.yaml --task classification
python -m src.training.train --config configs/config.yaml --task prediction
```

Every run is described entirely by its config file plus the logged git SHA — that is what
makes results reproducible weeks later.

## Layout

```
ai-model/
├── configs/            YAML run configs (config.yaml is the base)
├── data/
│   ├── raw/            As downloaded — never edited
│   ├── external/       IBTrACS, district shapefiles, reference data
│   ├── interim/        Calibrated / reprojected
│   └── processed/      Model-ready tensors + label manifests
├── notebooks/          EDA and analysis (clear outputs before committing)
├── models/checkpoints/ Saved weights (git-ignored)
├── experiments/        Run artifacts, MLflow logs (git-ignored)
└── src/
    ├── data/           dataset.py · preprocessing.py
    ├── features/       Environmental feature engineering from ERA5
    ├── models/         identification.py · classification.py · prediction.py
    ├── training/       train.py — config-driven loop
    ├── evaluation/     metrics.py · evaluate.py (vs IMD best track)
    ├── inference/      End-to-end chaining used by the service
    ├── serve/          app.py (FastAPI) · registry.py (checkpoint loading)
    └── utils/
```

## The three models

| Model | File | Input | Output |
|---|---|---|---|
| `CycloneDetector` | `models/identification.py` | `[C,256,256]` tile | Centre lat/lon, bbox, confidence |
| `CyclonePatternClassifier` | `models/classification.py` | `[C,224,224]` storm crop | Pattern, category, wind, pressure, T-number |
| `TrackIntensityPredictor` | `models/prediction.py` | `[T,C,224,224]` + env features | Track + intensity at T+6…72h, with uncertainty |

## Conventions that matter here

| Rule | Why |
|---|---|
| **Chronological splits, never random** | Adjacent frames of one storm are near-duplicates — a random split leaks and inflates every metric |
| **Hold out named storms entirely** | Amphan/Fani/Biparjoy/Tauktae are the case studies we demo; they must never be trained on |
| **Class-weighted loss** | SuCS events are rare, and an unweighted model ignores exactly the cases that matter |
| **Always report vs persistence + CLIPER** | A model that can't beat "assume nothing changes" isn't a result |
| **Every prediction carries a confidence** | Low confidence routes to analyst review instead of an automatic alert |
| **Export to ONNX for serving** | Framework-independent, faster, smaller runtime image |
| **Never commit weights, data, or notebook outputs** | Repo bloat — use MinIO / release assets |

## Data

Nothing under `data/` is committed. Get access credentials into `.env` and run the pipeline:

```bash
cd ../data-pipeline && python -m src.scheduler --once
```

Sources, formats, and access instructions: [`../docs/data-sources.md`](../docs/data-sources.md)

## Status

Model files define architecture and interfaces; bodies raise `NotImplementedError` with a
`TODO(ml)` marker pointing at the roadmap phase. Build order: Phase 1 (data) → Phase 2
(identification + classification) → Phase 3 (prediction).
