import { useEffect, useState } from 'react';
import { cyclones as cycloneApi } from '../services/api.js';

/**
 * Full event for one cyclone: observation history plus latest forecast.
 *
 * The list endpoint returns summaries only, so track and cone geometry are
 * fetched on selection rather than shipped for every system on every poll.
 */
export function useCycloneDetail(cycloneId) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!cycloneId) {
      setDetail(null);
      return undefined;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

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

    return () => {
      cancelled = true;
    };
  }, [cycloneId]);

  return { detail, loading, error };
}
