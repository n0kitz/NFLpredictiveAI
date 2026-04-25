"""Miscellaneous API endpoints: health, accuracy, factors, scrape status, model info, players, seasons, value picks."""

import logging
import time
from collections import defaultdict
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..deps import get_db, get_engine
from ..helpers import row_to_player_entry
from ..schemas import (
    HealthResponse, AccuracyResponse, ScrapeStatusResponse, ModelInfoResponse,
    FactorRequest, FactorResponse, FactorListResponse,
    PlayerProfile, PlayerStatsEntry, PlayerSearchResult,
    ValuePick, ValuePicksResponse, ValuePickHistoryItem, ValuePickHistoryResponse,
    PlayerWeeklyStatsResponse, PlayerWeekCell,
)
from ...prediction.backtester import Backtester
from ...prediction.factors import FactorAdjuster

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

# In-memory backtest cache: key → (result_dict, timestamp)
_backtest_cache: dict = {}
_CACHE_TTL = 86400  # 24 hours


@router.get("/api/health", response_model=HealthResponse, tags=["system"])
def health_check(db=Depends(get_db)):
    teams = db.fetchone("SELECT COUNT(*) as count FROM teams")
    games = db.fetchone("SELECT COUNT(*) as count FROM games")

    scrape_log = None
    try:
        scrape_log = db.get_latest_scrape_log()
    except Exception:
        pass

    # Data freshness: max fetched_at from injury_reports or roster_entries
    data_updated_at = None
    try:
        row = db.fetchone(
            """
            SELECT MAX(ts) AS latest FROM (
                SELECT MAX(report_date) AS ts FROM injury_reports
                UNION ALL
                SELECT MAX(fetched_at) AS ts FROM roster_entries
            )
            """
        )
        if row and row["latest"]:
            data_updated_at = str(row["latest"])[:10]
    except Exception:
        pass

    return HealthResponse(
        status="ok",
        total_teams=teams["count"] if teams else 0,
        total_games=games["count"] if games else 0,
        database="connected",
        last_scrape_at=str(scrape_log["run_at"])[:19] if scrape_log else None,
        last_scrape_ok=bool(scrape_log["success"]) if scrape_log else None,
        last_scrape_error=scrape_log["error_message"] if scrape_log else None,
        data_updated_at=data_updated_at,
    )


@router.get("/api/accuracy", response_model=AccuracyResponse, tags=["system"])
@limiter.limit("5/minute")
def get_accuracy(
    request: Request,
    seasons: str = Query("2024,2025"),
    db=Depends(get_db),
):
    try:
        season_list = [int(s.strip()) for s in seasons.split(",") if s.strip()]
    except ValueError:
        raise HTTPException(status_code=422, detail="seasons must be comma-separated integers, e.g. '2024,2025'")
    if not season_list:
        raise HTTPException(status_code=422, detail="At least one season is required")
    if len(season_list) > 10:
        raise HTTPException(status_code=422, detail="At most 10 seasons allowed per request")
    cache_key = tuple(sorted(season_list))

    now = time.time()
    cached = _backtest_cache.get(cache_key)
    if cached and (now - cached[1]) < _CACHE_TTL:
        return AccuracyResponse(**cached[0])

    # Evict stale entries before inserting
    stale = [k for k, (_, ts) in _backtest_cache.items() if (now - ts) >= _CACHE_TTL]
    for k in stale:
        del _backtest_cache[k]
    if len(_backtest_cache) >= 50:
        oldest = next(iter(_backtest_cache))
        del _backtest_cache[oldest]

    bt = Backtester(db)
    report = bt.run(seasons=season_list)
    result = report.to_dict()
    _backtest_cache[cache_key] = (result, now)
    return AccuracyResponse(**result)


@router.get("/api/factors/{game_id}", response_model=FactorListResponse, tags=["factors"])
def list_factors(game_id: int, db=Depends(get_db)):
    adjuster = FactorAdjuster(db)
    factors = adjuster.list_factors(game_id)
    return FactorListResponse(
        factors=[
            FactorResponse(
                factor_id=f["factor_id"], game_id=game_id, team_id=0,
                team_name=f["team"], factor_type=f["type"],
                description=f["description"], impact_rating=f["impact"],
            )
            for f in factors
        ],
        count=len(factors),
    )


