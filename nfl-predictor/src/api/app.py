"""FastAPI application for NFL Prediction System."""

import logging
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from ..database.db import Database
from ..prediction.engine import PredictionEngine
from ..prediction.metrics import calculate_team_metrics, calculate_head_to_head
from ..prediction.factors import FactorAdjuster
from ..prediction.backtester import Backtester
from .deps import get_db
from ..database.models import GameFactor, FactorType
from .schemas import (
    HealthResponse,
    TeamResponse, TeamListResponse,
    GameResponse, GameListResponse,
    PredictionRequest, PredictionResponse, AppliedFactor,
    H2HRequest, H2HResponse,
    TeamSeasonStatsResponse, TeamMetricsResponse,
    TeamProfileResponse, TeamProfileStats,
    FactorRequest, FactorResponse, FactorListResponse,
    ScrapeStatusResponse,
    AccuracyResponse,
    PredictionHistoryItem, PredictionHistoryResponse,
    GameOddsResponse, VegasContext,
    ModelInfoResponse,
    InjuryEntry, WeatherResponse, ConditionsSummary, GameConditionsResponse,
    ExplanationEntry, ExplainPredictionResponse,
    PlayerEntry, PlayerStatsEntry, TeamRosterResponse,
    PlayerProfile, PlayerSearchResult,
    FantasyPlayerEntry, FantasyLeaderboardResponse,
    ErrorResponse,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="NFL Prediction API",
    description="NFL game prediction system with historical data analysis",
    version="1.0.0",
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ─────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse, tags=["system"])
def health_check(db: Database = Depends(get_db)):
    """Check API health and database status."""
    teams = db.fetchone("SELECT COUNT(*) as count FROM teams")
    games = db.fetchone("SELECT COUNT(*) as count FROM games")
    return HealthResponse(
        status="ok",
        total_teams=teams["count"] if teams else 0,
        total_games=games["count"] if games else 0,
        database=str(db.db_path),
    )


# ── Teams ──────────────────────────────────────────────

@app.get("/api/teams", response_model=TeamListResponse, tags=["teams"])
def list_teams(
    active_only: bool = Query(True, description="Only show active teams"),
    db: Database = Depends(get_db),
):
    """List all NFL teams."""
    teams = db.get_all_teams(active_only=active_only)
    team_list = [TeamResponse(**dict(t)) for t in teams]
    return TeamListResponse(teams=team_list, count=len(team_list))


@app.get("/api/teams/{identifier}", response_model=TeamResponse, tags=["teams"])
def get_team(identifier: str, db: Database = Depends(get_db)):
    """Get a team by abbreviation, name, or city."""
    team = db.find_team(identifier)
    if not team:
        raise HTTPException(status_code=404, detail=f"Team not found: {identifier}")
    return TeamResponse(**dict(team))


@app.get(
    "/api/teams/{identifier}/stats",
    response_model=TeamMetricsResponse,
    tags=["teams"],
)
def get_team_metrics(identifier: str, db: Database = Depends(get_db)):
    """Get computed metrics for a team (used in predictions)."""
    team = db.find_team(identifier)
    if not team:
        raise HTTPException(status_code=404, detail=f"Team not found: {identifier}")

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


