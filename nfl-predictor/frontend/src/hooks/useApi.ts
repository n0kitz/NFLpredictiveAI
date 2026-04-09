import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import type { TeamList, Prediction, H2H, TeamMetrics, TeamProfile, GameList, AccuracyStats, InlineFactor } from '../api/types';

/** Generic hook for async data fetching with loading/error states. */
function useAsync<T>(fetcher: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetcher()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error };
}

/** Fetch all teams (cached for the session). */
export function useTeams() {
  return useAsync<TeamList>(() => api.getTeams(), []);
}

/** Fetch metrics for a single team. */
export function useTeamMetrics(identifier: string) {
  return useAsync<TeamMetrics>(() => api.getTeamMetrics(identifier), [identifier]);
}

/** Fetch all-time + last season profile for a team. */
export function useTeamProfile(identifier: string) {
  return useAsync<TeamProfile>(() => api.getTeamProfile(identifier), [identifier]);
}

/** Fetch recent games for a team. */
export function useTeamGames(identifier: string, limit = 10) {
  return useAsync<GameList>(() => api.getTeamGames(identifier, limit), [identifier, limit]);
}

/** Run a prediction — triggered manually via callback. */
export function usePrediction() {
  const [data, setData] = useState<Prediction | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const predict = useCallback(async (homeTeam: string, awayTeam: string, factors?: InlineFactor[]) => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.predict(homeTeam, awayTeam, factors);
      setData(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Prediction failed');
    } finally {
      setLoading(false);
    }
  }, []);

  return { data, loading, error, predict };
}

/** Fetch head-to-head between two teams. */
export function useH2H(team1: string, team2: string, limit = 10) {
  return useAsync<H2H>(
    () => api.h2h(team1, team2, limit),
    [team1, team2, limit],
  );
}

/** Fetch model accuracy stats. */
export function useAccuracy(seasons = '2024,2025') {
  return useAsync<AccuracyStats>(() => api.getAccuracy(seasons), [seasons]);
}
