import { useRef, useState } from 'react';
import { Upload, FileImage, AlertTriangle, RotateCcw } from 'lucide-react';
import { CategoryBadge, ConfidenceBar } from '../components/common/Badges.jsx';
import { LoadingState } from '../components/common/States.jsx';
import { inference } from '../services/api.js';
import { categoryColor, categoryLabel, PATTERN_TYPES } from '../utils/constants.js';

function Metric({ label, value, unit }) {
  return (
    <div className="rounded-lg bg-raised px-3 py-2.5 ring-1 ring-hairline">
      <div className="field-label">{label}</div>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="tnum font-display text-lg font-medium leading-none text-ink">
          {value ?? '—'}
        </span>
        {unit && <span className="text-2xs text-ink-mute">{unit}</span>}
      </div>
    </div>
  );
}

export default function Analyze() {
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const submit = async (file) => {
    if (!file) return;
    setError(null);
    setResult(null);
    setLoading(true);
    setPreview(URL.createObjectURL(file));
    try {
      setResult(await inference.upload(file));
    } catch (e) {
      setError(e?.response?.data?.detail ?? 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setPreview(null);
    setResult(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  const cls = result?.classification;

  return (
    <div className="space-y-3 p-4">
      <div
        className="panel flex items-start gap-3 px-4 py-3"
        style={{
          background:
            'linear-gradient(90deg, rgba(224,122,63,.10) 0%, rgba(224,122,63,0) 40%)',
        }}
      >
        <AlertTriangle size={15} className="mt-0.5 shrink-0 text-severity-orange" />
        <div>
          <div className="font-display text-xs font-medium text-ink">
            Mock inference — no model is trained yet
          </div>
          <p className="mt-0.5 max-w-3xl text-2xs leading-relaxed text-ink-dim">
            Results are generated, not predicted, so the interface and the alert pipeline can
            be tested before Phase 2. Output is seeded from the file hash, so the same image
            always returns the same answer. Replace{' '}
            <code className="text-ink-mute">_mock_result</code> in{' '}
            <code className="text-ink-mute">backend/app/api/v1/routes/inference.py</code> with a
            model-service call when the classifier lands.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <section className="panel">
          <div className="panel-header">
            <span className="panel-title">Satellite Image</span>
            {preview && (
              <button type="button" onClick={reset} className="btn">
                <RotateCcw size={11} />
                Clear
              </button>
            )}
          </div>

          <div className="p-4">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                submit(e.dataTransfer.files?.[0]);
              }}
              onClick={() => inputRef.current?.click()}
              className={`flex cursor-pointer flex-col items-center justify-center rounded-xl
                          border border-dashed px-4 py-10 text-center transition ${
                            dragging
                              ? 'border-gold bg-[#D3AF371F]'
                              : 'border-hairline-strong hover:border-ink-mute'
                          }`}
            >
              {preview ? (
                <img
                  src={preview}
                  alt="Uploaded satellite frame"
                  className="max-h-64 rounded-lg object-contain"
                />
              ) : (
                <>
                  <Upload size={22} className="mb-2 text-ink-mute" />
                  <div className="text-xs text-ink-dim">
                    Drop a satellite image, or click to browse
                  </div>
                  <div className="mt-1 text-2xs text-ink-mute">
                    PNG, JPEG, WebP or TIFF · up to 15 MB
                  </div>
                </>
              )}
              <input
                ref={inputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp,image/tiff"
                className="hidden"
                onChange={(e) => submit(e.target.files?.[0])}
              />
            </div>

            {result && (
              <div className="mt-3 flex items-center gap-2 text-2xs text-ink-mute">
                <FileImage size={11} />
                <span className="truncate">{result.filename}</span>
                <span className="tnum">· {(result.size_bytes / 1024).toFixed(0)} KB</span>
                <span className="tnum">· sha {result.sha256}</span>
              </div>
            )}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <span className="panel-title">Analysis</span>
            {result && (
              <span className="chip bg-[#E07A3F26] text-severity-orange">Mock result</span>
            )}
          </div>

          {loading && <LoadingState label="Analysing frame" />}

          {error && (
            <div className="px-4 py-6 text-center text-xs text-severity-red">{error}</div>
          )}

          {!loading && !error && !result && (
            <div className="px-4 py-12 text-center text-xs text-ink-mute">
              Upload an image to see the classification.
            </div>
          )}

          {result && !result.cyclone_detected && (
            <div className="space-y-3 p-4">
              <div className="text-sm font-medium text-ink">No cyclonic system detected</div>
              <p className="text-xs text-ink-dim">{result.message}</p>
              <Metric
                label="Detection probability"
                value={result.detection_probability}
                unit="%"
              />
            </div>
          )}

          {result?.cyclone_detected && cls && (
            <div className="space-y-3 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <div
                    className="font-display text-sm font-medium"
                    style={{ color: categoryColor(cls.intensity_category) }}
                  >
                    {categoryLabel(cls.intensity_category)}
                  </div>
                  <div className="text-2xs text-ink-mute">
                    Pattern: {PATTERN_TYPES[cls.pattern_type] ?? cls.pattern_type}
                  </div>
                </div>
                <CategoryBadge category={cls.intensity_category} size="lg" />
              </div>

              <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
                <Metric label="Detection" value={result.detection_probability} unit="%" />
                <Metric label="Max wind" value={Math.round(cls.est_wind_kt)} unit="kt" />
                <Metric label="Pressure" value={Math.round(cls.est_pressure_hpa)} unit="hPa" />
                <Metric label="Dvorak T" value={cls.dvorak_t_number} />
              </div>

              <div>
                <div className="mb-1.5 field-label">Pattern probabilities</div>
                <div className="space-y-1">
                  {Object.entries(cls.pattern_probabilities)
                    .sort((a, b) => b[1] - a[1])
                    .map(([name, pct], i) => (
                      <div key={name} className="flex items-center gap-2">
                        <span
                          className={`w-40 shrink-0 truncate text-2xs ${
                            i === 0 ? 'text-ink' : 'text-ink-mute'
                          }`}
                        >
                          {PATTERN_TYPES[name] ?? name}
                        </span>
                        <div className="h-1 flex-1 overflow-hidden rounded-full bg-overlay">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${pct}%`,
                              backgroundColor:
                                i === 0 ? categoryColor(cls.intensity_category) : '#2B3648',
                            }}
                          />
                        </div>
                        <span className="tnum w-10 shrink-0 text-right text-2xs text-ink-dim">
                          {pct}%
                        </span>
                      </div>
                    ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="mb-1 field-label">Model confidence</div>
                  <ConfidenceBar value={result.confidence} />
                </div>
                <div>
                  <div className="mb-1 field-label">Out-of-distribution</div>
                  <ConfidenceBar value={1 - result.out_of_distribution_score} />
                </div>
              </div>

              {result.wind_field?.wind_radii && (
                <div>
                  <div className="mb-1.5 field-label">Derived wind radii (Holland)</div>
                  <div className="grid grid-cols-3 gap-2">
                    {['r34_km', 'r50_km', 'r64_km'].map((k) => (
                      <Metric
                        key={k}
                        label={`R${k.slice(1, 3)}`}
                        value={
                          result.wind_field.wind_radii[k]
                            ? Math.round(result.wind_field.wind_radii[k])
                            : '—'
                        }
                        unit="km"
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