@app.get(
    "/api/teams/{identifier}/profile",
    response_model=TeamProfileResponse,
    tags=["teams"],
)
def get_team_profile(identifier: str, db: Database = Depends(get_db)):
    """Get all-time + last season stats for a team (for display, not prediction)."""
    team = db.find_team(identifier)
    if not team:
        raise HTTPException(status_code=404, detail=f"Team not found: {identifier}")

    team_id = team["team_id"]

    # Fetch all season rows from team_season_stats
    rows = db.fetchall(
        "SELECT * FROM team_season_stats WHERE team_id = ? ORDER BY season DESC",
        (team_id,),
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No stats found for {identifier}",
        )

    rows = [dict(r) for r in rows]

    # Aggregate all-time
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
        wins=total_wins,
        losses=total_losses,
        ties=total_ties,
        win_pct=round(total_wins / total_gp, 4) if total_gp else 0.0,
        games_played=total_gp,
        points_for=total_pf,
        points_against=total_pa,
        point_differential=total_pf - total_pa,
        home_wins=total_hw,
        home_losses=total_hl,
        away_wins=total_aw,
        away_losses=total_al,
        ppg=round(total_pf / total_gp, 1) if total_gp else 0.0,
        papg=round(total_pa / total_gp, 1) if total_gp else 0.0,
    )

    # Last season = most recent row (already sorted DESC)
    last = rows[0]
    last_gp = last["games_played"]
    last_season = TeamProfileStats(
        wins=last["wins"],
        losses=last["losses"],
        ties=last["ties"],
        win_pct=round(last["win_percentage"], 4),
        games_played=last_gp,
        points_for=last["points_for"],
        points_against=last["points_against"],
        point_differential=last["point_differential"],
        home_wins=last["home_wins"],
        home_losses=last["home_losses"],
        away_wins=last["away_wins"],
        away_losses=last["away_losses"],
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


@app.get(
    "/api/teams/{identifier}/season/{season}",
    response_model=TeamSeasonStatsResponse,
    tags=["teams"],
)
def get_team_season_stats(
    identifier: str, season: int, db: Database = Depends(get_db)
):
    """Get a team's stats for a specific season."""
    team = db.find_team(identifier)
    if not team:
        raise HTTPException(status_code=404, detail=f"Team not found: {identifier}")

    stats = db.get_team_season_stats(team["team_id"], season)
    if not stats:
        raise HTTPException(
            status_code=404,
            detail=f"No stats for {identifier} in {season}",
        )

    s = stats[0]
    return TeamSeasonStatsResponse(
        team_id=team["team_id"],
        team_name=f"{team['city']} {team['name']}",
        season=season,
        games_played=s["games_played"],
        wins=s["wins"],
        losses=s["losses"],
        ties=s["ties"],
        win_percentage=round(s["win_percentage"], 4),
        points_for=s["points_for"],
        points_against=s["points_against"],
        point_differential=s["point_differential"],
        home_wins=s["home_wins"],
        home_losses=s["home_losses"],
        away_wins=s["away_wins"],
        away_losses=s["away_losses"],
    )


# ── Games ──────────────────────────────────────────────

@app.get("/api/games", response_model=GameListResponse, tags=["games"])
def list_games(
    season: Optional[int] = Query(None, description="Filter by season"),
    game_type: Optional[str] = Query(None, description="Filter: regular or playoff"),
    limit: int = Query(100, ge=1, le=1000, description="Max games to return"),
    db: Database = Depends(get_db),
):
    """List games, optionally filtered by season and type."""
    if season:
        # No limit when filtering by season
        games = db.get_games_by_season(season, game_type)
    else:
        if game_type:
            games = db.fetchall(
                "SELECT * FROM game_details WHERE game_type = ? ORDER BY date DESC LIMIT ?",
                (game_type, limit),
            )
        else:
            games = db.fetchall(
                "SELECT * FROM game_details ORDER BY date DESC LIMIT ?",
                (limit,),
            )
    game_list = [_row_to_game(g) for g in games]
    return GameListResponse(games=game_list, count=len(game_list))


@app.get(
    "/api/games/{game_id}/odds",
    response_model=GameOddsResponse,
    tags=["games"],
)
def get_game_odds(game_id: int, db: Database = Depends(get_db)):
    """Get Vegas betting odds for a specific game."""
    odds = db.get_odds_for_game(game_id)
    if not odds:
        raise HTTPException(status_code=404, detail=f"No odds found for game {game_id}")
    return GameOddsResponse(**dict(odds))


@app.get(
    "/api/games/{game_id}/conditions",
    response_model=GameConditionsResponse,
    tags=["games"],
)
def get_game_conditions(game_id: int, db: Database = Depends(get_db)):
    """Get injury reports and weather conditions for a specific game."""
    game = db.fetchone(
        """
        SELECT g.game_id, g.date, g.home_team_id, g.away_team_id,
               ht.name AS home_team, at.name AS away_team
        FROM games g
        JOIN teams ht ON g.home_team_id = ht.team_id
        JOIN teams at ON g.away_team_id = at.team_id
        WHERE g.game_id = ?
        """,
        (game_id,),
    )
    if not game:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

    game_d = dict(game)
    home_team_id = game_d["home_team_id"]
    away_team_id = game_d["away_team_id"]

    # Injuries
    home_inj_rows = db.get_key_injuries_for_team(home_team_id)
    away_inj_rows = db.get_key_injuries_for_team(away_team_id)

    home_injuries = [
        InjuryEntry(
            player_name=r["player_name"],
            position=r["position"],
            injury_status=r["injury_status"],
            report_date=r["report_date"],
        )
        for r in home_inj_rows
    ]
    away_injuries = [
        InjuryEntry(
            player_name=r["player_name"],
            position=r["position"],
            injury_status=r["injury_status"],
            report_date=r["report_date"],
        )
        for r in away_inj_rows
    ]

    # Weather — try by game_id first, then by home_team + date
    weather_row = db.get_weather_for_game(game_id)
    if not weather_row:
        weather_row = db.get_weather_for_teams(home_team_id, str(game_d["date"]))

    weather: Optional[WeatherResponse] = None
    if weather_row:
        w = dict(weather_row)
        weather = WeatherResponse(
            is_dome=bool(w.get("is_dome", 0)),
            condition=w.get("condition", "Unknown"),
            temperature_c=w.get("temperature_c"),
            wind_speed_kmh=w.get("wind_speed_kmh"),
            precipitation_mm=w.get("precipitation_mm"),
            weather_code=w.get("weather_code"),
            is_adverse=bool(w.get("is_adverse", 0)),
        )

    return GameConditionsResponse(
        game_id=game_id,
        home_team=game_d.get("home_team", ""),
        away_team=game_d.get("away_team", ""),
        conditions=ConditionsSummary(
            home_injuries=home_injuries,
            away_injuries=away_injuries,
            weather=weather,
        ),
    )


@app.get(
    "/api/teams/{identifier}/games",
    response_model=GameListResponse,
    tags=["games"],
)
def get_team_games(
    identifier: str,
    season: Optional[int] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    db: Database = Depends(get_db),
):
    """Get recent games for a team."""
    team = db.find_team(identifier)
    if not team:
        raise HTTPException(status_code=404, detail=f"Team not found: {identifier}")

    games = db.get_team_games(team["team_id"], season=season, limit=limit)
    game_list = [_row_to_game(g) for g in games]
    return GameListResponse(
        games=game_list,
        count=len(game_list),
        team=f"{team['city']} {team['name']}",
    )


# ── Predictions ────────────────────────────────────────

@app.post("/api/predict", response_model=PredictionResponse, tags=["predictions"])
def predict_game(
    req: PredictionRequest,
    model: Optional[str] = Query(None, description="Model override: 'ml' to use ML model"),
    db: Database = Depends(get_db),
):
    """Predict the outcome of a matchup. Add ?model=ml to use the ML model."""
    from .schemas import InlineFactor
    from ..prediction.factors import apply_game_factors as _apply_factors

    engine = PredictionEngine(db)
    use_ml = (model == "ml")
    try:
        prediction = engine.predict(
            home_team=req.home_team,
            away_team=req.away_team,
            game_id=req.game_id,
            apply_factors=req.apply_factors,
            use_ml=use_ml,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Apply inline factors if provided
    if req.factors:
        inline_game_factors = []
        for f in req.factors:
            team_id = prediction.home_team_id if f.team == "home" else prediction.away_team_id
            inline_game_factors.append(
                GameFactor(
                    factor_id=0,
                    game_id=0,
                    team_id=team_id,
                    factor_type=FactorType(f.factor_type.value),
                    impact_rating=f.impact_rating,
                )
            )
        if inline_game_factors:
            prediction = _apply_factors(prediction, inline_game_factors)

    factors_applied = [
        AppliedFactor(
            factor_type=f.factor_type.value,
            team_abbr=f.team_abbr,
            impact_rating=f.impact_rating,
        )
        for f in prediction.factors_applied
    ]

    # Auto-save to prediction history
    predicted_winner_id = (
        prediction.home_team_id
        if prediction.home_win_probability > prediction.away_win_probability
        else prediction.away_team_id
    )
    try:
        db.insert_prediction(
            home_team_id=prediction.home_team_id,
            away_team_id=prediction.away_team_id,
            predicted_winner_id=predicted_winner_id,
            home_prob=round(prediction.home_win_probability, 4),
            away_prob=round(prediction.away_win_probability, 4),
            confidence=prediction.confidence,
        )
    except Exception:
        pass  # Don't fail the prediction if history save fails

    # Look up Vegas odds for context (display-only, never used as prediction input)
    vegas_context: Optional[VegasContext] = None
    try:
        from datetime import date as _date
        today = str(_date.today())
        odds_row = db.get_odds_for_teams(
            prediction.home_team_id,
            prediction.away_team_id,
            today,
        )
        if odds_row:
            odds_d = dict(odds_row)
            vegas_context = VegasContext(
                spread=odds_d.get("opening_spread"),
                over_under=odds_d.get("over_under"),
                home_implied_prob=odds_d.get("home_implied_prob"),
                away_implied_prob=odds_d.get("away_implied_prob"),
                fetched_at=odds_d.get("fetched_at"),
            )
    except Exception:
        pass  # Vegas context is best-effort only

    # Build conditions summary (injuries + weather) from DB — display-only enrichment
    conditions: Optional[ConditionsSummary] = None
    try:
        from datetime import date as _date2, timedelta
        today_str = str(_date.today())
        window_end = str(_date.today() + timedelta(days=14))

        # Only include conditions for upcoming games (next 14 days)
        upcoming = db.fetchone(
            """
            SELECT g.game_id, g.date FROM games g
            WHERE g.home_team_id = ? AND g.away_team_id = ?
              AND g.date BETWEEN ? AND ?
              AND g.home_score IS NULL
            ORDER BY g.date ASC LIMIT 1
            """,
            (prediction.home_team_id, prediction.away_team_id, today_str, window_end),
        )
        home_inj = db.get_key_injuries_for_team(prediction.home_team_id)
        away_inj = db.get_key_injuries_for_team(prediction.away_team_id)

        weather: Optional[WeatherResponse] = None
        if upcoming:
            w_row = db.get_weather_for_game(upcoming["game_id"])
            if not w_row:
                w_row = db.get_weather_for_teams(
                    prediction.home_team_id, str(upcoming["date"])
                )
            if w_row:
                w = dict(w_row)
                weather = WeatherResponse(
                    is_dome=bool(w.get("is_dome", 0)),
                    condition=w.get("condition", "Unknown"),
                    temperature_c=w.get("temperature_c"),
                    wind_speed_kmh=w.get("wind_speed_kmh"),
                    precipitation_mm=w.get("precipitation_mm"),
                    weather_code=w.get("weather_code"),
                    is_adverse=bool(w.get("is_adverse", 0)),
                )

        if home_inj or away_inj or weather:
            conditions = ConditionsSummary(
                home_injuries=[
                    InjuryEntry(
                        player_name=r["player_name"],
                        position=r["position"],
                        injury_status=r["injury_status"],
                        report_date=r["report_date"],
                    )
                    for r in home_inj
                ],
                away_injuries=[
                    InjuryEntry(
                        player_name=r["player_name"],
                        position=r["position"],
                        injury_status=r["injury_status"],
                        report_date=r["report_date"],
                    )
                    for r in away_inj
                ],
                weather=weather,
            )
    except Exception:
        pass  # Conditions are best-effort enrichment

    return PredictionResponse(
        home_team=prediction.home_team,
        away_team=prediction.away_team,
        home_team_id=prediction.home_team_id,
        away_team_id=prediction.away_team_id,
        home_win_probability=round(prediction.home_win_probability, 4),
        away_win_probability=round(prediction.away_win_probability, 4),
        predicted_winner=prediction.predicted_winner,
        predicted_winner_probability=round(prediction.predicted_winner_probability, 4),
        confidence=prediction.confidence,
        key_factors=prediction.key_factors,
        factors_applied=factors_applied,
        predicted_spread=(
            round(prediction.predicted_spread, 1) if prediction.predicted_spread is not None else None
        ),
        vegas_context=vegas_context,
        conditions=conditions,
    )


@app.get("/api/predict/{away_team}/{home_team}", response_model=PredictionResponse, tags=["predictions"])
def predict_game_get(
    away_team: str,
    home_team: str,
    model: Optional[str] = Query(None, description="Model override: 'ml' to use ML model"),
    db: Database = Depends(get_db),
):
    """Predict via GET: /api/predict/{away_team}/{home_team}. Add ?model=ml for ML model."""
    engine = PredictionEngine(db)
    use_ml = (model == "ml")
    try:
        prediction = engine.predict(home_team=home_team, away_team=away_team, use_ml=use_ml)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return PredictionResponse(
        home_team=prediction.home_team,
        away_team=prediction.away_team,
        home_team_id=prediction.home_team_id,
        away_team_id=prediction.away_team_id,
        home_win_probability=round(prediction.home_win_probability, 4),
        away_win_probability=round(prediction.away_win_probability, 4),
        predicted_winner=prediction.predicted_winner,
        predicted_winner_probability=round(prediction.predicted_winner_probability, 4),
        confidence=prediction.confidence,
        key_factors=prediction.key_factors,
        factors_applied=[],
    )


# ── Prediction Explanation (SHAP) ──────────────────────

@app.post("/api/predict/explain", response_model=ExplainPredictionResponse, tags=["predictions"])
def explain_prediction_endpoint(
    req: PredictionRequest,
    db: Database = Depends(get_db),
):
    """
    Same as POST /api/predict, but also returns a SHAP-based explanation list.

    The prediction probabilities always use the weighted-sum model (default).
    The explanation uses the ML model regardless of the active default.
    Returns explanation=[] silently when the ML model is not loaded.
    """
    from .schemas import InlineFactor
    from ..prediction.factors import apply_game_factors as _apply_factors

    engine = PredictionEngine(db)
    try:
        prediction = engine.predict(
            home_team=req.home_team,
            away_team=req.away_team,
            game_id=req.game_id,
            apply_factors=req.apply_factors,
            use_ml=False,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Apply inline factors
    if req.factors:
        inline_game_factors = []
        for f in req.factors:
            team_id = prediction.home_team_id if f.team == "home" else prediction.away_team_id
            inline_game_factors.append(
                GameFactor(
                    factor_id=0,
                    game_id=0,
                    team_id=team_id,
                    factor_type=FactorType(f.factor_type.value),
                    impact_rating=f.impact_rating,
                )
            )
        if inline_game_factors:
            prediction = _apply_factors(prediction, inline_game_factors)

    factors_applied = [
        AppliedFactor(
            factor_type=f.factor_type.value,
            team_abbr=f.team_abbr,
            impact_rating=f.impact_rating,
        )
        for f in prediction.factors_applied
    ]

    # Generate SHAP explanation from ML model (empty list if ML unavailable)
    try:
        explanation_data = engine.explain_prediction(
            home_team=req.home_team,
            away_team=req.away_team,
        )
    except Exception:
        explanation_data = []

    explanation = [
        ExplanationEntry(
            feature=e["feature"],
            label=e["label"],
            shap_value=e["shap_value"],
            direction=e["direction"],
            feature_value=e["feature_value"],
        )
        for e in explanation_data
    ]

    return ExplainPredictionResponse(
        home_team=prediction.home_team,
        away_team=prediction.away_team,
        home_team_id=prediction.home_team_id,
        away_team_id=prediction.away_team_id,
        home_win_probability=round(prediction.home_win_probability, 4),
        away_win_probability=round(prediction.away_win_probability, 4),
        predicted_winner=prediction.predicted_winner,
        predicted_winner_probability=round(prediction.predicted_winner_probability, 4),
        confidence=prediction.confidence,
        key_factors=prediction.key_factors,
        factors_applied=factors_applied,
        explanation=explanation,
    )


# ── Head-to-Head ───────────────────────────────────────

@app.get("/api/h2h/{team1}/{team2}", response_model=H2HResponse, tags=["head-to-head"])
def head_to_head(
    team1: str,
    team2: str,
    limit: int = Query(10, ge=1, le=50),
    db: Database = Depends(get_db),
):
    """Get head-to-head history between two teams."""
    t1 = db.find_team(team1)
    t2 = db.find_team(team2)
    if not t1:
        raise HTTPException(status_code=404, detail=f"Team not found: {team1}")
    if not t2:
        raise HTTPException(status_code=404, detail=f"Team not found: {team2}")

    h2h = calculate_head_to_head(db, t1["team_id"], t2["team_id"], limit)
    game_list = [_row_to_game(g) for g in h2h["games"]]

    return H2HResponse(
        team1_name=f"{t1['city']} {t1['name']}",
        team1_abbr=t1["abbreviation"],
        team2_name=f"{t2['city']} {t2['name']}",
        team2_abbr=t2["abbreviation"],
        team1_wins=h2h["team1_wins"],
        team2_wins=h2h["team2_wins"],
        ties=h2h["ties"],
        total_games=h2h["total_games"],
        games=game_list,
    )


# ── Factors ────────────────────────────────────────────

@app.get(
    "/api/factors/{game_id}",
    response_model=FactorListResponse,
    tags=["factors"],
)
def list_factors(game_id: int, db: Database = Depends(get_db)):
    """List all factors for a game."""
    adjuster = FactorAdjuster(db)
    factors = adjuster.list_factors(game_id)
    factor_list = [
        FactorResponse(
            factor_id=f["factor_id"],
            game_id=game_id,
            team_id=0,
            team_name=f["team"],
            factor_type=f["type"],
            description=f["description"],
            impact_rating=f["impact"],
        )
        for f in factors
    ]
    return FactorListResponse(factors=factor_list, count=len(factor_list))


@app.post("/api/factors", response_model=FactorResponse, tags=["factors"])
def add_factor(req: FactorRequest, db: Database = Depends(get_db)):
    """Add a game factor."""
    adjuster = FactorAdjuster(db)
    try:
        factor_id = adjuster.add_factor(
            game_id=req.game_id,
            team_id=req.team_id,
            factor_type=req.factor_type.value,
            description=req.description,
            impact_rating=req.impact_rating,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return FactorResponse(
        factor_id=factor_id,
        game_id=req.game_id,
        team_id=req.team_id,
        factor_type=req.factor_type.value,
        description=req.description,
        impact_rating=req.impact_rating,
    )


@app.delete("/api/factors/{factor_id}", tags=["factors"])
def remove_factor(factor_id: int, db: Database = Depends(get_db)):
    """Remove a game factor."""
    adjuster = FactorAdjuster(db)
    if not adjuster.remove_factor(factor_id):
        raise HTTPException(status_code=404, detail=f"Factor {factor_id} not found")
    return {"detail": "Factor removed"}


# ── Accuracy / Backtesting ─────────────────────────

# Cache the backtest result in-memory (expensive to recompute)
_backtest_cache: dict = {}


@app.get(
    "/api/accuracy",
    response_model=AccuracyResponse,
    tags=["system"],
)
def get_accuracy(
    seasons: str = Query("2024,2025", description="Comma-separated seasons to test"),
    db: Database = Depends(get_db),
):
    """Get model accuracy from backtesting historical games."""
    season_list = [int(s.strip()) for s in seasons.split(",")]
    cache_key = tuple(season_list)

    if cache_key not in _backtest_cache:
        bt = Backtester(db)
        report = bt.run(seasons=season_list)
        _backtest_cache[cache_key] = report.to_dict()

    return AccuracyResponse(**_backtest_cache[cache_key])


# ── Prediction History ─────────────────────────────────

@app.get(
    "/api/predictions/history",
    response_model=PredictionHistoryResponse,
    tags=["predictions"],
)
def prediction_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Database = Depends(get_db),
):
    """Get prediction history with accuracy stats."""
    rows = db.get_prediction_history(limit=limit, offset=offset)
    stats = db.get_prediction_history_stats()

    predictions = []
    for r in rows:
        d = dict(r)
        predictions.append(PredictionHistoryItem(
            id=d["id"],
            home_abbr=d["home_abbr"],
            away_abbr=d["away_abbr"],
            home_team=d["home_team"],
            away_team=d["away_team"],
            predicted_winner_abbr=d["predicted_winner_abbr"],
            home_prob=round(d["home_prob"], 4),
            away_prob=round(d["away_prob"], 4),
            confidence=d["confidence"],
            predicted_at=str(d["predicted_at"]),
            actual_winner_abbr=d.get("actual_winner_abbr"),
            correct=bool(d["correct"]) if d["correct"] is not None else None,
        ))

    total = stats["total"] if stats else 0
    resolved = stats["resolved"] if stats else 0
    correct = stats["correct"] if stats else 0

    return PredictionHistoryResponse(
        predictions=predictions,
        total=total,
        resolved=resolved,
        correct=correct,
        accuracy=round(correct / resolved, 4) if resolved > 0 else None,
    )


@app.post("/api/predictions/enrich", tags=["predictions"])
def enrich_predictions(db: Database = Depends(get_db)):
    """Match unresolved predictions to completed games."""
    count = db.enrich_prediction_history()
    return {"enriched": count}


# ── Scrape Status ──────────────────────────────────────

@app.get(
    "/api/scrape/status",
    response_model=ScrapeStatusResponse,
    tags=["system"],
)
def scrape_status(db: Database = Depends(get_db)):
    """Get data scraping progress."""
    from ..scraper.pfr_scraper import PFRScraper

    scraper = PFRScraper(db)
    progress = scraper.get_scrape_progress()
    return ScrapeStatusResponse(
        completed_seasons=progress["completed"],
        total_games=progress["total_games"],
        incomplete=progress["incomplete"],
    )


# ── Model info ─────────────────────────────────────────

@app.get("/api/model/info", response_model=ModelInfoResponse, tags=["system"])
def model_info(db: Database = Depends(get_db)):
    """Return which prediction model is active (ML or weighted-sum fallback)."""
    engine = PredictionEngine(db)
    info = engine.get_model_info()
    return ModelInfoResponse(**info)


# ── Roster / Players ───────────────────────────────────

def _row_to_player_entry(row) -> PlayerEntry:
    d = dict(row)
    stats = None
    if d.get("games_played") is not None:
        stats = PlayerStatsEntry(
            games_played=d.get("games_played", 0),
            pass_attempts=d.get("pass_attempts", 0),
            pass_completions=d.get("pass_completions", 0),
            pass_yards=d.get("pass_yards", 0),
            pass_tds=d.get("pass_tds", 0),
            interceptions=d.get("interceptions", 0),
            passer_rating=d.get("passer_rating", 0.0),
            rush_attempts=d.get("rush_attempts", 0),
            rush_yards=d.get("rush_yards", 0),
            rush_tds=d.get("rush_tds", 0),
            yards_per_carry=d.get("yards_per_carry", 0.0),
            targets=d.get("targets", 0),
            receptions=d.get("receptions", 0),
            rec_yards=d.get("rec_yards", 0),
            rec_tds=d.get("rec_tds", 0),
            yards_per_reception=d.get("yards_per_reception", 0.0),
            fantasy_points_ppr=d.get("fantasy_points_ppr", 0.0),
            fantasy_points_standard=d.get("fantasy_points_standard", 0.0),
        )
    return PlayerEntry(
        player_id=d["player_id"],
        espn_id=d.get("espn_id"),
        full_name=d.get("full_name", ""),
        position=d.get("position"),
        jersey_number=d.get("jersey_number"),
        depth_position=d.get("depth_position"),
        is_starter=bool(d.get("is_starter", 0)),
        roster_status=d.get("roster_status"),
        height_cm=d.get("height_cm"),
        weight_kg=d.get("weight_kg"),
        college=d.get("college"),
        experience_years=d.get("experience_years", 0),
        headshot_url=d.get("headshot_url"),
        stats=stats,
    )


@app.get(
    "/api/teams/{identifier}/roster",
    response_model=TeamRosterResponse,
    tags=["roster"],
)
def get_team_roster(
    identifier: str,
    season: Optional[int] = Query(None, description="Season year (defaults to most recent)"),
    db: Database = Depends(get_db),
):
    """Get full roster for a team, with player stats for the season."""
    team = db.find_team(identifier)
    if not team:
        raise HTTPException(status_code=404, detail=f"Team not found: {identifier}")

    rows = db.get_team_roster(team["team_id"], season)
    players = [_row_to_player_entry(r) for r in rows]

    actual_season = rows[0]["season"] if rows else (season or 0)

    return TeamRosterResponse(
        team_id=team["team_id"],
        team_abbr=team["abbreviation"],
        season=actual_season,
        players=players,
        count=len(players),
    )


@app.get(
    "/api/teams/{identifier}/starters",
    response_model=TeamRosterResponse,
    tags=["roster"],
)
def get_team_starters(
    identifier: str,
    season: Optional[int] = Query(None),
    db: Database = Depends(get_db),
):
    """Get starters for a team, ordered by position group."""
    team = db.find_team(identifier)
    if not team:
        raise HTTPException(status_code=404, detail=f"Team not found: {identifier}")

    rows = db.get_team_starters(team["team_id"], season)
    players = [_row_to_player_entry(r) for r in rows]
    actual_season = rows[0]["season"] if rows else (season or 0)

    return TeamRosterResponse(
        team_id=team["team_id"],
        team_abbr=team["abbreviation"],
        season=actual_season,
        players=players,
        count=len(players),
    )


@app.get("/api/players/search", response_model=list, tags=["roster"])
def search_players(
    q: str = Query(..., min_length=2, description="Search query (player name)"),
    db: Database = Depends(get_db),
):
    """Search players by name. Returns up to 20 results."""
    rows = db.search_players(q)
    return [
        PlayerSearchResult(
            player_id=r["player_id"],
            full_name=r["full_name"],
            position=r["position"],
            team_abbr=r["team_abbr"],
            jersey_number=r["jersey_number"],
            headshot_url=r["headshot_url"],
        )
        for r in rows
    ]


@app.get("/api/players/{player_id}", response_model=PlayerProfile, tags=["roster"])
def get_player(player_id: int, db: Database = Depends(get_db)):
    """Get a player's full profile including current season stats."""
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

    return PlayerProfile(
        player_id=d["player_id"],
        espn_id=d.get("espn_id"),
        full_name=d.get("full_name", ""),
        first_name=d.get("first_name"),
        last_name=d.get("last_name"),
        position=d.get("position"),
        jersey_number=d.get("jersey_number"),
        date_of_birth=d.get("date_of_birth"),
        height_cm=d.get("height_cm"),
        weight_kg=d.get("weight_kg"),
        college=d.get("college"),
        experience_years=d.get("experience_years", 0),
        status=d.get("status"),
        headshot_url=d.get("headshot_url"),
        team_abbr=team_abbr,
        current_stats=stats,
    )


# ── Fantasy ─────────────────────────────────────────────

@app.get(
    "/api/fantasy/top",
    response_model=FantasyLeaderboardResponse,
    tags=["fantasy"],
)
def get_fantasy_top(
    position: str = Query("QB", description="Position: QB, RB, WR, TE, K"),
    season: int = Query(2024, description="Season year"),
    scoring: str = Query("ppr", description="Scoring: ppr or standard"),
    limit: int = Query(50, ge=1, le=200),
    db: Database = Depends(get_db),
):
    """Get top fantasy players at a position for a season."""
    rows = db.get_fantasy_leaders(position, season, scoring, limit)
    players = [
        FantasyPlayerEntry(
            player_id=r["player_id"],
            full_name=r["full_name"],
            position=r.get("position"),
            team_abbr=r.get("team_abbr"),
            headshot_url=r.get("headshot_url"),
            games_played=r.get("games_played", 0),
            fantasy_points_ppr=r.get("fantasy_points_ppr", 0.0),
            fantasy_points_standard=r.get("fantasy_points_standard", 0.0),
            points_per_game_ppr=r.get("points_per_game_ppr", 0.0),
        )
        for r in rows
    ]
    return FantasyLeaderboardResponse(
        position=position.upper(),
        season=season,
        scoring=scoring,
        players=players,
        count=len(players),
    )


# ── Helpers ────────────────────────────────────────────

def _row_to_game(row) -> GameResponse:
    """Convert a database row to GameResponse."""
    d = dict(row)
    return GameResponse(
        game_id=d.get("game_id", 0),
        date=str(d.get("date", "")),
        season=d.get("season", 0),
        week=str(d.get("week", "")),
        game_type=d.get("game_type", "regular"),
        home_team_id=d.get("home_team_id", 0),
        away_team_id=d.get("away_team_id", 0),
        home_team=d.get("home_team"),
        home_abbr=d.get("home_abbr"),
        away_team=d.get("away_team"),
        away_abbr=d.get("away_abbr"),
        home_score=d.get("home_score"),
        away_score=d.get("away_score"),
        winner=d.get("winner"),
        winner_abbr=d.get("winner_abbr"),
        winner_id=d.get("winner_id"),
        overtime=bool(d.get("overtime", False)),
    )
