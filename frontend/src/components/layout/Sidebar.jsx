import { NavLink } from 'react-router-dom';
import { LayoutDashboard, BellRing, History, Satellite, Wind, ScanSearch } from 'lucide-react';

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/analyze', label: 'Image Analysis', icon: ScanSearch },
  { to: '/alerts', label: 'Alerts', icon: BellRing },
  { to: '/history', label: 'History', icon: History },
  { to: '/sources', label: 'Data Sources', icon: Satellite },
];

export default function Sidebar({ alertCount = 0 }) {
  return (
    <aside className="flex w-[216px] shrink-0 flex-col border-r border-hairline bg-surface">
      <div className="flex items-center gap-2.5 px-4 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#D3AF371F] ring-1 ring-[#D3AF3740]">
          <Wind size={16} className="text-gold" />
        </div>
        <div className="leading-tight">
          <div className="font-display text-[15px] font-medium tracking-tight text-ink">
            Vayu-X
          </div>
          <div className="text-2xs text-ink-mute">Cyclone Intelligence</div>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 px-2 pt-2">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `group relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] transition ${
                isActive
                  ? 'bg-overlay text-ink'
                  : 'text-ink-dim hover:bg-[#131A27B3] hover:text-ink'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <Icon size={15} className={isActive ? 'text-gold' : 'text-ink-mute'} />
                <span className={`flex-1 ${isActive ? 'font-medium' : ''}`}>{label}</span>
                {to === '/alerts' && alertCount > 0 && (
                  <span className="tnum rounded-md bg-[#E07A3F26] px-1.5 py-0.5 text-2xs font-semibold text-severity-orange">
                    {alertCount}
                  </span>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="space-y-0.5 border-t border-hairline px-4 py-3.5 text-2xs leading-relaxed">
        <div className="font-display font-medium text-ink-dim">SIH 2025 · PS 26070</div>
        <div className="text-ink-mute">Team Vayu-X (152)</div>
        <div className="text-ink-mute">MoES · India Meteorological Dept.</div>
      </div>
    </aside>
  );
}
