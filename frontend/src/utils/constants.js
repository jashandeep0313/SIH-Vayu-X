/** IMD North Indian Ocean intensity scale. */
export const INTENSITY_CATEGORIES = {
  LPA: { label: 'Low Pressure Area', short: 'Low Pressure', maxWindKt: 17 },
  D: { label: 'Depression', short: 'Depression', maxWindKt: 27 },
  DD: { label: 'Deep Depression', short: 'Deep Depression', maxWindKt: 33 },
  CS: { label: 'Cyclonic Storm', short: 'Cyclonic Storm', maxWindKt: 47 },
  SCS: { label: 'Severe Cyclonic Storm', short: 'Severe', maxWindKt: 63 },
  VSCS: { label: 'Very Severe Cyclonic Storm', short: 'Very Severe', maxWindKt: 89 },
  ESCS: { label: 'Extremely Severe Cyclonic Storm', short: 'Extremely Severe', maxWindKt: 119 },
  SuCS: { label: 'Super Cyclonic Storm', short: 'Super Cyclone', maxWindKt: Infinity },
};

/**
 * Escalating cool-to-warm ramp drawn from the Prosperon palette (slate → sage →
 * gold → orange → red). Severity must be readable from colour alone.
 */
export const CATEGORY_COLORS = {
  LPA: '#686F7C',
  D: '#6A9280',
  DD: '#94BCAB',
  CS: '#E9D79B',
  SCS: '#D3AF37',
  VSCS: '#E07A3F',
  ESCS: '#D4544E',
  SuCS: '#A8446B',
};

export const CATEGORY_ORDER = ['LPA', 'D', 'DD', 'CS', 'SCS', 'VSCS', 'ESCS', 'SuCS'];

/** IMD colour-coded warning levels. */
export const SEVERITY = {
  GREEN: { color: '#7FAF9A', label: 'Monitor', action: 'No action required' },
  YELLOW: { color: '#D3AF37', label: 'Watch', action: 'Be updated' },
  ORANGE: { color: '#E07A3F', label: 'Prepare', action: 'Be prepared' },
  RED: { color: '#D4544E', label: 'Take Action', action: 'Act now' },
};

/** Brand accents, mirrored from tailwind.config.js for use in canvas/SVG contexts. */
export const BRAND = {
  gold: '#D3AF37',
  sage: '#7FAF9A',
  ink: '#D2D4D8',
  inkDim: '#8E939D',
  inkMute: '#686F7C',
  hairline: '#1C2738',
  surface: '#0E141E',
  raised: '#131A27',
};

export const SEVERITY_ORDER = ['GREEN', 'YELLOW', 'ORANGE', 'RED'];

export const PATTERN_TYPES = {
  curved_band: 'Curved Band',
  shear: 'Shear',
  CDO: 'Central Dense Overcast',
  banding_eye: 'Banding Eye',
  eye: 'Eye',
  central_cold_cover: 'Central Cold Cover',
};

export const BASINS = {
  NIO: 'North Indian Ocean',
  BOB: 'Bay of Bengal',
  ARB: 'Arabian Sea',
};

export const STATUS_LABELS = {
  active: 'Active',
  weakened: 'Weakening',
  dissipated: 'Dissipated',
  landfall: 'Landfall',
  archived: 'Archived',
};

export const KT_TO_KMPH = 1.852;

export const ktToKmph = (kt) => kt * KT_TO_KMPH;

export const categoryColor = (category) => CATEGORY_COLORS[category] ?? '#64748B';

export const categoryLabel = (category) =>
  INTENSITY_CATEGORIES[category]?.label ?? category ?? 'Unclassified';

export const severityColor = (severity) => SEVERITY[severity]?.color ?? '#64748B';

/** Highest category present, by IMD scale order. */
export function peakCategory(categories) {
  const ranked = categories
    .filter(Boolean)
    .map((c) => CATEGORY_ORDER.indexOf(c))
    .filter((i) => i >= 0);
  return ranked.length ? CATEGORY_ORDER[Math.max(...ranked)] : null;
}

export function highestSeverity(severities) {
  const ranked = severities
    .filter(Boolean)
    .map((s) => SEVERITY_ORDER.indexOf(s))
    .filter((i) => i >= 0);
  return ranked.length ? SEVERITY_ORDER[Math.max(...ranked)] : null;
}

export function formatUtc(iso, opts = {}) {
  if (!iso) return '—';
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, '0');
  const time = `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}Z`;
  if (opts.timeOnly) return time;
  return `${pad(d.getUTCDate())} ${d.toLocaleString('en', { month: 'short', timeZone: 'UTC' })} ${time}`;
}

/** IST is what IMD and district authorities actually operate in. */
export function formatIst(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'Asia/Kolkata',
  });
}

export function relativeTime(iso) {
  if (!iso) return '—';
  const diffMin = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const h = Math.floor(diffMin / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function hoursUntil(iso) {
  if (!iso) return null;
  return (new Date(iso).getTime() - Date.now()) / 3600000;
}
