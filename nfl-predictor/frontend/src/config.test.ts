import { describe, it, expect } from 'vitest';
import {
  currentNflSeason,
  CURRENT_SEASON,
  LAST_COMPLETED_SEASON,
  FIRST_SEASON,
  SEASON_COUNT,
  SEASON_RANGE_LABEL,
  ACCURACY_SEASONS,
  ALL_SEASONS,
  recentSeasons,
} from './config';

describe('currentNflSeason', () => {
  it('returns the start year during Sep–Dec', () => {
    expect(currentNflSeason(new Date('2025-09-10'))).toBe(2025);
    expect(currentNflSeason(new Date('2025-12-31'))).toBe(2025);
  });

  it('returns the previous year during Jan–Aug', () => {
    expect(currentNflSeason(new Date('2026-01-05'))).toBe(2025);
    expect(currentNflSeason(new Date('2026-06-15'))).toBe(2025);
    expect(currentNflSeason(new Date('2026-08-31'))).toBe(2025);
  });
});

describe('derived season constants', () => {
  it('last completed season is one behind current', () => {
    expect(LAST_COMPLETED_SEASON).toBe(CURRENT_SEASON - 1);
  });

  it('season count and range label are consistent', () => {
    expect(SEASON_COUNT).toBe(CURRENT_SEASON - FIRST_SEASON + 1);
    expect(SEASON_RANGE_LABEL).toBe(`${FIRST_SEASON}–${CURRENT_SEASON}`);
  });

  it('accuracy seasons are the last two', () => {
    expect(ACCURACY_SEASONS).toBe(`${CURRENT_SEASON - 1},${CURRENT_SEASON}`);
  });

  it('ALL_SEASONS spans first..current, newest first', () => {
    expect(ALL_SEASONS[0]).toBe(CURRENT_SEASON);
    expect(ALL_SEASONS[ALL_SEASONS.length - 1]).toBe(FIRST_SEASON);
    expect(ALL_SEASONS).toHaveLength(SEASON_COUNT);
  });

  it('recentSeasons returns N newest seasons descending', () => {
    expect(recentSeasons(3)).toEqual([
      CURRENT_SEASON, CURRENT_SEASON - 1, CURRENT_SEASON - 2,
    ]);
  });
});
