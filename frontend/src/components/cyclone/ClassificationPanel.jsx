import { Eye, Gauge, Wind, Waves } from 'lucide-react';
import { CategoryBadge, ConfidenceBar } from '../common/Badges.jsx';
import {
  categoryColor,
  categoryLabel,
  ktToKmph,
  PATTERN_TYPES,
} from '../../utils/constants.js';

function Metric({ icon: Icon, label, value, unit, sub }) {
  return (
    <div className="rounded-md border border-hairline bg-raised px-3 py-2.5">
      <div className="flex items-center gap-1.5 text-2xs text-ink-mute">
        <Icon size={11} />
        {label}
      </div>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="tnum text-lg font-semibold leading-none text-ink">{value}</span>
        {unit && <span className="text-2xs text-ink-mute">{unit}</span>}
      </div>
      {sub && <div className="tnum mt-0.5 text-2xs text-ink-mute">{sub}</div>}
    </div>
  );
}

/**
 * What the classification model saw and how sure it was.
 *
 * The T-number cross-reference is deliberate: it lets an IMD analyst sanity-check
 * the output against the Dvorak method they already trust.
 */
export default function ClassificationPanel({ observation }) {
  if (!observation) return null;

  const probs = Object.entries(observation.class_probabilities ?? {}).sort(
    (a, b) => b[1] - a[1],
  );
  const color = categoryColor(observation.intensity_category);

  return (
    <div className="space-y-3 p-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold" style={{ color }}>
            {categoryLabel(observation.intensity_category)}
          </div>
          <div className="text-2xs text-ink-mute">
            Pattern: {PATTERN_TYPES[observation.pattern_type] ?? '—'}
          </div>
        </div>
        <CategoryBadge category={observation.intensity_category} size="lg" />
      </div>

      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        <Metric
          icon={Wind}
          label="Max wind"
          value={Math.round(observation.est_wind_kt ?? 0)}
          unit="kt"
          sub={`${Math.round(ktToKmph(observation.est_wind_kt ?? 0))} km/h`}
        />
        <Metric
          icon={Gauge}
          label="Pressure"
          value={Math.round(observation.est_pressure_hpa ?? 0)}
          unit="hPa"
        />
        <Metric
          icon={Eye}
          label="Dvorak T"
          value={observation.dvorak_t_number ?? '—'}
          sub="equivalent"
        />
        <Metric
          icon={Waves}
          label="RMW"
          value={Math.round(observation.radius_max_wind_km ?? 0)}
          unit="km"
        />
      </div>

      <div>
        <div className="mb-1.5 flex items-center justify-between">
          <span className="text-2xs uppercase tracking-wide text-ink-mute">
            Pattern probabilities
          </span>
          <span className="text-2xs text-ink-mute">
            {observation.model_versions?.classification ?? 'model'}
          </span>
        </div>
        <div className="space-y-1">
          {probs.map(([name, p], i) => (
            <div key={name} className="flex items-center gap-2">
              <span
                className={`w-40 shrink-0 truncate text-2xs ${i === 0 ? 'text-ink' : 'text-ink-mute'}`}
              >
                {PATTERN_TYPES[name] ?? name}
              </span>
              <div className="h-1 flex-1 overflow-hidden rounded-full bg-overlay">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${Math.round(p * 100)}%`,
                    backgroundColor: i === 0 ? color : '#2B3648',
                  }}
                />
              </div>
              <span className="tnum w-8 shrink-0 text-right text-2xs text-ink-dim">
                {Math.round(p * 100)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="mb-1 text-2xs uppercase tracking-wide text-ink-mute">
          Detection confidence
        </div>
        <ConfidenceBar value={observation.confidence} />
      </div>
    </div>
  );
}
