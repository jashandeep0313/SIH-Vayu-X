import { Circle, Tooltip } from 'react-leaflet';

// Standard operational wind radii. These are what IMD publishes and what
// district authorities plan evacuations against.
const WIND_RADII = [
  { key: 'r64_km', kt: 64, label: 'Hurricane force', color: '#D4544E' },
  { key: 'r50_km', kt: 50, label: 'Damaging', color: '#E07A3F' },
  { key: 'r34_km', kt: 34, label: 'Gale force', color: '#D3AF37' },
];

/**
 * Wind radii and closed isobars around the storm centre.
 *
 * Derived from our own forecast via the Holland (1980) parametric profile, not
 * from a third-party weather service — the pressure and wind structure follows
 * from central pressure, peak wind and radius of maximum wind, all of which the
 * model already produces.
 */
export default function WindField({ observation, showIsobars = true }) {
  const field = observation?.wind_field;
  if (!field) return null;

  const center = [observation.lat, observation.lon];

  return (
    <>
      {/* Isobars first so wind radii read above them */}
      {showIsobars &&
        field.isobars?.map((iso) => (
          <Circle
            key={`iso-${iso.pressure_hpa}`}
            center={center}
            radius={iso.radius_km * 1000}
            pathOptions={{
              color: '#8E939D',
              weight: 0.7,
              opacity: 0.45,
              fill: false,
            }}
            interactive={false}
          />
        ))}

      {/* Largest radius first, so smaller ones stay clickable on top */}
      {WIND_RADII.map(({ key, kt, label, color }) => {
        const km = field.wind_radii?.[key];
        if (!km) return null;
        return (
          <Circle
            key={key}
            center={center}
            radius={km * 1000}
            pathOptions={{
              color,
              weight: 1.2,
              opacity: 0.85,
              fillColor: color,
              fillOpacity: 0.06,
              dashArray: '4 4',
            }}
          >
            <Tooltip direction="top" opacity={1} sticky>
              <div className="text-2xs">
                <div className="font-semibold" style={{ color }}>
                  {kt} kt radius · {label}
                </div>
                <div className="tnum">{Math.round(km)} km from centre</div>
              </div>
            </Tooltip>
          </Circle>
        );
      })}

      {/* Radius of maximum wind — the eyewall */}
      {field.rmw_km && (
        <Circle
          center={center}
          radius={field.rmw_km * 1000}
          pathOptions={{ color: '#F6EFD7', weight: 1, opacity: 0.7, fill: false }}
          interactive={false}
        />
      )}
    </>
  );
}

export { WIND_RADII };
