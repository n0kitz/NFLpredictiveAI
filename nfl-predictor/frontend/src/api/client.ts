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
  TeamRoster, PlayerProfile, PlayerSearchResult, FantasyLeaderboard,
  FantasyProjection, StartSitResult, DraftRanking, TradeAnalysis,
  PlayoffPicture, TeamUpcoming, PowerRankings, TradeValues, RosterImportResult,
  MatchupGrade, ValuePicksResponse,
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

  // Roster
  getTeamRoster: (id: string, season?: number) =>
    get<TeamRoster>(`/teams/${encodeURIComponent(id)}/roster${season ? `?season=${season}` : ''}`),
  getTeamStarters: (id: string, season?: number) =>
    get<TeamRoster>(`/teams/${encodeURIComponent(id)}/starters${season ? `?season=${season}` : ''}`),

  // Players
  getPlayer: (playerId: number) => get<PlayerProfile>(`/players/${playerId}`),
  searchPlayers: (query: string) =>
    get<PlayerSearchResult[]>(`/players/search?q=${encodeURIComponent(query)}`),

  // Fantasy — leaderboard (existing)
  getFantasyTop: (position?: string, season = 2024, scoring = 'ppr', limit = 50) => {
    const params = new URLSearchParams({ season: String(season), scoring, limit: String(limit) });
    if (position) params.set('position', position);
    return get<FantasyLeaderboard>(`/fantasy/top?${params}`);
  },

  // Fantasy — extended
  getFantasyProjections: (week: number, season = 2024, position = 'all', scoring = 'ppr') =>
    get<FantasyProjection[]>(
      `/fantasy/projections?week=${week}&season=${season}&position=${encodeURIComponent(position)}&scoring=${scoring}`
    ),
  getStartSit: (player1Id: number, player2Id: number, week: number, season = 2024) =>
    get<StartSitResult>(
      `/fantasy/start-sit?player1_id=${player1Id}&player2_id=${player2Id}&week=${week}&season=${season}`
    ),
  getWaiverWire: (week: number, season = 2024, scoring = 'ppr', position = 'all', limit = 30) =>
    get<FantasyProjection[]>(
      `/fantasy/waiver?week=${week}&season=${season}&scoring=${scoring}&position=${encodeURIComponent(position)}&limit=${limit}`
    ),
  getDraftRankings: (season = 2025, scoring = 'ppr', position = 'all') =>
    get<DraftRanking[]>(
      `/fantasy/draft-rankings?season=${season}&scoring=${scoring}&position=${encodeURIComponent(position)}`
    ),
  analyzeTrade: (body: {
    give_player_ids: number[];
    get_player_ids: number[];
    week: number;
    season: number;
  }) => post<TradeAnalysis>('/fantasy/trade-analyze', body),

  // Playoff Picture
  getPlayoffPicture: (year: number) =>
    get<PlayoffPicture>(`/seasons/${year}/playoff-picture`),

  // Team upcoming schedule
  getTeamUpcoming: (id: string, season = 2025, limit = 4) =>
    get<TeamUpcoming>(`/teams/${encodeURIComponent(id)}/upcoming?season=${season}&limit=${limit}`),

  // Fantasy extended
  getFantasyPowerRankings: (week: number, season = 2024) =>
    get<PowerRankings>(`/fantasy/power-rankings?week=${week}&season=${season}`),

  getFantasyTradeValues: (week: number, season = 2024) =>
    get<TradeValues>(`/fantasy/trade-values?week=${week}&season=${season}`),

  importRosterByNames: (names: string[], season = 2024) =>
    post<RosterImportResult>('/fantasy/roster/import-by-names', { names, season }),

  // Value picks
  getValuePicks: () =>
    get<ValuePicksResponse>('/picks/value'),

  // Phase 2: matchup grade
  getMatchupGrade: (playerId: number, week: number, season = 2024) =>
    get<MatchupGrade>(`/fantasy/matchup/${playerId}?week=${week}&season=${season}`),
};
