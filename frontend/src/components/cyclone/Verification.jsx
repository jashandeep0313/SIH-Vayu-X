import { Target } from 'lucide-react';

/**
 * Forecast scored against what actually happened.
 *
 * Only meaningful for replayed historical storms, where the real outcome is
 * known. A forecast you cannot check is a claim; shown beside the outcome it
 * becomes a result — including when the result is bad.
 */
export default function Verification({ forecast }) {
  const rows = forecast?.verification;
  if (!rows?.length) return null;

  const meanTrack = rows.reduce((s, r) => s + r.track_error_km, 0) / rows.length;
  const meanIntensity =
    rows.reduce((s, r) => s + Math.abs(r.intensity_error_kt), 0) / rows.length;

  return (
    <section className="panel">
      <div className="panel-header">
        <span className="panel-title">Forecast vs Actual</span>
        <div className="flex items-center gap-3 text-2xs text-ink-mute">
          <Target size={12} />
          <span className="tnum">
            mean {Math.round(meanTrack)} km · {meanIntensity.toFixed(1)} kt
          </span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-hairline text-2xs uppercase tracking-label text-ink-mute">
              <th className="px-4 py-2 font-medium">Lead</th>
              <th className="px-2 py-2 font-medium">Forecast</th>
              <th className="px-2 py-2 font-medium">Actual</th>
              <th className="px-2 py-2 text-right font-medium">Track error</th>
              <th className="px-2 py-2 text-right font-medium">Fcst wind</th>
              <th className="px-2 py-2 text-right font-medium">Actual wind</th>
              <th className="px-4 py-2 text-right font-medium">Intensity error</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1C273899]">
            {rows.map((r) => {
              const bad = r.track_error_km > 200;
              const intBad = Math.abs(r.intensity_error_kt) > 15;
              return (
                <tr key={r.lead_hours} className="row-hover">
                  <td className="tnum px-4 py-2 font-medium text-ink">+{r.lead_hours}h</td>
                  <td className="tnum px-2 py-2 text-ink-dim">
                    {r.forecast_lat.toFixed(1)}°N {r.forecast_lon.toFixed(1)}°E
                  </td>
                  <td className="tnum px-2 py-2 text-ink-dim">
                    {r.actual_lat.toFixed(1)}°N {r.actual_lon.toFixed(1)}°E
                  </td>
                  <td
                    className={`tnum px-2 py-2 text-right ${bad ? 'text-severity-orange' : 'text-sage'}`}
                  >
                    {Math.round(r.track_error_km)} km
                  </td>
                  <td className="tnum px-2 py-2 text-right text-ink-dim">
                    {Math.round(r.forecast_wind_kt)} kt
                  </td>
                  <td className="tnum px-2 py-2 text-right text-ink">
                    {Math.round(r.actual_wind_kt)} kt
                  </td>
                  <td
                    className={`tnum px-4 py-2 text-right ${intBad ? 'text-severity-orange' : 'text-sage'}`}
                  >
                    {r.intensity_error_kt > 0 ? '+' : ''}
                    {r.intensity_error_kt.toFixed(1)} kt
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="border-t border-hairline px-4 py-2.5 text-2xs leading-relaxed text-ink-mute">
        Replayed storm from a season held out of training, scored against IBTrACS best track.
        Negative intensity error means the model under-forecast the storm — the known weakness
        at rapid intensification.
      </p>
    </section>
  );
}
