import {
  Area,
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts';
import { CATEGORY_COLORS, formatUtc } from '../../utils/constants.js';

// IMD category thresholds, drawn as reference lines so a wind value can be read
// straight off the chart as a category
const THRESHOLDS = [
  { kt: 34, label: 'CS', color: CATEGORY_COLORS.CS },
  { kt: 48, label: 'SCS', color: CATEGORY_COLORS.SCS },
  { kt: 64, label: 'VSCS', color: CATEGORY_COLORS.VSCS },
  { kt: 90, label: 'ESCS', color: CATEGORY_COLORS.ESCS },
];

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;

  return (
    <div className="rounded-md border border-hairline-strong bg-raised px-2.5 py-2 shadow-panel">
      <div className="tnum text-2xs text-ink-mute">{formatUtc(label)}</div>
      {point.observed != null && (
        <div className="tnum text-xs text-ink">
          Observed <span className="font-semibold">{Math.round(point.observed)} kt</span>
        </div>
      )}
      {point.forecast != null && (
        <div className="tnum text-xs" style={{ color: '#D3AF37' }}>
          Forecast <span className="font-semibold">{Math.round(point.forecast)} kt</span>
          {point.spread != null && (
            <span className="ml-1 text-ink-mute">±{Math.round(point.spread)}</span>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Observed and forecast intensity on one shared axis, so the forecast reads as a
 * continuation of the observation and any discontinuity at the handover is
 * visible rather than hidden.
 */
export default function IntensityChart({ observations = [], forecast }) {
  const observed = observations.map((o) => ({
    time: new Date(o.observed_at).getTime(),
    observed: o.est_wind_kt,
  }));

  const last = observations[observations.length - 1];
  const forecastPoints = (forecast?.points ?? []).map((p) => {
    // Uncertainty in position grows with lead time; intensity spread tracks it
    const spread = 4 + p.lead_hours * 0.28;
    return {
      time: new Date(p.valid_at).getTime(),
      forecast: p.est_wind_kt,
      spread,
      band: [Math.max(0, p.est_wind_kt - spread), p.est_wind_kt + spread],
    };
  });

  // Join the series at the last observation so the lines connect
  if (last && forecastPoints.length) {
    forecastPoints.unshift({
      time: new Date(last.observed_at).getTime(),
      forecast: last.est_wind_kt,
      spread: 0,
      band: [last.est_wind_kt, last.est_wind_kt],
    });
  }

  const byTime = new Map();
  [...observed, ...forecastPoints].forEach((row) => {
    byTime.set(row.time, { ...(byTime.get(row.time) ?? {}), ...row });
  });
  const data = [...byTime.values()].sort((a, b) => a.time - b.time);

  if (!data.length) return null;

  const maxWind = Math.max(...data.map((d) => Math.max(d.observed ?? 0, d.band?.[1] ?? 0)));
  const nowTs = last ? new Date(last.observed_at).getTime() : null;

  return (
    <ResponsiveContainer width="100%" height={230}>
      <ComposedChart data={data} margin={{ top: 8, right: 44, bottom: 4, left: -18 }}>
        <CartesianGrid stroke="#1C2738" strokeDasharray="2 4" vertical={false} />

        {THRESHOLDS.filter((t) => t.kt < maxWind + 12).map((t) => (
          <ReferenceLine
            key={t.label}
            y={t.kt}
            stroke={t.color}
            strokeDasharray="2 4"
            strokeOpacity={0.35}
            label={{
              value: t.label,
              position: 'right',
              fill: t.color,
              fontSize: 9,
              opacity: 0.8,
            }}
          />
        ))}

        {nowTs && (
          <ReferenceLine
            x={nowTs}
            stroke="#686F7C"
            strokeDasharray="3 3"
            label={{ value: 'now', position: 'top', fill: '#686F7C', fontSize: 9 }}
          />
        )}

        <XAxis
          dataKey="time"
          type="number"
          domain={['dataMin', 'dataMax']}
          scale="time"
          tick={{ fill: '#686F7C', fontSize: 10 }}
          tickFormatter={(t) => formatUtc(new Date(t).toISOString(), { timeOnly: true })}
          stroke="#1C2738"
        />
        <YAxis
          tick={{ fill: '#686F7C', fontSize: 10 }}
          stroke="#1C2738"
          width={44}
          label={{
            value: 'kt',
            angle: 0,
            position: 'insideTopLeft',
            fill: '#686F7C',
            fontSize: 10,
            offset: 12,
          }}
        />
        <Tooltip content={<ChartTooltip />} cursor={{ stroke: '#2B3648' }} />

        <Area
          dataKey="band"
          stroke="none"
          fill="#D3AF37"
          fillOpacity={0.12}
          isAnimationActive={false}
          connectNulls
        />
        <Line
          type="monotone"
          dataKey="observed"
          stroke="#7FAF9A"
          strokeWidth={2}
          dot={{ r: 2, fill: '#7FAF9A', strokeWidth: 0 }}
          isAnimationActive={false}
        />
        <Line
          type="monotone"
          dataKey="forecast"
          stroke="#D3AF37"
          strokeWidth={2}
          strokeDasharray="5 4"
          dot={{ r: 2.5, fill: '#0E141E', stroke: '#D3AF37', strokeWidth: 1.5 }}
          isAnimationActive={false}
          connectNulls
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
