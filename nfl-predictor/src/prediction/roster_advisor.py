"""Roster-aware lineup advice.

The DFS optimizer answers "who are the best players available". This module
answers the question a manager actually asks on Sunday morning: *given my
roster, what is my best legal lineup, and which specific changes get me there?*

The difference is the pool. `OptimizerTab` builds one from cached projections
across every position; here the pool is exactly the roster you own, with slots
derived from `LeagueSettings` so an 8-team standard league and a 14-team PPR
league both get correct answers.

No new solver: this constrains and post-processes `lineup_optimizer`.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .league_settings import LeagueSettings
from .lineup_optimizer import LineupPlayer, optimize_lineup

logger = logging.getLogger(__name__)

# Positions that may fill a FLEX slot in a standard NFL.com lineup.
FLEX_ELIGIBLE: Set[str] = {"RB", "WR", "TE"}


def build_roster_pool(
    scorer: Any,
    player_ids: Sequence[int],
    week: int,
    season: int,
    settings: Optional[LeagueSettings] = None,
) -> List[LineupPlayer]:
    """Project each rostered player directly into an optimizer pool.

    Deliberately does NOT read the ``fantasy_projections`` cache. For an
    upcoming season that table is unreliable — the bulk generator returned a
    backup QB at 12.0 and an elite RB at 5.4, exactly inverted, where
    ``calculate_projection`` gives 1.65 and 17.16. A roster is at most ~25
    players, so per-player projection is cheap, is the verified-correct path,
    picks up injury multipliers, and keeps lineup advice consistent with
    start/sit (which uses the same call).
    """
    settings = settings or LeagueSettings()
    pool: List[LineupPlayer] = []
    for pid in player_ids:
        proj = scorer.calculate_projection(pid, week, season, None)
        if not proj:
            continue
        proj = scorer._enrich_projection(proj, pid)
        pool.append(
            LineupPlayer(
                player_id=pid,
                full_name=proj.get("full_name", ""),
                position=(proj.get("position") or "").upper(),
                team_id=proj.get("team_id") or 0,
                team_abbr=proj.get("team_abbr"),
                projected_points=round(settings.points_from_projection(proj), 2),
                salary=0,
                headshot_url=proj.get("headshot_url"),
            )
        )
    return pool


def slots_from_settings(
    settings: Optional[LeagueSettings] = None,
) -> Tuple[Dict[str, int], Set[str]]:
    """Starting slots (bench removed) plus the FLEX-eligible positions."""
    settings = settings or LeagueSettings()
    slots = {k: v for k, v in settings.roster_slots.items() if k != "BN" and v > 0}
    return slots, set(FLEX_ELIGIBLE)


def naive_lineup(
    players: Sequence[LineupPlayer],
    slots: Dict[str, int],
    flex_positions: Optional[Set[str]] = None,
) -> List[LineupPlayer]:
    """The lineup a casual manager sets: best player per slot, greedily.

    Fills dedicated slots first, then FLEX from what's left. This is the
    baseline the swap list is measured against when the caller doesn't tell us
    what they're currently starting — greedy filling is exactly what misses the
    FLEX and RB2/WR3 boundary decisions.
    """
    flex_positions = flex_positions or set(FLEX_ELIGIBLE)
    remaining = sorted(players, key=lambda p: p.projected_points, reverse=True)
    chosen: List[LineupPlayer] = []
    used: Set[int] = set()

    for slot, count in slots.items():
        if slot == "FLEX":
            continue
        for p in remaining:
            if len([c for c in chosen if c.position == slot]) >= count:
                break
            if p.player_id in used or p.position != slot:
                continue
            chosen.append(p)
            used.add(p.player_id)

    for _ in range(slots.get("FLEX", 0)):
        for p in remaining:
            if p.player_id in used or p.position not in flex_positions:
                continue
            chosen.append(p)
            used.add(p.player_id)
            break

    return chosen


def _swap_reason(start: LineupPlayer, sit: LineupPlayer, delta: float) -> str:
    """Explain a swap in terms a manager can act on."""
    if delta < 1.0:
        margin = f"worth only +{delta:.1f} pts — close enough to be a coin flip"
    elif delta < 3.0:
        margin = f"worth +{delta:.1f} pts"
    else:
        margin = f"worth +{delta:.1f} pts — a clear upgrade"
    return (
        f"{start.full_name} ({start.position}, {start.projected_points:.1f} pts) "
        f"over {sit.full_name} ({sit.position}, {sit.projected_points:.1f} pts): "
        f"{margin}."
    )


def swap_list(
    optimal: Sequence[Dict[str, Any]],
    current: Sequence[Dict[str, Any]],
    pool_by_id: Dict[int, LineupPlayer],
) -> List[Dict[str, Any]]:
    """Diff an optimal lineup against the current one, biggest gain first."""
    optimal_ids = [p["player_id"] for p in optimal]
    current_ids = [p["player_id"] for p in current]

    to_start = [pid for pid in optimal_ids if pid not in current_ids]
    to_sit = [pid for pid in current_ids if pid not in optimal_ids]

    # Pair the biggest upgrade with the biggest downgrade.
    to_start.sort(key=lambda pid: pool_by_id[pid].projected_points, reverse=True)
    to_sit.sort(key=lambda pid: pool_by_id[pid].projected_points)

    slot_by_id = {p["player_id"]: p.get("slot") for p in optimal}

    swaps: List[Dict[str, Any]] = []
    for start_id, sit_id in zip(to_start, to_sit):
        start, sit = pool_by_id[start_id], pool_by_id[sit_id]
        delta = round(start.projected_points - sit.projected_points, 2)
        # Lineups that differ only by ties produce non-positive deltas. Telling
        # someone to make a change worth zero (or less) is noise, not advice.
        if delta <= 0:
            continue
        swaps.append(
            {
                "slot": slot_by_id.get(start_id),
                "start_player_id": start_id,
                "start_name": start.full_name,
                "sit_player_id": sit_id,
                "sit_name": sit.full_name,
                "point_delta": delta,
                "reason": _swap_reason(start, sit, delta),
            }
        )

    swaps.sort(key=lambda s: s["point_delta"], reverse=True)
    return swaps


def _missing_position_warnings(
    players: Sequence[LineupPlayer], slots: Dict[str, int]
) -> List[str]:
    warnings: List[str] = []
    for slot, count in slots.items():
        if slot == "FLEX":
            continue
        have = sum(1 for p in players if p.position == slot)
        if have < count:
            warnings.append(
                f"Only {have} {slot} on the roster but {count} must start — "
                "the lineup below is the best legal one available."
            )
    return warnings


def lineup_advice(
    players: Sequence[LineupPlayer],
    settings: Optional[LeagueSettings] = None,
    current_starter_ids: Optional[Sequence[int]] = None,
    locked_ids: Sequence[int] = (),
) -> Dict[str, Any]:
    """Best legal lineup from a roster, plus the swaps to reach it.

    ``correlations`` and the DFS per-team cap are disabled: QB-stack bonuses
    and the 8-players-from-one-team rule are DFS constructs that would distort
    a season-long roster you already own.
    """
    settings = settings or LeagueSettings()
    slots, flex_positions = slots_from_settings(settings)
    pool_by_id = {p.player_id: p for p in players}

    warnings = _missing_position_warnings(players, slots)

    # Shrink the slot requirement to what the roster can actually fill so the
    # MILP stays feasible; the shortfall is already reported as a warning.
    feasible_slots = dict(slots)
    for slot, count in slots.items():
        if slot == "FLEX":
            continue
        have = sum(1 for p in players if p.position == slot)
        if have < count:
            feasible_slots[slot] = have
    feasible_slots = {k: v for k, v in feasible_slots.items() if v > 0}

    if locked_ids:
        for pid in locked_ids:
            if pid in pool_by_id:
                pool_by_id[pid].is_locked = True

    result = optimize_lineup(
        players=list(players),
        slots=feasible_slots,
        flex_positions=flex_positions,
        salary_cap=None,
        n_lineups=1,
        correlations=False,
        max_from_team=len(players) or 1,
    )
    lineups = result.get("lineups") or []
    if not lineups:
        return {
            "lineup": [],
            "bench": [
                {"player_id": p.player_id, "full_name": p.full_name} for p in players
            ],
            "projected_points": 0.0,
            "swaps": [],
            "current_projected_points": 0.0,
            "points_gained": 0.0,
            "warnings": warnings + ["No legal lineup could be built from this roster."],
        }

    optimal = lineups[0]["players"]
    optimal_ids = {p["player_id"] for p in optimal}
    bench = [
        {
            "player_id": p.player_id,
            "full_name": p.full_name,
            "position": p.position,
            "team_abbr": p.team_abbr,
            "projected_points": round(p.projected_points, 2),
        }
        for p in players
        if p.player_id not in optimal_ids
    ]

    optimal_points = round(sum(p["projected_points"] for p in optimal), 2)

    # A slot the roster can only fill with a player projected at zero (ruled
    # out, on bye) is still the optimal lineup, but starting him is a decision
    # the manager has to know about — the fix is a waiver claim, not a swap.
    for p in optimal:
        if p["projected_points"] <= 0:
            warnings.append(
                f"{p['full_name']} starts at {p['slot']} projecting 0 pts — "
                "he is ruled out or on bye and you have no alternative on the "
                "roster. Look for a replacement on waivers."
            )

    current: List[Dict[str, Any]]
    if current_starter_ids is None:
        current_players = naive_lineup(players, feasible_slots, flex_positions)
        current = [
            {"player_id": p.player_id, "slot": p.position, "full_name": p.full_name}
            for p in current_players
        ]
    else:
        current = [
            {
                "player_id": pid,
                "slot": pool_by_id[pid].position,
                "full_name": pool_by_id[pid].full_name,
            }
            for pid in current_starter_ids
            if pid in pool_by_id
        ]

    current_points = round(
        sum(pool_by_id[p["player_id"]].projected_points for p in current), 2
    )
    swaps = swap_list(optimal, current, pool_by_id)

    return {
        "lineup": optimal,
        "bench": bench,
        "projected_points": optimal_points,
        "swaps": swaps,
        "current_projected_points": current_points,
        "points_gained": round(max(0.0, optimal_points - current_points), 2),
        "warnings": warnings,
    }
