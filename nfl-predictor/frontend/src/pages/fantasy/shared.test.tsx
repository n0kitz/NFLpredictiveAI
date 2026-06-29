import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MatchupGradePill } from './shared';
import { api } from '../../api/client';
import type { MatchupGrade } from '../../api/types';

vi.mock('../../api/client', () => ({
  api: { getMatchupGrade: vi.fn() },
}));

const grade = (over: Partial<MatchupGrade> = {}): MatchupGrade => ({
  player_id: 1, full_name: 'Test QB', position: 'QB', team_abbr: 'ARI',
  opp_team_id: 27, opp_team_abbr: 'NO', week: 1, season: 2025,
  grade: 'A', score: 88.0, rank_vs_league: 30, explanation: 'soft matchup.',
  dvp_6wk: 25, avg_league_dvp: 20, opp_ypp: 5.5, pace: 1.0, proe: 0.0,
  component_scores: { dvp: 80, ypp: 80, pace: 80, proe: 50 },
  ...over,
});

describe('MatchupGradePill', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders the letter grade once the fetch resolves', async () => {
    vi.mocked(api.getMatchupGrade).mockResolvedValue(grade({ grade: 'A' }));
    render(<MatchupGradePill playerId={1} week={1} season={2025} />);
    expect(await screen.findByText('A')).toBeInTheDocument();
    expect(api.getMatchupGrade).toHaveBeenCalledWith(1, 1, 2025);
  });

  it('renders nothing when the grade fetch fails (no opponent data)', async () => {
    vi.mocked(api.getMatchupGrade).mockRejectedValue(new Error('404'));
    const { container } = render(<MatchupGradePill playerId={2} week={1} season={2025} />);
    // loading ellipsis first, then collapses to empty after the rejection settles
    await waitFor(() => expect(container.textContent).toBe(''));
  });
});
