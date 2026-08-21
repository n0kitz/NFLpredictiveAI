import { describe, it, expect } from 'vitest';
import {
  currentNflSeason,
  lastCompletedSeason,
  activeSeason,
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

describe('activeSeason', () => {
  // The season being drafted for / played. Unlike UPCOMING_SEASON this must NOT
  // jump forward the moment September arrives — in Oct 2026 the season you are
  // playing is 2026, not 2027.
  it('is the upcoming season during the offseason', () => {
    expect(activeSeason(new Date('2026-08-21'))).toBe(2026);
    expect(activeSeason(new Date('2026-02-20'))).toBe(2026);
  });

  it('stays on the running season once it kicks off', () => {
    expect(activeSeason(new Date('2026-10-01'))).toBe(2026);
    expect(activeSeason(new Date('2027-01-05'))).toBe(2026);
  });

  it('is always lastCompletedSeason + 1', () => {
    for (const d of ['2026-01-15', '2026-05-15', '2026-09-15', '2027-02-15']) {
      const now = new Date(d);
      expect(activeSeason(now)).toBe(lastCompletedSeason(now) + 1);
    }
  });
});

describe('lastCompletedSeason', () => {
  // In the offseason the season labelled CURRENT_SEASON has already finished,
  // so "last completed" is that season itself — not one behind it. Getting this
  // wrong served two-year-old stats on the fantasy tabs during draft prep.
  it('is the current label during the offseason (Feb–Aug)', () => {
    expect(lastCompletedSeason(new Date('2026-08-20'))).toBe(2025);
    expect(lastCompletedSeason(new Date('2026-02-20'))).toBe(2025);
    expect(lastCompletedSeason(new Date('2026-06-01'))).toBe(2025);
  });

  it('is one behind while a season is in progress (Sep–Jan)', () => {
    expect(lastCompletedSeason(new Date('2026-09-15'))).toBe(2025);
    expect(lastCompletedSeason(new Date('2026-12-01'))).toBe(2025);
    // January = playoffs of the 2026 season, which is not finished yet.
    expect(lastCompletedSeason(new Date('2027-01-05'))).toBe(2025);
  });

  it('rolls forward once the season ends', () => {
    expect(lastCompletedSeason(new Date('2027-02-20'))).toBe(2026);
  });

  it('never points at a season that has not started', () => {
    for (const d of ['2026-08-20', '2026-09-15', '2027-01-05', '2027-02-20']) {
      const now = new Date(d);
      expect(lastCompletedSeason(now)).toBeLessThanOrEqual(currentNflSeason(now));
    }
  });
});

describe('derived season constants', () => {
  it('last completed season matches the date-aware helper', () => {
    expect(LAST_COMPLETED_SEASON).toBe(lastCompletedSeason());
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
