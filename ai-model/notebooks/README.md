# notebooks/

Exploration and analysis. Notebooks are for *understanding*; anything reusable moves into
`src/` where it can be tested and imported.

## Naming

```
NN_topic_owner.ipynb        e.g. 01_insat_frame_eda_jashan.ipynb
```

Numbered so the intended reading order is obvious.

## Planned

| Notebook | Purpose |
|---|---|
| `01_insat_frame_eda` | Inspect INSAT products, channel statistics, brightness-temperature ranges |
| `02_best_track_eda` | IMD best-track distributions, class imbalance, seasonality |
| `03_dataset_construction` | Verify frame↔label matching, visualize storm-centred crops |
| `04_baseline_classical_cv` | M0 sanity floor — thresholding + spiral fit |
| `05_model_error_analysis` | Where the model fails: by category, season, pattern type |
| `06_case_study_replay` | End-to-end replay of a historical severe cyclone for the demo |

## Rules

- **Clear all outputs before committing** (`Cell → All Output → Clear`). Notebook outputs
  embed images and bloat diffs beyond review.
- Don't import across notebooks — promote shared code to `src/`.
- A number claimed in the presentation must be reproducible from `src/`, not only from a notebook.
