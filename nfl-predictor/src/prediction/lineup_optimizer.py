"""
Phase 3 — Lineup Optimizer (MILP via PuLP).

Season-long and DFS lineup construction with QB-stacking, bring-back, and
RB/DEF anti-correlation. Generates up to N distinct optimal lineups.

Public API
----------
optimize_lineup(players, slots, salary_cap, n_lineups, correlations) → List[LineupResult]
    MILP optimizer for any slot configuration.

DFS_SLOTS — pre-defined slot configs for DraftKings / FanDuel.

LineupPlayer  — input player record (TypedDict).
LineupResult  — output lineup with projected points + exposure.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

DFS_SLOTS: Dict[str, Dict[str, Any]] = {
    'dk': {
        'salary_cap': 50_000,
        'slots': {'QB': 1, 'RB': 2, 'WR': 3, 'TE': 1, 'FLEX': 1, 'DST': 1},
        'flex_positions': {'RB', 'WR', 'TE'},
        'max_from_team': 8,
    },
    'fd': {
        'salary_cap': 60_000,
        'slots': {'QB': 1, 'RB': 2, 'WR': 3, 'TE': 1, 'FLEX': 1, 'DST': 1},
        'flex_positions': {'RB', 'WR', 'TE'},
        'max_from_team': 8,
    },
}

SEASON_LONG_SLOTS: Dict[str, int] = {
    'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'FLEX': 1, 'K': 1,
}
SEASON_LONG_FLEX: set = {'RB', 'WR', 'TE'}

# Correlation adjustment weights
_QB_STACK_BONUS    = 1.5   # extra projected pts when QB+WR from same team
_BRING_BACK_BONUS  = 0.8   # extra pts for opponent WR when QB vs that team
_RB_DEF_PENALTY    = 1.0   # subtract when RB and DEF from same team


# ── Data types ────────────────────────────────────────────────────────────────

class LineupPlayer:
    """A player candidate in the optimizer pool."""

    __slots__ = (
        'player_id', 'full_name', 'position', 'team_id', 'team_abbr',
        'projected_points', 'salary', 'is_locked', 'is_excluded',
        'headshot_url', 'opponent_team_id',
    )

    def __init__(
        self,
        player_id: int,
        full_name: str,
        position: str,
        team_id: int,
        team_abbr: str,
        projected_points: float,
        salary: int = 0,
        is_locked: bool = False,
        is_excluded: bool = False,
        headshot_url: Optional[str] = None,
        opponent_team_id: Optional[int] = None,
    ) -> None:
        self.player_id       = player_id
        self.full_name       = full_name
        self.position        = position.upper()
        self.team_id         = team_id
        self.team_abbr       = team_abbr
        self.projected_points = float(projected_points)
        self.salary          = int(salary)
        self.is_locked       = is_locked
        self.is_excluded     = is_excluded
        self.headshot_url    = headshot_url
        self.opponent_team_id = opponent_team_id


# ── Core optimizer ────────────────────────────────────────────────────────────

def optimize_lineup(
    players: List[LineupPlayer],
    slots: Dict[str, int],
    flex_positions: Optional[set] = None,
    salary_cap: Optional[int] = None,
    n_lineups: int = 20,
    correlations: bool = True,
    max_from_team: int = 8,
) -> List[Dict[str, Any]]:
    """Generate up to `n_lineups` distinct optimal lineups using MILP.

    Parameters
    ----------
    players         List of LineupPlayer candidates.
    slots           Dict mapping slot name → count, e.g. {'QB':1,'RB':2,...}.
    flex_positions  Set of positions eligible for FLEX slot.
    salary_cap      If set, enforce total salary ≤ salary_cap.
    n_lineups       How many distinct lineups to generate (iterative exclusion).
    correlations    If True, add QB-stack and bring-back bonuses.
    max_from_team   Max players allowed from one team (DFS rule).

    Returns
    -------
    List of lineup dicts, each with 'rank', 'players', 'projected_points',
    'total_salary', 'correlation_bonus', and 'slots'.
    """
    try:
        import pulp
    except ImportError:
        raise ImportError("pulp is required: pip install pulp")

    if flex_positions is None:
        flex_positions = SEASON_LONG_FLEX

    active = [p for p in players if not p.is_excluded]
    if not active:
        return {'lineups': [], 'exposure': {}, 'total_lineups': 0, 'slots': slots}

    # Pre-compute correlation bonuses per player pair
    corr_bonus = _correlation_bonus_map(active) if correlations else {}

    lineups: List[Dict[str, Any]] = []
    excluded_sets: List[frozenset] = []  # each past lineup's player set

    for attempt in range(n_lineups * 3):  # extra attempts for infeasible iterations
        if len(lineups) >= n_lineups:
            break

        result = _solve_once(
            active, slots, flex_positions, salary_cap,
            corr_bonus, max_from_team, excluded_sets, pulp,
        )
        if result is None:
            break  # no more feasible lineups

        sel_ids = frozenset(p['player_id'] for p in result['players'])
        excluded_sets.append(sel_ids)
        result['rank'] = len(lineups) + 1
        lineups.append(result)

    # Compute exposure %
    exposure: Dict[int, Dict[str, Any]] = {}
    total = len(lineups)
    for lu in lineups:
        for p in lu['players']:
            pid = p['player_id']
            if pid not in exposure:
                exposure[pid] = {'count': 0, 'pct': 0.0, 'full_name': p['full_name'], 'position': p['position']}
            exposure[pid]['count'] += 1
    for pid, data in exposure.items():
        data['pct'] = round(data['count'] / total * 100, 1) if total else 0.0

    return {
        'lineups': lineups,
        'exposure': exposure,
        'total_lineups': total,
        'slots': slots,
    }


def _solve_once(
    players: List[LineupPlayer],
    slots: Dict[str, int],
    flex_positions: set,
    salary_cap: Optional[int],
    corr_bonus: Dict[Tuple[int, int], float],
    max_from_team: int,
    excluded_sets: List[frozenset],
    pulp,
) -> Optional[Dict[str, Any]]:
    """Run one MILP pass and return the selected lineup or None if infeasible."""

    prob = pulp.LpProblem("lineup", pulp.LpMaximize)
    n = len(players)

    # ── Decision variables ────────────────────────────────────────────────────
    # x[i][slot] = 1 if player i assigned to slot
    slot_names = list(slots.keys())
    x: Dict[str, Dict[int, Any]] = {}
    for slot in slot_names:
        x[slot] = {i: pulp.LpVariable(f"x_{slot}_{i}", cat='Binary') for i in range(n)}

    # ── Objective: projected pts + correlation bonus ──────────────────────────
    obj_terms = []
    for slot in slot_names:
        for i, p in enumerate(players):
            obj_terms.append(p.projected_points * x[slot][i])

    # Correlation pair bonus: both in lineup → add bonus to objective
    # Approximate with auxiliary variable z[pair] = 1 if both selected
    pair_vars = {}
    for (i, j), bonus in corr_bonus.items():
        if bonus == 0:
            continue
        z = pulp.LpVariable(f"z_{i}_{j}", cat='Binary')
        pair_vars[(i, j)] = z
        obj_terms.append(bonus * z)
        # z ≤ sum_slot(x[slot][i]), z ≤ sum_slot(x[slot][j])
        prob += z <= pulp.lpSum(x[slot][i] for slot in slot_names)
        prob += z <= pulp.lpSum(x[slot][j] for slot in slot_names)

    prob += pulp.lpSum(obj_terms)

    # ── Player used at most once ──────────────────────────────────────────────
    for i in range(n):
        prob += pulp.lpSum(x[slot][i] for slot in slot_names) <= 1

    # ── Position constraints per slot ────────────────────────────────────────
    for slot, count in slots.items():
        eligible = []
        for i, p in enumerate(players):
            if slot == 'FLEX':
                ok = p.position in flex_positions
            elif slot == 'DST':
                ok = p.position in ('DST', 'DEF', 'D/ST')
            else:
                ok = p.position == slot
            if ok:
                eligible.append(x[slot][i])
            else:
                # Force ineligible player-slot variable to 0
                prob += x[slot][i] == 0
        prob += pulp.lpSum(eligible) == count

    # ── Salary cap ───────────────────────────────────────────────────────────
    if salary_cap is not None:
        prob += pulp.lpSum(
            players[i].salary * x[slot][i]
            for slot in slot_names for i in range(n)
        ) <= salary_cap

    # ── Max players per team ──────────────────────────────────────────────────
    team_ids = set(p.team_id for p in players)
    for tid in team_ids:
        team_players = [i for i, p in enumerate(players) if p.team_id == tid]
        prob += pulp.lpSum(
            x[slot][i] for slot in slot_names for i in team_players
        ) <= max_from_team

    # ── Locks ─────────────────────────────────────────────────────────────────
    for i, p in enumerate(players):
        if p.is_locked:
            prob += pulp.lpSum(x[slot][i] for slot in slot_names) == 1

    # ── Exclusion: differ from each past lineup by at least 1 player ─────────
    for past_ids in excluded_sets:
        past_indices = [i for i, p in enumerate(players) if p.player_id in past_ids]
        if past_indices:
            prob += pulp.lpSum(
                x[slot][i] for slot in slot_names for i in past_indices
            ) <= len(past_ids) - 1

    # ── Solve ─────────────────────────────────────────────────────────────────
    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[prob.status] != 'Optimal':
        return None

    # ── Extract solution ──────────────────────────────────────────────────────
    selected: List[Dict[str, Any]] = []
    total_salary = 0
    total_pts = 0.0

    for slot in slot_names:
        for i, p in enumerate(players):
            if pulp.value(x[slot][i]) and pulp.value(x[slot][i]) > 0.5:
                selected.append({
                    'player_id':       p.player_id,
                    'full_name':       p.full_name,
                    'position':        p.position,
                    'team_abbr':       p.team_abbr,
                    'headshot_url':    p.headshot_url,
                    'slot':            slot,
                    'projected_points': round(p.projected_points, 2),
                    'salary':          p.salary,
                })
                total_salary += p.salary
                total_pts += p.projected_points

    # Correlation bonus actually earned
    corr_earned = sum(
        bonus for (i, j), bonus in corr_bonus.items()
        if (i, j) in pair_vars and pulp.value(pair_vars[(i, j)]) and pulp.value(pair_vars[(i, j)]) > 0.5
    )

    return {
        'players':          selected,
        'projected_points': round(total_pts, 2),
        'total_salary':     total_salary,
        'correlation_bonus': round(corr_earned, 2),
    }


# ── Correlation helpers ───────────────────────────────────────────────────────

def _correlation_bonus_map(players: List[LineupPlayer]) -> Dict[Tuple[int, int], float]:
    """Build (i, j) → bonus dict for pairs worth stacking."""
    bonuses: Dict[Tuple[int, int], float] = {}
    qbs = [(i, p) for i, p in enumerate(players) if p.position == 'QB']
    wrs = [(i, p) for i, p in enumerate(players) if p.position in ('WR', 'TE')]

    for qi, qb in qbs:
        for wi, wr in wrs:
            if qb.team_id == wr.team_id:
                # QB + same-team WR/TE stack bonus
                key = (min(qi, wi), max(qi, wi))
                bonuses[key] = bonuses.get(key, 0.0) + _QB_STACK_BONUS
            elif qb.opponent_team_id and wr.team_id == qb.opponent_team_id:
                # Bring-back: opponent WR
                key = (min(qi, wi), max(qi, wi))
                bonuses[key] = bonuses.get(key, 0.0) + _BRING_BACK_BONUS

    # RB + DEF anti-correlation (penalty): handled as negative bonus
    rbs  = [(i, p) for i, p in enumerate(players) if p.position == 'RB']
    defs = [(i, p) for i, p in enumerate(players) if p.position in ('DST', 'DEF', 'D/ST')]
    for ri, rb in rbs:
        for di, df in defs:
            if rb.team_id == df.team_id:
                key = (min(ri, di), max(ri, di))
                bonuses[key] = bonuses.get(key, 0.0) - _RB_DEF_PENALTY

    return bonuses


# ── Convenience builders ──────────────────────────────────────────────────────

def players_from_projections(
    rows: List[Any],
    locked_ids: Optional[List[int]] = None,
    excluded_ids: Optional[List[int]] = None,
) -> List[LineupPlayer]:
    """Convert fantasy_projection DB rows to LineupPlayer objects.

    Rows must have: player_id, full_name, position, team_id (via roster),
    team_abbr, projected_points_ppr, opponent_team_id, headshot_url.
    Salary defaults to 0 when not present.
    """
    locked   = set(locked_ids   or [])
    excluded = set(excluded_ids or [])
    out = []
    for r in rows:
        pid = r['player_id'] if hasattr(r, '__getitem__') else r.player_id
        pos = (r['position'] or '').upper()
        if pos not in ('QB', 'RB', 'WR', 'TE', 'K', 'DST', 'DEF', 'D/ST'):
            continue
        out.append(LineupPlayer(
            player_id=pid,
            full_name=r['full_name'] or '',
            position=pos,
            team_id=r.get('team_id') or 0 if hasattr(r, 'get') else (r['team_id'] or 0),
            team_abbr=r['team_abbr'] or '',
            projected_points=float(r['projected_points_ppr'] or 0.0),
            salary=int(r['salary'] if 'salary' in r.keys() else 0) if hasattr(r, 'keys') else 0,
            is_locked=pid in locked,
            is_excluded=pid in excluded,
            headshot_url=r['headshot_url'],
            opponent_team_id=r['opponent_team_id'],
        ))
    return out
