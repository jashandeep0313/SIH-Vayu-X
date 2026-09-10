# Test images

Two sets, for two different purposes. The distinction matters: one set the model
should score, the other it should **refuse**.

## `in_domain/` and `nasa_ir_*.jpg` — use these for the model

Frames from the NASA / Radiant Earth Tropical Cyclone Wind Estimation set, spanning the
intensity range. **Ground truth wind speed is in the filename.** These match what
`intensity_from_image_v2` was trained on: storm-centred, single-channel infrared crops.

Measured against the running service (`intensity_from_image_v2`, severity-weighted):

| File | Actual | Estimate | Error | Confidence |
|---|---|---|---|---|
| `in_domain/weak_20kt_actual20kt.jpg` | 20 kt | 23.4 kt | +3.4 | 80% |
| `in_domain/moderate_45kt_actual50kt.jpg` | 50 kt | 44.0 kt | −6.0 | 45% |
| `in_domain/strong_70kt_actual74kt.jpg` | 74 kt | 40.8 kt | **−33.2** | **29%** |
| `in_domain/severe_100kt_actual103kt.jpg` | 103 kt | 98.9 kt | −4.1 | 90% |
| `in_domain/extreme_130kt_actual128kt.jpg` | 128 kt | 125.6 kt | −2.4 | 91% |

Mean absolute error across these five is 9.8 kt, consistent with the model's held-out
MAE of 10.25 kt.

The `strong_70kt` frame is the interesting one, and it is kept precisely because it
fails. The estimate is 33 kt low — but confidence drops to 29%, the lowest of the set,
and the interval widens accordingly. That is the calibration doing its job: the model
is wrong *and it says so*, rather than being wrong at 90% confidence. Confidence
tracking error is more useful than confidence being high.

`nasa_ir_*.jpg` in this directory are the same kind of frame with the IMD category in
the filename instead (LPA/D/DD/CS/SCS/VSCS/ESCS); two of them are the same frames as
`in_domain/`, renamed.

```bash
curl -F "file=@data/test_images/in_domain/severe_100kt_actual103kt.jpg" \
     http://localhost:8000/api/v1/inference/upload
```

## Wide-area frames (`*.png`, git-ignored, regenerable)

Real NASA GIBS VIIRS true-colour images of MOCHA, BIPARJOY, TAUKTAE, REMAL and a
clear-sky negative control:

```bash
python scripts/fetch_test_images.py
```

**These are for looking at, and for testing that the model refuses them.** They are
wide-area true colour, not storm-centred IR. All five are now rejected by the novelty
gates rather than scored:

| File | Refused by |
|---|---|
| `mocha_2023-05-14.png` | chroma + texture |
| `biparjoy_2023-06-15.png` | chroma + texture |
| `tauktae_2021-05-17.png` | chroma + texture |
| `remal_2024-05-26.png` | chroma + texture |
| `clear_sky_control_2024-02-10.png` | chroma |

This is the behaviour that matters. An earlier version *scored* these, reading MOCHA
at 40 kt against a real 115 kt — a 75 kt underestimate on a live cyclone, delivered
with a confident-looking number attached. Refusing is the correct answer: the frames
are the wrong modality, and "cannot assess this image" is a safe response where a
number is not.

Note the UI distinguishes **"cannot assess this image"** from **"no cyclonic system
detected"**. They are different claims, and conflating them is how a real storm gets
waved through.
