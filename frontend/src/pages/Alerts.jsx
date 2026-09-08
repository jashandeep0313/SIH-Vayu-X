import { useState } from 'react';
import {
  Check,
  Mail,
  MessageSquare,
  Smartphone,
  Webhook,
  ShieldAlert,
  Users,
} from 'lucide-react';
import { SeverityBadge } from '../components/common/Badges.jsx';
import { EmptyState, ErrorState, LoadingState } from '../components/common/States.jsx';
import { alerts as alertApi } from '../services/api.js';
import {
  formatIst,
  relativeTime,
  SEVERITY,
  SEVERITY_ORDER,
  severityColor,
} from '../utils/constants.js';

const CHANNEL_ICONS = {
  sms: MessageSquare,
  email: Mail,
  push: Smartphone,
  webhook: Webhook,
};

const DISPATCH_TONE = {
  sent: 'text-severity-green',
  partial: 'text-severity-yellow',
  failed: 'text-severity-red',
  queued: 'text-ink-mute',
  skipped: 'text-ink-mute',
};

export default function Alerts({ alerts, loading, error, onRefresh }) {
  const [filter, setFilter] = useState('ALL');
  const [acknowledged, setAcknowledged] = useState({});

  const visible = filter === 'ALL' ? alerts : alerts.filter((a) => a.severity === filter);

  const acknowledge = async (id) => {
    setAcknowledged((prev) => ({ ...prev, [id]: true }));
    try {
      await alertApi.acknowledge(id);
      onRefresh?.();
    } catch {
      // Endpoint is still a stub; the optimistic state is enough for now.
    }
  };

  if (error) return <ErrorState title="Alert service unavailable" />;
  if (loading) return <LoadingState label="Loading alerts" />;

  return (
    <div className="space-y-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1">
          {['ALL', ...SEVERITY_ORDER].map((level) => {
            const count =
              level === 'ALL'
                ? alerts.length
                : alerts.filter((a) => a.severity === level).length;
            const active = filter === level;
            return (
              <button
                key={level}
                type="button"
                onClick={() => setFilter(level)}
                className={`rounded-md px-2.5 py-1.5 text-2xs font-medium uppercase tracking-wide transition ${
                  active
                    ? 'bg-overlay text-ink'
                    : 'text-ink-mute hover:bg-raised hover:text-ink-dim'
                }`}
                style={
                  active && level !== 'ALL'
                    ? { color: severityColor(level), boxShadow: `inset 0 0 0 1px ${severityColor(level)}44` }
                    : undefined
                }
              >
                {level}
                <span className="tnum ml-1.5 text-ink-mute">{count}</span>
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-1.5 rounded-md border border-hairline bg-raised px-2.5 py-1.5">
          <ShieldAlert size={12} className="text-gold" />
          <span className="text-2xs text-ink-dim">
            Dry run — alerts logged, not delivered
          </span>
        </div>
      </div>

      {visible.length === 0 ? (
        <div className="panel">
          <EmptyState
            title="No alerts at this level"
            hint="Alerts are generated when a cyclone event matches a rule in alert_rules.yaml."
          />
        </div>
      ) : (
        <div className="space-y-3">
          {visible.map((alert) => {
            const color = severityColor(alert.severity);
            const isAck = acknowledged[alert.id] || alert.status === 'acknowledged';

            return (
              <article key={alert.id} className="panel overflow-hidden">
                {/* Severity reads from a tinted header band rather than a rule
                    down the edge — the tint carries further at a glance. */}
                <div
                  className="flex flex-wrap items-start justify-between gap-3 px-4 py-3"
                  style={{
                    background: `linear-gradient(90deg, ${color}14 0%, ${color}00 42%)`,
                  }}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <SeverityBadge severity={alert.severity} />
                      <span className="text-2xs text-ink-mute">
                        {SEVERITY[alert.severity]?.action}
                      </span>
                      {alert.cyclone_name && (
                        <span className="text-2xs text-ink-dim">· {alert.cyclone_name}</span>
                      )}
                      {isAck && (
                        <span className="chip bg-[#7FAF9A26] text-severity-green">
                          Acknowledged
                        </span>
                      )}
                    </div>

                    <h3 className="mt-1.5 text-sm font-semibold text-ink">{alert.headline}</h3>
                    <p className="mt-1 max-w-3xl text-xs leading-relaxed text-ink-dim">
                      {alert.body}
                    </p>
                  </div>

                  <div className="flex shrink-0 flex-col items-end gap-2">
                    <div className="tnum text-2xs text-ink-mute">
                      {formatIst(alert.issued_at)} IST · {relativeTime(alert.issued_at)}
                    </div>
                    {!isAck && (
                      <button
                        type="button"
                        onClick={() => acknowledge(alert.id)}
                        className="btn"
                      >
                        <Check size={12} />
                        Acknowledge
                      </button>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-px border-t border-hairline bg-hairline md:grid-cols-3">
                  <Block title="Affected areas">
                    {alert.affected_regions?.length ? (
                      <div className="flex flex-wrap gap-1">
                        {alert.affected_regions.map((r) => (
                          <span
                            key={r}
                            className="rounded border border-hairline bg-overlay px-1.5 py-0.5 text-2xs text-ink-dim"
                          >
                            {r}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-2xs text-ink-mute">No geofence — advisory only</span>
                    )}
                  </Block>

                  <Block title="Recommended actions">
                    <ul className="space-y-0.5">
                      {(alert.recommended_actions ?? []).map((a) => (
                        <li key={a} className="flex gap-1.5 text-2xs text-ink-dim">
                          <span className="text-ink-mute">·</span>
                          {a}
                        </li>
                      ))}
                    </ul>
                  </Block>

                  <Block title="Dispatch">
                    <div className="space-y-1">
                      {(alert.dispatches ?? []).map((d) => {
                        const Icon = CHANNEL_ICONS[d.channel] ?? Webhook;
                        return (
                          <div key={d.channel} className="flex items-center gap-2 text-2xs">
                            <Icon size={11} className="text-ink-mute" />
                            <span className="w-14 text-ink-dim">{d.channel}</span>
                            <span className="tnum flex items-center gap-1 text-ink-mute">
                              <Users size={9} />
                              {d.recipient_count.toLocaleString()}
                            </span>
                            <span
                              className={`ml-auto font-medium ${DISPATCH_TONE[d.status] ?? 'text-ink-mute'}`}
                            >
                              {d.status}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </Block>
                </div>

                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-hairline px-4 py-2 text-2xs text-ink-mute">
                  <span>
                    Rule <span className="text-ink-dim">{alert.matched_rule}</span>
                  </span>
                  <span>
                    Issued by <span className="text-ink-dim">{alert.issued_by}</span>
                  </span>
                  {alert.intensity_summary && (
                    <span className="tnum">
                      {alert.intensity_summary.category} ·{' '}
                      {Math.round(alert.intensity_summary.max_wind_kmph)} km/h
                    </span>
                  )}
                  <span className="tnum">Valid until {formatIst(alert.valid_until)} IST</span>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Block({ title, children }) {
  return (
    <div className="bg-surface px-4 py-3">
      <div className="mb-1.5 text-2xs uppercase tracking-wide text-ink-mute">{title}</div>
      {children}
    </div>
  );
}
