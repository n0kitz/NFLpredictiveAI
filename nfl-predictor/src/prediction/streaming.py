"""Streaming recommendations: best available DST/K/QB for a week.

``matchup_grade()`` scores a *position vs. an opponent*, not an individual
player — every QB on the same team facing the same defense gets an
identical grade. So the candidate pool is deduplicated to one player per
team before grading; grading every backup on a depth chart would just
repeat the same number under a different name.

``roster_entries`` carries no depth-chart or starter flag (empty on live
data for every position), so "who's actually playing" is approximated by
games played — this season if any exist yet, else the prior season as a
preseason fallback, mirroring the fallback pattern already used elsewhere
(``calculate_projection``, ``opp_position_dvp``).
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from .matchup_engine import matchup_grade
from .schedule_outlook import team_abbr, team_schedule

STREAMABLE_POSITIONS = {"QB", "K", "DST"}


def _team_candidates(db, position: str, season: int) -> Dict[int, int]:
    """team_id -> best-guess starting player_id for `position`, this season."""
    rows = db.fetchall(
        """
        SELECT re.team_id, p.player_id,
               COALESCE(cur.games_played, 0) AS gp_cur,
               COALESCE(prev.games_played, 0) AS gp_prev
        FROM roster_entries re
        JOIN players p ON p.player_id = re.player_id
        LEFT JOIN player_season_stats cur
               ON cur.player_id = p.player_id AND cur.season = ?
        LEFT JOIN player_season_stats prev
               ON prev.player_id = p.player_id AND prev.season = ? - 1
        WHERE re.season = ? AND p.position = ?
        """,
        (season, season, season, position),
    )
    best: Dict[int, tuple] = {}
    for r in rows:
        team_id = r["team_id"]
        gp = r["gp_cur"] if r["gp_cur"] > 0 else r["gp_prev"]
        if team_id not in best or gp > best[team_id][1]:
            best[team_id] = (r["player_id"], gp)
    return {team_id: pid for team_id, (pid, _gp) in best.items()}


def streaming_candidates(
    db,
    position: str,
    week: int,
    season: int,
    exclude_player_ids: Sequence[int] = (),
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Best-available `position` for `week`, ranked by matchup grade."""
    pos = position.upper()
    if pos not in STREAMABLE_POSITIONS:
        raise ValueError(
            f"position must be one of {sorted(STREAMABLE_POSITIONS)}, got {position!r}"
        )

    exclude = set(exclude_player_ids)
    team_candidates = _team_candidates(db, pos, season)

    results: List[Dict[str, Any]] = []
    for team_id, player_id in team_candidates.items():
        if player_id in exclude:
            continue
        opp = team_schedule(db, team_id, season).get(week)
        if opp is None:
            continue  # bye
        player = db.get_player_by_id(player_id)
        if not player:
            continue
        grade = matchup_grade(db, player_id, opp, pos, season, week)
        results.append(
            {
                "player_id": player_id,
                "full_name": player["full_name"],
                "team_abbr": team_abbr(db, team_id),
                "opponent_team_abbr": team_abbr(db, opp),
                "grade": grade["grade"],
                "score": grade["score"],
                "explanation": grade["explanation"],
            }
        )

    results.sort(key=lambda c: c["score"], reverse=True)
    return results[:limit]
