import { useEffect, useRef, useState } from 'react';
import { Layers, Check } from 'lucide-react';

/**
 * Custom layer switcher. Leaflet's built-in control is unstyleable enough that it
 * always reads as stock; this keeps the map chrome part of the design system.
 */
function ToggleRow({ item, active, onToggle, tone }) {
  return (
    <li>
      <button
        type="button"
        onClick={() => onToggle(item.id)}
        className="flex w-full items-start gap-2 px-3 py-1.5 text-left transition hover:bg-overlay"
      >
        <span className="mt-[3px] w-3 shrink-0">
          {active && <Check size={11} className={tone} />}
        </span>
        <span className="min-w-0">
          <span className={`block text-xs ${active ? 'text-ink' : 'text-ink-dim'}`}>
            {item.label}
          </span>
          <span className="block text-2xs leading-snug text-ink-mute">{item.hint}</span>
        </span>
      </button>
    </li>
  );
}

export default function LayerControl({
  basemaps,
  activeBasemap,
  onBasemapChange,
  overlays,
  activeOverlays,
  onOverlayToggle,
  analysis = [],
  activeAnalysis = [],
  onAnalysisToggle,
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDocClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [open]);

  const current = basemaps.find((b) => b.id === activeBasemap);

  return (
    <div ref={ref} className="absolute right-3 top-3 z-[1000]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-lg bg-raised px-2.5 py-1.5 text-xs
                   text-ink-dim shadow-lift ring-1 ring-hairline-strong transition
                   hover:text-ink"
      >
        <Layers size={13} className="text-gold" />
        <span className="font-medium">{current?.label ?? 'Layers'}</span>
        {activeOverlays.length > 0 && (
          <span className="tnum rounded bg-[#D3AF3733] px-1 text-2xs font-semibold text-gold">
            +{activeOverlays.length}
          </span>
        )}
      </button>

      {/* Panel is fully opaque on purpose: it sits over bright satellite
          imagery, where any translucency makes the text unreadable. */}
      {open && (
        <div className="mt-1.5 max-h-[360px] w-64 overflow-y-auto rounded-xl bg-raised shadow-lift ring-1 ring-hairline-strong">
          <div className="sticky top-0 z-10 border-b border-hairline bg-raised px-3 py-2">
            <span className="field-label">Base layer</span>
          </div>
          <ul className="py-1">
            {basemaps.map((b) => (
              <li key={b.id}>
                <button
                  type="button"
                  onClick={() => {
                    onBasemapChange(b.id);
                    setOpen(false);
                  }}
                  className="flex w-full items-start gap-2 px-3 py-1.5 text-left transition hover:bg-overlay"
                >
                  <span className="mt-[3px] w-3 shrink-0">
                    {b.id === activeBasemap && <Check size={11} className="text-gold" />}
                  </span>
                  <span className="min-w-0">
                    <span
                      className={`block text-xs ${b.id === activeBasemap ? 'text-ink' : 'text-ink-dim'}`}
                    >
                      {b.label}
                    </span>
                    <span className="block text-2xs leading-snug text-ink-mute">{b.hint}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>

          <div className="border-y border-hairline px-3 py-2">
            <span className="field-label">Satellite overlays</span>
          </div>
          <ul className="py-1">
            {overlays.map((o) => (
              <ToggleRow
                key={o.id}
                item={o}
                active={activeOverlays.includes(o.id)}
                onToggle={onOverlayToggle}
                tone="text-sage"
              />
            ))}
          </ul>

          {analysis.length > 0 && (
            <>
              <div className="border-y border-hairline px-3 py-2">
                <span className="field-label">Model analysis</span>
              </div>
              <ul className="py-1">
                {analysis.map((a) => (
                  <ToggleRow
                    key={a.id}
                    item={a}
                    active={activeAnalysis.includes(a.id)}
                    onToggle={onAnalysisToggle}
                    tone="text-gold"
                  />
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}
