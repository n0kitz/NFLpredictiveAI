"""FAAB waiver advisor: rank targets by value over YOUR roster's replacement level.

VBD ranks a player against the league; this ranks a candidate against the
worst player *you* already roster at that position — the number that
actually decides whether a waiver claim helps this specific team. Reuses
`roster_advisor.build_roster_pool` for both sides (roster and candidates)
since that's the verified cache-independent projection path — the bulk
`fantasy_projections` generator is unreliable for an upcoming season (see
`roster_advisor` module docstring).

Non-positive value is filtered out entirely, mirroring `swap_list`'s
established rule: a bid on a below-replacement player is noise, not advice.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .league_settings import LeagueSettings
from .roster_advisor import build_roster_pool

_ROSTERED_POSITIONS = ("QB", "RB", "WR", "TE", "K", "DST")

# (delta upper bound inclusive, suggested bid %, tier label) — first match wins.
BID_TIERS: List[Tuple[float, int, str]] = [
    (2.0, 3, "speculative"),
    (5.0, 10, "solid"),
    (8.0, 20, "priority"),
    (float("inf"), 30, "must-add"),
]


def _bid_tier(delta: float) -> Tuple[int, str]:
    for max_delta, pct, tier in BID_TIERS:
        if delta <= max_delta:
            return pct, tier
    return BID_TIERS[-1][1], BID_TIERS[-1][2]


def _candidate_pool_ids(
    db, season: int, exclude_ids: Sequence[int], position: str = "all"
) -> List[int]:
    """Player ids on an NFL roster for `season`, excluding your fantasy roster."""
    exclude = list(exclude_ids) or [-1]
    placeholders = ",".join("?" for _ in exclude)
    pos = position.upper()
    pos_filter = "" if pos == "ALL" else "AND p.position = ?"
    params: List[Any] = [season]
    if pos != "ALL":
        params.append(pos)
    params.extend(exclude)

    rows = db.fetchall(
        f"""
        SELECT DISTINCT p.player_id
        FROM players p
        JOIN roster_entries re ON re.player_id = p.player_id
        WHERE re.season = ?
          AND p.position IN {_ROSTERED_POSITIONS}
          {pos_filter}
          AND p.player_id NOT IN ({placeholders})
        """,
        tuple(params),
    )
    return [r["player_id"] for r in rows]


def faab_recommendations(
    db,
    scorer: Any,
    roster_player_ids: Sequence[int],
    week: int,
    season: int,
    settings: Optional[LeagueSettings] = None,
    position: str = "all",
    budget_remaining: int = 100,
    limit: int = 15,
) -> List[Dict[str, Any]]:
    """Rank waiver candidates by value over the roster's own replacement level."""
    settings = settings or LeagueSettings()

    roster_pool = build_roster_pool(
        scorer, roster_player_ids, week, season, settings=settings
    )
    replacement_points: Dict[str, float] = {}
    for p in roster_pool:
        cur = replacement_points.get(p.position)
        if cur is None or p.projected_points < cur:
            replacement_points[p.position] = p.projected_points

    candidate_ids = _candidate_pool_ids(db, season, roster_player_ids, position)
    candidate_pool = build_roster_pool(
        scorer, candidate_ids, week, season, settings=settings
    )

    pos_filter = position.upper()
    results: List[Dict[str, Any]] = []
    for c in candidate_pool:
        if pos_filter != "ALL" and c.position != pos_filter:
            continue
        replacement = replacement_points.get(c.position, 0.0)
        delta = round(c.projected_points - replacement, 2)
        if delta <= 0:
            continue
        pct, tier = _bid_tier(delta)
        results.append(
            {
                "player_id": c.player_id,
                "full_name": c.full_name,
                "position": c.position,
                "team_abbr": c.team_abbr,
                "projected_points": c.projected_points,
                "replacement_points": replacement,
                "delta": delta,
                "tier": tier,
                "suggested_bid_pct": pct,
                "suggested_bid_amount": round(budget_remaining * pct / 100),
            }
        )

    results.sort(key=lambda r: r["delta"], reverse=True)
    return results[:limit]
