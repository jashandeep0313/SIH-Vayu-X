import { useEffect, useMemo, useState } from 'react';
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Polyline,
  Polygon,
  Tooltip,
  useMap,
} from 'react-leaflet';
import LayerControl from './LayerControl.jsx';
import TimelineControl from './TimelineControl.jsx';
import WindField from './WindField.jsx';
import { buildBasemaps, buildOverlays } from '../../utils/basemaps.js';
import { categoryColor, categoryLabel, formatUtc } from '../../utils/constants.js';

const DEFAULT_CENTER = [
  Number(import.meta.env.VITE_DEFAULT_CENTER_LAT ?? 15),
  Number(import.meta.env.VITE_DEFAULT_CENTER_LON ?? 82),
];
const DEFAULT_ZOOM = Number(import.meta.env.VITE_DEFAULT_ZOOM ?? 5);
const MAP_MAX_ZOOM = 12;

// Derived from our own forecast, not a third-party weather service
const ANALYSIS_LAYERS = [
  {
    id: 'windfield',
    label: 'Wind radii (R34/50/64)',
    hint: 'Gale, damaging and hurricane-force extent',
  },
  {
    id: 'isobars',
    label: 'Isobars',
    hint: 'Closed pressure contours at 4 hPa intervals',
  },
];

function PanTo({ position }) {
  const map = useMap();
  useEffect(() => {
    if (position) map.panTo(position, { animate: true, duration: 0.6 });
  }, [position, map]);
  return null;
}

/** Track drawn segment-by-segment so intensity change is legible along the path. */
function ObservedTrack({ observations }) {
  return observations.slice(1).map((obs, i) => {
    const prev = observations[i];
    return (
      <Polyline
        key={obs.observed_at}
        positions={[
          [prev.lat, prev.lon],
          [obs.lat, obs.lon],
        ]}
        pathOptions={{
          color: categoryColor(obs.intensity_category),
          weight: 3,
          opacity: 0.95,
        }}
      />
    );
  });
}

