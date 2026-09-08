import { NavLink } from 'react-router-dom';
import { LayoutDashboard, BellRing, History, Satellite, Wind } from 'lucide-react';

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/alerts', label: 'Alerts', icon: BellRing },
  { to: '/history', label: 'History', icon: History },
  { to: '/sources', label: 'Data Sources', icon: Satellite },
];

export default function Sidebar({ alertCount = 0 }) {
  return (
    <aside className="flex w-[212px] shrink-0 flex-col border-r border-line bg-surface">
      <div className="flex items-center gap-2.5 border-b border-line px-4 py-3.5">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-accent/15 ring-1 ring-accent/30">
          <Wind size={15} className="text-accent" />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold tracking-tight text-ink">Vayu-X</div>
          <div className="text-2xs text-ink-mute">Cyclone Intelligence</div>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 p-2">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `group flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] transition ${
                isActive
                  ? 'bg-overlay font-medium text-ink'
                  : 'text-ink-dim hover:bg-raised hover:text-ink'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <Icon size={15} className={isActive ? 'text-accent' : 'text-ink-mute'} />
                <span className="flex-1">{label}</span>
                {to === '/alerts' && alertCount > 0 && (
                  <span className="tnum rounded bg-severity-orange/20 px-1.5 py-0.5 text-2xs font-semibold text-severity-orange">
                    {alertCount}
                  </span>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-line px-4 py-3">
        <div className="text-2xs leading-relaxed text-ink-mute">
          <div className="font-medium text-ink-dim">SIH 2025 · PS 26070</div>
          <div>Team Vayu-X (152)</div>
          <div>MoES · India Meteorological Dept.</div>
        </div>
      </div>
    </aside>
  );
}
