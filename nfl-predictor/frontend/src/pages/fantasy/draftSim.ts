// Draft simulator: run mock drafts against bot opponents to find out which
// drafting strategy actually wins from your slot, in your league's settings.
//
// Pure functions only — no React, no network — so the whole thing is unit
// testable and can run a few hundred drafts synchronously in the browser.
// Snake order and positional-need logic are shared with the live draft board
// (draftBoard.ts) so the simulator and the real thing can't drift apart.

import type { DraftRanking } from '../../api/types';
import type { Scoring } from './leagueSettings';
import { teamForPick, positionalNeeds } from './draftBoard';

export interface SimSettings {
  leagueSize: number;
  mySlot: number; // 1-based draft slot
  rounds: number;
  scoring: Scoring;
  rosterSlots: Record<string, number>;
}

export interface SimPick {
  overall: number;
  teamIdx: number;
  playerId: number;
}

export interface SimResult {
  allPicks: SimPick[];
  myRoster: DraftRanking[];
}

export interface StrategyContext {
  available: DraftRanking[];
  myPicks: DraftRanking[];
  round: number;
  settings: SimSettings;
  rng: Rng;
}

export interface Strategy {
  label: string;
  description: string;
  pick: (ctx: StrategyContext) => number;
}

export type Rng = () => number;

const FLEX_ELIGIBLE = new Set(['RB', 'WR', 'TE']);
const EMPTY_SET: ReadonlySet<string> = new Set();

// ── Deterministic RNG ────────────────────────────────────────────────────────

/**
 * Seeded pseudo-random generator (mulberry32).
 *
 * Simulation results have to be reproducible: a strategy comparison that
 * shuffles differently on every render is impossible to trust or to test.
 */
