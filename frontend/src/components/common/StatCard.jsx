export default function StatCard({ label, value, unit, sub, accent, icon: Icon, tone }) {
  return (
    <div className="panel px-4 py-3">
      <div className="flex items-start justify-between">
        <span className="text-2xs uppercase tracking-[0.08em] text-ink-mute">{label}</span>
        {Icon && <Icon size={13} className="text-ink-mute" />}
      </div>
      <div className="mt-2 flex items-baseline gap-1.5">
        <span
          className="stat-value"
          style={accent ? { color: accent } : undefined}
        >
          {value}
        </span>
        {unit && <span className="text-xs text-ink-mute">{unit}</span>}
      </div>
      {sub && (
        <div className={`mt-1 truncate text-2xs ${tone ?? 'text-ink-mute'}`} title={sub}>
          {sub}
        </div>
      )}
    </div>
  );
}
