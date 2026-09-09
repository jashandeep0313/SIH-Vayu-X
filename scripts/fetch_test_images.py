"""Download real satellite images of real cyclones, for testing the upload path.

Pulls NASA GIBS true-colour imagery centred on historical storm positions taken
from IBTrACS, and writes one PNG per storm. Public, no credentials.

    python scripts/fetch_test_images.py
    python scripts/fetch_test_images.py --out my_dir --zoom 5

These are genuine satellite frames of genuine cyclones — useful for exercising
the upload endpoint end to end, and for a demo where a judge hands you an image.
"""

from __future__ import annotations

import argparse
import io
import math
from pathlib import Path

import httpx

GIBS = (
    "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/"
    "{layer}/default/{date}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg"
)

# Real North Indian Ocean cyclones at or near peak intensity (IBTrACS positions)
STORMS = [
    {"name": "MOCHA", "date": "2023-05-14", "lat": 19.0, "lon": 92.5, "peak_kt": 115,
     "note": "ESCS, Bay of Bengal, landfall Myanmar/Bangladesh"},
    {"name": "BIPARJOY", "date": "2023-06-15", "lat": 22.5, "lon": 68.0, "peak_kt": 90,
     "note": "VSCS, Arabian Sea, landfall Gujarat"},
    {"name": "TAUKTAE", "date": "2021-05-17", "lat": 19.5, "lon": 71.0, "peak_kt": 100,
     "note": "ESCS, Arabian Sea, landfall Gujarat"},
    {"name": "REMAL", "date": "2024-05-26", "lat": 21.0, "lon": 89.0, "peak_kt": 60,
     "note": "SCS, Bay of Bengal, landfall West Bengal/Bangladesh"},
    {"name": "CLEAR_SKY_CONTROL", "date": "2024-02-10", "lat": 15.0, "lon": 85.0, "peak_kt": 0,
     "note": "Negative control — calm Bay of Bengal, no cyclone present"},
]


def _tile_xy(lat: float, lon: float, z: int) -> tuple[int, int]:
    n = 2**z
    x = int((lon + 180.0) / 360.0 * n)
    lat_r = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    return x, y


def fetch_storm(storm: dict, out_dir: Path, zoom: int, span: int,
                layer: str = "VIIRS_SNPP_CorrectedReflectance_TrueColor") -> Path | None:
    from PIL import Image

    cx, cy = _tile_xy(storm["lat"], storm["lon"], zoom)
    half = span // 2
    size = 256
    canvas = Image.new("RGB", (size * span, size * span))

    got = 0
    for dy in range(-half, -half + span):
        for dx in range(-half, -half + span):
            url = GIBS.format(layer=layer, date=storm["date"], z=zoom, x=cx + dx, y=cy + dy)
            try:
                r = httpx.get(url, timeout=45, follow_redirects=True)
                if r.status_code != 200 or "image" not in r.headers.get("content-type", ""):
                    continue
                tile = Image.open(io.BytesIO(r.content)).convert("RGB")
                canvas.paste(tile, ((dx + half) * size, (dy + half) * size))
                got += 1
            except Exception:
                continue

    if got == 0:
        print(f"  {storm['name']:20} no tiles returned")
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{storm['name'].lower()}_{storm['date']}.png"
    canvas.save(path)
    kb = path.stat().st_size / 1024
    print(f"  {storm['name']:20} {got:2}/{span*span} tiles  {canvas.size[0]}x{canvas.size[1]}  {kb:6.0f} KB  {storm['note']}")
    return path


def main() -> None:
    p = argparse.ArgumentParser(description="Fetch real cyclone satellite images")
    p.add_argument("--out", default="data/test_images")
    p.add_argument("--zoom", type=int, default=5)
    p.add_argument("--span", type=int, default=3, help="tiles per side")
    args = p.parse_args()

    out = Path(args.out)
    print(f"Fetching real cyclone imagery from NASA GIBS -> {out}/")
    written = [fetch_storm(s, out, args.zoom, args.span) for s in STORMS]
    ok = [w for w in written if w]
    print(f"\n{len(ok)}/{len(STORMS)} images written to {out}/")
    if ok:
        print("\nTest the upload endpoint:")
        print(f'  curl -F "file=@{ok[0]}" http://localhost:8000/api/v1/inference/upload')


if __name__ == "__main__":
    main()
