import { useEffect, useState } from 'react';
import { Radio, RefreshCw, Database } from 'lucide-react';
import { formatUtc } from '../../utils/constants.js';

function Meter({ icon: Icon, label, value, tone = 'text-ink', iconTone, title }) {
  return (
    <div
      className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 ring-1 ring-hairline"
      title={title}
    >
      <Icon size={12} className={iconTone ?? 'text-ink-mute'} />
      <span className="text-2xs text-ink-mute">{label}</span>
      <span className={`tnum text-2xs font-medium ${tone}`}>{value}</span>
    </div>
  );
}

/**
 * Data staleness sits in the top bar deliberately: a stalled ingestion pipeline
 * is indistinguishable from calm weather unless it is made visible.
 */
export default function TopBar({ title, subtitle, connected, pipeline, dataSource, onRefresh }) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const staleness = pipeline?.staleness_minutes;
  const cadence = pipeline?.expected_cadence_minutes ?? 30;
  const stale = staleness != null && staleness > cadence * 2;

  return (
    <header className="flex h-[58px] shrink-0 items-center justify-between gap-4 border-b border-hairline bg-surface px-5">
      <div className="min-w-0">
        <h1 className="truncate font-display text-[15px] font-medium tracking-tight text-ink">
          {title}
        </h1>
        {subtitle && <p className="truncate text-2xs text-ink-mute">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-2">
        {dataSource &&
          (dataSource.real_data ? (
            <span
              className="chip bg-[#7FAF9A1F] text-sage ring-1 ring-inset ring-[#7FAF9A40]"
              title={dataSource.note}
            >
              Real Data
            </span>
          ) : (
            <span
              className="chip bg-[#D3AF371F] text-gold ring-1 ring-inset ring-[#D3AF3740]"
              title={dataSource.note}
            >
              Synthetic
            </span>
          ))}

        <Meter
          icon={Database}
          label="Data"
          value={staleness == null ? '—' : `${staleness}m`}
          tone={stale ? 'text-severity-orange' : 'text-ink'}
          iconTone={stale ? 'text-severity-orange' : 'text-ink-mute'}
          title={
            staleness == null
              ? 'Ingestion status unknown'
              : `Last satellite frame ingested ${staleness} min ago · expected every ${cadence} min`
          }
        />

        <Meter
          icon={Radio}
          label={connected ? 'Live' : 'Reconnecting'}
          value=""
          iconTone={connected ? 'text-sage' : 'text-severity-yellow'}
          title={connected ? 'Receiving live updates' : 'Reconnecting to live feed'}
        />

        <div className="hidden items-center rounded-lg px-2.5 py-1.5 ring-1 ring-hairline lg:flex">
          <span className="tnum text-2xs text-ink-dim">{formatUtc(now.toISOString())}</span>
        </div>

        <button type="button" onClick={onRefresh} className="btn" title="Refresh data">
          <RefreshCw size={12} />
        </button>
      </div>
    </header>
  );
}
