import { useEffect, useState } from 'react';

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

interface Settled<T> {
  deps: readonly unknown[];
  data: T | null;
  error: string | null;
}

function sameDeps(a: readonly unknown[], b: readonly unknown[]): boolean {
  return a.length === b.length && a.every((v, i) => Object.is(v, b[i]));
}

/**
 * Fetch on mount and whenever `deps` change.
 *
 * `loading` is derived — true until the request for the *current* deps has
 * settled — rather than toggled with setState inside the effect, so there is
 * no extra render per fetch and no frame where new deps show old "loaded"
 * state. Until the new request settles, `data` still holds the previous
 * result (callers decide whether to show it); an error clears it.
 *
 * Pass `null` as the fetcher to skip the request (e.g. a collapsed panel or a
 * missing id).
 */
export function useAsync<T>(
  fetcher: (() => Promise<T>) | null,
  deps: readonly unknown[],
  fallbackError = 'Request failed',
): AsyncState<T> {
  const [settled, setSettled] = useState<Settled<T> | null>(null);
  const enabled = fetcher !== null;

  useEffect(() => {
    if (!fetcher) return;
    let cancelled = false;
    fetcher().then(
      (data) => {
        if (!cancelled) setSettled({ deps, data, error: null });
      },
      (err: unknown) => {
        if (cancelled) return;
        const message = err instanceof Error && err.message ? err.message : fallbackError;
        setSettled({ deps, data: null, error: message });
      },
    );
    return () => {
      cancelled = true;
    };
    // The caller's deps list is the contract, as with useEffect itself.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, ...deps]);

  const current = settled !== null && sameDeps(settled.deps, deps);
  return {
    data: settled?.data ?? null,
    loading: enabled && !current,
    error: current ? settled.error : null,
  };
}
