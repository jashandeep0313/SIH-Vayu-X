# frontend/ — Operations Dashboard

React + Vite dashboard: live basin map, cyclone tracks, cone of uncertainty, intensity
charts, and the alert console.

## Run

```bash
npm install
npm run dev
```

http://localhost:5173 — proxies `/api` and `/ws` to the backend on :8000.

## Layout

```
src/
├── main.jsx                 Entry point
├── App.jsx                  App shell, routes, shared data fetching
├── pages/
│   ├── Dashboard.jsx        KPI row + map + storm detail + forecast
│   ├── Alerts.jsx           Alert console with dispatch status
│   ├── History.jsx          Past events, verification
│   └── DataSources.jsx      Per-source ingestion freshness
├── components/
│   ├── layout/              Sidebar.jsx · TopBar.jsx
│   ├── map/CycloneMap.jsx           Leaflet basin map, track + cone
│   ├── charts/IntensityChart.jsx    Observed vs forecast, category thresholds
│   ├── cyclone/             StormList · ClassificationPanel · ForecastTable
│   └── common/              Badges.jsx · StatCard.jsx · States.jsx
├── hooks/
│   ├── useLiveCyclones.js    REST seed + WebSocket updates
│   └── useCycloneDetail.js   Track + forecast for the selected system
├── services/
│   ├── api.js                All REST calls
│   └── websocket.js          Live connection with backoff reconnect
├── utils/constants.js        IMD categories, colours, conversions
└── styles/index.css          Design tokens + Leaflet theming
```

## Design system

Dark by default — these screens sit in operations rooms running continuously.
Palette and type come from the **Prosperon** design system: navy `#1C2738`,
sage `#7FAF9A`, gold `#D3AF37`, set in DM Sans (display) and Urbanist (body).

| Token group | Purpose |
|---|---|
| `canvas` → `overlay` | Layered navy surfaces; depth from elevation, not heavy outlines |
| `ink` / `ink-dim` / `ink-mute` | Three-step text hierarchy |
| `gold` | Brand accent — active nav, focus, key affordances |
| `sage` | Positive / healthy states |
| `severity.*` | **Reserved for IMD warning levels.** Never decorative |
| `CATEGORY_COLORS` | Slate → sage → gold → orange → red intensity ramp |

Conventions worth keeping:

- Numeric columns use `.tnum` (tabular figures) so measurements align.
- Severity is conveyed by a **badge plus a tinted header wash**, never a coloured
  rule down the edge of a card — the wash carries further and keeps cards flush.
- Micro-labels use `.field-label` (uppercase, letterspaced, muted) rather than headings.

## Map layers

Base layers and overlays are catalogued in `src/utils/basemaps.js`; the switcher is a
custom control (`components/map/LayerControl.jsx`) rather than Leaflet's stock one.
**Every source is key-free.**

| Layer | Source | Why it's here |
|---|---|---|
| Dark Canvas | Esri | Neutral default — the storm is the brightest thing on screen |
| True Colour | NASA GIBS (MODIS Terra) | Real satellite cloud imagery for the demo date |
| VIIRS True Colour | NASA GIBS (SNPP) | Finer detail, second daily pass |
| Satellite | Esri World Imagery | High-resolution context near landfall |
| Ocean | Esri | Bathymetry — pairs with ocean-heat-content discussion |
| Street | OpenStreetMap | Settlements and roads for evacuation planning |
| Precipitation *(overlay)* | NASA GIBS (GPM IMERG) | Rain-band structure; composites cleanly |

**No IR / cloud-top overlay is included.** `MODIS_*_Brightness_Temp_Band31` and
`MODIS_*_Cloud_Top_Temp` were both tried and rejected: they ship fixed, heavily
saturated colour ramps built for standalone NASA Worldview viewing, and composited
under the track they obliterate the basemap. The cyclone-relevant IR view will come
from our own INSAT composites in `data-pipeline/`, rendered with a ramp we control.

GIBS serves only to zoom 9 (some products to 6), so layers set `maxNativeZoom` —
without it the map goes blank when zoomed past the source's limit instead of upscaling.

## Conventions

| Rule | Why |
|---|---|
| Data fetching only in `services/` | Components stay mockable while the backend still returns 501s |
| Functional components + hooks only | One consistent pattern across the codebase |
| `PascalCase.jsx` components, `useCamelCase.js` hooks | Predictable file lookup |
| IMD colours come from `utils/constants.js` | Severity colour is meaning, not decoration — never hardcode it |
| Always render a loading, empty, and error state | The backend will be down often during development |

## Design decisions worth keeping

- **Always draw the cone of uncertainty**, never a bare forecast line. A single line implies a
  precision the model does not have, and that misreads as certainty to whoever acts on it.
- **Surface model confidence** on every observation. Analysts need to know when to distrust it.
- **The live/reconnecting indicator is deliberate.** A dashboard that has silently stopped
  updating during a cyclone is worse than one that is obviously offline.
- **Dark theme** — these screens sit in operations rooms running continuously.

## Environment

```
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws
VITE_DEFAULT_CENTER_LAT=15.0
VITE_DEFAULT_CENTER_LON=80.0
VITE_DEFAULT_ZOOM=5
```

Only `VITE_*` variables reach the browser — never put a secret in one.

## Build

```bash
npm run build     # → dist/
npm run preview
```
