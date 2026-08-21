import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ScheduleTab from './ScheduleTab';
import { api } from '../../api/client';
import type { ScheduleOutlook } from '../../api/types';

vi.mock('../../api/client', () => ({
  api: { getScheduleOutlook: vi.fn() },
}));

const outlook = (over: Partial<ScheduleOutlook> = {}): ScheduleOutlook => ({
  season: 2026,
  players: [
    {
      player_id: 1,
      full_name: 'Josh Allen',
      position: 'QB',
      team_abbr: 'BUF',
      bye_week: 7,
      playoff_weeks: [
        { week: 15, opponent_team_id: 9, opponent_team_abbr: 'NE', dvp: 15.4, difficulty: 'hard' },
        { week: 16, opponent_team_id: 3, opponent_team_abbr: 'MIA', dvp: 24.1, difficulty: 'easy' },
        { week: 17, opponent_team_id: 8, opponent_team_abbr: 'NYJ', dvp: 19.9, difficulty: 'medium' },
      ],
      playoff_sos_score: 19.8,
    },
    {
      player_id: 2,
      full_name: 'Stefon Diggs',
      position: 'WR',
      team_abbr: 'HOU',
      bye_week: 7,
      playoff_weeks: [],
      playoff_sos_score: null,
    },
  ],
  bye_collisions: {},
  ...over,
});

beforeEach(() => vi.clearAllMocks());

describe('ScheduleTab', () => {
  it('shows the import helper and calls nothing when the roster is empty', () => {
    render(<ScheduleTab rosterIds={[]} onImported={() => {}} />);
    expect(screen.getByText(/import your roster/i)).toBeInTheDocument();
    expect(api.getScheduleOutlook).not.toHaveBeenCalled();
  });

  it('requests the outlook with exactly the roster ids', async () => {
    vi.mocked(api.getScheduleOutlook).mockResolvedValue(outlook());
    render(<ScheduleTab rosterIds={[1, 2, 3]} onImported={() => {}} />);

    await userEvent.click(screen.getByRole('button', { name: /check schedule/i }));

    await waitFor(() => expect(api.getScheduleOutlook).toHaveBeenCalled());
    expect(vi.mocked(api.getScheduleOutlook).mock.calls[0][0]).toEqual([1, 2, 3]);
  });

  it('renders bye week and playoff-week difficulty per player', async () => {
    vi.mocked(api.getScheduleOutlook).mockResolvedValue(outlook());
    render(<ScheduleTab rosterIds={[1, 2]} onImported={() => {}} />);
    await userEvent.click(screen.getByRole('button', { name: /check schedule/i }));

    await waitFor(() => {
      expect(screen.getAllByText('Josh Allen').length).toBeGreaterThan(0);
      // Both fixture players share bye week 7 on purpose (collision coverage).
      expect(screen.getAllByText(/bye 7/i).length).toBe(2);
      expect(screen.getByText('NE')).toBeInTheDocument();
      expect(screen.getByText('19.8')).toBeInTheDocument();
    });
  });

  it('flags a bye-week collision shared by 3+ roster players', async () => {
    vi.mocked(api.getScheduleOutlook).mockResolvedValue(
      outlook({ bye_collisions: { '7': [1, 2, 3] } }),
    );
    render(<ScheduleTab rosterIds={[1, 2, 3]} onImported={() => {}} />);
    await userEvent.click(screen.getByRole('button', { name: /check schedule/i }));

    await waitFor(() =>
      expect(screen.getByText(/3 players share bye week 7/i)).toBeInTheDocument(),
    );
  });

  it('shows no collision warning when bye_collisions is empty', async () => {
    vi.mocked(api.getScheduleOutlook).mockResolvedValue(outlook());
    render(<ScheduleTab rosterIds={[1, 2]} onImported={() => {}} />);
    await userEvent.click(screen.getByRole('button', { name: /check schedule/i }));

    await waitFor(() => screen.getByText('Josh Allen'));
    expect(screen.queryByText(/share bye week/i)).not.toBeInTheDocument();
  });

  it('renders an error without crashing', async () => {
    vi.mocked(api.getScheduleOutlook).mockRejectedValue(new Error('boom'));
    render(<ScheduleTab rosterIds={[1, 2]} onImported={() => {}} />);
    await userEvent.click(screen.getByRole('button', { name: /check schedule/i }));

    await waitFor(() => expect(screen.getByText('boom')).toBeInTheDocument());
  });
});