export function makeRng(seed: number): Rng {
  let a = seed >>> 0;
  return function rng(): number {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ── Roster helpers ───────────────────────────────────────────────────────────

const value = (p: DraftRanking): number => p.vbd ?? p.projected_season_points ?? 0;
const points = (p: DraftRanking): number => p.projected_season_points ?? 0;

/** Starting slots that must be filled, in fill order (FLEX last — it soaks up surplus). */
function startingSlots(rosterSlots: Record<string, number>): string[] {
  return Object.keys(rosterSlots).filter((s) => s !== 'BN' && s !== 'FLEX');
}

export interface Lineup {
  starters: DraftRanking[];
  points: number;
  missing: string[];
}

/**
 * Greedily fill the starting lineup with the highest-scoring eligible players.
 *
 * Primary slots first, then FLEX from whatever RB/WR/TE is left over — the same
 * order a real lineup is set in, and good enough that a stronger roster always
 * scores higher than a weaker one.
 */
export function bestStartingLineup(
  roster: DraftRanking[],
  rosterSlots: Record<string, number>,
): Lineup {
  const pool = [...roster].sort((a, b) => points(b) - points(a));
  const used = new Set<number>();
  const starters: DraftRanking[] = [];
  const missing: string[] = [];

  for (const slot of startingSlots(rosterSlots)) {
    for (let i = 0; i < (rosterSlots[slot] || 0); i++) {
      const pick = pool.find((p) => p.position === slot && !used.has(p.player_id));
      if (pick) {
        used.add(pick.player_id);
        starters.push(pick);
      } else {
        missing.push(slot);
      }
    }
  }

  for (let i = 0; i < (rosterSlots.FLEX || 0); i++) {
    const pick = pool.find(
      (p) => p.position && FLEX_ELIGIBLE.has(p.position) && !used.has(p.player_id),
    );
    if (pick) {
      used.add(pick.player_id);
      starters.push(pick);
    } else {
      missing.push('FLEX');
    }
  }

  return {
    starters,
    points: Math.round(starters.reduce((sum, p) => sum + points(p), 0) * 10) / 10,
    missing,
  };
}

export interface RosterEvaluation {
  starterPoints: number;
  benchPoints: number;
  starters: DraftRanking[];
  missing: string[];
  byPosition: Record<string, number>;
}

/** Score a finished roster by the points its best legal starting lineup produces. */
export function evaluateRoster(
  roster: DraftRanking[],
  settings: SimSettings,
): RosterEvaluation {
  const { starters, points: starterPoints, missing } = bestStartingLineup(
    roster,
    settings.rosterSlots,
  );
  const starterIds = new Set(starters.map((p) => p.player_id));
  const benchPoints =
    Math.round(
      roster.filter((p) => !starterIds.has(p.player_id)).reduce((s, p) => s + points(p), 0) * 10,
    ) / 10;

  const byPosition: Record<string, number> = {};
  for (const p of roster) {
    if (p.position) byPosition[p.position] = (byPosition[p.position] || 0) + 1;
  }

  return { starterPoints, benchPoints, starters, missing, byPosition };
}

// ── Legality: never end the draft with an empty mandatory slot ───────────────

/** Rounds left for me after this one. */
function picksRemaining(round: number, settings: SimSettings): number {
  return settings.rounds - round;
}

/**
 * Slots I still must fill, ordered by scarcity of my remaining picks.
 *
 * Once the number of unfilled mandatory slots equals the picks I have left, the
 * strategy loses its freedom — otherwise a Zero-RB run happily ends with no
 * kicker and an illegal lineup.
 */
function forcedPositions(
  myPicks: DraftRanking[],
  round: number,
  settings: SimSettings,
): string[] {
  const needs = positionalNeeds(
    myPicks.map((p) => p.position || ''),
    settings.rosterSlots,
  );
  const open: string[] = [];
  for (const [slot, count] of Object.entries(needs)) {
    if (slot === 'FLEX') continue;
    for (let i = 0; i < count; i++) open.push(slot);
  }
  return open.length >= picksRemaining(round, settings) + 1 ? open : [];
}

/**
 * How many players at a position are worth owning, given the roster shape.
 *
 * Without this a "best available" run happily ends with eight quarterbacks:
 * raw VBD says QB1 and QB8 are both fine picks, but only one can start. Backups
 * are worth a bench spot at most, and a second kicker is worth nothing.
 */
function positionCap(position: string, rosterSlots: Record<string, number>): number {
  const starters = rosterSlots[position] || 0;
  if (position === 'K' || position === 'DST') return Math.max(1, starters);
  if (FLEX_ELIGIBLE.has(position)) {
    return starters + (rosterSlots.FLEX || 0) + 2; // room for real bench depth
  }
  return starters + 1; // one backup (QB)
}

/** Positions I already own enough of — excluded outright, not merely discounted.
 *
 * A soft multiplier is not enough: late in a draft every position is capped, so
 * a shared penalty cancels out and the raw-VBD leader (a third quarterback)
 * wins again. Removing them from consideration is the only stable rule.
 */
function saturatedPositions(
  myPicks: DraftRanking[],
  rosterSlots: Record<string, number>,
): Set<string> {
  const counts: Record<string, number> = {};
  for (const p of myPicks) {
    if (p.position) counts[p.position] = (counts[p.position] || 0) + 1;
  }
  const full = new Set<string>();
  for (const [position, have] of Object.entries(counts)) {
    if (have >= positionCap(position, rosterSlots)) full.add(position);
  }
  return full;
}

/** Best available player restricted to `positions` (falls back to the whole pool). */
function bestAt(available: DraftRanking[], positions: string[]): DraftRanking | undefined {
  const eligible = positions.length
    ? available.filter((p) => p.position && positions.includes(p.position))
    : available;
  const from = eligible.length ? eligible : available;
  return from.reduce<DraftRanking | undefined>(
    (best, p) => (!best || value(p) > value(best) ? p : best),
    undefined,
  );
}

/**
 * Wrap a strategy so it can never produce an illegal roster.
 *
 * When the remaining picks are exactly enough to fill the mandatory slots, the
 * choice is overridden with the best player at a still-empty slot.
 */
function withLegality(
  choose: (ctx: StrategyContext) => number,
): (ctx: StrategyContext) => number {
  return (ctx) => {
    const forced = forcedPositions(ctx.myPicks, ctx.round, ctx.settings);
    if (forced.length) {
      const pick = bestAt(ctx.available, forced);
      if (pick) return pick.player_id;
    }
    return choose(ctx);
  };
}

/**
 * Best available by roster-aware value, optionally excluding positions.
 * Falls back to the whole pool if the exclusions leave nothing.
 */
function bestExcluding(
  available: DraftRanking[],
  banned: Set<string>,
  myPicks: DraftRanking[] = [],
  settings?: SimSettings,
): DraftRanking {
  const full = settings
    ? saturatedPositions(myPicks, settings.rosterSlots)
    : EMPTY_SET;

  // One pass, three tiers of preference. A strategy ban is a preference;
  // saturation is nearly a rule; the raw pool is the last resort. Computing the
  // saturated set once per pick (rather than per comparison) is what keeps a
  // few hundred simulated drafts fast enough to run in a click.
  let best: DraftRanking | undefined;
  let bestScore = -Infinity;
  let relaxed: DraftRanking | undefined;
  let relaxedScore = -Infinity;

  for (const p of available) {
    const pos = p.position;
    const isSaturated = !!pos && full.has(pos);
    const isBanned = isSaturated || (!!pos && banned.has(pos));
    const v = value(p);
    if (!isBanned) {
      if (v > bestScore) { bestScore = v; best = p; }
    } else if (!isSaturated && v > relaxedScore) {
      relaxedScore = v;
      relaxed = p;
    }
  }
  return best ?? relaxed ?? available[0];
}

// ── Strategies ───────────────────────────────────────────────────────────────

/** Positions you should essentially never spend an early pick on. */
const LATE_ONLY = new Set(['K', 'DST']);

/** How many of the best remaining players count as "available at this pick". */
const ADP_WINDOW = 20;

function earlyBan(round: number, extra: string[] = []): Set<string> {
  // K and DST are a waste of any pick before the last few rounds.
  const banned = new Set(extra);
  if (round <= 12) for (const p of LATE_ONLY) banned.add(p);
  return banned;
}

export const STRATEGIES: Record<string, Strategy> = {
  'best-available': {
    label: 'Best Available',
    description: 'Always take the highest VBD player left. Ignores roster shape entirely.',
    pick: withLegality(({ available, myPicks, round, settings }) =>
      bestExcluding(available, earlyBan(round), myPicks, settings).player_id,
    ),
  },

  'need-based': {
    label: 'Need-Based',
    description:
      'VBD boosted 15% for positions where a starting slot is still open — the live board’s own suggestion logic.',
    pick: withLegality(({ available, myPicks, round, settings }) => {
      const needs = positionalNeeds(
        myPicks.map((p) => p.position || ''),
        settings.rosterSlots,
      );
      const banned = earlyBan(round);
      for (const pos of saturatedPositions(myPicks, settings.rosterSlots)) banned.add(pos);
      const allowed = available.filter((p) => !p.position || !banned.has(p.position));
      const from = allowed.length ? allowed : available;
      let best = from[0];
      let bestScore = -Infinity;
      for (const p of from) {
        const posNeed = (p.position && needs[p.position]) || 0;
        const flexNeed = p.position && FLEX_ELIGIBLE.has(p.position) ? needs.FLEX || 0 : 0;
        const score = value(p) * (posNeed > 0 || flexNeed > 0 ? 1.15 : 1.0);
        if (score > bestScore) {
          bestScore = score;
          best = p;
        }
      }
      return best.player_id;
    }),
  },

  'zero-rb': {
    label: 'Zero-RB',
    description: 'No running backs in rounds 1–4; load up on WR/TE early and mine RB value later.',
    pick: withLegality(({ available, myPicks, round, settings }) =>
      bestExcluding(available, earlyBan(round, round <= 4 ? ['RB'] : []), myPicks, settings)
        .player_id,
    ),
  },

  'robust-rb': {
    label: 'Robust-RB',
    description: 'Running backs with the first three picks, then best available.',
    pick: withLegality(({ available, myPicks, round, settings }) => {
      if (round <= 3) {
        const rbs = available.filter((p) => p.position === 'RB');
        if (rbs.length) return bestAt(rbs, [])!.player_id;
      }
      return bestExcluding(available, earlyBan(round), myPicks, settings).player_id;
    }),
  },

  'hero-rb': {
    label: 'Hero-RB',
    description: 'One elite RB in round 1, then no RB until round 5 — pair a workhorse with a deep WR corps.',
    pick: withLegality(({ available, myPicks, round, settings }) => {
      if (round === 1) {
        const rbs = available.filter((p) => p.position === 'RB');
        if (rbs.length) return bestAt(rbs, [])!.player_id;
      }
      const banned = earlyBan(round, round >= 2 && round <= 4 ? ['RB'] : []);
      return bestExcluding(available, banned, myPicks, settings).player_id;
    }),
  },

  'late-qb': {
    label: 'Late-QB',
    description: 'Never spend a pick on a quarterback before round 8 — the position is deep, so build elsewhere first.',
    pick: withLegality(({ available, myPicks, round, settings }) =>
      bestExcluding(available, earlyBan(round, round < 8 ? ['QB'] : []), myPicks, settings)
        .player_id,
    ),
  },

  'value-adp': {
    label: 'Value vs ADP',
    description:
      'Take the biggest faller — the player whose ADP is latest relative to his VBD rank. Pure market-inefficiency drafting.',
    pick: withLegality(({ available, myPicks, round, settings }) => {
      const banned = earlyBan(round);
      for (const pos of saturatedPositions(myPicks, settings.rosterSlots)) banned.add(pos);
      const allowed = available.filter((p) => !p.position || !banned.has(p.position));
      const from = allowed.length ? allowed : available;
      // Compare only players actually in range for this pick. Scanning the whole
      // board makes the *worst* player look like the biggest bargain, because a
      // late ADP minus an early index is a huge positive gap.
      const byValue = [...from].sort((a, b) => value(b) - value(a)).slice(0, ADP_WINDOW);
      let best = byValue[0];
      let bestGap = -Infinity;
      byValue.forEach((p, idx) => {
        const gap = (p.adp ?? p.overall_rank) - (idx + 1);
        if (gap > bestGap) {
          bestGap = gap;
          best = p;
        }
      });
      return best.player_id;
    }),
  },

  'tier-based': {
    label: 'Tier-Based',
    description:
      'Draft from a position whose current tier is about to run out; otherwise take the best player available.',
    pick: withLegality(({ available, myPicks, round, settings }) => {
      const banned = earlyBan(round);
      for (const pos of saturatedPositions(myPicks, settings.rosterSlots)) banned.add(pos);
      const allowed = available.filter((p) => !p.position || !banned.has(p.position));
      const from = allowed.length ? allowed : available;

      const needs = positionalNeeds(
        myPicks.map((p) => p.position || ''),
        settings.rosterSlots,
      );

      const byPos: Record<string, DraftRanking[]> = {};
      for (const p of from) {
        if (p.position) (byPos[p.position] ||= []).push(p);
      }

      let urgent: DraftRanking | undefined;
      let urgentValue = -Infinity;
      for (const [pos, rows] of Object.entries(byPos)) {
        const wanted =
          (needs[pos] || 0) > 0 || (FLEX_ELIGIBLE.has(pos) && (needs.FLEX || 0) > 0);
        if (!wanted) continue;
        const bestTier = Math.min(...rows.map((r) => r.tier));
        const left = rows.filter((r) => r.tier === bestTier).length;
        const hasCliff = rows.some((r) => r.tier > bestTier);
        if (left <= 2 && hasCliff) {
          const candidate = rows.reduce((b, p) => (value(p) > value(b) ? p : b), rows[0]);
          if (value(candidate) > urgentValue) {
            urgentValue = value(candidate);
            urgent = candidate;
          }
        }
      }

      return (urgent ?? bestExcluding(from, new Set(), myPicks, settings)).player_id;
    }),
  },
};

/**
 * True when ADP carries no market information.
 *
 * With `player_adp` empty the backend synthesises ADP from the VBD rank itself,
 * so "value vs ADP" compares a number to itself and the strategy is noise. The
 * UI has to say so — otherwise the comparison table looks like evidence that
 * market-based drafting is bad, which it isn't.
 */
export function adpLooksSynthetic(players: DraftRanking[]): boolean {
  const sample = players.slice(0, 50);
  if (!sample.length) return false;
  const identical = sample.filter((p) => p.adp === p.overall_rank).length;
  return identical / sample.length > 0.8;
}

export function strategyIds(): string[] {
  return Object.keys(STRATEGIES);
}

// ── Bot opponents ────────────────────────────────────────────────────────────

export interface BotArchetype {
  label: string;
  /** Higher = more likely to reach past the consensus best pick. */
  noise: number;
  /** Positional multipliers applied to VBD. */
  bias?: Record<string, number>;
  /** Weight roster needs like a human does. */
  needAware?: boolean;
}

export const BOT_ARCHETYPES: Record<string, BotArchetype> = {
  'adp-follower': { label: 'ADP follower', noise: 0.15 },
  'rb-hungry': { label: 'RB hungry', noise: 0.25, bias: { RB: 1.25 } },
  reacher: { label: 'Reacher', noise: 0.6 },
  'need-based': { label: 'Need drafter', noise: 0.2, needAware: true },
};

const ARCHETYPE_IDS = Object.keys(BOT_ARCHETYPES);

/** Give every opponent (but not me) a random personality. */
export function assignBotArchetypes(
  settings: SimSettings,
  rng: Rng,
): Record<number, string> {
  const bots: Record<number, string> = {};
  const myIdx = settings.mySlot - 1;
  for (let i = 0; i < settings.leagueSize; i++) {
    if (i === myIdx) continue;
    bots[i] = ARCHETYPE_IDS[Math.floor(rng() * ARCHETYPE_IDS.length)];
  }
  return bots;
}

/**
 * One opponent pick. Exported so the interactive mock draft advances bots with
 * exactly the same logic the batch simulator uses — two implementations of
 * "what would a bot do here" would drift apart immediately.
 */
export function botPick(
  archetypeId: string,
  available: DraftRanking[],
  roster: DraftRanking[],
  round: number,
  settings: SimSettings,
  rng: Rng,
): DraftRanking {
  const archetype = BOT_ARCHETYPES[archetypeId] ?? BOT_ARCHETYPES['adp-follower'];

  const forced = forcedPositions(roster, round, settings);
  if (forced.length) {
    const pick = bestAt(available, forced);
    if (pick) return pick;
  }

  const banned = earlyBan(round);
  for (const pos of saturatedPositions(roster, settings.rosterSlots)) banned.add(pos);
  const allowed = available.filter((p) => !p.position || !banned.has(p.position));
  const from = allowed.length ? allowed : available;

  const needs = archetype.needAware
    ? positionalNeeds(roster.map((p) => p.position || ''), settings.rosterSlots)
    : null;

  let best = from[0];
  let bestScore = -Infinity;
  for (const p of from) {
    let score = value(p);
    if (archetype.bias && p.position && archetype.bias[p.position]) {
      score *= archetype.bias[p.position];
    }
    if (needs && p.position) {
      const posNeed = needs[p.position] || 0;
      const flexNeed = FLEX_ELIGIBLE.has(p.position) ? needs.FLEX || 0 : 0;
      if (posNeed > 0 || flexNeed > 0) score *= 1.15;
    }
    // Personality noise, scaled to the pool's value range so it stays meaningful
    // deep into the draft where VBD differences shrink.
    score *= 1 + (rng() - 0.5) * archetype.noise;
    if (score > bestScore) {
      bestScore = score;
      best = p;
    }
  }
  return best;
}

// ── The draft itself ─────────────────────────────────────────────────────────

/**
 * Run one complete mock draft.
 *
 * `myStrategy` controls my slot; every other seat is a bot with a random
 * archetype. Pass a seeded `rng` to make the whole thing reproducible.
 */
export function simulateDraft(
  players: DraftRanking[],
  settings: SimSettings,
  myStrategy: string,
  rng: Rng,
): SimResult {
  const strategy = STRATEGIES[myStrategy] ?? STRATEGIES['best-available'];
  const bots = assignBotArchetypes(settings, rng);
  const myIdx = settings.mySlot - 1;

  const available = [...players];
  const rosters: Record<number, DraftRanking[]> = {};
  for (let i = 0; i < settings.leagueSize; i++) rosters[i] = [];

  const allPicks: SimPick[] = [];
  const totalPicks = settings.leagueSize * settings.rounds;

  for (let overall = 1; overall <= totalPicks; overall++) {
    if (!available.length) break;
    const teamIdx = teamForPick(overall, settings.leagueSize);
    const round = Math.floor((overall - 1) / settings.leagueSize) + 1;

    let chosen: DraftRanking;
    if (teamIdx === myIdx) {
      const id = strategy.pick({
        available,
        myPicks: rosters[myIdx],
        round,
        settings,
        rng,
      });
      chosen = available.find((p) => p.player_id === id) ?? available[0];
    } else {
      chosen = botPick(bots[teamIdx], available, rosters[teamIdx], round, settings, rng);
    }

    rosters[teamIdx].push(chosen);
    allPicks.push({ overall, teamIdx, playerId: chosen.player_id });
    available.splice(
      available.findIndex((p) => p.player_id === chosen.player_id),
      1,
    );
  }

  return { allPicks, myRoster: rosters[myIdx] };
}

// ── Batch comparison ─────────────────────────────────────────────────────────

export interface BatchRow {
  strategy: string;
  label: string;
  avgPoints: number;
  winPct: number;
  best: number;
  worst: number;
  sims: number;
}

/**
 * Run `sims` drafts for each strategy and rank them.
 *
 * Every strategy faces the *same* seeded sequence of leagues, so differences in
 * the results come from the strategy rather than from luck of the draw.
 * `winPct` is how often a strategy produced the top roster of those compared.
 */
export function runBatch(
  players: DraftRanking[],
  settings: SimSettings,
  strategies: string[],
  sims: number,
  seed = 1,
): BatchRow[] {
  const scores: Record<string, number[]> = {};
  for (const id of strategies) scores[id] = [];

  for (let i = 0; i < sims; i++) {
    for (const id of strategies) {
      // Same seed per simulation index → identical bot behaviour across strategies.
      const result = simulateDraft(players, settings, id, makeRng(seed + i * 1000));
      scores[id].push(evaluateRoster(result.myRoster, settings).starterPoints);
    }
  }

  const wins: Record<string, number> = {};
  for (const id of strategies) wins[id] = 0;
  for (let i = 0; i < sims; i++) {
    let winner = strategies[0];
    for (const id of strategies) {
      if (scores[id][i] > scores[winner][i]) winner = id;
    }
    wins[winner] += 1;
  }

  return strategies
    .map((id) => {
      const values = scores[id];
      const avg = values.reduce((s, v) => s + v, 0) / (values.length || 1);
      return {
        strategy: id,
        label: STRATEGIES[id]?.label ?? id,
        avgPoints: Math.round(avg * 10) / 10,
        winPct: Math.round((wins[id] / (sims || 1)) * 1000) / 10,
        best: Math.max(...values),
        worst: Math.min(...values),
        sims,
      };
    })
    .sort((a, b) => b.avgPoints - a.avgPoints);
}
