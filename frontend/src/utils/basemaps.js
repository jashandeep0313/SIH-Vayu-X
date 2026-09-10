/**
 * Map layer catalogue.
 *
 * All sources are key-free. NASA GIBS matters most here: it serves the actual
 * satellite products this project reasons about — true-colour cloud imagery and
 * infrared brightness temperature, which is the channel the Dvorak technique and
 * our classification model read.
 */

/** GIBS imagery lags by a few hours; step back a day to guarantee coverage. */
export function gibsDate(offsetDays = 1) {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - offsetDays);
  return d.toISOString().slice(0, 10);
}

const gibs = (layer, matrix, ext, date) =>
  `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/${layer}/default/${date}/${matrix}/{z}/{y}/{x}.${ext}`;

const ESRI_ATTR = 'Tiles &copy; Esri';
const NASA_ATTR = 'Imagery &copy; NASA EOSDIS GIBS';

// Dark-text reference for dark basemaps; light reference for bright imagery,
// where the dark labels would be unreadable.
const LABELS_DARK =
  'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}';
const LABELS_IMAGERY =
  'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}';

export function buildBasemaps(date = gibsDate()) {
  return [
    {
      id: 'dark',
      label: 'Dark Canvas',
      hint: 'Neutral reference — storm reads clearest',
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
      attribution: ESRI_ATTR,
      maxZoom: 16,
      labels: LABELS_DARK,
    },
    {
      id: 'ocean',
      label: 'Ocean',
      hint: 'Blue ocean — the base for the enhanced IR overlay',
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}',
      attribution: ESRI_ATTR,
      maxZoom: 13,
    },
    {
      id: 'viirs',
      label: 'VIIRS True Colour',
      hint: `VIIRS SNPP · ${date} · finer detail`,
      url: gibs('VIIRS_SNPP_CorrectedReflectance_TrueColor', 'GoogleMapsCompatible_Level9', 'jpg', date),
      attribution: NASA_ATTR,
      maxZoom: 9,
      labels: LABELS_IMAGERY,
    },
    {
      id: 'imagery',
      label: 'Satellite',
      hint: 'High-resolution basemap for landfall context',
      url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      attribution: ESRI_ATTR,
      maxZoom: 17,
      labels: LABELS_IMAGERY,
    },
    {
      id: 'street',
      label: 'Street',
      hint: 'Settlements and roads — evacuation planning',
      url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 18,
    },
  ];
}

export function buildOverlays(date = gibsDate(), isoTime = null) {
  return [
    {
      id: 'ir',
      label: 'Enhanced IR (Meteosat)',
      hint: 'Colour-enhanced cloud-top temperature · best over Ocean or Satellite',
      // Served by our own backend, which fetches Meteosat IODC from EUMETSAT and
      // applies the enhancement curve. `time` lets the imagery follow the timeline.
      url: `/api/v1/imagery/ir/{z}/{x}/{y}.png${isoTime ? `?time=${encodeURIComponent(isoTime)}` : ''}`,
      attribution: 'Imagery &copy; EUMETSAT · Meteosat IODC',
      maxZoom: 8,
      opacity: 1,
      pairsWith: 'ocean',
    },
    // NASA's own MODIS brightness-temperature and cloud-top layers are not used:
    // both ship fixed, heavily saturated ramps meant for standalone Worldview
    // viewing, and composited under the track they obliterate the basemap. The IR
    // layer above is Meteosat IODC put through our own enhancement curve instead.
    {
      id: 'precip',
      label: 'Precipitation',
      hint: 'GPM IMERG rain rate — rain-band structure',
      url: gibs('IMERG_Precipitation_Rate', 'GoogleMapsCompatible_Level6', 'png', `${date}T00:00:00Z`),
      attribution: NASA_ATTR,
      maxZoom: 6,
      opacity: 0.75,
    },
  ];
}
