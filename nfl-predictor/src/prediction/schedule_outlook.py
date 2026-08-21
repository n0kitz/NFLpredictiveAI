"""Bye-week + playoff-strength-of-schedule outlook for a roster.

Answers two draft-prep questions the app couldn't before: does my roster
stack byes into too few weeks, and which of my players face a brutal
stretch in the fantasy playoffs (weeks 15-17)? Both derive from the
schedule already loaded — ``get_bye_weeks`` and the ``games`` table — never
a hardcoded bye table, so a new season needs no manual update.

``team_schedule`` and ``team_abbr`` are also reused by ``streaming.py``,
which needs the same week -> opponent lookup for a different purpose.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .matchup_engine import league_avg_dvp, opp_position_dvp

DEFAULT_PLAYOFF_WEEKS: Tuple[int, ...] = (15, 16, 17)

# Roster-wide, not restricted to a given week's starters — "starter" only
# exists relative to a specific week's optimal lineup, which shifts weekly.
# Three or more of the ~15-25 rostered players sharing a bye is still the
# actionable draft-time signal for "don't stack byes here".
BYE_COLLISION_THRESHOLD = 3

# opp_position_dvp only has a meaningful baseline for positions that are
# regularly targeted by a defense; DST-vs-DST has no such benchmark.
_DVP_POSITIONS = {"QB", "RB", "WR", "TE", "K"}

_HARD_RATIO = 0.85
_EASY_RATIO = 1.15


def team_schedule(db, team_id: int, season: int) -> Dict[int, int]:
    """week -> opponent_team_id for a team's regular-season games."""
    rows = db.fetchall(
        """
        SELECT CAST(week AS INTEGER) AS week_int, home_team_id, away_team_id
        FROM games
        WHERE season = ? AND game_type = 'regular'
          AND (home_team_id = ? OR away_team_id = ?)
        """,
        (season, team_id, team_id),
    )
    schedule: Dict[int, int] = {}
    for r in rows:
        schedule[r["week_int"]] = (
            r["away_team_id"] if r["home_team_id"] == team_id else r["home_team_id"]
        )
    return schedule


def team_abbr(db, team_id: Optional[int]) -> Optional[str]:
    if team_id is None:
        return None
    row = db.fetchone("SELECT abbreviation FROM teams WHERE team_id = ?", (team_id,))
    return row["abbreviation"] if row else None


def _difficulty(dvp: float, avg: float) -> str:
    """Classify a defense's DvP relative to the league-average baseline.

    Lower DvP = the defense allows fewer points to the position = tougher
    matchup for the player.
    """
    if avg <= 0:
        return "medium"
    ratio = dvp / avg
    if ratio <= _HARD_RATIO:
        return "hard"
    if ratio >= _EASY_RATIO:
        return "easy"
    return "medium"


def build_schedule_outlook(
    db,
    player_ids: Sequence[int],
    season: int,
    weeks: Sequence[int] = DEFAULT_PLAYOFF_WEEKS,
) -> Dict[str, Any]:
    """Bye week + per-week playoff matchup difficulty for each rostered player."""
    bye_by_team = db.get_bye_weeks(season)
    players: List[Dict[str, Any]] = []
    bye_groups: Dict[int, List[int]] = {}

    for pid in player_ids:
        player = db.get_player_by_id(pid)
        if not player:
            continue
        pos = (player["position"] or "").upper()
        team_id = db.get_player_team_id(pid, season)
        bye_week = bye_by_team.get(team_id) if team_id is not None else None
        if bye_week is not None:
            bye_groups.setdefault(bye_week, []).append(pid)

        playoff_weeks: List[Dict[str, Any]] = []
        if team_id is not None:
            schedule = team_schedule(db, team_id, season)
            for w in weeks:
                opp = schedule.get(w)
                if opp is None:
                    continue
                entry: Dict[str, Any] = {
                    "week": w,
                    "opponent_team_id": opp,
                    "opponent_team_abbr": team_abbr(db, opp),
                    "dvp": None,
                    "difficulty": None,
                }
                if pos in _DVP_POSITIONS:
                    dvp = opp_position_dvp(db, opp, pos, season, w)
                    entry["dvp"] = dvp
                    entry["difficulty"] = _difficulty(dvp, league_avg_dvp(pos))
                playoff_weeks.append(entry)

        dvp_values = [pw["dvp"] for pw in playoff_weeks if pw["dvp"] is not None]
        sos_score = (
            round(sum(dvp_values) / len(dvp_values), 2) if dvp_values else None
        )

        players.append(
            {
                "player_id": pid,
                "full_name": player["full_name"],
                "position": pos,
                "team_abbr": team_abbr(db, team_id),
                "bye_week": bye_week,
                "playoff_weeks": playoff_weeks,
                "playoff_sos_score": sos_score,
            }
        )

    bye_collisions = {
        week: ids
        for week, ids in bye_groups.items()
        if len(ids) >= BYE_COLLISION_THRESHOLD
    }

    return {
        "season": season,
        "players": players,
        "bye_collisions": bye_collisions,
    }
