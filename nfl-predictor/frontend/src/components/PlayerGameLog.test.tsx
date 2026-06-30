import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PlayerGameLog from './PlayerGameLog';
import { api } from '../api/client';
import type { PlayerWeekCell, PlayerWeeklyStatsResponse } from '../api/types';

vi.mock('../api/client', () => ({
  api: { getPlayerWeeklyStats: vi.fn() },
}));

const cell = (over: Partial<PlayerWeekCell> = {}): PlayerWeekCell => ({
  week: 1, is_bye: false, snaps: 60, snap_pct: 0.95, route_pct: 0, routes: 0,
  targets: 0, target_share: 0, receptions: 0, rec_yards: 0, rec_tds: 0,
  air_yards: 0, adot: 0, rush_attempts: 4, rush_yards: 45, rush_tds: 0,
  pass_attempts: 39, pass_completions: 21, pass_yards: 226, pass_tds: 2,
  interceptions: 1, fantasy_points_ppr: 19.5, fantasy_points_standard: 19.5,
  opponent_abbr: 'DET', is_home: false, team_score: 20, opp_score: 21, result: 'L',
  ...over,
});

// A blank week (no game played) — should be filtered out of the log.
const blank = (week: number, is_bye = false): PlayerWeekCell =>
  cell({
    week, is_bye, opponent_abbr: null, result: null, team_score: null, opp_score: null,
    snap_pct: 0, snaps: null, fantasy_points_ppr: 0, fantasy_points_standard: 0,
    pass_attempts: 0, pass_completions: 0, pass_yards: 0, rush_attempts: 0, rush_yards: 0, targets: 0,
  });

describe('PlayerGameLog', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders a played QB week and filters out bye / no-data weeks', async () => {
    const resp: PlayerWeeklyStatsResponse = {
      player_id: 1, season: 2023,
      weeks: [cell({ week: 1 }), blank(2, true), blank(3)],
    };
    vi.mocked(api.getPlayerWeeklyStats).mockResolvedValue(resp);

    render(<MemoryRouter><PlayerGameLog playerId={1} position="QB" /></MemoryRouter>);

    await waitFor(() => expect(screen.getByText('21/39')).toBeInTheDocument());
    // QB-specific columns surface the full line
    expect(screen.getByText('226')).toBeInTheDocument();          // pass yards
    expect(screen.getByText(/L\s+20/)).toBeInTheDocument();        // result + score
    expect(screen.getByRole('link', { name: /DET/ })).toBeInTheDocument();
    // bye + no-data weeks filtered → exactly one game row (one PPR value)
    expect(screen.getAllByText('19.5')).toHaveLength(1);
  });

  it('shows an empty-state when there are no games', async () => {
    vi.mocked(api.getPlayerWeeklyStats).mockResolvedValue({ player_id: 1, season: 2023, weeks: [] });
    render(<MemoryRouter><PlayerGameLog playerId={1} position="WR" /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/No game data/i)).toBeInTheDocument());
  });
});
