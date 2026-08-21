import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MyTeamTab from './MyTeamTab';
import { api } from '../../api/client';
import type { LineupAdvice, StartSitRank } from '../../api/types';

vi.mock('../../api/client', () => ({
  api: { getMyTeamLineup: vi.fn(), getStartSitRank: vi.fn() },
}));

const advice = (over: Partial<LineupAdvice> = {}): LineupAdvice => ({
  lineup: [
    { player_id: 1, full_name: 'Josh Allen', position: 'QB', team_abbr: 'BUF', slot: 'QB', projected_points: 22.8 },
    { player_id: 2, full_name: 'Bijan Robinson', position: 'RB', team_abbr: 'ATL', slot: 'RB', projected_points: 17.2 },
  ],
  bench: [
    { player_id: 3, full_name: 'Jake Haener', position: 'QB', team_abbr: 'NO', slot: null, projected_points: 1.7 },
  ],
  projected_points: 40.0,
  current_projected_points: 36.0,
  points_gained: 4.0,
  swaps: [
    {
      slot: 'FLEX',
      start_player_id: 2,
      start_name: 'Bijan Robinson',
      sit_player_id: 3,
      sit_name: 'Jake Haener',
      point_delta: 4.0,
      reason: 'Bijan Robinson (RB, 17.2 pts) over Jake Haener (QB, 1.7 pts): worth +4.0 pts — a clear upgrade.',
    },
  ],
  warnings: [],
  ...over,
});

const ranking = (): StartSitRank => ({
  week: 1,
  season: 2026,
  slots: 1,
  scoring: 'standard',
  confidence: 'medium',
  ranked: [
    {
      rank: 1, player_id: 1, full_name: 'Josh Allen', position: 'QB', team_abbr: 'BUF',
      headshot_url: null, projected_points: 22.8, projected_points_ppr: 24.1,
      matchup_score: 1.1, injury_status: null, verdict: 'start', edge_over_next: 21.1,
      confidence: 'high', reasoning: 'Favourable matchup (score 1.10). Projects 22.8 pts.',
    },
    {
      rank: 2, player_id: 3, full_name: 'Jake Haener', position: 'QB', team_abbr: 'NO',
      headshot_url: null, projected_points: 1.7, projected_points_ppr: 1.7,
      matchup_score: 0.9, injury_status: null, verdict: 'sit', edge_over_next: 0,
      confidence: 'low', reasoning: 'Projects 1.7 pts.',
    },
  ],
});

beforeEach(() => vi.clearAllMocks());

describe('MyTeamTab', () => {
  it('shows the import helper and calls nothing when the roster is empty', () => {
    render(<MyTeamTab rosterIds={[]} onImported={() => {}} />);
    expect(screen.getByText(/import your roster/i)).toBeInTheDocument();
    expect(api.getMyTeamLineup).not.toHaveBeenCalled();
    expect(api.getStartSitRank).not.toHaveBeenCalled();
  });

  it('requests the lineup with exactly the roster ids', async () => {
    // Regression guard: the Optimizer tab searches every player in the league;
    // this tab must stay constrained to the roster the user owns.
    vi.mocked(api.getMyTeamLineup).mockResolvedValue(advice());
    render(<MyTeamTab rosterIds={[1, 2, 3]} onImported={() => {}} />);

    await userEvent.click(screen.getByRole('button', { name: /recommend lineup/i }));

    await waitFor(() => expect(api.getMyTeamLineup).toHaveBeenCalled());
    const call = vi.mocked(api.getMyTeamLineup).mock.calls[0];
    expect(call[0]).toEqual([1, 2, 3]);
    expect(call[1]).toBe(1); // week
  });

  it('renders every lineup slot and player', async () => {
    vi.mocked(api.getMyTeamLineup).mockResolvedValue(advice());
    render(<MyTeamTab rosterIds={[1, 2, 3]} onImported={() => {}} />);
    await userEvent.click(screen.getByRole('button', { name: /recommend lineup/i }));

    await waitFor(() => {
      expect(screen.getAllByText('Josh Allen').length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Bijan Robinson/).length).toBeGreaterThan(0);
    });
  });

  it('renders swaps with the delta and the reason, not just a number', async () => {
    vi.mocked(api.getMyTeamLineup).mockResolvedValue(advice());
    render(<MyTeamTab rosterIds={[1, 2, 3]} onImported={() => {}} />);
    await userEvent.click(screen.getByRole('button', { name: /recommend lineup/i }));

    await waitFor(() => {
      expect(screen.getByText(/Start Bijan Robinson/i)).toBeInTheDocument();
      // The delta appears twice on purpose: once as the headline number and
      // once inside the reason sentence.
      expect(screen.getAllByText(/\+4\.0 pts/).length).toBeGreaterThan(0);
      expect(screen.getByText(/a clear upgrade/i)).toBeInTheDocument();
    });
  });

  it('says the lineup is optimal instead of showing an empty panel', async () => {
    vi.mocked(api.getMyTeamLineup).mockResolvedValue(
      advice({ swaps: [], points_gained: 0 }),
    );
    render(<MyTeamTab rosterIds={[1, 2]} onImported={() => {}} />);
    await userEvent.click(screen.getByRole('button', { name: /recommend lineup/i }));

    await waitFor(() =>
      expect(screen.getByText(/already optimal/i)).toBeInTheDocument(),
    );
  });

  it('surfaces warnings about players who cannot score', async () => {
    vi.mocked(api.getMyTeamLineup).mockResolvedValue(
      advice({ warnings: ['George Kittle starts at TE projecting 0 pts — he is ruled out'] }),
    );
    render(<MyTeamTab rosterIds={[1, 2]} onImported={() => {}} />);
    await userEvent.click(screen.getByRole('button', { name: /recommend lineup/i }));

    await waitFor(() =>
      expect(screen.getByText(/ruled out/i)).toBeInTheDocument(),
    );
  });

  it('ranks players by position when asked who to start', async () => {
    vi.mocked(api.getMyTeamLineup).mockResolvedValue(advice());
    vi.mocked(api.getStartSitRank).mockResolvedValue(ranking());
    render(<MyTeamTab rosterIds={[1, 2, 3]} onImported={() => {}} />);
    await userEvent.click(screen.getByRole('button', { name: /recommend lineup/i }));

    await waitFor(() => screen.getByRole('button', { name: /compare qbs/i }));
    await userEvent.click(screen.getByRole('button', { name: /compare qbs/i }));

    await waitFor(() => {
      // Both QBs on the roster are compared, starter first with reasoning.
      expect(vi.mocked(api.getStartSitRank).mock.calls[0][0]).toEqual([1, 3]);
      expect(screen.getByText(/1\. Josh Allen/)).toBeInTheDocument();
      expect(screen.getByText(/Favourable matchup/)).toBeInTheDocument();
    });
  });

  it('renders an error without crashing', async () => {
    vi.mocked(api.getMyTeamLineup).mockRejectedValue(new Error('boom'));
    render(<MyTeamTab rosterIds={[1, 2]} onImported={() => {}} />);
    await userEvent.click(screen.getByRole('button', { name: /recommend lineup/i }));

    await waitFor(() => expect(screen.getByText('boom')).toBeInTheDocument());
  });
});
