import { ChevronRight } from 'lucide-react';
import { CategoryBadge, ConfidenceBar } from '../common/Badges.jsx';
import {
  BASINS,
  categoryColor,
  ktToKmph,
  PATTERN_TYPES,
  relativeTime,
  STATUS_LABELS,
} from '../../utils/constants.js';

export default function StormList({ cyclones, selectedId, onSelect }) {
  return (
    <ul className="divide-y divide-line">
      {cyclones.map((cyclone) => {
        const obs = cyclone.latest_observation ?? {};
        const isSelected = cyclone.id === selectedId;
        const color = categoryColor(obs.intensity_category);

        return (
          <li key={cyclone.id}>
            <button
              type="button"
              onClick={() => onSelect(cyclone.id)}
              className={`relative w-full px-4 py-3 text-left transition ${
                isSelected ? 'bg-overlay' : 'hover:bg-raised'
              }`}
            >
              {isSelected && (
                <span
                  className="absolute inset-y-0 left-0 w-0.5"
                  style={{ backgroundColor: color }}
                />
              )}

              <div className="flex items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                  <span className="truncate text-[13px] font-semibold text-ink">
                    {cyclone.name ?? 'Unnamed system'}
                  </span>
                  <CategoryBadge category={obs.intensity_category} />
                </div>
                <ChevronRight
                  size={14}
                  className={isSelected ? 'text-ink-dim' : 'text-ink-mute'}
                />
              </div>

              <div className="mt-1.5 flex items-baseline gap-3">
                <span className="tnum text-lg font-semibold leading-none" style={{ color }}>
                  {Math.round(obs.est_wind_kt ?? 0)}
                  <span className="ml-0.5 text-2xs font-normal text-ink-mute">kt</span>
                </span>
                <span className="tnum text-2xs text-ink-dim">
                  {Math.round(ktToKmph(obs.est_wind_kt ?? 0))} km/h
                </span>
                <span className="tnum text-2xs text-ink-mute">
                  {Math.round(obs.est_pressure_hpa ?? 0)} hPa
                </span>
              </div>

              <div className="mt-1.5 flex items-center justify-between text-2xs text-ink-mute">
                <span>
                  {BASINS[cyclone.basin] ?? cyclone.basin} ·{' '}
                  {PATTERN_TYPES[obs.pattern_type] ?? 'pattern pending'}
                </span>
                <span>{STATUS_LABELS[cyclone.status] ?? cyclone.status}</span>
              </div>

              <div className="mt-2 flex items-center gap-2">
                <span className="w-16 shrink-0 text-2xs text-ink-mute">Confidence</span>
                <ConfidenceBar value={obs.confidence} />
              </div>

              <div className="mt-1 text-2xs text-ink-mute">
                Updated {relativeTime(obs.observed_at)}
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
