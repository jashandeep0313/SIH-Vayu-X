import { useEffect, useState } from 'react';
import { Radio, RefreshCw, Database } from 'lucide-react';
import { formatUtc } from '../../utils/constants.js';

/**
 * Data staleness sits in the top bar on purpose: a stalled ingestion pipeline
 * is indistinguishable from calm weather unless it is made visible.
 */
export default function TopBar({ title, subtitle, connected, pipeline, demoMode, onRefresh }) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const staleness = pipeline?.staleness_minutes;
  const cadence = pipeline?.expected_cadence_minutes ?? 30;
  const stale = staleness != null && staleness > cadence * 2;

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-line bg-surface px-5">
      <div className="min-w-0">
        <h1 className="truncate text-sm font-semibold text-ink">{title}</h1>
        {subtitle && <p className="truncate text-2xs text-ink-mute">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-2">
        {demoMode && (
          <span
            className="chip bg-accent/15 text-accent ring-1 ring-inset ring-accent/30"
            title="Synthetic data — no live satellite feed connected"
          >
            Demo Data
          </span>
        )}

        <div
          className="flex items-center gap-1.5 rounded-md border border-line bg-raised px-2.5 py-1.5"
          title={
            staleness == null
              ? 'Ingestion status unknown'
              : `Last satellite frame ingested ${staleness} min ago · expected every ${cadence} min`
          }
        >
          <Database size={12} className={stale ? 'text-severity-orange' : 'text-ink-mute'} />
          <span className="text-2xs text-ink-dim">Data</span>
          <span
            className={`tnum text-2xs font-medium ${stale ? 'text-severity-orange' : 'text-ink'}`}
          >
            {staleness == null ? '—' : `${staleness}m`}
          </span>
        </div>

        <div
          className="flex items-center gap-1.5 rounded-md border border-line bg-raised px-2.5 py-1.5"
          title={connected ? 'Receiving live updates' : 'Reconnecting to live feed'}
        >
          <Radio
            size={12}
            className={connected ? 'text-severity-green' : 'text-severity-yellow'}
          />
          <span className="text-2xs text-ink-dim">
            {connected ? 'Live' : 'Reconnecting'}
          </span>
        </div>

        <div className="hidden items-center rounded-md border border-line bg-raised px-2.5 py-1.5 lg:flex">
          <span className="tnum text-2xs text-ink-dim">{formatUtc(now.toISOString())}</span>
        </div>

        <button type="button" onClick={onRefresh} className="btn" title="Refresh data">
          <RefreshCw size={12} />
        </button>
      </div>
    </header>
  );
}
