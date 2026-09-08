import { useCallback, useEffect, useState } from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';

import Sidebar from './components/layout/Sidebar.jsx';
import TopBar from './components/layout/TopBar.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Alerts from './pages/Alerts.jsx';
import History from './pages/History.jsx';
import DataSources from './pages/DataSources.jsx';
import Analyze from './pages/Analyze.jsx';
import { useLiveCyclones } from './hooks/useLiveCyclones.js';
import { alerts as alertApi } from './services/api.js';

const PAGE_META = {
  '/': { title: 'Operations Overview', subtitle: 'Live cyclone identification, classification and forecast' },
  '/analyze': { title: 'Image Analysis', subtitle: 'Upload a satellite frame for classification' },
  '/alerts': { title: 'Alert Console', subtitle: 'Issued warnings, geofencing and dispatch status' },
  '/history': { title: 'Event History', subtitle: 'Past systems and forecast verification' },
  '/sources': { title: 'Data Sources', subtitle: 'Multi-source satellite ingestion status' },
};

export default function App() {
  const location = useLocation();
  const live = useLiveCyclones();

  const [alerts, setAlerts] = useState([]);
  const [alertsLoading, setAlertsLoading] = useState(true);
  const [alertsError, setAlertsError] = useState(null);

  const loadAlerts = useCallback(() => {
    setAlertsError(null);
    return alertApi
      .list({ limit: 50 })
      .then((d) => setAlerts(d.items ?? []))
      .catch(setAlertsError)
      .finally(() => setAlertsLoading(false));
  }, []);

  useEffect(() => {
    loadAlerts();
  }, [loadAlerts]);

  const refreshAll = useCallback(() => {
    live.refresh();
    loadAlerts();
  }, [live, loadAlerts]);

  const meta = PAGE_META[location.pathname] ?? PAGE_META['/'];

  return (
    <div className="flex h-full">
      <Sidebar alertCount={alerts.filter((a) => a.severity === 'ORANGE' || a.severity === 'RED').length} />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          title={meta.title}
          subtitle={meta.subtitle}
          connected={live.connected}
          pipeline={live.pipeline}
          demoMode={live.demoMode}
          onRefresh={refreshAll}
        />

        <main className="min-h-0 flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Dashboard live={live} alerts={alerts} />} />
            <Route
              path="/alerts"
              element={
                <Alerts
                  alerts={alerts}
                  loading={alertsLoading}
                  error={alertsError}
                  onRefresh={loadAlerts}
                />
              }
            />
            <Route path="/analyze" element={<Analyze />} />
            <Route path="/history" element={<History cyclones={live.cyclones} />} />
            <Route path="/sources" element={<DataSources pipeline={live.pipeline} />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
