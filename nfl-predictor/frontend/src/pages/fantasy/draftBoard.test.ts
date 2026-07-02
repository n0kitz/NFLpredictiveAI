import { describe, it, expect, beforeEach } from 'vitest';
import {
  teamForPick,
  draftReducer,
  initialDraftState,
  myRoster,
  picksUntilMine,
  positionalNeeds,
  tierBreakPositions,
  applyNeedBoost,
  loadDraftState,
  saveDraftState,
  type DraftState,
} from './draftBoard';
import type { DraftRanking } from '../../api/types';

const SETTINGS = {
  leagueSize: 10, mySlot: 3, rounds: 15,
  scoring: 'standard' as const,
  rosterSlots: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, K: 1, DST: 1, BN: 7 },
};

function started(): DraftState {
  return draftReducer(initialDraftState(), { type: 'SETUP', settings: SETTINGS });
}

function ranking(overrides: Partial<DraftRanking>): DraftRanking {
  return {
    player_id: 1, full_name: 'P', position: 'RB', team_abbr: 'KC',
    headshot_url: null, overall_rank: 1, position_rank: 1, tier: 1,
    adp: 1, projected_season_points: 200, season: 2026,
    scoring_format: 'standard', vbd: 100, boom_pct: null, bust_pct: null,
    ...overrides,
  } as DraftRanking;
}

describe('snake order', () => {
  it('round 1 goes in slot order', () => {
    expect(teamForPick(1, 10)).toBe(0);
    expect(teamForPick(10, 10)).toBe(9);
  });

  it('round 2 reverses', () => {
    expect(teamForPick(11, 10)).toBe(9);
    expect(teamForPick(20, 10)).toBe(0);
    expect(teamForPick(21, 10)).toBe(0); // round 3 forward again
  });

  it('works for 8 and 20 teams', () => {
    expect(teamForPick(8, 8)).toBe(7);
    expect(teamForPick(9, 8)).toBe(7);
    expect(teamForPick(20, 20)).toBe(19);
    expect(teamForPick(40, 20)).toBe(0);
  });
});

describe('draft reducer', () => {
  it('setup starts the draft', () => {
    const s = started();
    expect(s.started).toBe(true);
    expect(s.picks).toEqual([]);
  });

  it('picks assign the on-the-clock team', () => {
    let s = started();
    s = draftReducer(s, { type: 'PICK', playerId: 101 });
    s = draftReducer(s, { type: 'PICK', playerId: 102 });
    expect(s.picks[0]).toEqual({ overall: 1, teamIdx: 0, playerId: 101 });
    expect(s.picks[1]).toEqual({ overall: 2, teamIdx: 1, playerId: 102 });
  });

  it('undo removes the last pick', () => {
    let s = started();
    s = draftReducer(s, { type: 'PICK', playerId: 101 });
    s = draftReducer(s, { type: 'UNDO' });
    expect(s.picks).toEqual([]);
  });

  it('ignores duplicate players', () => {
    let s = started();
    s = draftReducer(s, { type: 'PICK', playerId: 101 });
    s = draftReducer(s, { type: 'PICK', playerId: 101 });
    expect(s.picks.length).toBe(1);
  });

  it('reset returns to initial state', () => {
    let s = started();
    s = draftReducer(s, { type: 'PICK', playerId: 101 });
    s = draftReducer(s, { type: 'RESET' });
    expect(s.started).toBe(false);
    expect(s.picks).toEqual([]);
  });

  it('stops at the end of the draft', () => {
    let s = draftReducer(initialDraftState(), {
      type: 'SETUP',
      settings: { ...SETTINGS, leagueSize: 8, rounds: 1 },
    });
    for (let i = 0; i < 10; i++) {
      s = draftReducer(s, { type: 'PICK', playerId: 200 + i });
    }
    expect(s.picks.length).toBe(8); // 8 teams × 1 round
  });
});

describe('my roster + clock', () => {
  it('myRoster returns only my picks', () => {
    let s = started(); // my slot 3 → teamIdx 2
    for (let i = 0; i < 12; i++) {
      s = draftReducer(s, { type: 'PICK', playerId: 300 + i });
    }
    expect(myRoster(s)).toEqual([302]); // pick 3 was mine
  });

  it('picksUntilMine counts down to my turn', () => {
    let s = started();
    expect(picksUntilMine(s)).toBe(2); // picks 1,2 then me at 3
    s = draftReducer(s, { type: 'PICK', playerId: 1 });
    expect(picksUntilMine(s)).toBe(1);
    s = draftReducer(s, { type: 'PICK', playerId: 2 });
    expect(picksUntilMine(s)).toBe(0); // I'm on the clock
  });
});

describe('positional needs', () => {
  it('full needs at draft start', () => {
    const needs = positionalNeeds([], SETTINGS.rosterSlots);
    expect(needs).toEqual({ QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, K: 1, DST: 1 });
  });

  it('primary slots fill before flex', () => {
    const needs = positionalNeeds(['RB', 'RB'], SETTINGS.rosterSlots);
    expect(needs.RB).toBe(0);
    expect(needs.FLEX).toBe(1);
  });

  it('third RB consumes flex', () => {
    const needs = positionalNeeds(['RB', 'RB', 'RB'], SETTINGS.rosterSlots);
    expect(needs.FLEX).toBe(0);
  });

  it('K never eats flex', () => {
    const needs = positionalNeeds(['K', 'K'], SETTINGS.rosterSlots);
    expect(needs.K).toBe(0);
    expect(needs.FLEX).toBe(1);
  });
});

describe('tier breaks + need boost', () => {
  it('flags positions with <=2 players left in the current tier', () => {
    const avail = [
      ranking({ player_id: 1, position: 'RB', tier: 1 }),
      ranking({ player_id: 2, position: 'RB', tier: 1 }),
      ranking({ player_id: 3, position: 'RB', tier: 2 }),
      ranking({ player_id: 4, position: 'WR', tier: 1 }),
      ranking({ player_id: 5, position: 'WR', tier: 1 }),
      ranking({ player_id: 6, position: 'WR', tier: 1 }),
    ];
    expect(tierBreakPositions(avail)).toEqual(['RB']);
  });

  it('need boost raises VBD for unfilled starter positions', () => {
    const avail = [
      ranking({ player_id: 1, position: 'RB', vbd: 100 }),
      ranking({ player_id: 2, position: 'QB', vbd: 100 }),
    ];
    const needs = { QB: 1, RB: 0, WR: 2, TE: 1, FLEX: 0, K: 1, DST: 1 };
    const boosted = applyNeedBoost(avail, needs);
    const qb = boosted.find((r) => r.position === 'QB')!;
    const rb = boosted.find((r) => r.position === 'RB')!;
    expect(qb.needScore).toBeGreaterThan(rb.needScore);
  });
});

describe('persistence', () => {
  beforeEach(() => localStorage.clear());

  it('round-trips draft state', () => {
    let s = started();
    s = draftReducer(s, { type: 'PICK', playerId: 42 });
    saveDraftState(s);
    expect(loadDraftState()).toEqual(s);
  });

  it('returns fresh state when nothing stored', () => {
    expect(loadDraftState().started).toBe(false);
  });
});
