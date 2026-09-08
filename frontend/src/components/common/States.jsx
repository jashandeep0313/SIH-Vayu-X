import { AlertTriangle, Inbox, Loader2 } from 'lucide-react';

export function Skeleton({ className = '' }) {
  return <div className={`animate-shimmer rounded bg-overlay ${className}`} />;
}

export function LoadingState({ label = 'Loading' }) {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-xs text-ink-mute">
      <Loader2 size={14} className="animate-spin" />
      {label}
    </div>
  );
}

export function EmptyState({ title, hint, icon: Icon = Inbox }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-4 py-10 text-center">
      <Icon size={20} className="text-ink-mute" />
      <p className="text-sm text-ink-dim">{title}</p>
      {hint && <p className="max-w-xs text-2xs text-ink-mute">{hint}</p>}
    </div>
  );
}

export function ErrorState({ title = 'Service unavailable', hint }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-4 py-10 text-center">
      <AlertTriangle size={20} className="text-severity-orange" />
      <p className="text-sm text-ink">{title}</p>
      {hint && <p className="max-w-xs text-2xs text-ink-mute">{hint}</p>}
    </div>
  );
}
