// Live draft board logic: snake order, pick tracking, positional needs,
// tier-break alerts and need-weighted suggestions. Pure functions + reducer —
// no React, no network — so the whole draft flow is unit-testable.
// State persists in localStorage so a page refresh mid-draft loses nothing.

import type { DraftRanking } from '../../api/types';
import type { Scoring } from './leagueSettings';

export interface DraftSettings {
  leagueSize: number;
  mySlot: number; // 1-based draft slot
  rounds: number;
  scoring: Scoring;
  rosterSlots: Record<string, number>;
}

export interface DraftPick {
  overall: number; // 1-based overall pick number
  teamIdx: number; // 0-based team index
  playerId: number;
}

export interface DraftState {
  settings: DraftSettings;
  picks: DraftPick[];
  started: boolean;
}

export type DraftAction =
  | { type: 'SETUP'; settings: DraftSettings }
  | { type: 'PICK'; playerId: number }
  | { type: 'UNDO' }
  | { type: 'RESET' };

const STORAGE_KEY = 'nfl-predictor.draftBoard.v1';

// Positions that never absorb a FLEX slot
const FLEX_ELIGIBLE = new Set(['RB', 'WR', 'TE']);

// VBD multiplier for positions where a starter slot is still open
const NEED_BOOST = 1.15;

export function initialDraftState(): DraftState {
  return {
    settings: {
      leagueSize: 10, mySlot: 1, rounds: 15,
      scoring: 'standard',
      rosterSlots: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, K: 1, DST: 1, BN: 7 },
    },
    picks: [],
    started: false,
  };
}

/** 0-based team index on the clock for a 1-based overall pick (snake order). */
export function teamForPick(overall: number, leagueSize: number): number {
  const round = Math.floor((overall - 1) / leagueSize);
  const idx = (overall - 1) % leagueSize;
  return round % 2 === 0 ? idx : leagueSize - 1 - idx;
}

export function draftReducer(state: DraftState, action: DraftAction): DraftState {
  switch (action.type) {
    case 'SETUP':
      return { settings: action.settings, picks: [], started: true };
    case 'PICK': {
      if (!state.started) return state;
      const total = state.settings.leagueSize * state.settings.rounds;
      if (state.picks.length >= total) return state;
      if (state.picks.some((p) => p.playerId === action.playerId)) return state;
      const overall = state.picks.length + 1;
      return {
        ...state,
        picks: [...state.picks, {
          overall,
          teamIdx: teamForPick(overall, state.settings.leagueSize),
          playerId: action.playerId,
        }],
      };
    }
    case 'UNDO':
      return { ...state, picks: state.picks.slice(0, -1) };
    case 'RESET':
      return initialDraftState();
    default:
      return state;
  }
}

export function myTeamIdx(state: DraftState): number {
  return state.settings.mySlot - 1;
}

export function myRoster(state: DraftState): number[] {
  const mine = myTeamIdx(state);
  return state.picks.filter((p) => p.teamIdx === mine).map((p) => p.playerId);
}

/** Picks remaining before my next turn. 0 = I'm on the clock. */
export function picksUntilMine(state: DraftState): number {
  const mine = myTeamIdx(state);
  const total = state.settings.leagueSize * state.settings.rounds;
  for (let overall = state.picks.length + 1; overall <= total; overall++) {
    if (teamForPick(overall, state.settings.leagueSize) === mine) {
      return overall - state.picks.length - 1;
    }
  }
  return Infinity;
}

/**
 * Remaining starter needs given the positions already on my roster.
 * Primary slots fill first; surplus RB/WR/TE then consumes FLEX.
 */
export function positionalNeeds(
  myPositions: string[],
  rosterSlots: Record<string, number>,
): Record<string, number> {
  const needs: Record<string, number> = {};
  for (const [slot, count] of Object.entries(rosterSlots)) {
    if (slot !== 'BN') needs[slot] = count;
  }
  let flexUsed = 0;
  const counts: Record<string, number> = {};
  for (const pos of myPositions) {
    counts[pos] = (counts[pos] || 0) + 1;
  }
  for (const [pos, count] of Object.entries(counts)) {
    const starters = rosterSlots[pos] || 0;
    needs[pos] = Math.max(0, starters - count);
    const surplus = Math.max(0, count - starters);
    if (FLEX_ELIGIBLE.has(pos)) flexUsed += surplus;
  }
  if ('FLEX' in needs) {
    needs.FLEX = Math.max(0, (rosterSlots.FLEX || 0) - flexUsed);
  }
  return needs;
}

/** Positions with ≤2 players left in their current best tier — draft-now alerts. */
export function tierBreakPositions(available: DraftRanking[]): string[] {
  const byPos: Record<string, DraftRanking[]> = {};
  for (const r of available) {
    if (!r.position) continue;
    (byPos[r.position] ||= []).push(r);
  }
  const breaks: string[] = [];
  for (const [pos, rows] of Object.entries(byPos)) {
    const bestTier = Math.min(...rows.map((r) => r.tier));
    const inTier = rows.filter((r) => r.tier === bestTier).length;
    const hasLater = rows.some((r) => r.tier > bestTier);
    if (inTier <= 2 && hasLater) breaks.push(pos);
  }
  return breaks.sort();
}

export type SuggestedRanking = DraftRanking & { needScore: number };

/** Rank available players by VBD, boosted where I still need a starter. */
export function applyNeedBoost(
  available: DraftRanking[],
  needs: Record<string, number>,
): SuggestedRanking[] {
  return available
    .map((r) => {
      const base = r.vbd ?? 0;
      const posNeed = (r.position && needs[r.position]) || 0;
      const flexNeed = r.position && FLEX_ELIGIBLE.has(r.position)
        ? needs.FLEX || 0 : 0;
      const boost = posNeed > 0 || flexNeed > 0 ? NEED_BOOST : 1.0;
      return { ...r, needScore: Math.round(base * boost * 10) / 10 };
    })
    .sort((a, b) => b.needScore - a.needScore);
}

// ── Persistence ──────────────────────────────────────────────────────────────

export function saveDraftState(state: DraftState): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

export function loadDraftState(): DraftState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return initialDraftState();
    const parsed = JSON.parse(raw) as DraftState;
    if (!parsed || !Array.isArray(parsed.picks) || !parsed.settings) {
      return initialDraftState();
    }
    return parsed;
  } catch {
    return initialDraftState();
  }
}

export function clearDraftState(): void {
  localStorage.removeItem(STORAGE_KEY);
}