export default function CycloneMap({ cyclones = [], selectedId, onSelect }) {
  const [timeIndex, setTimeIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(450);

  const selectedCyclone = cyclones.find((c) => c.id === selectedId);
  const history = selectedCyclone?.observations ?? [];

  // Reset playback whenever a different storm is selected
  useEffect(() => {
    setTimeIndex(Math.max(0, history.length - 1));
    setPlaying(false);
     
  }, [selectedId, history.length]);

  const atLatest = timeIndex >= history.length - 1;
  const frame = history[Math.min(timeIndex, Math.max(0, history.length - 1))];

  // Satellite imagery follows the storm: GIBS is date-addressed, so scrubbing
  // the timeline also moves the basemap to that day.
  const imageryDate = frame?.observed_at ? frame.observed_at.slice(0, 10) : undefined;
  const basemaps = useMemo(() => buildBasemaps(imageryDate), [imageryDate]);
  // The IR overlay is time-addressed, so it needs the exact frame timestamp,
  // not just the date.
  const frameTime = frame?.observed_at ?? null;
  const overlays = useMemo(
    () => buildOverlays(imageryDate, frameTime),
    [imageryDate, frameTime],
  );
  const [basemapId, setBasemapId] = useState('ocean');
  const [activeOverlays, setActiveOverlays] = useState(['ir']);
  const [analysis, setAnalysis] = useState(['windfield']);

  const showWindField = analysis.includes('windfield');
  const showIsobars = analysis.includes('isobars');

  const toggleAnalysis = (id) =>
    setAnalysis((prev) => (prev.includes(id) ? prev.filter((a) => a !== id) : [...prev, id]));

  const basemap = basemaps.find((b) => b.id === basemapId) ?? basemaps[0];

  const toggleOverlay = (id) => {
    setActiveOverlays((prev) => {
      const next = prev.includes(id) ? prev.filter((o) => o !== id) : [...prev, id];
      // Some overlays only read correctly over a particular base — the IR
      // enhancement needs blue ocean beneath it, not a grey canvas.
      const wants = overlays.find((o) => o.id === id)?.pairsWith;
      if (wants && !prev.includes(id) && basemapId === 'dark') setBasemapId(wants);
      return next;
    });
  };

  const selected = cyclones.find((c) => c.id === selectedId);
  const focus = selected?.latest_observation
    ? [selected.latest_observation.lat, selected.latest_observation.lon]
    : null;

  return (
    <div className="relative h-full w-full">
      <MapContainer
        center={DEFAULT_CENTER}
        zoom={DEFAULT_ZOOM}
        maxZoom={MAP_MAX_ZOOM}
        className="h-full w-full"
        scrollWheelZoom
        zoomControl
      >
        {/* maxNativeZoom, not maxZoom: GIBS only serves to zoom 9, and without
            this the layer blanks out instead of upscaling when zoomed past it. */}
        <TileLayer
          key={basemap.id}
          url={basemap.url}
          attribution={basemap.attribution}
          maxNativeZoom={basemap.maxZoom}
          maxZoom={MAP_MAX_ZOOM}
        />

        {overlays
          .filter((o) => activeOverlays.includes(o.id))
          .map((o) => (
            <TileLayer
              key={`${o.id}-${o.url}`}
              url={o.url}
              attribution={o.attribution}
              maxNativeZoom={o.maxZoom}
              maxZoom={MAP_MAX_ZOOM}
              opacity={o.opacity}
            />
          ))}

        {/* Place names sit above imagery so coastlines stay identifiable */}
        {basemap.labels && (
          <TileLayer
            key={`${basemap.id}-labels`}
            url={basemap.labels}
            maxNativeZoom={13}
            maxZoom={MAP_MAX_ZOOM}
          />
        )}

        <PanTo position={focus} />

        {cyclones.map((cyclone) => {
          const obs = cyclone.latest_observation;
          if (!obs) return null;

          const isSelected = cyclone.id === selectedId;
          const track = cyclone.observations ?? [];
          // While scrubbing, show the storm only as far as the chosen moment
          const shown = isSelected ? track.slice(0, timeIndex + 1) : track;
          const head = (isSelected && shown[shown.length - 1]) || obs;
          const color = categoryColor(head.intensity_category);
          const forecast = cyclone.latest_forecast;
          const forecastPoints = forecast?.points ?? [];
          // For replayed historical storms the real outcome is known, so the
          // forecast can be drawn against what actually happened.
          const verified = forecast?.verification ?? [];
          const cone = forecast?.cone_geojson?.coordinates?.[0]?.map(([lon, lat]) => [lat, lon]);

          return (
            <div key={cyclone.id}>
              {/* Cone of uncertainty — a bare forecast line implies a precision
                  the model does not have */}
              {isSelected && atLatest && showWindField && (
                <WindField observation={head} showIsobars={showIsobars} />
              )}

              {isSelected && atLatest && cone && (
                <Polygon
                  positions={cone}
                  pathOptions={{
                    color,
                    weight: 1,
                    opacity: 0.5,
                    fillColor: color,
                    fillOpacity: 0.1,
                    dashArray: '3 5',
                  }}
                />
              )}

              {shown.length > 1 && <ObservedTrack observations={shown} />}

              {forecastPoints.length > 0 && (!isSelected || atLatest) && (
                <Polyline
                  positions={[[head.lat, head.lon], ...forecastPoints.map((p) => [p.lat, p.lon])]}
                  pathOptions={{ color, weight: 2, opacity: 0.85, dashArray: '6 6' }}
                />
              )}

              {/* What actually happened — only exists for replayed storms */}
              {isSelected && atLatest && verified.length > 0 && (
                <Polyline
                  positions={[
                    [head.lat, head.lon],
                    ...verified.map((v) => [v.actual_lat, v.actual_lon]),
                  ]}
                  pathOptions={{ color: '#7FAF9A', weight: 2.5, opacity: 0.95 }}
                />
              )}

              {isSelected &&
                atLatest &&
                verified.map((v) => (
                  <CircleMarker
                    key={`actual-${v.lead_hours}`}
                    center={[v.actual_lat, v.actual_lon]}
                    radius={4}
                    pathOptions={{
                      color: '#7FAF9A',
                      weight: 1.5,
                      fillColor: '#0E141E',
                      fillOpacity: 1,
                    }}
                  >
                    <Tooltip direction="top" offset={[0, -6]} opacity={1}>
                      <div className="text-2xs">
                        <div className="font-semibold" style={{ color: '#7FAF9A' }}>
                          Actual +{v.lead_hours}h
                        </div>
                        <div className="tnum">{Math.round(v.actual_wind_kt)} kt</div>
                        <div className="tnum opacity-70">
                          forecast off by {Math.round(v.track_error_km)} km
                        </div>
                      </div>
                    </Tooltip>
                  </CircleMarker>
                ))}

              {isSelected && atLatest &&
                forecastPoints.map((p) => (
                  <CircleMarker
                    key={p.lead_hours}
                    center={[p.lat, p.lon]}
                    radius={4}
                    pathOptions={{
                      color,
                      weight: 1.5,
                      fillColor: '#0E141E',
                      fillOpacity: 1,
                    }}
                  >
                    <Tooltip direction="top" offset={[0, -6]} opacity={1}>
                      <div className="text-2xs">
                        <div className="font-semibold">+{p.lead_hours}h</div>
                        <div>
                          {Math.round(p.est_wind_kt)} kt · {p.intensity_category}
                        </div>
                        <div className="opacity-60">±{p.radius_uncertainty_km} km</div>
                      </div>
                    </Tooltip>
                  </CircleMarker>
                ))}

              {shown.slice(0, -1).map((h) => (
                <CircleMarker
                  key={h.observed_at}
                  center={[h.lat, h.lon]}
                  radius={2.5}
                  pathOptions={{
                    color: categoryColor(h.intensity_category),
                    fillColor: categoryColor(h.intensity_category),
                    fillOpacity: 0.95,
                    weight: 0,
                  }}
                />
              ))}

              {isSelected && (
                <CircleMarker
                  center={[head.lat, head.lon]}
                  radius={7}
                  className="storm-pulse"
                  pathOptions={{ color, fillColor: color, fillOpacity: 0.3, weight: 0 }}
                />
              )}

              <CircleMarker
                center={[head.lat, head.lon]}
                radius={isSelected ? 8 : 6}
                pathOptions={{
                  color: isSelected ? '#F6EFD7' : color,
                  fillColor: color,
                  fillOpacity: 1,
                  weight: isSelected ? 2 : 1.5,
                }}
                eventHandlers={{ click: () => onSelect?.(cyclone.id) }}
              >
                <Tooltip direction="top" offset={[0, -8]} opacity={1}>
                  <div className="space-y-0.5">
                    <div className="text-xs font-semibold" style={{ color }}>
                      {cyclone.name ?? 'Unnamed system'}
                    </div>
                    <div className="text-2xs">{categoryLabel(head.intensity_category)}</div>
                    <div className="tnum text-2xs">
                      {Math.round(head.est_wind_kt)} kt · {Math.round(head.est_pressure_hpa)} hPa
                    </div>
                    <div className="tnum text-2xs opacity-60">{formatUtc(head.observed_at)}</div>
                  </div>
                </Tooltip>
              </CircleMarker>
            </div>
          );
        })}
      </MapContainer>

      <TimelineControl
        observations={history}
        index={timeIndex}
        onIndexChange={setTimeIndex}
        playing={playing}
        onPlayingChange={setPlaying}
        speed={speed}
        onSpeedChange={setSpeed}
      />

      <LayerControl
        basemaps={basemaps}
        activeBasemap={basemapId}
        onBasemapChange={setBasemapId}
        overlays={overlays}
        activeOverlays={activeOverlays}
        onOverlayToggle={toggleOverlay}
        analysis={ANALYSIS_LAYERS}
        activeAnalysis={analysis}
        onAnalysisToggle={toggleAnalysis}
      />
    </div>
  );
}
