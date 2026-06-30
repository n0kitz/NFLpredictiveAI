import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import GameDetail from './GameDetail';
import { api } from '../api/client';
import type { GameBoxScorePlayer, GameDetail as GameDetailType } from '../api/types';

vi.mock('../api/client', () => ({
  api: { getGameDetail: vi.fn() },
}));

const boxPlayer = (over: Partial<GameBoxScorePlayer> = {}): GameBoxScorePlayer => ({
  player_id: 1067, full_name: 'Patrick Mahomes', position: 'QB', team_id: 2,
  team_abbr: 'KC', headshot_url: null, is_home: true,
  pass_completions: 21, pass_attempts: 39, pass_yards: 226, pass_tds: 2,
  interceptions: 1, rush_attempts: 4, rush_yards: 45, rush_tds: 0,
  targets: 0, receptions: 0, rec_yards: 0, rec_tds: 0, fantasy_points_ppr: 19.5,
  ...over,
});

const detail = (over: Partial<GameDetailType> = {}): GameDetailType => ({
  game_id: 1, date: '2023-09-07', season: 2023, week: '1', game_type: 'regular',
  home_team_id: 2, away_team_id: 5, home_team: 'Kansas City Chiefs', home_abbr: 'KC',
  away_team: 'Detroit Lions', away_abbr: 'DET', home_score: 20, away_score: 21,
  winner: 'Detroit Lions', winner_abbr: 'DET', winner_id: 5, overtime: false,
  venue: 'Arrowhead Stadium', attendance: 73000,
  odds: { id: 1, game_id: 1, opening_spread: -3, over_under: 53, home_implied_prob: 0.65, away_implied_prob: 0.35, fetched_at: null },
  weather: null, factors: [],
  home_box: [boxPlayer()], away_box: [boxPlayer({ player_id: 99, full_name: 'Jared Goff', team_id: 5, team_abbr: 'DET', is_home: false, pass_yards: 253 })],
  box_score_available: true,
  ...over,
});

function renderAt(d: GameDetailType) {
  vi.mocked(api.getGameDetail).mockResolvedValue(d);
  return render(
    <MemoryRouter initialEntries={['/games/1']}>
      <Routes>
        <Route path="/games/:id" element={<GameDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('GameDetail', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders the scoreboard, meta and box-score leaders', async () => {
    renderAt(detail());
    await waitFor(() => expect(screen.getByText('Arrowhead Stadium')).toBeInTheDocument());
    // both teams + scores
    expect(screen.getByText('KC')).toBeInTheDocument();
    expect(screen.getByText('DET')).toBeInTheDocument();
    expect(screen.getByText('73,000')).toBeInTheDocument();
    // box-score leaders (a QB with rush yards lists in both passing + rushing)
    expect(screen.getAllByRole('link', { name: /Patrick Mahomes/ }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: /Jared Goff/ }).length).toBeGreaterThan(0);
    expect(screen.getByText('Box Score')).toBeInTheDocument();
  });

  it('computes the against-the-spread cover result', async () => {
    // home favored by 3 (-3) but only lost by 1 → away (DET) covers
    renderAt(detail());
    await waitFor(() => expect(screen.getByText(/covered/)).toBeInTheDocument());
    expect(screen.getByText('DET covered')).toBeInTheDocument();
  });

  it('shows a fallback when no box score is available', async () => {
    renderAt(detail({ box_score_available: false, home_box: [], away_box: [] }));
    await waitFor(() => expect(screen.getByText(/2018 onward/i)).toBeInTheDocument());
  });
});
