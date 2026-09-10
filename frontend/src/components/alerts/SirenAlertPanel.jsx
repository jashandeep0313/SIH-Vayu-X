import { useCallback, useEffect, useState } from 'react';
import { Siren, Radio, Square, Loader2, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { alerts as alertApi } from '../../services/api.js';
import { severityColor } from '../../utils/constants.js';

const SIREN_CATEGORIES = ['SCS', 'VSCS', 'ESCS', 'SuCS'];
const SEVERITY_FOR = { SCS: 'YELLOW', VSCS: 'ORANGE', ESCS: 'RED', SuCS: 'RED' };

/**
 * The last-mile siren tower.
 *
 * Unlike the SMS panel this one may already have fired by the time you see it:
 * a sounding costs nothing and a tower that waits for an operator is no use
 * when the control room link is down. `result.siren` carries what the backend
 * did automatically, and the button below is the manual override for when it
 * decided not to — a low-confidence read, or the automatic path switched off.
 */
export default function SirenAlertPanel({ analysis, autoResult }) {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(null);
  const [outcome, setOutcome] = useState(null);
  const [error, setError] = useState(null);

  const refresh = useCallback(() => {
    alertApi
      .sirenStatus()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  useEffect(refresh, [refresh]);
  useEffect(() => {
    setOutcome(null);
    setError(null);
  }, [analysis]);

  const category = analysis?.classification?.intensity_category;
  const alertable = SIREN_CATEGORIES.includes(category);
  const color = severityColor(SEVERITY_FOR[category] ?? 'GREEN');

  const run = async (label, fn) => {
    setBusy(label);
    setError(null);
    try {
      const res = await fn();
      setOutcome(res);
      if (res.sounded === false) setError(res.reason ?? 'Not sounded');
      if (res.ok === false) setError(res.reason ?? 'Failed');
    } catch (e) {
      setError(e?.response?.data?.detail ?? 'Request failed');
    } finally {
      setBusy(null);
      refresh();
    }
  };

  // Hide entirely when there is no tower configured and nothing to say about it.
  if (!status?.enabled && !status?.connected && !autoResult?.attempted) return null;

  const online = status?.connected && status?.firmware;

  return (
    <div
      className="rounded-lg p-3 ring-1 ring-hairline"
      style={{ background: `linear-gradient(90deg, ${color}14 0%, ${color}00 55%)` }}
    >
      <div className="flex items-center gap-2">
        <Siren size={14} style={{ color }} />
        <span className="font-display text-xs font-medium text-ink">Siren tower</span>
        <span
          className="ml-auto inline-flex items-center gap-1 text-2xs"
          style={{ color: online ? '#7FAF9A' : '#E07A3F' }}
        >
          <Radio size={10} />
          {online ? `Online · ${status.port}` : 'Offline'}
        </span>
      </div>

      {/* What the backend already did, before anyone touched a button. */}
      {autoResult && (
        <div className="mt-2 flex items-start gap-1.5 rounded-md bg-raised px-2.5 py-2 text-2xs leading-relaxed">
          {autoResult.sounded ? (
            <>
              <CheckCircle2 size={11} className="mt-0.5 shrink-0 text-severity-green" />
              <span className="text-ink-dim">
                Sounded <span className="text-ink">{autoResult.severity}</span> automatically for{' '}
                {autoResult.seconds}s on this classification — no operator action.
              </span>
            </>
          ) : (
            <>
              <AlertTriangle size={11} className="mt-0.5 shrink-0 text-gold" />
              <span className="text-ink-dim">
                Not sounded automatically: {autoResult.reason}
              </span>
            </>
          )}
        </div>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => run('test', alertApi.sirenTest)}
          disabled={!!busy || !online}
          className="btn disabled:opacity-50"
        >
          {busy === 'test' ? <Loader2 size={11} className="animate-spin" /> : <Radio size={11} />}
          Self-test
        </button>

        {alertable && (
          <button
            type="button"
            onClick={() =>
              run('sound', () =>
                alertApi.soundSiren({
                  intensity_category: category,
                  seconds: 15,
                  confirm: true,
                }),
              )
            }
            disabled={!!busy || !online}
            className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs
                       font-medium text-canvas disabled:opacity-50"
            style={{ backgroundColor: color }}
          >
            {busy === 'sound' ? (
              <Loader2 size={11} className="animate-spin" />
            ) : (
              <Siren size={11} />
            )}
            Sound siren ({category})
          </button>
        )}

        <button
          type="button"
          onClick={() => run('stop', alertApi.stopSiren)}
          disabled={!!busy || !online}
          className="btn disabled:opacity-50"
        >
          {busy === 'stop' ? <Loader2 size={11} className="animate-spin" /> : <Square size={11} />}
          All clear
        </button>

        {outcome?.sounded && (
          <span className="chip bg-[#7FAF9A26] text-severity-green">
            {outcome.severity} · {outcome.seconds}s
          </span>
        )}
      </div>

      {error && (
        <div className="mt-2 flex items-start gap-1.5 text-2xs text-severity-orange">
          <AlertTriangle size={11} className="mt-0.5 shrink-0" />
          {error}
        </div>
      )}

      {!online && (
        <p className="mt-2 text-2xs leading-relaxed text-ink-mute">
          {status?.error ?? 'No tower detected on a serial port.'}
        </p>
      )}

      <p className="mt-2 text-2xs leading-relaxed text-ink-mute">
        Reaches people with no cellular coverage — the case SMS cannot cover. Demonstrated over
        USB; in the field the last hop is LoRa at 433 MHz, which needs no infrastructure at all.
      </p>
    </div>
  );
}
