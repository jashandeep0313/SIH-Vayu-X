import { useCallback, useEffect, useState } from 'react';
import { cyclones as cycloneApi, system } from '../services/api.js';
import { liveConnection } from '../services/websocket.js';

/**
 * Active cyclones, seeded by REST and kept current over WebSocket.
 *
 * The initial fetch matters: a dashboard opened mid-event must show current
 * state immediately rather than waiting for the next push.
 */
export function useLiveCyclones() {
  const [cyclones, setCyclones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [connected, setConnected] = useState(false);
  const [pipeline, setPipeline] = useState(null);
  const [demoMode, setDemoMode] = useState(false);

  const refresh = useCallback(() => {
    setError(null);
    return Promise.all([
      cycloneApi.listActive().then((d) => setCyclones(d.items ?? [])),
      system.pipeline().then(setPipeline).catch(() => setPipeline(null)),
      system
        .version()
        .then((v) => setDemoMode(Boolean(v.demo_mode)))
        .catch(() => {}),
    ])
      .catch(setError)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const unsubscribers = [
      liveConnection.on('connection.open', () => setConnected(true)),
      liveConnection.on('connection.closed', () => setConnected(false)),
      liveConnection.on('cyclone.detected', (p) => setCyclones((prev) => [...prev, p])),
      liveConnection.on('cyclone.updated', (p) =>
        setCyclones((prev) => prev.map((c) => (c.id === p.id ? { ...c, ...p } : c))),
      ),
      liveConnection.on('pipeline.status', setPipeline),
    ];

    liveConnection.connect();
    return () => {
      unsubscribers.forEach((off) => off());
      liveConnection.close();
    };
  }, []);

  return { cyclones, loading, error, connected, pipeline, demoMode, refresh };
}
