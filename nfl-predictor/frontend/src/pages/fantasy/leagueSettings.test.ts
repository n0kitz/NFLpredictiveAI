import { describe, it, expect, beforeEach } from 'vitest';
import {
  DEFAULT_LEAGUE_SETTINGS,
  loadLeagueSettings,
  saveLeagueSettings,
  NFL_DEFAULT_SLOTS,
} from './leagueSettings';
import { POSITIONS, posColor } from './helpers';

describe('league settings persistence', () => {
  beforeEach(() => localStorage.clear());

  it('defaults to NFL.com standard, 10 teams', () => {
    const s = loadLeagueSettings();
    expect(s.scoring).toBe('standard');
    expect(s.leagueSize).toBe(10);
  });

  it('round-trips through localStorage', () => {
    saveLeagueSettings({ scoring: 'half_ppr', leagueSize: 12 });
    expect(loadLeagueSettings()).toEqual({ scoring: 'half_ppr', leagueSize: 12 });
  });

  it('ignores corrupt stored values', () => {
    localStorage.setItem('nfl-predictor.leagueSettings', '{nonsense');
    expect(loadLeagueSettings()).toEqual(DEFAULT_LEAGUE_SETTINGS);
  });

  it('clamps out-of-range league size', () => {
    saveLeagueSettings({ scoring: 'standard', leagueSize: 99 });
    expect(loadLeagueSettings().leagueSize).toBe(10);
  });

  it('default slots include K, DST and bench', () => {
    expect(NFL_DEFAULT_SLOTS.K).toBe(1);
    expect(NFL_DEFAULT_SLOTS.DST).toBe(1);
    expect(NFL_DEFAULT_SLOTS.BN).toBe(7);
  });
});

describe('DST position support', () => {
  it('POSITIONS filter includes DST', () => {
    expect(POSITIONS).toContain('DST');
  });

  it('posColor has a DST colour', () => {
    expect(posColor('DST')).not.toBe('#888');
  });
});
