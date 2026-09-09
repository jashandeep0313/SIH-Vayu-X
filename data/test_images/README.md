# Test images

## `in_domain/` — use these for the model

Five frames from the NASA / Radiant Earth Tropical Cyclone Wind Estimation set, spanning the
intensity range. **Ground truth wind speed is in the filename.** These match what
`intensity_from_image_v1` was trained on: storm-centred infrared crops.

| File | Actual | Model predicts |
|---|---|---|
| `weak_20kt_actual20kt.jpg` | 20 kt | ~30 kt |
| `moderate_45kt_actual50kt.jpg` | 50 kt | ~45 kt |
| `strong_70kt_actual74kt.jpg` | 74 kt | ~42 kt |
| `severe_100kt_actual103kt.jpg` | 103 kt | ~107 kt |
| `extreme_130kt_actual128kt.jpg` | 128 kt | ~120 kt |

Mean absolute error across these five is 11.6 kt, consistent with the model's held-out
MAE of 11.2 kt.

```bash
curl -F "file=@data/test_images/in_domain/severe_100kt_actual103kt.jpg" \
     http://localhost:8000/api/v1/inference/upload
```

## Wide-area frames (git-ignored, regenerable)

Real NASA GIBS VIIRS true-colour images of MOCHA, BIPARJOY, TAUKTAE, REMAL and a clear-sky
negative control:

```bash
python scripts/fetch_test_images.py
```

**These are for looking at, not for the model.** They are wide-area true colour, not
storm-centred IR, and the model under-reads them badly — measured at −75 kt on MOCHA and
+30 kt on the clear-sky control. That gap is the honest limitation to state out loud, and it
closes when the model is retrained on INSAT data.
