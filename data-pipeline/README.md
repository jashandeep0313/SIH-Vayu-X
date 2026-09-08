# data-pipeline/ — Ingestion & ETL

Gets multi-source satellite data into a clean, model-ready form. **Everything downstream is
blocked on this** — it is Phase 1 for a reason.

Sources and formats: [`../docs/data-sources.md`](../docs/data-sources.md)

## Run

```bash
pip install -r requirements.txt
python -m src.scheduler --once     # one cycle
python -m src.scheduler            # continuous, on the configured cron
```

Requires MOSDAC / Earthdata / CDS credentials in the root `.env`.

## Layout

```
src/
├── scheduler.py        Cron loop — fetch → transform → load → notify model service
├── ingest/
│   ├── base.py         BaseFetcher interface + FetchResult
│   ├── insat.py        INSAT-3D/3DR (MOSDAC) — primary imagery
│   ├── scatsat.py      SCATSAT-1 / ASCAT ocean winds
│   ├── imerg.py        GPM precipitation
│   ├── era5.py         ERA5 environmental predictors
│   └── best_track.py   IMD best track + IBTrACS labels
├── transform/          Calibrate · reproject · crop · normalize · tile
├── load/               MinIO upload, PostGIS metadata, label indexing
└── utils/
config/sources.yaml     Source registry
```

## Source-pluggable by design

Adding a satellite is **one fetcher class + one YAML entry**. Nothing else in the system
changes:

```python
class MyFetcher(BaseFetcher):
    def available_timestamps(self, since, until): ...
    def fetch(self, timestamp, destination): ...
```

```yaml
- id: my_satellite
  fetcher: MyFetcher
  enabled: true
```

## Pipeline stages

| Stage | What happens |
|---|---|
| **Ingest** | Per-source fetchers pull products for a lookback window, skipping what is already on disk |
| **Transform** | Counts → radiance → brightness temperature; reproject to a common grid (with parallax correction); crop to the North Indian Ocean; normalize; tile |
| **Load** | Processed arrays → MinIO; frame metadata and best-track labels → PostGIS/TimescaleDB |
| **Notify** | `POST /infer` on the model service for each new frame |

## Failure handling

| Rule | Why |
|---|---|
| A fetcher must never raise — it returns a failed `FetchResult` | One bad file must not abort the cycle |
| One failing source never stops the others | A scatterometer outage must not block INSAT imagery |
| Already-downloaded files are skipped | Cycles are idempotent and safe to re-run |
| Raw files are never edited in place | Reprocessing must always be possible from `raw/` |
| Retries use exponential backoff | Providers throttle; hammering makes it worse |

## Notes

- `available_timestamps()` returns the *expected* schedule. Providers publish irregularly, so
  `fetch()` still has to handle a slot that was never published.
- ERA5 reanalysis lags real time — use it for training, and forecast fields operationally.
- Raw data is retained for 30 days by default (`storage.retain_raw_days`); processed tiles are kept.
