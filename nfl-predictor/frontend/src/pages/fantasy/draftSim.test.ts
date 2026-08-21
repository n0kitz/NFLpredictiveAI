import { describe, it, expect } from 'vitest';
import type { DraftRanking } from '../../api/types';
import {
  makeRng,
  STRATEGIES,
  BOT_ARCHETYPES,
  strategyIds,
  assignBotArchetypes,
  bestStartingLineup,
  evaluateRoster,
  simulateDraft,
  runBatch,
  adpLooksSynthetic,
  type SimSettings,
} from './draftSim';

/**
 * Synthetic player pool: n per position, descending value.
 * Must comfortably exceed leagueSize * rounds (150) or the draft runs dry.
 */
function pool(): DraftRanking[] {
  const spec: Array<[string, number]> = [
    ['RB', 60], ['WR', 70], ['QB', 30], ['TE', 40], ['K', 20], ['DST', 20],
  ];
  const players: DraftRanking[] = [];
  let id = 1;
  for (const [position, count] of spec) {
    for (let i = 0; i < count; i++) {
      players.push({
        player_id: id,
        full_name: `${position}${i + 1}`,
        position,
        team_abbr: 'KC',
        headshot_url: null,
        overall_rank: id,
        position_rank: i + 1,
        tier: Math.floor(i / 4) + 1,
        adp: id,
        projected_season_points: 300 - i * 5,
        season: 2026,
        scoring_format: 'standard',
        vbd: 200 - i * 6,
        boom_pct: null,
        bust_pct: null,
      });
      id++;
    }
  }
  return players;
}

const SETTINGS: SimSettings = {
  leagueSize: 10,
  mySlot: 4,
  rounds: 15,
  scoring: 'standard',
  rosterSlots: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, K: 1, DST: 1, BN: 7 },
};

describe('makeRng', () => {
  it('is deterministic for a given seed', () => {
    const a = makeRng(42);
    const b = makeRng(42);
    const seqA = [a(), a(), a()];
    const seqB = [b(), b(), b()];
    expect(seqA).toEqual(seqB);
  });

  it('produces different sequences for different seeds', () => {
    expect(makeRng(1)()).not.toBe(makeRng(2)());
  });

  it('stays within [0, 1)', () => {
    const rng = makeRng(7);
    for (let i = 0; i < 200; i++) {
      const v = rng();
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(1);
    }
  });
});

describe('strategy registry', () => {
  it('exposes all eight strategies', () => {
    expect(strategyIds()).toHaveLength(8);
  });

  it('every strategy has a label and a pick function', () => {
    for (const id of strategyIds()) {
      expect(STRATEGIES[id].label).toBeTruthy();
      expect(typeof STRATEGIES[id].pick).toBe('function');
    }
  });

  it('every strategy returns a player that is actually available', () => {
    const available = pool();
    for (const id of strategyIds()) {
      const chosen = STRATEGIES[id].pick({
        available,
        myPicks: [],
        round: 1,
        settings: SETTINGS,
        rng: makeRng(1),
      });
      expect(available.some((p) => p.player_id === chosen)).toBe(true);
    }
  });
});

describe('positional strategy behaviour', () => {
  const available = pool();

  function firstPick(id: string, round = 1, myPicks: DraftRanking[] = []) {
    const chosen = STRATEGIES[id].pick({
      available, myPicks, round, settings: SETTINGS, rng: makeRng(3),
    });
    return available.find((p) => p.player_id === chosen)!;
  }

  it('zero-rb avoids running backs early', () => {
    expect(firstPick('zero-rb').position).not.toBe('RB');
  });

  it('robust-rb takes a running back first', () => {
    expect(firstPick('robust-rb').position).toBe('RB');
  });

  it('hero-rb takes an RB in round 1 but not in round 2', () => {
    expect(firstPick('hero-rb', 1).position).toBe('RB');
    const rb = available.find((p) => p.position === 'RB')!;
    expect(firstPick('hero-rb', 2, [rb]).position).not.toBe('RB');
  });

  it('late-qb refuses a quarterback before round 8', () => {
    for (const round of [1, 3, 7]) {
      expect(firstPick('late-qb', round).position).not.toBe('QB');
    }
  });

  it('best-available takes the highest VBD player', () => {
    const best = [...available].sort((a, b) => (b.vbd ?? 0) - (a.vbd ?? 0))[0];
    expect(firstPick('best-available').player_id).toBe(best.player_id);
  });
});

