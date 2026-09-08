import { Satellite, CheckCircle2, AlertCircle } from 'lucide-react';
import PointForecast from '../components/cyclone/PointForecast.jsx';
import { relativeTime } from '../utils/constants.js';

const CATALOGUE = {
  insat3d: { name: 'INSAT-3D', provider: 'ISRO / MOSDAC', role: 'Primary imagery — TIR-1, TIR-2, WV, MIR' },
  insat3dr: { name: 'INSAT-3DR', provider: 'ISRO / MOSDAC', role: 'Staggered scan — effective 15-min cadence' },
  scatsat1: { name: 'SCATSAT-1', provider: 'ISRO', role: 'Ocean surface winds — intensity cross-check' },
  era5: { name: 'ERA5 Reanalysis', provider: 'ECMWF / Copernicus', role: 'SST, shear, vorticity — track predictors' },
};

export default function DataSources({ pipeline }) {
  const sources = pipeline?.sources ?? [];

  return (
    <div className="space-y-3 p-4">
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Ingestion Status</span>
          <span
            className={`chip ${
              pipeline?.healthy
                ? 'bg-[#7FAF9A26] text-severity-green'
                : 'bg-[#E07A3F26] text-severity-orange'
            }`}
          >
            {pipeline?.healthy ? 'Healthy' : 'Degraded'}
          </span>
        </div>

        <div className="divide-y divide-hairline">
          {sources.map((s) => {
            const meta = CATALOGUE[s.id] ?? { name: s.id, provider: '—', role: '—' };
            const lagging = s.status !== 'ok';
            return (
              <div key={s.id} className="flex items-center gap-4 px-4 py-3">
                <Satellite size={15} className="shrink-0 text-ink-mute" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-ink">{meta.name}</span>
                    <span className="text-2xs text-ink-mute">{meta.provider}</span>
                  </div>
                  <div className="truncate text-2xs text-ink-dim">{meta.role}</div>
                </div>
                <div className="tnum shrink-0 text-right text-2xs">
                  <div className={lagging ? 'text-severity-yellow' : 'text-ink-dim'}>
                    {s.last_seen_minutes} min ago
                  </div>
                  <div className="flex items-center justify-end gap-1 text-ink-mute">
                    {lagging ? (
                      <AlertCircle size={10} className="text-severity-yellow" />
                    ) : (
                      <CheckCircle2 size={10} className="text-severity-green" />
                    )}
                    {s.status}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Live Numerical Forecast</span>
          <span className="chip bg-[#7FAF9A1F] text-sage ring-1 ring-inset ring-[#7FAF9A40]">Live</span>
        </div>
        <PointForecast />
      </div>

      <div className="panel px-4 py-3">
        <div className="panel-title mb-1">Why staleness is the metric that matters</div>
        <p className="max-w-2xl text-xs leading-relaxed text-ink-dim">
          A stalled ingestion pipeline looks exactly like calm weather — no new detections, no
          alerts, a quiet dashboard. Freshness per source is surfaced here and in the top bar so
          silence is never mistaken for safety. Last frame ingested{' '}
          <span className="text-ink">{relativeTime(pipeline?.last_frame_at)}</span>, against an
          expected cadence of {pipeline?.expected_cadence_minutes ?? 30} minutes.
        </p>
      </div>
    </div>
  );
}
