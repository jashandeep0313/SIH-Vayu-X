import { useEffect } from 'react';
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Polyline,
  Polygon,
  Tooltip,
  useMap,
} from 'react-leaflet';
import { categoryColor, categoryLabel, formatUtc } from '../../utils/constants.js';

const DEFAULT_CENTER = [
  Number(import.meta.env.VITE_DEFAULT_CENTER_LAT ?? 15),
  Number(import.meta.env.VITE_DEFAULT_CENTER_LON ?? 82),
];
const DEFAULT_ZOOM = Number(import.meta.env.VITE_DEFAULT_ZOOM ?? 5);

// Dark basemap keeps the storm the brightest thing on screen.
// Esri Dark Gray Canvas is key-free; CARTO now watermarks unkeyed requests.
const TILE_URL =
  import.meta.env.VITE_MAP_TILE_URL ??
  'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}';

// Separate label layer so coastlines and place names sit above the track
const LABEL_URL =
  'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}';

function PanTo({ position }) {
  const map = useMap();
  useEffect(() => {
    if (position) map.panTo(position, { animate: true, duration: 0.6 });
  }, [position, map]);
  return null;
}

/** Track drawn segment-by-segment so intensity change is visible along the path. */
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
          weight: 2.5,
          opacity: 0.9,
        }}
      />
    );
  });
}

export default function CycloneMap({ cyclones = [], selectedId, onSelect }) {
  const selected = cyclones.find((c) => c.id === selectedId);
  const focus = selected?.latest_observation
    ? [selected.latest_observation.lat, selected.latest_observation.lon]
    : null;

  return (
    <MapContainer
      center={DEFAULT_CENTER}
      zoom={DEFAULT_ZOOM}
      className="h-full w-full"
      scrollWheelZoom
      zoomControl
      attributionControl
    >
      <TileLayer
        url={TILE_URL}
        attribution="Tiles &copy; Esri — Esri, DeLorme, NAVTEQ"
        maxZoom={16}
      />
      <TileLayer url={LABEL_URL} maxZoom={16} />
      <PanTo position={focus} />

      {cyclones.map((cyclone) => {
        const obs = cyclone.latest_observation;
        if (!obs) return null;

        const isSelected = cyclone.id === selectedId;
        const color = categoryColor(obs.intensity_category);
        const history = cyclone.observations ?? [];
        const forecast = cyclone.latest_forecast;
        const forecastPoints = forecast?.points ?? [];
        const cone = forecast?.cone_geojson?.coordinates?.[0]?.map(([lon, lat]) => [lat, lon]);

        return (
          <div key={cyclone.id}>
            {/* Cone of uncertainty — never draw a bare forecast line, it reads
                as a precision the model does not have */}
            {isSelected && cone && (
              <Polygon
                positions={cone}
                pathOptions={{
                  color,
                  weight: 1,
                  opacity: 0.45,
                  fillColor: color,
                  fillOpacity: 0.08,
                  dashArray: '3 4',
                }}
              />
            )}

            {history.length > 1 && <ObservedTrack observations={history} />}

            {forecastPoints.length > 0 && (
              <Polyline
                positions={[[obs.lat, obs.lon], ...forecastPoints.map((p) => [p.lat, p.lon])]}
                pathOptions={{ color, weight: 2, opacity: 0.75, dashArray: '5 6' }}
              />
            )}

            {isSelected &&
              forecastPoints.map((p) => (
                <CircleMarker
                  key={p.lead_hours}
                  center={[p.lat, p.lon]}
                  radius={3.5}
                  pathOptions={{
                    color,
                    weight: 1.5,
                    fillColor: '#0E1420',
                    fillOpacity: 1,
                  }}
                >
                  <Tooltip direction="top" offset={[0, -6]} opacity={1}>
                    <div className="text-2xs">
                      <div className="font-semibold">+{p.lead_hours}h</div>
                      <div>
                        {p.est_wind_kt} kt · {p.intensity_category}
                      </div>
                      <div className="text-ink-mute">±{p.radius_uncertainty_km} km</div>
                    </div>
                  </Tooltip>
                </CircleMarker>
              ))}

            {/* Historical positions */}
            {history.slice(0, -1).map((h) => (
              <CircleMarker
                key={h.observed_at}
                center={[h.lat, h.lon]}
                radius={2}
                pathOptions={{
                  color: categoryColor(h.intensity_category),
                  fillColor: categoryColor(h.intensity_category),
                  fillOpacity: 0.9,
                  weight: 0,
                }}
              />
            ))}

            {isSelected && (
              <CircleMarker
                center={[obs.lat, obs.lon]}
                radius={6}
                className="storm-pulse"
                pathOptions={{ color, fillColor: color, fillOpacity: 0.35, weight: 0 }}
              />
            )}

            {/* Current centre */}
            <CircleMarker
              center={[obs.lat, obs.lon]}
              radius={isSelected ? 8 : 6}
              pathOptions={{
                color: isSelected ? '#E8EDF5' : color,
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
                  <div className="text-2xs">{categoryLabel(obs.intensity_category)}</div>
                  <div className="text-2xs">
                    {obs.est_wind_kt} kt · {obs.est_pressure_hpa} hPa
                  </div>
                  <div className="text-2xs opacity-70">{formatUtc(obs.observed_at)}</div>
                </div>
              </Tooltip>
            </CircleMarker>
          </div>
        );
      })}
    </MapContainer>
  );
}
