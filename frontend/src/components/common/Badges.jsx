import {
  categoryColor,
  categoryLabel,
  INTENSITY_CATEGORIES,
  SEVERITY,
} from '../../utils/constants.js';

/** Intensity category chip. Colour carries the meaning; the code is the label. */
export function CategoryBadge({ category, size = 'sm' }) {
  if (!category) return <span className="text-2xs text-ink-mute">Unclassified</span>;

  const color = categoryColor(category);
  return (
    <span
      className={`chip ${size === 'lg' ? 'px-2 py-1 text-xs' : ''}`}
      style={{ backgroundColor: `${color}1F`, color, boxShadow: `inset 0 0 0 1px ${color}55` }}
      title={categoryLabel(category)}
    >
      {category}
    </span>
  );
}

export function CategoryLabel({ category }) {
  return (
    <span className="text-xs text-ink-dim">
      {INTENSITY_CATEGORIES[category]?.short ?? '—'}
    </span>
  );
}

/** IMD warning level. Filled treatment — alerts must not be missed. */
export function SeverityBadge({ severity }) {
  const meta = SEVERITY[severity];
  if (!meta) return null;

  return (
    <span
      className="chip gap-1.5"
      style={{ backgroundColor: `${meta.color}1F`, color: meta.color, boxShadow: `inset 0 0 0 1px ${meta.color}55` }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: meta.color }} />
      {severity}
    </span>
  );
}

export function StatusPill({ status }) {
  const tone =
    status === 'active'
      ? 'text-gold'
      : status === 'weakened'
        ? 'text-ink-dim'
        : 'text-ink-mute';
  return <span className={`text-2xs uppercase tracking-wide ${tone}`}>{status}</span>;
}

/**
 * Model confidence. Always shown next to a prediction — an operator needs to
 * know when to distrust the number, and low confidence routes to human review
 * rather than an automatic alert.
 */
export function ConfidenceBar({ value, showLabel = true }) {
  if (value == null) return null;

  const pct = Math.round(value * 100);
  const color = value >= 0.8 ? '#7FAF9A' : value >= 0.6 ? '#D3AF37' : '#E07A3F';

  return (
    <div className="flex items-center gap-2">
      <div className="h-1 w-full overflow-hidden rounded-full bg-overlay">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      {showLabel && <span className="tnum text-2xs text-ink-dim">{pct}%</span>}
    </div>
  );
}
