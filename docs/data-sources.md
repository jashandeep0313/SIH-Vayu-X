# Data Sources — Vayu-X

"Multi-source satellite data" is the core of PS 26070. This is what we fuse, why, and how to get it.

---

## 1. Primary imagery — INSAT-3D / 3DR / 3DS

**Provider:** ISRO · **Portal:** [MOSDAC](https://www.mosdac.gov.in/) (free registration required)

| Channel | Band | Resolution | Why we use it |
|---|---|---|---|
| **TIR-1** | 10.3–11.3 µm | 4 km | Primary — cloud-top brightness temperature; eye, CDO and banding structure |
| **TIR-2** | 11.5–12.5 µm | 4 km | Split-window with TIR-1 → cloud microphysics, moisture correction |
| **WV** | 6.5–7.1 µm | 8 km | Mid-tropospheric moisture, dry-air intrusion, shear signatures |
| **VIS** | 0.55–0.75 µm | 1 km | Daytime structural detail (unusable at night — model must handle this) |
| **MIR** | 3.8–4.0 µm | 4 km | Low cloud / fog discrimination, night-time proxy for VIS |
| **SWIR** | 1.55–1.70 µm | 1 km | Cloud phase discrimination |

- **Cadence:** full disk every ~30 min (3D + 3DR staggered → effectively ~15 min combined)
- **Formats:** HDF5 (L1B/L1C), NetCDF (L2)
- **Products of interest:** `3DIMG_L1B_STD`, `3DIMG_L1C_ASIA_MER`, plus L2 SST/OLR
- **Note:** INSAT-3DS launched Feb 2024 — same instrument family, use as an additional stream

## 2. Ocean surface winds — scatterometry

| Source | Product | Resolution | Use |
|---|---|---|---|
| **SCATSAT-1** (ISRO) | L2B wind vectors | 25 km | Surface wind field, radius of maximum wind |
| **ASCAT** (EUMETSAT/METOP) | Coastal + 12.5 km winds | 12.5–25 km | Cross-validation of intensity, wider swath coverage |
| **OSCAT / OceanSat-3** | Wind vectors | 25 km | Continuity after SCATSAT |

Scatterometer winds are the closest thing to a direct intensity observation and are valuable as an
independent check against image-derived (Dvorak-style) intensity.

## 3. Precipitation & microwave

| Source | Product | Use |
|---|---|---|
| **GPM IMERG** (NASA/JAXA) | Half-hourly gridded precipitation, 0.1° | Rain-band structure, eyewall convection intensity |
| **GMI / SSMIS** | Passive microwave 89/37 GHz | Sees *through* cirrus to the low-level circulation centre — critical when the eye is obscured in IR |

Access: [NASA Earthdata](https://urs.earthdata.nasa.gov/) (free account).

## 4. Environmental / reanalysis predictors

**ERA5** (ECMWF, via [Copernicus CDS](https://cds.climate.copernicus.eu/)) — hourly, 0.25°.

| Variable | Why it matters for prediction |
|---|---|
| Sea surface temperature | Energy source; >26.5 °C sustains intensification |
| Vertical wind shear (200–850 hPa) | High shear disrupts the vortex → weakening |
| Relative humidity (mid-level) | Dry-air entrainment suppresses convection |
| Relative vorticity (850 hPa) | Low-level spin, genesis indicator |
| Steering flow (deep-layer mean wind) | Dominant control on track direction |
| Ocean heat content / D26 | Rapid-intensification predictor |

These features are what let the prediction model do better than pure image extrapolation.

## 5. Ground truth / labels

| Source | Contents | Role |
|---|---|---|
| **IMD Best Track (RSMC New Delhi)** | 3-hourly position, pressure, wind, category, for North Indian Ocean cyclones | **Primary labels** — the standard our output is judged against |
| **IBTrACS** (NOAA NCEI) | Global merged best-track archive, 1842–present | Extra training data; global pre-training before fine-tuning on NIO |
| **JTWC Best Track** | Independent NIO analyses | Label cross-checking, disagreement analysis |

**Intensity classification scale (IMD, North Indian Ocean):**

| Category | Code | Sustained wind (kt) |
|---|---|---|
| Low Pressure Area | LPA | < 17 |
| Depression | D | 17–27 |
| Deep Depression | DD | 28–33 |
| Cyclonic Storm | CS | 34–47 |
| Severe Cyclonic Storm | SCS | 48–63 |
| Very Severe Cyclonic Storm | VSCS | 64–89 |
| Extremely Severe Cyclonic Storm | ESCS | 90–119 |
| Super Cyclonic Storm | SuCS | ≥ 120 |

**Pattern classes (Dvorak-derived, for the classification head):**
`curved_band` · `shear` · `central_dense_overcast (CDO)` · `banding_eye` · `eye` · `central_cold_cover`

## 6. Access setup

```bash
# credentials go in .env — never commit them
MOSDAC_USERNAME=...        # https://www.mosdac.gov.in/  → register
MOSDAC_PASSWORD=...
EARTHDATA_USERNAME=...     # https://urs.earthdata.nasa.gov/
EARTHDATA_PASSWORD=...
CDS_API_KEY=...            # https://cds.climate.copernicus.eu/  → your API key
NOAA_API_TOKEN=...
```

Each fetcher in `data-pipeline/src/ingest/` reads these from config. Run one cycle manually:

```bash
make ingest
```

## 7. Preprocessing chain

```
Raw HDF5/NetCDF
  → radiometric calibration (counts → radiance → brightness temperature)
  → geo-reference & reproject to common grid (Mercator / equirectangular)
  → crop to North Indian Ocean bbox (lat 0–30 N, lon 55–100 E)
  → co-register all sources onto one grid + timestamp
  → normalize per channel (BT range clipped, scaled to [0,1])
  → tile into fixed patches (e.g. 256×256) around candidate centres
  → stack temporal sequence (N past frames) for the prediction model
  → write to MinIO; index metadata in PostGIS
```

Handled by `data-pipeline/src/transform/`.

## 8. Known data challenges (and how we handle them)

| Challenge | Handling |
|---|---|
| VIS unusable at night | Model trained on IR/WV-only path; VIS is an optional extra channel with masking |
| Parallax at high satellite zenith angle | Parallax correction during reprojection |
| Different resolutions & cadences per source | Resample to a common grid; nearest-in-time matching within a tolerance window |
| Class imbalance (few SuCS events) | Weighted loss, oversampling, augmentation, global IBTrACS pre-training |
| Cirrus obscuring the low-level centre | Fuse microwave channels which penetrate cirrus |
| Missing frames / feed outage | Temporal interpolation for gaps; explicit staleness flag when unrecoverable |
| Large data volume | Store only the NIO crop; tile-level storage in MinIO; lazy loading via xarray/dask |

## 9. Storage layout

```
ai-model/data/
├── raw/         # exactly as downloaded — never edited
├── external/    # third-party reference data (IBTrACS, shapefiles, district boundaries)
├── interim/     # partially processed (calibrated, reprojected)
└── processed/   # model-ready tensors / tiles + label files
```

All four are git-ignored. Only `.gitkeep` and per-folder `README.md` are tracked.

## 10. Licensing

Datasets stay under their providers' terms (ISRO/MOSDAC, IMD, NASA, ECMWF, NOAA, EUMETSAT).
**No third-party data is redistributed in this repository.** Cite sources in any published output.