describe('bestStartingLineup', () => {
  const slots = { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, K: 1, DST: 1, BN: 7 };

  function player(position: string, points: number, id: number): DraftRanking {
    return { ...pool()[0], player_id: id, position, projected_season_points: points };
  }

  it('fills each starting slot once', () => {
    const roster = [
      player('QB', 300, 1), player('RB', 200, 2), player('RB', 190, 3),
      player('WR', 180, 4), player('WR', 170, 5), player('TE', 120, 6),
      player('K', 130, 7), player('DST', 110, 8), player('RB', 160, 9),
    ];
    const { starters } = bestStartingLineup(roster, slots);
    expect(starters).toHaveLength(9); // 8 primary slots + FLEX
  });

  it('puts the best eligible surplus player in FLEX', () => {
    const roster = [
      player('RB', 200, 1), player('RB', 190, 2),
      player('RB', 185, 3), player('WR', 100, 4),
    ];
    const { starters } = bestStartingLineup(roster, slots);
    expect(starters.some((s) => s.player_id === 3)).toBe(true);
  });

  it('does not count the same player twice', () => {
    const roster = [player('RB', 200, 1)];
    const { starters } = bestStartingLineup(roster, slots);
    const ids = starters.map((s) => s.player_id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('handles an empty roster without throwing', () => {
    expect(bestStartingLineup([], slots).points).toBe(0);
  });
});

describe('evaluateRoster', () => {
  it('scores a full roster above a thin one', () => {
    const strong = pool().slice(0, 9);
    const weak = pool().slice(0, 2);
    expect(evaluateRoster(strong, SETTINGS).starterPoints)
      .toBeGreaterThan(evaluateRoster(weak, SETTINGS).starterPoints);
  });

  it('reports which starting slots are unfilled', () => {
    const rbOnly = pool().filter((p) => p.position === 'RB').slice(0, 2);
    const { missing } = evaluateRoster(rbOnly, SETTINGS);
    expect(missing).toContain('QB');
    expect(missing).not.toContain('RB');
  });
});

describe('simulateDraft', () => {
  it('makes exactly leagueSize * rounds picks', () => {
    const result = simulateDraft(pool(), SETTINGS, 'best-available', makeRng(5));
    expect(result.allPicks).toHaveLength(SETTINGS.leagueSize * SETTINGS.rounds);
  });

  it('never drafts the same player twice', () => {
    const result = simulateDraft(pool(), SETTINGS, 'need-based', makeRng(9));
    const ids = result.allPicks.map((p) => p.playerId);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('gives me exactly `rounds` players', () => {
    const result = simulateDraft(pool(), SETTINGS, 'zero-rb', makeRng(11));
    expect(result.myRoster).toHaveLength(SETTINGS.rounds);
  });

  it('is reproducible for the same seed', () => {
    const a = simulateDraft(pool(), SETTINGS, 'hero-rb', makeRng(21));
    const b = simulateDraft(pool(), SETTINGS, 'hero-rb', makeRng(21));
    expect(a.myRoster.map((p) => p.player_id))
      .toEqual(b.myRoster.map((p) => p.player_id));
  });

  it('assigns my picks to my draft slot', () => {
    const result = simulateDraft(pool(), SETTINGS, 'best-available', makeRng(4));
    const myIdx = SETTINGS.mySlot - 1;
    const mine = result.allPicks.filter((p) => p.teamIdx === myIdx);
    expect(mine).toHaveLength(SETTINGS.rounds);
  });

  it('fills my mandatory starting slots by the end of the draft', () => {
    const result = simulateDraft(pool(), SETTINGS, 'zero-rb', makeRng(13));
    expect(evaluateRoster(result.myRoster, SETTINGS).missing).toEqual([]);
  });
});

describe('positional saturation', () => {
  // Regression: without a cap, raw VBD said QB1 and QB8 were equally good picks
  // and "best available" finished a draft holding eight quarterbacks.
  it('never hoards quarterbacks', () => {
    for (const id of strategyIds()) {
      const result = simulateDraft(pool(), SETTINGS, id, makeRng(17));
      const qbs = result.myRoster.filter((p) => p.position === 'QB').length;
      expect(qbs, `${id} drafted ${qbs} QBs`).toBeLessThanOrEqual(2);
    }
  });

  it('never drafts more than one kicker or defense', () => {
    for (const id of strategyIds()) {
      const { byPosition } = evaluateRoster(
        simulateDraft(pool(), SETTINGS, id, makeRng(23)).myRoster,
        SETTINGS,
      );
      expect(byPosition.K ?? 0, `${id} kickers`).toBeLessThanOrEqual(1);
      expect(byPosition.DST ?? 0, `${id} defenses`).toBeLessThanOrEqual(1);
    }
  });

  it('produces a legal lineup for every strategy', () => {
    for (const id of strategyIds()) {
      const result = simulateDraft(pool(), SETTINGS, id, makeRng(31));
      expect(evaluateRoster(result.myRoster, SETTINGS).missing, id).toEqual([]);
    }
  });
});

describe('bot archetypes', () => {
  it('assigns an archetype to every opponent but not to me', () => {
    const bots = assignBotArchetypes(SETTINGS, makeRng(2));
    expect(Object.keys(bots)).toHaveLength(SETTINGS.leagueSize - 1);
    expect(bots[SETTINGS.mySlot - 1]).toBeUndefined();
  });

  it('only uses known archetypes', () => {
    const bots = assignBotArchetypes(SETTINGS, makeRng(6));
    for (const name of Object.values(bots)) {
      expect(BOT_ARCHETYPES[name]).toBeDefined();
    }
  });
});

describe('runBatch', () => {
  it('returns one row per strategy, sorted best first', () => {
    const rows = runBatch(pool(), SETTINGS, ['best-available', 'zero-rb'], 5, 1);
    expect(rows).toHaveLength(2);
    expect(rows[0].avgPoints).toBeGreaterThanOrEqual(rows[1].avgPoints);
  });

  it('win rates across the compared strategies sum to ~100%', () => {
    const rows = runBatch(pool(), SETTINGS, ['best-available', 'zero-rb', 'robust-rb'], 6, 3);
    const total = rows.reduce((sum, r) => sum + r.winPct, 0);
    expect(total).toBeCloseTo(100, 0);
  });

  it('reports best and worst outcomes per strategy', () => {
    const [row] = runBatch(pool(), SETTINGS, ['need-based'], 4, 8);
    expect(row.best).toBeGreaterThanOrEqual(row.avgPoints);
    expect(row.worst).toBeLessThanOrEqual(row.avgPoints);
    expect(row.sims).toBe(4);
  });

  it('is reproducible for the same seed', () => {
    const a = runBatch(pool(), SETTINGS, ['best-available', 'late-qb'], 4, 77);
    const b = runBatch(pool(), SETTINGS, ['best-available', 'late-qb'], 4, 77);
    expect(a.map((r) => r.avgPoints)).toEqual(b.map((r) => r.avgPoints));
  });
});

describe('adpLooksSynthetic', () => {
  it('flags a board whose ADP is just the rank', () => {
    expect(adpLooksSynthetic(pool())).toBe(true);
  });

  it('accepts a board with real market ADP', () => {
    const real = pool().map((p, i) => ({ ...p, adp: p.overall_rank + ((i % 7) - 3) * 4 }));
    expect(adpLooksSynthetic(real)).toBe(false);
  });

  it('is false for an empty board', () => {
    expect(adpLooksSynthetic([])).toBe(false);
  });
});
