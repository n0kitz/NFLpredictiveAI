import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import History from './History';
import { api } from '../api/client';
import type { PredictionHistory, PredictionHistoryItem } from '../api/types';

vi.mock('../api/client', () => ({
  api: { getPredictionHistory: vi.fn() },
}));

const item = (over: Partial<PredictionHistoryItem> = {}): PredictionHistoryItem => ({
  id: 1, home_abbr: 'KC', away_abbr: 'PHI', home_team: 'Kansas City Chiefs',
  away_team: 'Philadelphia Eagles', predicted_winner_abbr: 'KC',
  home_prob: 0.6, away_prob: 0.4, confidence: 'medium',
  predicted_at: '2026-04-09 10:14:52', actual_winner_abbr: 'KC',
  correct: true, game_id: 9199,
  ...over,
});

const payload = (items: PredictionHistoryItem[]): PredictionHistory => ({
  predictions: items, total: items.length, resolved: items.length,
  correct: items.filter((i) => i.correct).length, accuracy: 0.5,
});

describe('History', () => {
  beforeEach(() => vi.clearAllMocks());

  it('links resolved predictions to their game detail page', async () => {
    vi.mocked(api.getPredictionHistory).mockResolvedValue(payload([item()]));
    render(<MemoryRouter><History /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/CORRECT/)).toBeInTheDocument());
    const link = screen.getByTitle('View game detail');
    expect(link).toHaveAttribute('href', '/games/9199');
  });

  it('renders a plain badge when no game is linked', async () => {
    vi.mocked(api.getPredictionHistory).mockResolvedValue(
      payload([item({ correct: false, game_id: null, actual_winner_abbr: 'PHI' })]),
    );
    render(<MemoryRouter><History /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText('WRONG')).toBeInTheDocument());
    expect(screen.queryByTitle('View game detail')).not.toBeInTheDocument();
  });
});
