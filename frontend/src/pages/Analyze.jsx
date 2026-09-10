import { useRef, useState } from 'react';
import { Upload, FileImage, AlertTriangle, RotateCcw } from 'lucide-react';
import { CategoryBadge, ConfidenceBar } from '../components/common/Badges.jsx';
import { LoadingState } from '../components/common/States.jsx';
import SmsAlertPanel from '../components/alerts/SmsAlertPanel.jsx';
import SirenAlertPanel from '../components/alerts/SirenAlertPanel.jsx';
import { inference } from '../services/api.js';
import {
  categoryColor,
  categoryLabel,
  INTENSITY_CATEGORIES,
  PATTERN_TYPES,
} from '../utils/constants.js';

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

// Bundled in frontend/public/samples so the feature is testable without hunting
// for files. Ground truth is in the filename.
const SAMPLES = [
  { file: 'nasa_ir_LPA_15kt.jpg', label: 'LPA · 15 kt' },
  { file: 'nasa_ir_D_20kt.jpg', label: 'D · 20 kt' },
  { file: 'nasa_ir_DD_33kt.jpg', label: 'DD · 33 kt' },
  { file: 'nasa_ir_CS_35kt.jpg', label: 'CS · 35 kt' },
  { file: 'nasa_ir_SCS_50kt.jpg', label: 'SCS · 50 kt' },
  { file: 'nasa_ir_VSCS_74kt.jpg', label: 'VSCS · 74 kt' },
  { file: 'nasa_ir_ESCS_112kt.jpg', label: 'ESCS · 112 kt' },
  { file: 'mocha_2023-05-14.png', label: 'MOCHA true-colour (tests OOD guard)' },
];

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

  const loadSample = async (name) => {
    const blob = await (await fetch(`/samples/${name}`)).blob();
    const type = name.endsWith('.png') ? 'image/png' : 'image/jpeg';
    submit(new File([blob], name, { type }));
  };

  const reset = () => {
    setPreview(null);
    setResult(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  const cls = result?.classification;
  const trained = result?.trained_on;

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
            Trained model — but it expects storm-centred infrared frames
          </div>
          <p className="mt-0.5 max-w-3xl text-2xs leading-relaxed text-ink-dim">
            <code className="text-ink-mute">{trained?.model ?? 'intensity_from_image_v2'}</code>{' '}
            is real: gradient boosting over radial IR structure, fitted to{' '}
            {(trained?.frames ?? 70257).toLocaleString()} labelled frames from{' '}
            {trained?.storms ?? 494} storms (NASA/Radiant Earth), split by storm. Held-out wind
            MAE <strong>{trained?.wind_mae_kt ?? '—'} kt</strong>, within one IMD category{' '}
            <strong>
              {trained?.category_within_one
                ? `${Math.round(trained.category_within_one * 100)}%`
                : '—'}
            </strong>
            .
            <br />
            It was trained on <strong>storm-centred infrared crops</strong>. Colour or wide-area
            imagery is refused rather than scored — a greyscale check plus a Mahalanobis distance
            flags it as out-of-distribution. Sample frames with ground truth in the filename are
            bundled below. INSAT frames will differ until the model is retrained on MOSDAC data.
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

            <div className="mt-3">
              <div className="field-label mb-1.5">Or try a labelled sample</div>
              <div className="flex flex-wrap gap-1.5">
                {SAMPLES.map((s) => (
                  <button
                    key={s.file}
                    type="button"
                    onClick={() => loadSample(s.file)}
                    className="btn text-2xs"
                  >
                    {s.label}
                  </button>
                ))}
              </div>
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
            {result &&
              (result.mock ? (
                <span className="chip bg-[#E07A3F26] text-severity-orange">Mock result</span>
              ) : (
                <span className="chip bg-[#7FAF9A1F] text-sage">
                  {result.model ?? 'model'}
                </span>
              ))}
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
              {/* "Cannot assess" and "no storm here" are different answers, and
                  conflating them is how a real cyclone gets waved through. */}
              <div className="text-sm font-medium text-ink">
                {result.out_of_distribution?.flagged
                  ? 'Cannot assess this image'
                  : 'No cyclonic system detected'}
              </div>
              <p className="text-xs leading-relaxed text-ink-dim">
                {result.warning ?? result.message}
              </p>
              {result.out_of_distribution?.flagged && (
                <div className="grid grid-cols-2 gap-2">
                  <Metric
                    label="Reason"
                    value={
                      result.out_of_distribution.reason?.includes('colour')
                        ? 'Colour imagery'
                        : 'Off-distribution'
                    }
                  />
                  <Metric
                    label="Chroma"
                    value={result.out_of_distribution.chroma}
                    unit={`limit ${result.out_of_distribution.chroma_limit}`}
                  />
                </div>
              )}
              <p className="text-2xs leading-relaxed text-ink-mute">
                This is not a low-intensity reading — the model declined to score the frame.
                Feed it a storm-centred infrared crop, such as the labelled samples on the left.
              </p>
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
                <Metric
                  label="Confidence"
                  value={result.confidence_pct ?? result.detection_probability}
                  unit="%"
                />
                <Metric label="Max wind" value={Math.round(cls.est_wind_kt)} unit="kt" />
                <Metric label="Pressure" value={Math.round(cls.est_pressure_hpa)} unit="hPa" />
                <Metric label="Dvorak T" value={cls.dvorak_t_number} />
              </div>

              {!result.mock && cls.wind_range_kt && (
                <div className="rounded-lg bg-raised px-3 py-2.5 ring-1 ring-hairline">
                  <div className="field-label">Likely wind range</div>
                  <div className="tnum mt-1 text-sm text-ink">
                    {cls.wind_range_kt[0]} – {cls.wind_range_kt[1]} kt
                  </div>
                  <div className="mt-1 text-2xs leading-relaxed text-ink-mute">
                    From {cls.interval_source ?? 'the model'}
                    {cls.interval_width_kt ? ` · ${cls.interval_width_kt} kt wide` : ''}. Pattern is{' '}
                    {cls.pattern_source ?? 'inferred'}.
                  </div>
                </div>
              )}

              {/* A known directional error is only useful if the operator sees
                  it. IR saturates at the top of the scale, so intense storms
                  read low — the dangerous direction for a warning system. */}
              {cls.intensity_caveat && (
                <div
                  className="flex items-start gap-2 rounded-lg px-3 py-2.5 ring-1 ring-[#D3AF3740]"
                  style={{ background: 'rgba(211,175,55,.10)' }}
                >
                  <AlertTriangle size={13} className="mt-0.5 shrink-0 text-gold" />
                  <div>
                    <div className="field-label text-gold">Likely an underestimate</div>
                    <p className="mt-0.5 text-2xs leading-relaxed text-ink-dim">
                      {cls.intensity_caveat}
                    </p>
                  </div>
                </div>
              )}

              {result.trained_on && (
                <div className="text-2xs leading-relaxed text-ink-mute">
                  Trained on {result.trained_on.frames?.toLocaleString()} frames from{' '}
                  {result.trained_on.storms} storms · held-out MAE{' '}
                  {result.trained_on.wind_mae_kt} kt
                  {result.trained_on.per_category_error?.[cls.intensity_category] && (
                    <>
                      {' '}(
                      {result.trained_on.per_category_error[cls.intensity_category].mae_kt} kt for{' '}
                      {cls.intensity_category})
                    </>
                  )}{' '}
                  · {result.trained_on.sensor_note}
                </div>
              )}

              {(cls.category_probabilities ?? cls.pattern_probabilities) && (
              <div>
                <div className="mb-1.5 flex items-center justify-between">
                  <span className="field-label">
                    {cls.category_probabilities ? 'Category probabilities' : 'Pattern probabilities'}
                  </span>
                  <span className="text-2xs text-ink-mute">sums to 100</span>
                </div>
                <div className="space-y-1">
                  {Object.entries(cls.category_probabilities ?? cls.pattern_probabilities)
                    .sort((a, b) => b[1] - a[1])
                    .map(([name, pct], i) => (
                      <div key={name} className="flex items-center gap-2">
                        <span
                          className={`w-40 shrink-0 truncate text-2xs ${
                            i === 0 ? 'text-ink' : 'text-ink-mute'
                          }`}
                        >
                          {INTENSITY_CATEGORIES[name]?.label ?? PATTERN_TYPES[name] ?? name}
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
              )}

              {result.confidence_pct != null && (
                <div>
                  <div className="mb-1 flex items-center justify-between">
                    <span className="field-label">Model confidence</span>
                    <span className="tnum text-2xs text-ink-dim">{result.confidence_pct}%</span>
                  </div>
                  <ConfidenceBar value={result.confidence_pct / 100} showLabel={false} />
                  <p className="mt-1 text-2xs leading-relaxed text-ink-mute">
                    Top category probability, reduced when the wind interval is wide. Low
                    confidence means an ambiguous frame — not a low-intensity storm.
                  </p>
                </div>
              )}

              <SmsAlertPanel analysis={result} />
              <SirenAlertPanel analysis={result} autoResult={result.siren} />

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
