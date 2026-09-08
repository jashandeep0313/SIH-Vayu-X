import { CategoryBadge } from '../components/common/Badges.jsx';
import { EmptyState } from '../components/common/States.jsx';
import { BASINS, formatIst, STATUS_LABELS } from '../utils/constants.js';

/**
 * Past events and, once Phase 6 lands, model-vs-IMD-best-track verification.
 * Also the entry point for case-study replay — the demo path that does not
 * depend on a live satellite feed.
 */
export default function History({ cyclones }) {
  return (
    <div className="space-y-3 p-4">
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Event Archive</span>
          <span className="tnum text-2xs text-ink-mute">{cyclones.length} events</span>
        </div>

        {cyclones.length === 0 ? (
          <EmptyState title="No archived events" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-hairline text-2xs uppercase tracking-wide text-ink-mute">
                  <th className="px-4 py-2 font-medium">System</th>
                  <th className="px-2 py-2 font-medium">Basin</th>
                  <th className="px-2 py-2 font-medium">Peak</th>
                  <th className="px-2 py-2 font-medium">Status</th>
                  <th className="px-2 py-2 font-medium">First seen</th>
                  <th className="px-4 py-2 font-medium">Last seen</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1C273899]">
                {cyclones.map((c) => (
                  <tr key={c.id} className="transition hover:bg-raised">
                    <td className="px-4 py-2.5 font-medium text-ink">
                      {c.name ?? 'Unnamed system'}
                    </td>
                    <td className="px-2 py-2.5 text-ink-dim">{BASINS[c.basin] ?? c.basin}</td>
                    <td className="px-2 py-2.5">
                      <CategoryBadge
                        category={
                          c.peak_intensity_category ?? c.latest_observation?.intensity_category
                        }
                      />
                    </td>
                    <td className="px-2 py-2.5 text-ink-dim">
                      {STATUS_LABELS[c.status] ?? c.status}
                    </td>
                    <td className="tnum px-2 py-2.5 text-ink-mute">{formatIst(c.first_seen)}</td>
                    <td className="tnum px-4 py-2.5 text-ink-mute">{formatIst(c.last_seen)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="panel px-4 py-3">
        <div className="panel-title mb-1">Verification</div>
        <p className="max-w-2xl text-xs leading-relaxed text-ink-dim">
          Track error, intensity MAE and skill against persistence/CLIPER baselines will be
          reported here, computed on held-out seasons against IMD best track. Named storms
          (Amphan, Fani, Biparjoy, Tauktae) are excluded from training so they can be replayed
          end-to-end as case studies.
        </p>
      </div>
    </div>
  );
}