@router.post("/api/factors", response_model=FactorResponse, tags=["factors"])
def add_factor(req: FactorRequest, db=Depends(get_db)):
    adjuster = FactorAdjuster(db)
    try:
        factor_id = adjuster.add_factor(
            game_id=req.game_id, team_id=req.team_id,
            factor_type=req.factor_type.value, description=req.description,
            impact_rating=req.impact_rating,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return FactorResponse(
        factor_id=factor_id, game_id=req.game_id, team_id=req.team_id,
        factor_type=req.factor_type.value, description=req.description,
        impact_rating=req.impact_rating,
    )


@router.delete("/api/factors/{factor_id}", tags=["factors"])
def remove_factor(factor_id: int, db=Depends(get_db)):
    adjuster = FactorAdjuster(db)
    if not adjuster.remove_factor(factor_id):
        raise HTTPException(status_code=404, detail=f"Factor {factor_id} not found")
    return {"detail": "Factor removed"}


@router.get("/api/scrape/status", response_model=ScrapeStatusResponse, tags=["system"])
def scrape_status(db=Depends(get_db)):
    from ...scraper.pfr_scraper import PFRScraper
    scraper = PFRScraper(db)
    progress = scraper.get_scrape_progress()
    return ScrapeStatusResponse(
        completed_seasons=progress["completed"],
        total_games=progress["total_games"],
        incomplete=progress["incomplete"],
    )


@router.get("/api/model/info", response_model=ModelInfoResponse, tags=["system"])
def model_info():
    engine = get_engine()
    info = engine.get_model_info()
    return ModelInfoResponse(**info)


@router.get("/api/players/search", response_model=List[PlayerSearchResult], tags=["roster"])
def search_players(
    q: str = Query(..., min_length=2, max_length=50),
    db=Depends(get_db),
):
    rows = db.search_players(q)
    return [
        PlayerSearchResult(
            player_id=r["player_id"], full_name=r["full_name"],
            position=r["position"], team_abbr=r["team_abbr"],
            jersey_number=r["jersey_number"], headshot_url=r["headshot_url"],
        )
        for r in rows
    ]


@router.get("/api/players/{player_id}", response_model=PlayerProfile, tags=["roster"])
def get_player(player_id: int, db=Depends(get_db)):
    player = db.get_player_by_id(player_id)
    if not player:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    d = dict(player)
    stats_row = db.get_player_stats(player_id)
    stats = None
    team_abbr = None

    if stats_row:
        s = dict(stats_row)
        stats = PlayerStatsEntry(
            games_played=s.get("games_played", 0),
            pass_attempts=s.get("pass_attempts", 0),
            pass_completions=s.get("pass_completions", 0),
            pass_yards=s.get("pass_yards", 0),
            pass_tds=s.get("pass_tds", 0),
            interceptions=s.get("interceptions", 0),
            passer_rating=s.get("passer_rating", 0.0),
            rush_attempts=s.get("rush_attempts", 0),
            rush_yards=s.get("rush_yards", 0),
            rush_tds=s.get("rush_tds", 0),
            yards_per_carry=s.get("yards_per_carry", 0.0),
            targets=s.get("targets", 0),
            receptions=s.get("receptions", 0),
            rec_yards=s.get("rec_yards", 0),
            rec_tds=s.get("rec_tds", 0),
            yards_per_reception=s.get("yards_per_reception", 0.0),
            fantasy_points_ppr=s.get("fantasy_points_ppr", 0.0),
            fantasy_points_standard=s.get("fantasy_points_standard", 0.0),
        )
        team_row = db.get_team_by_id(s.get("team_id", 0))
        if team_row:
            team_abbr = team_row["abbreviation"]

    # Boom/bust from the latest available season in weekly stats (data-driven, not clock-driven)
    from ...prediction.fantasy_scorer import calc_boom_bust_from_rows
    latest_season_row = db.fetchone(
        "SELECT MAX(season) AS season FROM player_weekly_stats WHERE player_id = ?",
        (player_id,),
    )
    weekly_rows = []
    if latest_season_row and latest_season_row["season"] is not None:
        weekly_rows = db.fetchall(
            """
            SELECT fantasy_points_ppr, snaps, snap_pct FROM player_weekly_stats
            WHERE player_id = ? AND season = ?
            """,
            (player_id, latest_season_row["season"]),
        )
    bb = calc_boom_bust_from_rows(weekly_rows) if weekly_rows else None

    return PlayerProfile(
        player_id=d["player_id"], espn_id=d.get("espn_id"),
        full_name=d.get("full_name", ""), first_name=d.get("first_name"),
        last_name=d.get("last_name"), position=d.get("position"),
        jersey_number=d.get("jersey_number"), date_of_birth=d.get("date_of_birth"),
        height_cm=d.get("height_cm"), weight_kg=d.get("weight_kg"),
        college=d.get("college"), experience_years=d.get("experience_years", 0),
        status=d.get("status"), headshot_url=d.get("headshot_url"),
        team_abbr=team_abbr, current_stats=stats,
        boom_pct=bb.get("boom_pct") if bb else None,
        bust_pct=bb.get("bust_pct") if bb else None,
    )


@router.get(
    "/api/players/{player_id}/weekly-stats",
    response_model=PlayerWeeklyStatsResponse,
    tags=["roster"],
)
def get_player_weekly_stats(
    player_id: int,
    season: int = Query(..., ge=1990, le=2100),
    db=Depends(get_db),
):
    if not db.get_player_by_id(player_id):
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    rows = db.fetchall(
        """
        SELECT pws.week, pws.snaps, pws.snap_pct, pws.routes, pws.targets,
               pws.target_share, pws.rec_yards, pws.rush_yards, pws.pass_yards,
               pws.fantasy_points_ppr, pws.fantasy_points_standard,
               pws.is_home, pws.team_id, pws.opponent_team_id,
               opp.abbreviation AS opponent_abbr
        FROM player_weekly_stats pws
        LEFT JOIN teams opp ON opp.team_id = pws.opponent_team_id
        WHERE pws.player_id = ? AND pws.season = ?
        ORDER BY pws.week ASC
        """,
        (player_id, season),
    )
    by_week = {r["week"]: r for r in rows}

    # Determine player's team in this season for bye derivation.
    # Prefer the team_id present in weekly rows (matches the data we're returning);
    # tie-break by most frequent, then latest week, then smallest team_id.
    team_counts: dict = {}
    team_last_week: dict = {}
    for r in rows:
        tid = r["team_id"]
        if tid is None:
            continue
        team_counts[tid] = team_counts.get(tid, 0) + 1
        team_last_week[tid] = max(team_last_week.get(tid, 0), r["week"])
    selected_team_id: Optional[int] = None
    if team_counts:
        selected_team_id = min(
            team_counts.keys(),
            key=lambda tid: (-team_counts[tid], -team_last_week.get(tid, 0), tid),
        )
    else:
        # Fallback to roster_entries — pick most-frequent (handles mid-season trades)
        team_row = db.fetchone(
            """
            SELECT team_id FROM roster_entries
            WHERE player_id = ? AND season = ? AND team_id IS NOT NULL
            GROUP BY team_id
            ORDER BY COUNT(*) DESC, team_id ASC
            LIMIT 1
            """,
            (player_id, season),
        )
        if team_row:
            selected_team_id = team_row["team_id"]
    bye_week: Optional[int] = None
    if selected_team_id is not None:
        byes = db.get_bye_weeks(season)
        bye_week = byes.get(selected_team_id)

    max_week = max(list(by_week.keys()) + ([bye_week] if bye_week else []) + [0])
    if max_week == 0:
        return PlayerWeeklyStatsResponse(player_id=player_id, season=season, weeks=[])

    cells: List[PlayerWeekCell] = []
    for w in range(1, max_week + 1):
        r = by_week.get(w)
        if r is not None:
            cells.append(PlayerWeekCell(
                week=w,
                is_bye=False,
                snaps=int(r["snaps"] or 0),
                snap_pct=float(r["snap_pct"] or 0),
                routes=int(r["routes"] or 0),
                targets=int(r["targets"] or 0),
                target_share=float(r["target_share"] or 0),
                rec_yards=int(r["rec_yards"] or 0),
                rush_yards=int(r["rush_yards"] or 0),
                pass_yards=int(r["pass_yards"] or 0),
                fantasy_points_ppr=float(r["fantasy_points_ppr"] or 0),
                fantasy_points_standard=float(r["fantasy_points_standard"] or 0),
                opponent_abbr=r["opponent_abbr"],
                is_home=bool(r["is_home"]),
            ))
        else:
            cells.append(PlayerWeekCell(
                week=w,
                is_bye=(bye_week is not None and w == bye_week),
            ))

    return PlayerWeeklyStatsResponse(player_id=player_id, season=season, weeks=cells)


@router.get("/api/seasons/{year}/playoff-picture", tags=["seasons"])
def get_playoff_picture(year: int, db=Depends(get_db)):
    teams_rows = db.fetchall(
        """
        SELECT team_id, name, city, abbreviation, conference, division
        FROM teams
        WHERE (active_from IS NULL OR active_from <= ?)
          AND (active_until IS NULL OR active_until >= ?)
        ORDER BY conference, division, name
        """,
        (year, year),
    )
    if not teams_rows:
        raise HTTPException(status_code=404, detail=f"No teams found for season {year}")

    games_rows = db.fetchall(
        "SELECT home_team_id, away_team_id, home_score, away_score, winner_id, week FROM games WHERE season = ? AND game_type = 'regular'",
        (year,),
    )

    stats: dict = {}
    for t in teams_rows:
        stats[t["team_id"]] = {
            "team_id": t["team_id"], "team_abbr": t["abbreviation"],
            "team_name": f"{t['city']} {t['name']}",
            "conference": t["conference"],
            "division": f"{t['conference']} {t['division']}",
            "wins": 0, "losses": 0, "ties": 0,
            "conf_wins": 0, "conf_losses": 0,
            "div_wins": 0, "div_losses": 0,
            "points_for": 0, "points_against": 0, "games_played": 0,
        }

    team_conf = {t["team_id"]: t["conference"] for t in teams_rows}
    team_div = {t["team_id"]: f"{t['conference']} {t['division']}" for t in teams_rows}
    max_week = 0

    for g in games_rows:
        if g["home_score"] is None:
            continue
        h_id, a_id = g["home_team_id"], g["away_team_id"]
        if h_id not in stats or a_id not in stats:
            continue

        hs, aws = stats[h_id], stats[a_id]
        hs["points_for"] += g["home_score"]; hs["points_against"] += g["away_score"]; hs["games_played"] += 1
        aws["points_for"] += g["away_score"]; aws["points_against"] += g["home_score"]; aws["games_played"] += 1

        if g["winner_id"] == h_id:
            hs["wins"] += 1; aws["losses"] += 1
        elif g["winner_id"] == a_id:
            aws["wins"] += 1; hs["losses"] += 1
        else:
            hs["ties"] += 1; aws["ties"] += 1

        same_conf = team_conf.get(h_id) == team_conf.get(a_id)
        same_div = team_div.get(h_id) == team_div.get(a_id)
        if same_conf:
            if g["winner_id"] == h_id:
                hs["conf_wins"] += 1; aws["conf_losses"] += 1
            elif g["winner_id"] == a_id:
                aws["conf_wins"] += 1; hs["conf_losses"] += 1
            if same_div:
                if g["winner_id"] == h_id:
                    hs["div_wins"] += 1; aws["div_losses"] += 1
                elif g["winner_id"] == a_id:
                    aws["div_wins"] += 1; hs["div_losses"] += 1

        try:
            max_week = max(max_week, int(g["week"]))
        except (TypeError, ValueError):
            pass

    for s in stats.values():
        total = s["wins"] + s["losses"] + s["ties"]
        s["win_pct"] = (s["wins"] + s["ties"] * 0.5) / total if total > 0 else 0.0
        s["conf_record"] = f"{s['conf_wins']}-{s['conf_losses']}"
        s["div_record"] = f"{s['div_wins']}-{s['div_losses']}"
        s["point_diff"] = s["points_for"] - s["points_against"]

    def sort_key(t: dict):
        return (t["win_pct"], t["conf_wins"] - t["conf_losses"], t["point_diff"])

    def make_row(t: dict) -> dict:
        return {
            "team_id": t["team_id"], "team_abbr": t["team_abbr"], "team_name": t["team_name"],
            "wins": t["wins"], "losses": t["losses"], "ties": t["ties"],
            "win_pct": round(t["win_pct"], 3), "conf_record": t["conf_record"],
            "div_record": t["div_record"], "point_diff": t["point_diff"],
            "games_played": t["games_played"],
        }

    conf_data = {}
    for conf in ("AFC", "NFC"):
        conf_teams = [s for s in stats.values() if s["conference"] == conf]
        divisions_seen = sorted(set(s["division"] for s in conf_teams))
        division_leaders = []
        non_leaders = []

        for div in divisions_seen:
            div_teams = sorted([s for s in conf_teams if s["division"] == div], key=sort_key, reverse=True)
            if div_teams:
                division_leaders.append(div_teams[0])
                non_leaders.extend(div_teams[1:])

        division_leaders.sort(key=sort_key, reverse=True)
        non_leaders.sort(key=sort_key, reverse=True)

        conf_data[conf] = {
            "division_leaders": [make_row(t) for t in division_leaders],
            "wildcard": [make_row(t) for t in non_leaders[:3]],
            "bubble": [make_row(t) for t in non_leaders[3:6]],
        }

    return {"season": year, "weeks_played": max_week, "has_playoff_picture": max_week >= 10, **conf_data}


@router.get("/api/picks/value", response_model=ValuePicksResponse, tags=["predictions"])
@limiter.limit("10/minute")
def get_value_picks(
    request: Request,
    min_edge: float = Query(0.04, ge=0.0, le=0.5),
    db=Depends(get_db),
):
    from datetime import datetime, timezone

    engine = get_engine()
    rows = db.fetchall(
        """
        SELECT g.game_id, g.date, g.season, g.week, g.game_type,
               g.home_team_id, g.away_team_id,
               ht.abbreviation AS home_abbr, at.abbreviation AS away_abbr,
               ht.name AS home_name, at.name AS away_name,
               go.home_implied_prob, go.away_implied_prob, go.opening_spread AS spread,
               gw.is_adverse, gw.condition AS weather_condition
        FROM games g
        JOIN teams ht ON g.home_team_id = ht.team_id
        JOIN teams at ON g.away_team_id = at.team_id
        JOIN game_odds go ON go.game_id = g.game_id
        LEFT JOIN game_weather gw ON gw.home_team_id = g.home_team_id
                                  AND gw.game_date = g.date
        WHERE g.home_score IS NULL
          AND go.home_implied_prob IS NOT NULL
          AND go.away_implied_prob IS NOT NULL
        ORDER BY g.date ASC
        LIMIT 50
        """
    )

    picks = []
    for row in rows:
        d = dict(row)
        try:
            prediction = engine.predict(
                home_team=d["home_abbr"], away_team=d["away_abbr"],
                current_season=d["season"], is_playoff=(d["game_type"] != "regular"),
                week=d["week"], use_ml=False,
            )
        except Exception as e:
            logger.warning("Prediction failed for value pick %s @ %s: %s", d.get("away_abbr"), d.get("home_abbr"), e)
            continue

        model_prob = prediction.home_win_probability
        vegas_prob = float(d["home_implied_prob"])
        edge = round(model_prob - vegas_prob, 4)
        if abs(edge) < min_edge:
            continue

        picks.append(ValuePick(
            game_id=d["game_id"], game_date=str(d["date"])[:10],
            home_team=d["home_abbr"], away_team=d["away_abbr"],
            model_home_prob=round(model_prob, 4),
            vegas_home_implied_prob=round(vegas_prob, 4),
            edge=edge, edge_side="home" if edge > 0 else "away",
            model_confidence=prediction.confidence.upper(),
            vegas_spread=float(d["spread"]) if d["spread"] is not None else None,
            is_adverse_weather=bool(d["is_adverse"]) if d["is_adverse"] is not None else False,
            weather_condition=d["weather_condition"],
        ))

    picks.sort(key=lambda p: abs(p.edge), reverse=True)

    if not rows:
        note = "No upcoming games with Vegas odds available"
    elif not picks:
        note = f"No upcoming games with model-Vegas disagreement ≥ {min_edge * 100:.0f}pp"
    else:
        note = f"{len(picks)} game{'s' if len(picks) != 1 else ''} with model-Vegas disagreement ≥ {min_edge * 100:.0f}pp"

    return ValuePicksResponse(
        picks=picks,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        note=note,
    )


@router.get("/api/picks/history", response_model=ValuePickHistoryResponse, tags=["predictions"])
def get_value_picks_history(
    min_edge: float = Query(0.04, ge=0.0, le=0.5),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
):
    """Past predictions with model-vs-Vegas edge, including outcome tracking."""
    rows = db.get_value_picks_history(min_edge=min_edge, limit=limit)

    picks = []
    for r in rows:
        d = dict(r)
        edge = round(float(d["edge"]), 4)
        picks.append(ValuePickHistoryItem(
            id=d["id"],
            predicted_at=str(d["predicted_at"])[:19],
            home_abbr=d["home_abbr"],
            away_abbr=d["away_abbr"],
            predicted_winner_abbr=d["predicted_winner_abbr"] or "",
            home_prob=round(float(d["home_prob"]), 4),
            vegas_home_implied_prob=round(float(d["home_implied_prob"]), 4),
            edge=edge,
            edge_side="home" if edge > 0 else "away",
            vegas_spread=float(d["opening_spread"]) if d["opening_spread"] is not None else None,
            confidence=d["confidence"] or "medium",
            correct=bool(d["correct"]) if d["correct"] is not None else None,
            actual_winner_abbr=d.get("actual_winner_abbr"),
        ))

    resolved = [p for p in picks if p.correct is not None]
    correct_count = sum(1 for p in resolved if p.correct)
    return ValuePickHistoryResponse(
        picks=picks,
        total=len(picks),
        resolved=len(resolved),
        correct=correct_count,
        hit_rate=round(correct_count / len(resolved), 4) if resolved else None,
    )
