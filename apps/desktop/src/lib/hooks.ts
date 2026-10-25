import { useCallback, useEffect, useState } from "react";

import { errorMessage } from "./api";

export interface AsyncState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
  setData: (data: T | null) => void;
}

/** Пауза между автоматическими повторами загрузки. */
const RETRY_DELAY_MS = 1500;

export function useAsyncData<T>(
  loader: () => Promise<T>,
  deps: unknown[] = [],
  retries = 1,
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((value) => value + 1), []);

  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    setLoading(true);
    setError(null);

    async function run(attemptLeft: number): Promise<void> {
      try {
        const value = await loader();
        if (!active) return;
        setData(value);
        setLoading(false);
      } catch (err) {
        if (!active) return;
        if (attemptLeft > 0) {
          timer = window.setTimeout(() => void run(attemptLeft - 1), RETRY_DELAY_MS);
          return;
        }
        setError(errorMessage(err));
        setLoading(false);
      }
    }

    void run(retries);
    return () => {
      active = false;
      if (timer) window.clearTimeout(timer);
    };
  }, [...deps, nonce, retries]);

  return { data, error, loading, reload, setData };
}
