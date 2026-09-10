"""Colour-enhanced infrared satellite imagery for the Indian Ocean.

Source: EUMETSAT EUMETView WMS, layer `msg_iodc:ir108` — Meteosat Indian Ocean
Data Coverage, thermal infrared at 10.8 µm. Free, no key, and the same satellite
Zoom Earth uses for this basin. History runs to Sept 2020 at 15-minute steps, so
imagery can follow a storm through its lifetime.

The service returns greyscale brightness temperature. Meteorologists never read
it raw — they apply an *enhancement curve* that maps cloud-top temperature to
colour, so the deep convection around an eyewall separates from ordinary cloud.
That curve is applied here, server-side, for three reasons: the ramp stays
consistent, tiles can be cached so EUMETSAT is not hammered, and the browser
never needs canvas pixel access.

Warm pixels are made transparent rather than grey, so the ocean basemap shows
through and the storm reads the way it does on an IMD bulletin.
"""

from __future__ import annotations

import io
import time
from datetime import UTC, datetime, timedelta

import httpx
import numpy as np
from PIL import Image

WMS_URL = "https://view.eumetsat.int/geoserver/wms"
LAYER = "msg_iodc:ir108"
TILE_PX = 256
CACHE_TTL_SECONDS = 900
CACHE_MAX = 512

# Enhancement curve. Input is the 8-bit IR luminance where brighter = colder.
# Anchors are (luminance, R, G, B, alpha).
#
# Below ~120 the scene is warm — ocean, land, low cloud — and is left fully
# transparent so the basemap carries it. Above that the ramp runs
# white -> green -> yellow -> orange -> red -> magenta, which is the
# conventional deep-convection enhancement.
_ANCHORS = [
    (118, 255, 255, 255, 0),
    (140, 235, 240, 245, 90),
    (165, 200, 220, 230, 150),
    (185, 90, 200, 120, 205),
    (203, 240, 235, 90, 225),
    (219, 245, 170, 60, 235),
    (233, 230, 80, 55, 245),
    (245, 175, 40, 90, 250),
    (255, 235, 160, 235, 255),
]


def _build_lut() -> np.ndarray:
    """256-entry RGBA lookup table interpolated between the anchors."""
    lut = np.zeros((256, 4), dtype=np.uint8)
    for i in range(256):
        if i <= _ANCHORS[0][0]:
            lut[i] = (255, 255, 255, 0)
            continue
        for a, b in zip(_ANCHORS, _ANCHORS[1:], strict=False):
            if i <= b[0]:
                span = b[0] - a[0]
                t = (i - a[0]) / span if span else 0.0
                lut[i] = [round(a[j + 1] + t * (b[j + 1] - a[j + 1])) for j in range(4)]
                break
        else:
            lut[i] = _ANCHORS[-1][1:]
    return lut


_LUT = _build_lut()
_cache: dict[tuple, tuple[float, bytes]] = {}


def _tile_bbox(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """XYZ tile to Web Mercator bbox in metres."""
    extent = 20037508.342789244
    size = 2 * extent / (2**z)
    minx = -extent + x * size
    maxy = extent - y * size
    return (minx, maxy - size, minx + size, maxy)


def snap_time(when: datetime | str | None) -> str:
    """Round to the nearest 15-minute slot the service actually publishes.

    Also steps back ~30 minutes: the newest slot is often not yet processed and
    returns an empty tile, which looks like a bug rather than a data lag.
    """
    if when is None:
        dt = datetime.now(UTC) - timedelta(minutes=30)
    elif isinstance(when, str):
        try:
            dt = datetime.fromisoformat(when.replace("Z", "+00:00"))
        except ValueError:
            dt = datetime.now(UTC) - timedelta(minutes=30)
    else:
        dt = when
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    dt = dt.replace(minute=(dt.minute // 15) * 15, second=0, microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _colourise(raw: bytes) -> bytes:
    grey = np.array(Image.open(io.BytesIO(raw)).convert("L"))
    rgba = _LUT[grey]
    return _to_png(Image.fromarray(rgba, mode="RGBA"))


def _to_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


_TRANSPARENT = _to_png(Image.new("RGBA", (TILE_PX, TILE_PX), (0, 0, 0, 0)))


async def enhanced_ir_tile(z: int, x: int, y: int, when: str | None = None) -> bytes:
    """One colour-enhanced IR tile, cached briefly."""
    stamp = snap_time(when)
    key = (z, x, y, stamp)
    now = time.monotonic()

    hit = _cache.get(key)
    if hit and now - hit[0] < CACHE_TTL_SECONDS:
        return hit[1]

    minx, miny, maxx, maxy = _tile_bbox(z, x, y)
    params = {
        "service": "WMS",
        "version": "1.3.0",
        "request": "GetMap",
        "layers": LAYER,
        "styles": "",
        "crs": "EPSG:3857",
        "bbox": f"{minx},{miny},{maxx},{maxy}",
        "width": TILE_PX,
        "height": TILE_PX,
        "format": "image/png",
        "transparent": "true",
        "time": stamp,
    }

    try:
        async with httpx.AsyncClient(timeout=25) as client:
            r = await client.get(WMS_URL, params=params)
        if r.status_code != 200 or "image" not in r.headers.get("content-type", ""):
            png = _TRANSPARENT
        else:
            png = _colourise(r.content)
    except Exception:
        # A missing tile must not break the map — return nothing to draw.
        png = _TRANSPARENT

    if len(_cache) > CACHE_MAX:
        _cache.clear()
    _cache[key] = (now, png)
    return png


def legend() -> list[dict]:
    """Colour key for the enhancement curve, for the map legend."""
    return [
        {"label": "Low / warm cloud", "color": "#E8F0F5"},
        {"label": "Mid cloud", "color": "#C8DCE6"},
        {"label": "Deep cloud", "color": "#5AC878"},
        {"label": "Strong convection", "color": "#F0EB5A"},
        {"label": "Very cold tops", "color": "#F5AA3C"},
        {"label": "Overshooting tops", "color": "#E65037"},
        {"label": "Coldest", "color": "#EBA0EB"},
    ]
