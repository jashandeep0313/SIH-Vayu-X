import { useEffect, useRef } from 'react';
import { Play, Pause, SkipBack, SkipForward, Gauge } from 'lucide-react';
import { CategoryBadge } from '../common/Badges.jsx';
import { categoryColor, formatIst } from '../../utils/constants.js';

const SPEEDS = [
  { label: '1×', ms: 900 },
  { label: '2×', ms: 450 },
  { label: '4×', ms: 200 },
];

/**
 * Playback control for a storm's own history.
 *
 * Stepping the index also steps the satellite basemap date, so the imagery
 * follows the storm through its lifetime rather than showing one fixed day.
 */
export default function TimelineControl({
  observations = [],
  index,
  onIndexChange,
  playing,
  onPlayingChange,
  speed,
  onSpeedChange,
}) {
  const timer = useRef(null);

  useEffect(() => {
    if (!playing || observations.length < 2) return undefined;
    timer.current = setInterval(() => {
      onIndexChange((prev) => {
        if (prev >= observations.length - 1) {
          onPlayingChange(false);
          return prev;
        }
        return prev + 1;
      });
    }, speed);
    return () => clearInterval(timer.current);
  }, [playing, speed, observations.length, onIndexChange, onPlayingChange]);

  if (observations.length < 2) return null;

  const current = observations[Math.min(index, observations.length - 1)];
  const atEnd = index >= observations.length - 1;
  const color = categoryColor(current?.intensity_category);

  return (
    <div className="absolute bottom-3 left-1/2 z-[1000] w-[min(94%,620px)] -translate-x-1/2">
      <div className="rounded-xl bg-raised px-3 py-2.5 shadow-lift ring-1 ring-hairline-strong">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onIndexChange(0)}
            className="rounded-md p-1.5 text-ink-mute transition hover:bg-overlay hover:text-ink"
            title="Back to start"
          >
            <SkipBack size={13} />
          </button>

          <button
            type="button"
            onClick={() => {
              if (atEnd) onIndexChange(0);
              onPlayingChange(!playing);
            }}
            className="rounded-md p-2 text-canvas transition"
            style={{ backgroundColor: color }}
            title={playing ? 'Pause' : 'Play storm history'}
          >
            {playing ? <Pause size={14} /> : <Play size={14} />}
          </button>

          <button
            type="button"
            onClick={() => onIndexChange(observations.length - 1)}
            className="rounded-md p-1.5 text-ink-mute transition hover:bg-overlay hover:text-ink"
            title="Jump to latest"
          >
            <SkipForward size={13} />
          </button>

          <input
            type="range"
            min={0}
            max={observations.length - 1}
            value={index}
            onChange={(e) => {
              onPlayingChange(false);
              onIndexChange(Number(e.target.value));
            }}
            className="h-1 flex-1 cursor-pointer appearance-none rounded-full bg-overlay
                       accent-gold"
            style={{ accentColor: color }}
          />

          <div className="flex items-center gap-0.5 rounded-md bg-overlay p-0.5">
            {SPEEDS.map((s) => (
              <button
                key={s.label}
                type="button"
                onClick={() => onSpeedChange(s.ms)}
                className={`rounded px-1.5 py-0.5 text-2xs transition ${
                  speed === s.ms ? 'bg-raised text-ink' : 'text-ink-mute hover:text-ink-dim'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-2xs">
          <span className="tnum text-ink">{formatIst(current?.observed_at)} IST</span>
          <CategoryBadge category={current?.intensity_category} />
          <span className="tnum text-ink-dim">
            {Math.round(current?.est_wind_kt ?? 0)} kt ·{' '}
            {Math.round(current?.est_pressure_hpa ?? 0)} hPa
          </span>
          <span className="tnum text-ink-mute">
            {current?.lat?.toFixed(1)}°N {current?.lon?.toFixed(1)}°E
          </span>
          <span className="tnum ml-auto flex items-center gap-1 text-ink-mute">
            <Gauge size={10} />
            {index + 1}/{observations.length}
          </span>
        </div>
      </div>
    </div>
  );
}
