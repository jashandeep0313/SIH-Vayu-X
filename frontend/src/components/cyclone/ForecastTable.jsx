import { CategoryBadge } from '../common/Badges.jsx';
import { formatIst, ktToKmph } from '../../utils/constants.js';

export default function ForecastTable({ forecast }) {
  if (!forecast?.points?.length) return null;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b border-hairline text-2xs uppercase tracking-wide text-ink-mute">
            <th className="px-4 py-2 font-medium">Lead</th>
            <th className="px-2 py-2 font-medium">Valid (IST)</th>
            <th className="px-2 py-2 font-medium">Position</th>
            <th className="px-2 py-2 text-right font-medium">Wind</th>
            <th className="px-2 py-2 text-right font-medium">Pressure</th>
            <th className="px-2 py-2 font-medium">Category</th>
            <th className="px-4 py-2 text-right font-medium">Uncertainty</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[#1C273899]">
          {forecast.points.map((p) => (
            <tr key={p.lead_hours} className="transition hover:bg-raised">
              <td className="tnum px-4 py-2 font-semibold text-ink">+{p.lead_hours}h</td>
              <td className="tnum px-2 py-2 text-ink-dim">{formatIst(p.valid_at)}</td>
              <td className="tnum px-2 py-2 text-ink-dim">
                {p.lat.toFixed(1)}°N {p.lon.toFixed(1)}°E
              </td>
              <td className="tnum px-2 py-2 text-right text-ink">
                {Math.round(p.est_wind_kt)} kt
                <span className="ml-1 text-2xs text-ink-mute">
                  {Math.round(ktToKmph(p.est_wind_kt))} km/h
                </span>
              </td>
              <td className="tnum px-2 py-2 text-right text-ink-dim">
                {Math.round(p.est_pressure_hpa)}
              </td>
              <td className="px-2 py-2">
                <CategoryBadge category={p.intensity_category} />
              </td>
              <td className="tnum px-4 py-2 text-right text-ink-mute">
                ±{Math.round(p.radius_uncertainty_km)} km
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
