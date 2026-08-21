/**
 * Centralized season configuration — single source of truth for year values.
 *
 * Replaces hardcoded 2024/2025 literals scattered across the app so the UI rolls
 * forward automatically instead of going stale each NFL season.
 *
 * NFL season labelling: a season runs Sep–early Feb and is named for the year it
 * starts in. So Jan–Aug belongs to the *previous* season label.
 */

export const FIRST_SEASON = 1990;

/** The current NFL season label, derived from today's date. */
export function currentNflSeason(now: Date = new Date()): number {
  const year = now.getFullYear();
  const month = now.getMonth(); // 0 = Jan … 8 = Sep
  return month >= 8 ? year : year - 1;
}

/** Current season (upcoming games, schedule, live accuracy). */
export const CURRENT_SEASON = currentNflSeason();

/**
 * Last season with complete played data — used for fantasy leaderboards, waiver
 * ranks, power rankings and trade values, which all need a fully-played season.
 *
 * This is NOT simply `CURRENT_SEASON - 1`. During the offseason (Feb–Aug) the
 * season labelled `CURRENT_SEASON` has already finished, so it *is* the last
 * completed one; only while a season is running (Sep–Jan, January being its
 * playoffs) does the completed season sit one label behind.
 */
export function lastCompletedSeason(now: Date = new Date()): number {
  const season = currentNflSeason(now);
  const month = now.getMonth(); // 0 = Jan … 8 = Sep
  const seasonInProgress = month >= 8 || month === 0; // Sep–Dec, plus Jan playoffs
  return seasonInProgress ? season - 1 : season;
}

export const LAST_COMPLETED_SEASON = lastCompletedSeason();

/**
 * The season being drafted for. During the offseason (Feb–Aug) fantasy drafts
 * target the *next* season label, i.e. CURRENT_SEASON + 1.
 */
export const UPCOMING_SEASON = CURRENT_SEASON + 1;

/**
 * The season actually being drafted for or played — `lastCompletedSeason() + 1`.
 *
 * Differs from `UPCOMING_SEASON` on purpose: that one rolls to the *following*
 * year the moment September arrives, which is right for draft prep in the
 * offseason but wrong once the season kicks off. Use `ACTIVE_SEASON` for
 * rosters, weekly projections and lineup advice; mirrors `ACTIVE_SEASON` in
 * the backend `src/config.py`.
 */
export function activeSeason(now: Date = new Date()): number {
  return lastCompletedSeason(now) + 1;
}

export const ACTIVE_SEASON = activeSeason();

export const SEASON_COUNT = CURRENT_SEASON - FIRST_SEASON + 1;

/** e.g. "1990–2025" */
export const SEASON_RANGE_LABEL = `${FIRST_SEASON}–${CURRENT_SEASON}`;

/** Comma-separated recent seasons for backtest accuracy (last two). */
export const ACCURACY_SEASONS = `${CURRENT_SEASON - 1},${CURRENT_SEASON}`;

/** All seasons, newest first — for dropdowns. */
export const ALL_SEASONS: number[] = Array.from(
  { length: SEASON_COUNT },
  (_, i) => CURRENT_SEASON - i,
);

/** Recent N seasons, newest first — for compact selectors. */
export function recentSeasons(n: number): number[] {
  return Array.from({ length: n }, (_, i) => CURRENT_SEASON - i);
}
