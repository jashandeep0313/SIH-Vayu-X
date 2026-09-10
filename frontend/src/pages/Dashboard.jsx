import { useEffect, useMemo, useState } from 'react';
import { Activity, BellRing, Gauge, Timer, MapPin, TrendingUp } from 'lucide-react';

import CycloneMap from '../components/map/CycloneMap.jsx';
import IntensityChart from '../components/charts/IntensityChart.jsx';
import StormList from '../components/cyclone/StormList.jsx';
import ClassificationPanel from '../components/cyclone/ClassificationPanel.jsx';
import ForecastTable from '../components/cyclone/ForecastTable.jsx';
import Verification from '../components/cyclone/Verification.jsx';
import StatCard from '../components/common/StatCard.jsx';
import { EmptyState, ErrorState, LoadingState, Skeleton } from '../components/common/States.jsx';
import { useCycloneDetail } from '../hooks/useCycloneDetail.js';
import {
  categoryColor,
  formatIst,
  hoursUntil,
  INTENSITY_CATEGORIES,
  peakCategory,
  severityColor,
} from '../utils/constants.js';

export default function Dashboard({ live, alerts }) {
  const { cyclones, loading, error } = live;
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
    if (!selectedId && cyclones.length) setSelectedId(cyclones[0].id);
  }, [cyclones, selectedId]);

  const { detail, loading: detailLoading } = useCycloneDetail(selectedId);

  // Merge the fetched detail (history + forecast) into the summary rows so the
  // map can draw the track and cone for the selected system.
  const mapCyclones = useMemo(
    () =>
      cyclones.map((c) =>
        c.id === detail?.id
          ? { ...c, observations: detail.observations, latest_forecast: detail.latest_forecast }
          : c,
      ),
    [cyclones, detail],
  );

  const selected = cyclones.find((c) => c.id === selectedId);
  const replay = detail?.metadata?.replay ? detail.metadata : null;
  const observation = detail?.observations?.[detail.observations.length - 1]
    ?? selected?.latest_observation;
  const forecast = detail?.latest_forecast;
  const landfall = forecast?.landfall_estimate;

  const peak = peakCategory(cyclones.map((c) => c.latest_observation?.intensity_category));
  const activeAlerts = alerts.filter((a) => a.status !== 'cancelled');
  const topAlert = activeAlerts[0];
  const hoursToLandfall = landfall ? hoursUntil(landfall.expected_at) : null;

  if (error) {
    return (
      <ErrorState
        title="Cannot reach the API gateway"
        hint="Confirm the backend is running on port 8000."
      />
    );
  }

  return (
    <div className="space-y-3 p-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          label="Active systems"
          value={loading ? '—' : cyclones.length}
          icon={Activity}
          sub={`${cyclones.filter((c) => c.status === 'active').length} active · ${cyclones.filter((c) => c.status === 'weakened').length} weakening`}
        />
        <StatCard
          label="Peak intensity"
          value={peak ?? '—'}
          accent={peak ? categoryColor(peak) : undefined}
          icon={Gauge}
          sub={peak ? INTENSITY_CATEGORIES[peak]?.label : 'No systems tracked'}
        />
        <StatCard
          label="Active alerts"
          value={activeAlerts.length}
          icon={BellRing}
          accent={topAlert ? severityColor(topAlert.severity) : undefined}
          sub={topAlert ? `Highest: ${topAlert.severity}` : 'None issued'}
        />
        <StatCard
          label="Time to landfall"
          value={hoursToLandfall != null ? Math.max(0, Math.round(hoursToLandfall)) : '—'}
          unit={hoursToLandfall != null ? 'h' : ''}
          icon={Timer}
          accent={hoursToLandfall != null && hoursToLandfall < 36 ? '#D3AF37' : undefined}
          sub={landfall ? landfall.region : 'No landfall forecast'}
        />
      </div>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1fr_340px]">
        <section className="panel overflow-hidden">
          <div className="panel-header">
            <span className="panel-title">Basin View — North Indian Ocean</span>
            <div className="flex items-center gap-3.5 text-2xs text-ink-mute">
              <LegendItem
                swatch={
                  <span
                    className="h-0.5 w-5 rounded-full"
                    style={{
                      background:
                        'linear-gradient(90deg,#6A9280,#94BCAB,#D3AF37,#E07A3F,#D4544E)',
                    }}
                  />
                }
                label="Observed (by category)"
              />
              <LegendItem
                swatch={<span className="h-0.5 w-5 border-t border-dashed border-ink-dim" />}
                label="Forecast"
              />
              <LegendItem
                swatch={<span className="h-0.5 w-5 rounded-full bg-sage" />}
                label="Actual outcome"
              />
              <LegendItem
                swatch={
                  <span className="h-2.5 w-2.5 rounded-sm border border-dashed border-ink-mute bg-[#686F7C26]" />
                }
                label="Uncertainty cone"
              />
            </div>
          </div>
          <div className="h-[440px]">
            <CycloneMap
              cyclones={mapCyclones}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          </div>
        </section>

        <section className="panel flex flex-col overflow-hidden">
          <div className="panel-header">
            <span className="panel-title">Tracked Systems</span>
            <span className="tnum text-2xs text-ink-mute">{cyclones.length}</span>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {loading ? (
              <div className="space-y-3 p-4">
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-16 w-full" />
              </div>
            ) : cyclones.length === 0 ? (
              <EmptyState
                title="No systems in the basin"
                hint="Detections appear here as the pipeline ingests new satellite frames."
              />
            ) : (
              <StormList
                cyclones={cyclones}
                selectedId={selectedId}
                onSelect={setSelectedId}
              />
            )}
          </div>
        </section>
      </div>

      {replay && (
        <div className="panel flex flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2.5">
          <span className="chip bg-[#7FAF9A1F] text-sage ring-1 ring-inset ring-[#7FAF9A40]">
            Real data
          </span>
          <span className="text-2xs text-ink-dim">
            Historical replay ·{' '}
            <span className="text-ink">
              {selected?.name ?? 'system'} ({replay.season})
            </span>{' '}
            from {replay.source}
          </span>
          <span className="text-2xs text-ink-mute">
            Season held out of model training · forecast scored against the real outcome below
          </span>
        </div>
      )}

      {selected && (
        <>
          {landfall && (
            <div
              className="panel flex flex-wrap items-center gap-x-8 gap-y-3 px-4 py-3"
              style={{
                background:
                  'linear-gradient(90deg, rgba(224,122,63,.10) 0%, rgba(224,122,63,0) 38%)',
              }}
            >
              <div className="flex items-center gap-2">
                <MapPin size={14} className="text-severity-orange" />
                <span className="font-display text-xs font-medium text-ink">
                  Landfall expected
                </span>
              </div>
              <Field label="Region" value={landfall.region} />
              <Field label="Expected (IST)" value={formatIst(landfall.expected_at)} />
              <Field
                label="Lead time"
                value={`${Math.max(0, Math.round(hoursToLandfall ?? 0))} hours`}
              />
              <Field
                label="Confidence"
                value={`${Math.round((landfall.confidence ?? 0) * 100)}%`}
              />
              {forecast?.rapid_intensification_risk != null && (
                <Field
                  label="RI risk (24h)"
                  value={`${Math.round(forecast.rapid_intensification_risk * 100)}%`}
                />
              )}
            </div>
          )}

          <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
            <section className="panel">
              <div className="panel-header">
                <span className="panel-title">
                  Intensity — Observed vs Forecast
                </span>
                <span className="text-2xs text-ink-mute">
                  {forecast?.model_version ?? '—'}
                </span>
              </div>
              <div className="p-2">
                {detailLoading ? (
                  <LoadingState label="Loading intensity history" />
                ) : (
                  <IntensityChart
                    observations={detail?.observations ?? []}
                    forecast={forecast}
                  />
                )}
              </div>
            </section>

            <section className="panel">
              <div className="panel-header">
                <span className="panel-title">Classification</span>
                <span className="text-2xs text-ink-mute">
                  {selected.name ?? 'Unnamed system'}
                </span>
              </div>
              {detailLoading ? (
                <LoadingState label="Loading classification" />
              ) : (
                <ClassificationPanel observation={observation} />
              )}
            </section>
          </div>

          <section className="panel">
            <div className="panel-header">
              <span className="panel-title">Track Forecast</span>
              <div className="flex items-center gap-2 text-2xs text-ink-mute">
                <TrendingUp size={12} />
                Issued {forecast ? formatIst(forecast.issued_at) : '—'} IST
              </div>
            </div>
            {detailLoading ? (
              <LoadingState label="Loading forecast" />
            ) : forecast ? (
              <ForecastTable forecast={forecast} />
            ) : (
              <EmptyState title="No forecast issued for this system" />
            )}
          </section>

          <Verification forecast={forecast} />
        </>
      )}
    </div>
  );
}

function LegendItem({ swatch, label }) {
  return (
    <span className="flex items-center gap-1.5">
      {swatch}
      {label}
    </span>
  );
}

function Field({ label, value }) {
  return (
    <div>
      <div className="text-2xs uppercase tracking-wide text-ink-mute">{label}</div>
      <div className="tnum text-xs text-ink">{value}</div>
    </div>
  );
}
