import { useEffect, useState } from 'react';
import { Send, ShieldAlert, Check, AlertTriangle, Loader2 } from 'lucide-react';
import { alerts as alertApi } from '../../services/api.js';
import { severityColor } from '../../utils/constants.js';

const DEFAULT_NUMBER = import.meta.env.VITE_ALERT_TEST_NUMBER ?? '6202972050';

/**
 * Operator-triggered SMS dispatch for a classification result.
 *
 * Never fires on its own. Two deliberate reasons: Fast2SMS credits are finite,
 * and an unreviewed model output should not be able to text the public. The
 * analyst reads the message, then presses send.
 */
export default function SmsAlertPanel({ analysis, region }) {
  const [preview, setPreview] = useState(null);
  const [number, setNumber] = useState(DEFAULT_NUMBER);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(null);
  const [error, setError] = useState(null);
  const [armed, setArmed] = useState(false);

  useEffect(() => {
    setSent(null);
    setError(null);
    setArmed(false);
    if (!analysis) return;
    alertApi
      .previewSms({ number, analysis, region })
      .then(setPreview)
      .catch(() => setPreview(null));
    // number is intentionally excluded: changing it must not re-compose the text
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysis, region]);

  if (!preview?.alertable) return null;

  const msg = preview.message;
  const color = severityColor(msg.severity);

  const send = async () => {
    setSending(true);
    setError(null);
    try {
      const res = await alertApi.sendSms({
        number,
        analysis,
        region,
        confirm: true,
        flash: true,
      });
      setSent(res);
      if (!res.sent) setError(res.reason ?? res.error ?? 'Not sent');
    } catch (e) {
      setError(e?.response?.data?.detail ?? 'Request failed');
    } finally {
      setSending(false);
      setArmed(false);
    }
  };

  return (
    <div
      className="rounded-lg p-3 ring-1 ring-hairline"
      style={{ background: `linear-gradient(90deg, ${color}14 0%, ${color}00 55%)` }}
    >
      <div className="flex items-center gap-2">
        <ShieldAlert size={14} style={{ color }} />
        <span className="font-display text-xs font-medium text-ink">
          {msg.severity} — SMS alert available
        </span>
        <span className="ml-auto text-2xs text-ink-mute">{msg.length}/160 chars</span>
      </div>

      <p className="mt-2 rounded-md bg-raised px-2.5 py-2 font-mono text-2xs leading-relaxed text-ink-dim">
        {msg.text}
      </p>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <input
          value={number}
          onChange={(e) => setNumber(e.target.value)}
          placeholder="10-digit number"
          className="w-40 rounded-md bg-raised px-2 py-1.5 font-mono text-2xs text-ink
                     ring-1 ring-hairline focus:outline-none focus:ring-gold"
        />

        {!armed && !sent && (
          <button type="button" onClick={() => setArmed(true)} className="btn">
            <Send size={11} />
            Send SMS alert
          </button>
        )}

        {armed && (
          <>
            <button
              type="button"
              onClick={send}
              disabled={sending}
              className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs
                         font-medium text-canvas disabled:opacity-60"
              style={{ backgroundColor: color }}
            >
              {sending ? <Loader2 size={11} className="animate-spin" /> : <Check size={11} />}
              Confirm send to {number}
            </button>
            <button type="button" onClick={() => setArmed(false)} className="btn">
              Cancel
            </button>
          </>
        )}

        {sent?.sent && (
          <span className="chip bg-[#7FAF9A26] text-severity-green">
            Sent · {sent.sends_this_run}/{sent.cap} this run
          </span>
        )}
        {sent && !sent.sent && sent.dry_run && (
          <span className="chip bg-[#D3AF371F] text-gold">Dry run — no API key set</span>
        )}
      </div>

      {error && (
        <div className="mt-2 flex items-start gap-1.5 text-2xs text-severity-orange">
          <AlertTriangle size={11} className="mt-0.5 shrink-0" />
          {error}
        </div>
      )}

      <p className="mt-2 text-2xs leading-relaxed text-ink-mute">
        Sent as a flash SMS so it renders over the lock screen. Vibration and alert tone follow
        the recipient&apos;s own notification settings — SMS carries no field to control them; that
        needs the push channel and a companion app.
      </p>
    </div>
  );
}
