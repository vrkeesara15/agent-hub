'use client';
import { useState, useCallback } from 'react';

export function useAgent<TReq, TRes>(
  apiCall: (req: TReq) => Promise<TRes>
) {
  const [data, setData] = useState<TRes | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const execute = useCallback(async (request: TReq) => {
    setLoading(true);
    setError(null);
    try {
      const result = await apiCall(request);
      setData(result);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
      return null;
    } finally {
      setLoading(false);
    }
  }, [apiCall]);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return { data, loading, error, execute, reset };
}
