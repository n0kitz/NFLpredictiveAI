import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ModelHub from './ModelHub';
import { api } from '../api/client';
import type { AccuracyStats, AccuracyDetail, ModelInfo, DataCoverage, ValuePickHistoryResponse } from '../api/types';

vi.mock('../api/client', () => ({
  api: {
    getAccuracy: vi.fn(),
    getAccuracyDetail: vi.fn(),
    getModelInfo: vi.fn(),
    getValuePicksHistory: vi.fn(),
    getDataCoverage: vi.fn(),
  },
}));

const accuracy: AccuracyStats = {
  seasons: [2024, 2025],
  total_games: 544,
  correct_predictions: 366,
  accuracy: 0.6728,
  by_confidence: {
    high: { total: 120, correct: 96, accuracy: 0.8 },
    medium: { total: 300, correct: 200, accuracy: 0.6667 },
    low: { total: 124, correct: 70, accuracy: 0.5645 },
  },
  calibration: {
    '50-55%': { total: 100, correct: 53 },
    '80%+': { total: 40, correct: 35 },
  },
  season_accuracy: {
    '2024': { total: 272, correct: 187, accuracy: 0.6875 },
    '2025': { total: 272, correct: 179, accuracy: 0.6581 },
  },
};

const detail: AccuracyDetail = {
  season: 2025,
  total_games: 272,
  correct_predictions: 179,
  accuracy: 0.6581,
  weekly: [
    { week: '1', total: 16, correct: 12, accuracy: 0.75 },
    { week: '2', total: 16, correct: 9, accuracy: 0.5625 },
  ],
  best_calls: [{
    game_id: 9001, week: '8', home_team: 'DEN', away_team: 'CAR',
    predicted_winner: 'Denver Broncos', actual_winner: 'Denver Broncos',
    winner_prob: 0.91, correct: true,
  }],
  biggest_misses: [{
    game_id: 9002, week: '2', home_team: 'PHI', away_team: 'ATL',
    predicted_winner: 'Philadelphia Eagles', actual_winner: 'Atlanta Falcons',
    winner_prob: 0.86, correct: false,
  }],
};

const modelInfo: ModelInfo = {
  model_type: 'weighted_sum', active_model: 'weighted_sum',
  ml_model_loaded: true, ml_available: true, ensemble_available: true,
  feature_count: 34, model_file_exists: true,
  ml_oos_accuracy: 0.668, weighted_sum_oos_accuracy: 0.672,
  ensemble_oos_accuracy: null, recommendation: null,
  spread_model_loaded: true, spread_model_mae: null, vegas_feature_removed: true,
  feature_importance: [
    { feature: 'home_turnover_margin', label: 'Home Turnover Margin', importance: 0.09 },
    { feature: 'away_turnover_margin', label: 'Away Turnover Margin', importance: 0.07 },
  ],
};

const picksEmpty: ValuePickHistoryResponse = {
  picks: [], total: 0, resolved: 0, correct: 0, hit_rate: null,
};

const picksWithData: ValuePickHistoryResponse = {
  picks: [{
    id: 1, predicted_at: '2026-01-01 12:00:00', home_abbr: 'KC', away_abbr: 'BUF',
    predicted_winner_abbr: 'KC', home_prob: 0.62, vegas_home_implied_prob: 0.55,
    edge: 0.07, edge_side: 'home', vegas_spread: -3.0, confidence: 'high',
    correct: true, actual_winner_abbr: 'KC',
  }],
  total: 1, resolved: 1, correct: 1, hit_rate: 1.0,
};

const coverage: DataCoverage = {
  tables: [
    { table: 'games', rows: 9455, season_min: 1990, season_max: 2025, last_updated: '2026-04-06', powers: 'Schedules, scores' },
    { table: 'game_odds', rows: 0, season_min: null, season_max: null, last_updated: null, powers: 'Betting lines' },
  ],
  generated_at: '2026-07-02 08:00:00',
};

function mockAll(picks: ValuePickHistoryResponse = picksEmpty) {
  vi.mocked(api.getAccuracy).mockResolvedValue(accuracy);
  vi.mocked(api.getAccuracyDetail).mockResolvedValue(detail);
  vi.mocked(api.getModelInfo).mockResolvedValue(modelInfo);
  vi.mocked(api.getValuePicksHistory).mockResolvedValue(picks);
  vi.mocked(api.getDataCoverage).mockResolvedValue(coverage);
}

describe('ModelHub', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders headline accuracy and confidence tiers', async () => {
    mockAll();
    render(<MemoryRouter><ModelHub /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText('67.3%')).toBeInTheDocument());
    expect(screen.getByText(/366\/544 games/)).toBeInTheDocument();
    expect(screen.getByText(/80.0% · 120 games/)).toBeInTheDocument();
  });

  it('links notable games to their game pages', async () => {
    mockAll();
    render(<MemoryRouter><ModelHub /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/CAR @ DEN/)).toBeInTheDocument());
    const links = screen.getAllByRole('link').filter((a) =>
      a.getAttribute('href')?.startsWith('/games/'));
    expect(links.map((l) => l.getAttribute('href'))).toEqual(
      expect.arrayContaining(['/games/9001', '/games/9002']),
    );
    expect(screen.getByText(/Atlanta Falcons won/)).toBeInTheDocument();
  });

  it('shows an empty state when no edge picks exist', async () => {
    mockAll(picksEmpty);
    render(<MemoryRouter><ModelHub /></MemoryRouter>);
    await waitFor(() =>
      expect(screen.getByText(/No edge picks recorded yet/)).toBeInTheDocument());
  });

  it('renders the edge picks track record when picks exist', async () => {
    mockAll(picksWithData);
    render(<MemoryRouter><ModelHub /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText('BUF @ KC')).toBeInTheDocument());
    expect(screen.getByText('HIT')).toBeInTheDocument();
    expect(screen.getByText('100%')).toBeInTheDocument();
  });

  it('renders feature importance bars and data coverage table', async () => {
    mockAll();
    render(<MemoryRouter><ModelHub /></MemoryRouter>);
    await waitFor(() =>
      expect(screen.getByText('Home Turnover Margin')).toBeInTheDocument());
    expect(screen.getByText('games')).toBeInTheDocument();
    expect(screen.getByText('9,455')).toBeInTheDocument();
    expect(screen.getByText('empty')).toBeInTheDocument();
  });
});
