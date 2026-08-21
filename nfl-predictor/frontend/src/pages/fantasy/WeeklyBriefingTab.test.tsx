import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import WeeklyBriefingTab from './WeeklyBriefingTab';
import { api } from '../../api/client';
import type {
  LineupAdvice, ScheduleOutlook, StreamingResult, FaabResult,
} from '../../api/types';

vi.mock('../../api/client', () => ({
  api: {
    getMyTeamLineup: vi.fn(),
    getScheduleOutlook: vi.fn(),
    getStreamingCandidates: vi.fn(),
    getFaabRecommendations: vi.fn(),
  },
}));

const advice = (over: Partial<LineupAdvice> = {}): LineupAdvice => ({
  lineup: [
    { player_id: 1, full_name: 'Josh Allen', position: 'QB', team_abbr: 'BUF', slot: 'QB', projected_points: 22.8 },
  ],
  bench: [],
  projected_points: 22.8,
  current_projected_points: 18.8,
  points_gained: 4.0,
  swaps: [
    {
      slot: 'FLEX', start_player_id: 2, start_name: 'Bijan Robinson',
      sit_player_id: 3, sit_name: 'Jake Haener', point_delta: 4.0,
      reason: 'Bijan Robinson over Jake Haener: worth +4.0 pts.',
    },
  ],
  warnings: [],
  ...over,
});

const outlook = (over: Partial<ScheduleOutlook> = {}): ScheduleOutlook => ({
  season: 2026,
  players: [
    { player_id: 1, full_name: 'Josh Allen', position: 'QB', team_abbr: 'BUF', bye_week: null, playoff_weeks: [], playoff_sos_score: null },
    // Bye week 1 matches the component's default selected week.
    { player_id: 5, full_name: 'Stefon Diggs', position: 'WR', team_abbr: 'HOU', bye_week: 1, playoff_weeks: [], playoff_sos_score: null },
  ],
  bye_collisions: {},
  ...over,
});

const streaming = (over: Partial<StreamingResult> = {}): StreamingResult => ({
  position: 'DST',
  week: 3,
  season: 2026,
  candidates: [
    {
      player_id: 2272, full_name: 'Miami Dolphins DST', team_abbr: 'MIA',
      opponent_team_abbr: 'LV', grade: 'D', score: 47.9, explanation: '...',
    },
  ],
  ...over,
});

const faab = (over: Partial<FaabResult> = {}): FaabResult => ({
  week: 3,
  season: 2026,
  budget_remaining: 100,
  candidates: [
    {
      player_id: 96, full_name: 'Bijan Robinson', position: 'RB', team_abbr: 'ATL',
      projected_points: 17.16, replacement_points: 3.92, delta: 13.24,
      tier: 'must-add', suggested_bid_pct: 30, suggested_bid_amount: 30,
    },
  ],
  ...over,
});

beforeEach(() => vi.clearAllMocks());

describe('WeeklyBriefingTab', () => {
  it('shows the import helper and calls nothing when the roster is empty', () => {
    render(<WeeklyBriefingTab rosterIds={[]} onImported={() => {}} />);
    expect(screen.getByText(/import your roster/i)).toBeInTheDocument();
    expect(api.getMyTeamLineup).not.toHaveBeenCalled();
  });

  it('fetches all four sources for the selected week when generated', async () => {
    vi.mocked(api.getMyTeamLineup).mockResolvedValue(advice());
    vi.mocked(api.getScheduleOutlook).mockResolvedValue(outlook());
    vi.mocked(api.getStreamingCandidates).mockResolvedValue(streaming());
    vi.mocked(api.getFaabRecommendations).mockResolvedValue(faab());
    render(<WeeklyBriefingTab rosterIds={[1, 5]} onImported={() => {}} />);

    await userEvent.click(screen.getByRole('button', { name: /generate briefing/i }));

    await waitFor(() => {
      expect(api.getMyTeamLineup).toHaveBeenCalled();
      expect(api.getScheduleOutlook).toHaveBeenCalled();
      expect(api.getStreamingCandidates).toHaveBeenCalled();
      expect(api.getFaabRecommendations).toHaveBeenCalled();
    });
    // Schedule outlook must be scoped to the briefing's own week, not the default 15-17.
    const scheduleCall = vi.mocked(api.getScheduleOutlook).mock.calls[0];
    expect(scheduleCall[2]).toEqual([1]);
  });

  it('renders the lineup swap summary', async () => {
    vi.mocked(api.getMyTeamLineup).mockResolvedValue(advice());
    vi.mocked(api.getScheduleOutlook).mockResolvedValue(outlook());
    vi.mocked(api.getStreamingCandidates).mockResolvedValue(streaming());
    vi.mocked(api.getFaabRecommendations).mockResolvedValue(faab());
    render(<WeeklyBriefingTab rosterIds={[1, 5]} onImported={() => {}} />);
    await userEvent.click(screen.getByRole('button', { name: /generate briefing/i }));

    await waitFor(() => {
      expect(screen.getByText(/start bijan robinson/i)).toBeInTheDocument();
    });
  });

  it('flags a rostered player on bye this week', async () => {
    vi.mocked(api.getMyTeamLineup).mockResolvedValue(advice());
    vi.mocked(api.getScheduleOutlook).mockResolvedValue(outlook());
    vi.mocked(api.getStreamingCandidates).mockResolvedValue(streaming());
    vi.mocked(api.getFaabRecommendations).mockResolvedValue(faab());
    render(<WeeklyBriefingTab rosterIds={[1, 5]} onImported={() => {}} />);
    await userEvent.click(screen.getByRole('button', { name: /generate briefing/i }));

    await waitFor(() => {
      expect(screen.getByText(/stefon diggs/i)).toBeInTheDocument();
      // "On bye this week" header + the per-player "— bye" line both match.
      expect(screen.getAllByText(/bye/i).length).toBeGreaterThan(1);
    });
  });

  it('renders top streaming pick and top FAAB target', async () => {
    vi.mocked(api.getMyTeamLineup).mockResolvedValue(advice());
    vi.mocked(api.getScheduleOutlook).mockResolvedValue(outlook());
    vi.mocked(api.getStreamingCandidates).mockResolvedValue(streaming());
    vi.mocked(api.getFaabRecommendations).mockResolvedValue(faab());
    render(<WeeklyBriefingTab rosterIds={[1, 5]} onImported={() => {}} />);
    await userEvent.click(screen.getByRole('button', { name: /generate briefing/i }));

    await waitFor(() => {
      expect(screen.getByText(/miami dolphins dst/i)).toBeInTheDocument();
      expect(screen.getAllByText(/bijan robinson/i).length).toBeGreaterThan(0);
    });
  });

  it('renders partial results when one source fails', async () => {
    vi.mocked(api.getMyTeamLineup).mockResolvedValue(advice());
    vi.mocked(api.getScheduleOutlook).mockRejectedValue(new Error('boom'));
    vi.mocked(api.getStreamingCandidates).mockResolvedValue(streaming());
    vi.mocked(api.getFaabRecommendations).mockResolvedValue(faab());
    render(<WeeklyBriefingTab rosterIds={[1, 5]} onImported={() => {}} />);
    await userEvent.click(screen.getByRole('button', { name: /generate briefing/i }));

    await waitFor(() => {
      expect(screen.getByText(/start bijan robinson/i)).toBeInTheDocument();
      expect(screen.getByText(/miami dolphins dst/i)).toBeInTheDocument();
    });
  });
});
