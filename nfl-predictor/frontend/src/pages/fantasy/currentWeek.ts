import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';

// One lookup per page load, shared by every tab's week picker.
let pending: Promise<number | null> | null = null;

function fetchCurrentWeek(): Promise<number | null> {
  if (!pending) {
    pending = Promise.resolve()
      .then(() => api.getCurrentWeek())
      .then((r) => r.week)
      .catch(() => {
        pending = null; // let a later mount retry
        return null;
      });
  }
  return pending;
}

/** Test hook: forget the cached lookup. */
export function resetCurrentWeekCache(): void {
  pending = null;
}

/**
 * Week picker state that opens on the week still to be played (from
 * `/api/fantasy/current-week`) instead of week 1. Falls back to 1 when the
 * lookup fails, and never overrides a week the user chose themselves.
 */
export function useFantasyWeek(): [number, (week: number) => void] {
  const [week, setWeekState] = useState(1);
  const touched = useRef(false);

  useEffect(() => {
    let alive = true;
    fetchCurrentWeek().then((w) => {
      if (alive && w && !touched.current) setWeekState(w);
    });
    return () => {
      alive = false;
    };
  }, []);

  const setWeek = useCallback((w: number) => {
    touched.current = true;
    setWeekState(w);
  }, []);

  return [week, setWeek];
}
