# data/

**Nothing in this tree is committed.** Only `.gitkeep` and this README are tracked — satellite
products are hundreds of MB per day and would destroy the repository.

## Layout

| Folder | Contents | Rule |
|---|---|---|
| `raw/` | Exactly as downloaded — INSAT HDF5, ERA5 NetCDF, best-track CSV | **Never edit.** Reprocessing must always be possible from here |
| `external/` | Third-party reference data — IBTrACS, district/taluk shapefiles, coastline | Read-only inputs not produced by our pipeline |
| `interim/` | Calibrated, reprojected, cropped — partially processed | Safe to delete and regenerate |
| `processed/` | Model-ready tensors, tiles, and label manifests | What the DataLoader reads |

## Populating it

```bash
cd ../../data-pipeline
python -m src.scheduler --once          # one ingestion cycle
```

Requires MOSDAC / Earthdata / CDS credentials in the root `.env`.
See [`../../docs/data-sources.md`](../../docs/data-sources.md).

## Suggested naming

```
raw/insat3d/2025/09/08/3DIMG_08SEP2025_1230_L1B_STD.h5
interim/insat3d/2025/09/08/tir1_1230_nio.npy
processed/train/manifest.jsonl
processed/train/crops/20250908T1230Z_b1f7c2de.npy
```

Keep a `manifest.jsonl` per split — one JSON object per sample with paths, labels, and the
environmental features. It is what makes the dataset reproducible and inspectable.
