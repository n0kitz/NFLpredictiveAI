import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import OptimizerTab from './OptimizerTab';
import { api } from '../../api/client';
import type { FantasyProjection, OptimizeResponse } from '../../api/types';

vi.mock('../../api/client', () => ({
  api: { getFantasyProjections: vi.fn(), optimizeLineup: vi.fn(), optimizeDFS: vi.fn() },
}));

const proj = (over: Partial<FantasyProjection> = {}): FantasyProjection => ({
  player_id: 1, full_name: 'Test QB', position: 'QB', team_abbr: 'ARI',
  headshot_url: null, opponent_team_id: 27, week: 1, season: 2025,
  projected_points_ppr: 20, projected_points_std: 18, matchup_score: 1.0,
  opportunity_score: 5, confidence: 'high', injury_status: null,
  weather_impact: false, model_source: 'ml', model_version: 'ml-v1-QB',
  floor_ppr: 14, ceiling_ppr: 27, contributions: [], boom_pct: 20,
  bust_pct: 10, bye_week: null, ...over,
});

const response: OptimizeResponse = {
  lineups: [{ rank: 1, players: [], projected_points: 123.4, total_salary: 0, correlation_bonus: 0 }],
  exposure: {}, total_lineups: 1, slots: { QB: 1 },
};

describe('OptimizerTab', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders the config panel with an Optimize button', () => {
    render(<OptimizerTab />);
    expect(screen.getByText('Optimize')).toBeInTheDocument();
    expect(screen.getByText(/Configure options above/i)).toBeInTheDocument();
  });

  it('forwards opponent_team_id from projections into the optimizer player pool', async () => {
    vi.mocked(api.getFantasyProjections).mockResolvedValue([proj({ opponent_team_id: 27 })]);
    vi.mocked(api.optimizeLineup).mockResolvedValue(response);
    const user = userEvent.setup();

    render(<OptimizerTab />);
    await user.click(screen.getByText('Optimize'));

    await waitFor(() => expect(api.optimizeLineup).toHaveBeenCalled());
    const body = vi.mocked(api.optimizeLineup).mock.calls[0][0];
    // every pooled player carries the opponent id through (Step 2 wiring)
    expect(body.players.length).toBeGreaterThan(0);
    expect(body.players[0].opponent_team_id).toBe(27);
  });
});
