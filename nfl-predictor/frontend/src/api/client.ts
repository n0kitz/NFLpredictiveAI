/**
 * Typed API client for the NFL Prediction backend.
 *
 * All functions hit /api/* which Vite proxies to the FastAPI server in dev,
 * and nginx proxies in production (Docker).
 */

import type {
  Team, TeamList, GameList, Prediction, PredictionExplanation,
  H2H, TeamMetrics, TeamSeasonStats, TeamProfile, HealthStatus,
  AccuracyStats, InlineFactor, PredictionHistory,
} from './types';

const BASE = '/api';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? `Request failed: ${res.status}`);
  }
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? `Request failed: ${res.status}`);
  }
  return res.json();
}

// ── Public API ───────────────────────────────────────

export const api = {
  health: () => get<HealthStatus>('/health'),

  // Teams
  getTeams: () => get<TeamList>('/teams'),
  getTeam: (id: string) => get<Team>(`/teams/${encodeURIComponent(id)}`),
  getTeamMetrics: (id: string) => get<TeamMetrics>(`/teams/${encodeURIComponent(id)}/stats`),
  getTeamSeason: (id: string, season: number) =>
    get<TeamSeasonStats>(`/teams/${encodeURIComponent(id)}/season/${season}`),
  getTeamProfile: (id: string) =>
    get<TeamProfile>(`/teams/${encodeURIComponent(id)}/profile`),
  getTeamGames: (id: string, limit = 10) =>
    get<GameList>(`/teams/${encodeURIComponent(id)}/games?limit=${limit}`),

  // Games
  getGames: (season?: number, type?: string) => {
    const params = new URLSearchParams();
    if (season) params.set('season', String(season));
    if (type) params.set('game_type', type);
    const qs = params.toString();
    return get<GameList>(`/games${qs ? `?${qs}` : ''}`);
  },

  // Predictions
  predict: (homeTeam: string, awayTeam: string, factors?: InlineFactor[]) =>
    post<Prediction>('/predict', {
      home_team: homeTeam,
      away_team: awayTeam,
      ...(factors && factors.length > 0 ? { factors } : {}),
    }),
  explainPrediction: (homeTeam: string, awayTeam: string, factors?: InlineFactor[]) =>
    post<PredictionExplanation>('/predict/explain', {
      home_team: homeTeam,
      away_team: awayTeam,
      ...(factors && factors.length > 0 ? { factors } : {}),
    }),
  predictGet: (awayTeam: string, homeTeam: string) =>
    get<Prediction>(`/predict/${encodeURIComponent(awayTeam)}/${encodeURIComponent(homeTeam)}`),

  // Head-to-head
  h2h: (team1: string, team2: string, limit = 10) =>
    get<H2H>(`/h2h/${encodeURIComponent(team1)}/${encodeURIComponent(team2)}?limit=${limit}`),

  // Accuracy
  getAccuracy: (seasons = '2024,2025') =>
    get<AccuracyStats>(`/accuracy?seasons=${encodeURIComponent(seasons)}`),

  // Prediction history
  getPredictionHistory: (limit = 50, offset = 0) =>
    get<PredictionHistory>(`/predictions/history?limit=${limit}&offset=${offset}`),
};
