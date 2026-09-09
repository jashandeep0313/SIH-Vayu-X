import { useEffect, useState } from 'react';
import { cyclones as cycloneApi, predictions } from '../services/api.js';

/**
 * Full event for one cyclone: observation history plus a model forecast.
 *
 * The forecast is fetched separately because it is generated on demand by the
 * model service rather than stored on the event — so the two calls are issued
 * together and merged here.
 */
export function useCycloneDetail(cycloneId) {
  const [detail, setDetail] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!cycloneId) {
      setDetail(null);
      setForecast(null);
      return undefined;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    setForecast(null);

    cycloneApi
      .get(cycloneId)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    // Inference can take a moment; let the history render without waiting on it.
    predictions
      .latest(cycloneId)
      .then((f) => {
        if (!cancelled) setForecast(f);
      })
      .catch(() => {
        if (!cancelled) setForecast(null);
      });

    return () => {
      cancelled = true;
    };
  }, [cycloneId]);

  const merged = detail
    ? { ...detail, latest_forecast: forecast ?? detail.latest_forecast }
    : null;

  return { detail: merged, forecast, loading, error };
}
