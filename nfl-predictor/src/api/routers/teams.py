"""Team-related API endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path

from ..deps import get_db
from ..helpers import resolve_team, row_to_game, row_to_player_entry
from ..schemas import (
    TeamResponse, TeamListResponse,
    TeamMetricsResponse, TeamProfileResponse, TeamProfileStats,
    TeamSeasonStatsResponse, GameListResponse, TeamRosterResponse,
    TeamScheduleEntry, TeamScheduleResponse,
)
from ...prediction.metrics import calculate_team_metrics

logger = logging.getLogger(__name__)
router = APIRouter(tags=["teams"])


@router.get("/api/teams", response_model=TeamListResponse)
def list_teams(
    active_only: bool = Query(True, description="Only show active teams"),
    db=Depends(get_db),
):
    teams = db.get_all_teams(active_only=active_only)
    team_list = [TeamResponse(**dict(t)) for t in teams]
    return TeamListResponse(teams=team_list, count=len(team_list))


@router.get("/api/teams/{identifier}", response_model=TeamResponse)
def get_team(identifier: str = Path(..., max_length=50), db=Depends(get_db)):
    return TeamResponse(**dict(resolve_team(db, identifier)))


@router.get("/api/teams/{identifier}/stats", response_model=TeamMetricsResponse)
def get_team_metrics(identifier: str = Path(..., max_length=50), db=Depends(get_db)):
    team = resolve_team(db, identifier)
    metrics = calculate_team_metrics(db, team["team_id"])
    return TeamMetricsResponse(
        team_id=metrics.team_id,
        team_name=metrics.team_name,
        team_abbr=metrics.team_abbr,
        current_season_wins=metrics.current_season_wins,
        current_season_losses=metrics.current_season_losses,
        current_season_ties=metrics.current_season_ties,
        win_percentage=round(metrics.win_percentage, 4),
        avg_points_scored=round(metrics.avg_points_scored, 1),
        avg_points_allowed=round(metrics.avg_points_allowed, 1),
        point_differential=metrics.point_differential,
        home_wins=metrics.home_wins,
        home_losses=metrics.home_losses,
        away_wins=metrics.away_wins,
        away_losses=metrics.away_losses,
        home_win_pct=round(metrics.home_win_pct, 4),
        away_win_pct=round(metrics.away_win_pct, 4),
        recent_wins=metrics.recent_wins,
        recent_losses=metrics.recent_losses,
        recent_win_pct=round(metrics.recent_win_pct, 4),
        offensive_strength=round(metrics.offensive_strength, 4),
        defensive_strength=round(metrics.defensive_strength, 4),
        strength_of_schedule=round(metrics.strength_of_schedule, 4),
        dynamic_hfa=round(metrics.dynamic_hfa, 4),
        rest_days=metrics.rest_days,
        games_analyzed=metrics.games_analyzed,
    )


@router.get("/api/teams/{identifier}/profile", response_model=TeamProfileResponse)
def get_team_profile(identifier: str, db=Depends(get_db)):
    team = resolve_team(db, identifier)
    team_id = team["team_id"]

    rows = db.fetchall(
        "SELECT * FROM team_season_stats WHERE team_id = ? ORDER BY season DESC",
        (team_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"No stats found for {identifier}")

    rows = [dict(r) for r in rows]
    total_wins = sum(r["wins"] for r in rows)
    total_losses = sum(r["losses"] for r in rows)
    total_ties = sum(r["ties"] for r in rows)
    total_gp = sum(r["games_played"] for r in rows)
    total_pf = sum(r["points_for"] for r in rows)
    total_pa = sum(r["points_against"] for r in rows)
    total_hw = sum(r["home_wins"] for r in rows)
    total_hl = sum(r["home_losses"] for r in rows)
    total_aw = sum(r["away_wins"] for r in rows)
    total_al = sum(r["away_losses"] for r in rows)

    all_time = TeamProfileStats(
        wins=total_wins, losses=total_losses, ties=total_ties,
        win_pct=round(total_wins / total_gp, 4) if total_gp else 0.0,
        games_played=total_gp, points_for=total_pf, points_against=total_pa,
        point_differential=total_pf - total_pa,
        home_wins=total_hw, home_losses=total_hl, away_wins=total_aw, away_losses=total_al,
        ppg=round(total_pf / total_gp, 1) if total_gp else 0.0,
        papg=round(total_pa / total_gp, 1) if total_gp else 0.0,
    )

    last = rows[0]
    last_gp = last["games_played"]
    last_season = TeamProfileStats(
        wins=last["wins"], losses=last["losses"], ties=last["ties"],
        win_pct=round(last["win_percentage"], 4),
        games_played=last_gp, points_for=last["points_for"], points_against=last["points_against"],
        point_differential=last["point_differential"],
        home_wins=last["home_wins"], home_losses=last["home_losses"],
        away_wins=last["away_wins"], away_losses=last["away_losses"],
        ppg=round(last["points_for"] / last_gp, 1) if last_gp else 0.0,
        papg=round(last["points_against"] / last_gp, 1) if last_gp else 0.0,
    )

    return TeamProfileResponse(
        team_id=team_id,
        team_name=f"{team['city']} {team['name']}",
        team_abbr=team["abbreviation"],
        all_time=all_time,
        last_season=last_season,
        last_season_year=last["season"],
    )


@router.get("/api/teams/{identifier}/season/{season}", response_model=TeamSeasonStatsResponse)
def get_team_season_stats(identifier: str, season: int, db=Depends(get_db)):
    team = resolve_team(db, identifier)
    stats = db.get_team_season_stats(team["team_id"], season)
    if not stats:
        raise HTTPException(status_code=404, detail=f"No stats for {identifier} in {season}")
    s = stats[0]
    return TeamSeasonStatsResponse(
        team_id=team["team_id"],
        team_name=f"{team['city']} {team['name']}",
        season=season,
        games_played=s["games_played"],
        wins=s["wins"], losses=s["losses"], ties=s["ties"],
        win_percentage=round(s["win_percentage"], 4),
        points_for=s["points_for"], points_against=s["points_against"],
        point_differential=s["point_differential"],
        home_wins=s["home_wins"], home_losses=s["home_losses"],
        away_wins=s["away_wins"], away_losses=s["away_losses"],
    )


@router.get("/api/teams/{identifier}/games", response_model=GameListResponse)
def get_team_games(
    identifier: str,
    season: Optional[int] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    db=Depends(get_db),
):
    team = resolve_team(db, identifier)
    games = db.get_team_games(team["team_id"], season=season, limit=limit)
    return GameListResponse(
        games=[row_to_game(g) for g in games],
        count=len(games),
        team=f"{team['city']} {team['name']}",
    )


@router.get("/api/teams/{identifier}/roster", response_model=TeamRosterResponse)
def get_team_roster(
    identifier: str,
    season: Optional[int] = Query(None),
    db=Depends(get_db),
):
    team = resolve_team(db, identifier)
    rows = db.get_team_roster(team["team_id"], season)
    players = [row_to_player_entry(r) for r in rows]
    actual_season = rows[0]["season"] if rows else (season or 0)
    return TeamRosterResponse(
        team_id=team["team_id"], team_abbr=team["abbreviation"],
        season=actual_season, players=players, count=len(players),
    )


@router.get("/api/teams/{identifier}/starters", response_model=TeamRosterResponse)
def get_team_starters(
    identifier: str,
    season: Optional[int] = Query(None),
    db=Depends(get_db),
):
    team = resolve_team(db, identifier)
    rows = db.get_team_starters(team["team_id"], season)
    players = [row_to_player_entry(r) for r in rows]
    actual_season = rows[0]["season"] if rows else (season or 0)
    return TeamRosterResponse(
        team_id=team["team_id"], team_abbr=team["abbreviation"],
        season=actual_season, players=players, count=len(players),
    )


@router.get("/api/teams/{identifier}/upcoming")
def get_team_upcoming(
    identifier: str,
    season: int = Query(2025),
    limit: int = Query(4, ge=1, le=20),
    db=Depends(get_db),
):
    team = resolve_team(db, identifier)
    tid = team["team_id"]
    rows = db.fetchall(
        """
        SELECT g.game_id, g.date, g.season, g.week,
               g.home_team_id, g.away_team_id,
               ht.abbreviation AS home_abbr, at.abbreviation AS away_abbr
        FROM games g
        JOIN teams ht ON ht.team_id = g.home_team_id
        JOIN teams at ON at.team_id = g.away_team_id
        WHERE g.season = ? AND (g.home_team_id = ? OR g.away_team_id = ?)
          AND g.home_score IS NULL
        ORDER BY g.date ASC LIMIT ?
        """,
        (season, tid, tid, limit),
    )

    games = []
    for r in rows:
        is_home = r["home_team_id"] == tid
        opp_abbr = r["away_abbr"] if is_home else r["home_abbr"]
        opp_id = r["away_team_id"] if is_home else r["home_team_id"]

        opp_stats = db.fetchone(
            """
            SELECT
              SUM(CASE WHEN winner_id=? THEN 1 ELSE 0 END) AS wins,
              SUM(CASE WHEN home_score IS NOT NULL AND winner_id!=? AND winner_id IS NOT NULL THEN 1 ELSE 0 END) AS losses,
              AVG(CASE WHEN home_team_id=? THEN home_score-away_score ELSE away_score-home_score END) AS avg_diff
            FROM games
            WHERE season=? AND game_type='regular'
              AND (home_team_id=? OR away_team_id=?) AND home_score IS NOT NULL
            """,
            (opp_id, opp_id, opp_id, season, opp_id, opp_id),
        )
        opp_w = int(opp_stats["wins"] or 0) if opp_stats else 0
        opp_l = int(opp_stats["losses"] or 0) if opp_stats else 0
        diff = float(opp_stats["avg_diff"] or 0) if opp_stats else 0.0
        difficulty = "hard" if diff >= 7 else "easy" if diff <= -3 else "medium"

        games.append({
            "game_id": r["game_id"], "date": str(r["date"]),
            "week": str(r["week"]), "is_home": is_home,
            "opp_abbr": opp_abbr, "opp_team_id": opp_id,
            "opp_record": f"{opp_w}-{opp_l}", "opp_diff": round(diff, 1),
            "difficulty": difficulty,
        })

    return {"team_abbr": team["abbreviation"], "season": season, "games": games}


@router.get("/api/teams/{identifier}/schedule", response_model=TeamScheduleResponse)
def get_team_schedule(
    identifier: str = Path(..., max_length=50),
    season: Optional[int] = Query(None),
    db=Depends(get_db),
):
    """Full season schedule for a team — completed games with results + upcoming games."""
    from datetime import datetime as _dt
    team = resolve_team(db, identifier)
    tid = team["team_id"]
    if season is None:
        now = _dt.now()
        season = now.year if now.month >= 9 else now.year - 1

    rows = db.fetchall(
        """
        SELECT g.game_id, g.date, g.season, g.week, g.game_type,
               g.home_team_id, g.away_team_id,
               g.home_score, g.away_score, g.winner_id, g.overtime,
               ht.abbreviation AS home_abbr, ht.name AS home_name, ht.city AS home_city,
               at.abbreviation AS away_abbr, at.name AS away_name, at.city AS away_city
        FROM games g
        JOIN teams ht ON g.home_team_id = ht.team_id
        JOIN teams at ON g.away_team_id = at.team_id
        WHERE g.season = ? AND (g.home_team_id = ? OR g.away_team_id = ?)
        ORDER BY g.date ASC
        """,
        (season, tid, tid),
    )

    wins = losses = ties = 0
    entries = []
    for r in rows:
        is_home = r["home_team_id"] == tid
        opp_abbr = r["away_abbr"] if is_home else r["home_abbr"]
        opp_name_full = (
            f"{r['away_city']} {r['away_name']}" if is_home
            else f"{r['home_city']} {r['home_name']}"
        )
        team_score = r["home_score"] if is_home else r["away_score"]
        opp_score = r["away_score"] if is_home else r["home_score"]

        result: Optional[str] = None
        if r["home_score"] is not None:
            if r["winner_id"] == tid:
                result = "W"
                wins += 1
            elif r["winner_id"] is None:
                result = "T"
                ties += 1
            else:
                result = "L"
                losses += 1

        # Difficulty rating for upcoming games based on opponent's current season record
        difficulty: Optional[str] = None
        if result is None:
            opp_id = r["away_team_id"] if is_home else r["home_team_id"]
            opp_stats = db.fetchone(
                """
                SELECT wins, losses, point_differential FROM team_season_stats
                WHERE team_id = ? AND season = ?
                """,
                (opp_id, season),
            )
            if opp_stats:
                gp = (opp_stats["wins"] or 0) + (opp_stats["losses"] or 0)
                if gp > 0:
                    win_pct = opp_stats["wins"] / gp
                    difficulty = "hard" if win_pct >= 0.6 else "easy" if win_pct <= 0.4 else "medium"

        entries.append(TeamScheduleEntry(
            game_id=r["game_id"],
            date=str(r["date"])[:10],
            week=str(r["week"]),
            game_type=r["game_type"],
            is_home=is_home,
            opp_abbr=opp_abbr,
            opp_name=opp_name_full,
            home_score=r["home_score"],
            away_score=r["away_score"],
            team_score=team_score,
            opp_score=opp_score,
            result=result,
            overtime=bool(r["overtime"]),
            difficulty=difficulty,
        ))

    return TeamScheduleResponse(
        team_id=tid,
        team_abbr=team["abbreviation"],
        team_name=f"{team['city']} {team['name']}",
        season=season,
        games=entries,
        wins=wins, losses=losses, ties=ties,
    )
