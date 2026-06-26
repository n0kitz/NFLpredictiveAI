"""Advanced Matchup Engine + Lineup Optimizer endpoints (/api/fantasy/*).

Ported from the phase-2-matchup-engine branch into the post-Wave-5 router layout.
Heavy prediction modules are imported lazily so the app still boots if `pulp`
is absent (the optimizer endpoints then return 503).
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from ..deps import get_db
from ..schemas import (
    MatchupComponentScores, MatchupGradeResponse,
    OptimizeRequest, OptimizeDFSRequest,
    LineupPlayerOut, LineupResult, ExposureEntry, OptimizeResponse,
)
from ...database.db import Database

router = APIRouter()


def _build_lineup_response(result: dict) -> OptimizeResponse:
    lineups = []
    for lu in result['lineups']:
        players_out = [
            LineupPlayerOut(
                player_id=p['player_id'],
                full_name=p['full_name'],
                position=p['position'],
                team_abbr=p['team_abbr'],
                headshot_url=p.get('headshot_url'),
                slot=p['slot'],
                projected_points=p['projected_points'],
                salary=p.get('salary', 0),
            )
            for p in lu['players']
        ]
        lineups.append(LineupResult(
            rank=lu['rank'],
            players=players_out,
            projected_points=lu['projected_points'],
            total_salary=lu['total_salary'],
            correlation_bonus=lu['correlation_bonus'],
        ))
    exposure = {
        str(pid): ExposureEntry(
            count=e['count'], pct=e['pct'],
            full_name=e['full_name'], position=e['position'],
        )
        for pid, e in result['exposure'].items()
    }
    return OptimizeResponse(
        lineups=lineups,
        exposure=exposure,
        total_lineups=result['total_lineups'],
        slots=result['slots'],
    )


@router.post("/api/fantasy/optimize", response_model=OptimizeResponse, tags=["fantasy"])
def optimize_lineup(req: OptimizeRequest):
    """Season-long lineup optimizer. Provide a player pool + slot config."""
    from ...prediction.lineup_optimizer import LineupPlayer, optimize_lineup as _opt

    pool = [
        LineupPlayer(
            player_id=p.player_id, full_name=p.full_name, position=p.position,
            team_id=p.team_id, team_abbr=p.team_abbr,
            projected_points=p.projected_points, salary=p.salary,
            is_locked=p.is_locked, is_excluded=p.is_excluded,
            headshot_url=p.headshot_url, opponent_team_id=p.opponent_team_id,
        )
        for p in req.players
    ]
    try:
        result = _opt(
            players=pool,
            slots=req.slots,
            flex_positions=set(req.flex_positions),
            salary_cap=req.salary_cap,
            n_lineups=min(req.n_lineups, 150),
            correlations=req.correlations,
            max_from_team=req.max_from_team,
        )
    except ImportError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _build_lineup_response(result)


@router.post("/api/fantasy/optimize/dfs", response_model=OptimizeResponse, tags=["fantasy"])
def optimize_dfs(req: OptimizeDFSRequest):
    """DFS lineup optimizer for DraftKings ('dk') or FanDuel ('fd')."""
    from ...prediction.lineup_optimizer import (
        LineupPlayer, optimize_lineup as _opt, DFS_SLOTS,
    )

    site = req.site.lower()
    if site not in DFS_SLOTS:
        raise HTTPException(status_code=400, detail=f"Unknown site '{site}'. Use 'dk' or 'fd'.")

    cfg = DFS_SLOTS[site]
    locked   = set(req.locked_player_ids)
    excluded = set(req.excluded_player_ids)

    pool = [
        LineupPlayer(
            player_id=p.player_id, full_name=p.full_name, position=p.position,
            team_id=p.team_id, team_abbr=p.team_abbr,
            projected_points=p.projected_points, salary=p.salary,
            is_locked=(p.player_id in locked or p.is_locked),
            is_excluded=(p.player_id in excluded or p.is_excluded),
            headshot_url=p.headshot_url, opponent_team_id=p.opponent_team_id,
        )
        for p in req.players
    ]
    try:
        result = _opt(
            players=pool,
            slots=cfg['slots'],
            flex_positions=cfg['flex_positions'],
            salary_cap=cfg['salary_cap'],
            n_lineups=min(req.n_lineups, 150),
            correlations=req.correlations,
            max_from_team=cfg['max_from_team'],
        )
    except ImportError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _build_lineup_response(result)


@router.get("/api/fantasy/matchup/{player_id}", response_model=MatchupGradeResponse, tags=["fantasy"])
def get_matchup_grade(
    player_id: int,
    week: int = Query(..., ge=1, le=22, description="NFL week number"),
    season: int = Query(2024, ge=1990, le=2100),
    db: Database = Depends(get_db),
):
    """Advanced matchup grade for a player vs their scheduled opponent.

    Returns an A–F letter grade plus a 0–100 composite score built from:
    6-week position DvP (45%), YPP allowed (25%), game pace (20%), PROE (10%).
    """
    from ...prediction.matchup_engine import matchup_grade

    player = db.get_player_by_id(player_id)
    if not player:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    pos = (player['position'] or '').upper()

    team_row = db.fetchone(
        """
        SELECT re.team_id, t.abbreviation
        FROM roster_entries re
        JOIN teams t ON t.team_id = re.team_id
        WHERE re.player_id = ? ORDER BY re.season DESC LIMIT 1
        """,
        (player_id,),
    )
    if not team_row:
        raise HTTPException(status_code=404, detail="Player has no team roster entry")

    team_id = team_row['team_id']
    game = db.fetchone(
        """
        SELECT game_id, home_team_id, away_team_id FROM games
        WHERE season = ?
          AND (CAST(week AS INTEGER) = ? OR week = CAST(? AS TEXT))
          AND (home_team_id = ? OR away_team_id = ?)
        LIMIT 1
        """,
        (season, week, str(week), team_id, team_id),
    )
    if not game:
        raise HTTPException(
            status_code=404,
            detail=f"No game found for player's team in season {season} week {week}",
        )

    opp_team_id = (
        game['away_team_id'] if game['home_team_id'] == team_id else game['home_team_id']
    )
    opp_team_row = db.fetchone(
        "SELECT abbreviation FROM teams WHERE team_id = ?", (opp_team_id,)
    )
    opp_abbr = opp_team_row['abbreviation'] if opp_team_row else None

    result = matchup_grade(db, player_id, opp_team_id, pos, season, week)

    return MatchupGradeResponse(
        player_id=player_id,
        full_name=player['full_name'],
        position=pos or None,
        team_abbr=team_row['abbreviation'],
        opp_team_id=opp_team_id,
        opp_team_abbr=opp_abbr,
        week=week,
        season=season,
        grade=result['grade'],
        score=result['score'],
        rank_vs_league=result['rank_vs_league'],
        explanation=result['explanation'],
        dvp_6wk=result['dvp_6wk'],
        avg_league_dvp=result['avg_league_dvp'],
        opp_ypp=result['opp_ypp'],
        pace=result['pace'],
        proe=result['proe'],
        component_scores=MatchupComponentScores(**result['component_scores']),
    )
