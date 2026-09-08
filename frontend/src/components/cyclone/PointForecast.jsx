import { useEffect, useState } from 'react';
import {
  Area,
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Wind, Gauge, CloudRain, ExternalLink } from 'lucide-react';
import { EmptyState, LoadingState } from '../common/States.jsx';
import { system } from '../../services/api.js';
import { formatIst } from '../../utils/constants.js';

function Stat({ icon: Icon, label, value, unit }) {
  return (
    <div className="rounded-lg bg-raised px-3 py-2 ring-1 ring-hairline">
      <div className="flex items-center gap-1.5">
        <Icon size={11} className="text-ink-mute" />
        <span className="field-label">{label}</span>
      </div>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="tnum font-display text-lg font-medium leading-none text-ink">
          {value ?? '—'}
        </span>
        {unit && <span className="text-2xs text-ink-mute">{unit}</span>}
      </div>
    </div>
  );
}

/**
 * Live numerical-model forecast at a fixed coastal reference point, via Windy.
 *
 * Deliberately NOT rendered beside the tracked cyclone: in DEMO_MODE the storm is
 * synthetic, so a real GFS feed would show calm conditions next to a synthetic
 * VSCS and read as a broken dashboard. In live operation this same endpoint
 * becomes a genuine cross-check — our estimate comes from satellite imagery,
 * this comes from a numerical model, and disagreement is worth surfacing.
 */
export default function PointForecast({ lat = 19.8, lon = 85.0, place = 'Puri, Odisha' }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    system
      .environmentPoint(lat, lon, 72)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [lat, lon]);

  if (loading) return <LoadingState label="Fetching numerical forecast" />;
  if (error)
    return (
      <EmptyState
        title="Point forecast unavailable"
        hint="Set WINDY_POINT_API_KEY in .env to enable this feed."
      />
    );
  if (!data?.points?.length) return <EmptyState title="No forecast data returned" />;

  const chart = data.points.map((p) => ({
    t: new Date(p.valid_at).getTime(),
    wind: p.wind_kt,
    pressure: p.pressure_hpa,
    precip: p.precip_mm_3h,
  }));

  return (
    <div className="space-y-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="font-display text-xs font-medium text-ink">{place}</div>
          <div className="tnum text-2xs text-ink-mute">
            {lat.toFixed(2)}°N {lon.toFixed(2)}°E · {data.model} · fetched{' '}
            {formatIst(data.fetched_at)} IST
          </div>
        </div>
        <a
          href="https://api.windy.com/point-forecast/docs"
          target="_blank"
          rel="noreferrer"
          className="btn"
        >
          {data.source}
          <ExternalLink size={10} />
        </a>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <Stat icon={Wind} label="Peak wind 72h" value={data.summary.max_wind_kt} unit="kt" />
        <Stat
          icon={Gauge}
          label="Min pressure"
          value={data.summary.min_pressure_hpa}
          unit="hPa"
        />
        <Stat
          icon={CloudRain}
          label="Total rain"
          value={data.summary.total_precip_mm}
          unit="mm"
        />
      </div>

      <ResponsiveContainer width="100%" height={150}>
        <ComposedChart data={chart} margin={{ top: 6, right: 8, bottom: 0, left: -22 }}>
          <CartesianGrid stroke="#1C2738" strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="t"
            type="number"
            domain={['dataMin', 'dataMax']}
            scale="time"
            tick={{ fill: '#686F7C', fontSize: 9 }}
            tickFormatter={(t) => new Date(t).toISOString().slice(11, 16)}
            stroke="#1C2738"
          />
          <YAxis tick={{ fill: '#686F7C', fontSize: 9 }} stroke="#1C2738" width={38} />
          <Tooltip
            contentStyle={{
              background: '#131A27',
              border: '1px solid #2B3648',
              borderRadius: 8,
              fontSize: 11,
            }}
            labelFormatter={(t) => formatIst(new Date(t).toISOString()) + ' IST'}
          />
          <Area
            dataKey="precip"
            stroke="none"
            fill="#7FAF9A"
            fillOpacity={0.22}
            name="Rain (mm/3h)"
            isAnimationActive={false}
          />
          <Line
            dataKey="wind"
            stroke="#D3AF37"
            strokeWidth={2}
            dot={false}
            name="Wind (kt)"
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>

      <p className="text-2xs leading-relaxed text-ink-mute">
        Independent numerical-model feed, shown here rather than beside the tracked system:
        the demo cyclone is synthetic, so a live model would disagree with it by design. In
        live operation this becomes a cross-check on the satellite-derived intensity estimate.
      </p>
    </div>
  );
}
