"""FastAPI application for NFL Prediction System."""

import logging
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from ..database.db import Database, DEFAULT_DB_PATH
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
    FantasyProjectionEntry, StartSitPlayerEntry, StartSitResponse,
    DraftRankingEntry, TradePlayerEntry, TradeAnalysisResponse,
    FantasyRosterRequest, TradeAnalyzeRequest, ImportByNamesRequest,
    ValuePick, ValuePicksResponse,
    ErrorResponse,
)

logger = logging.getLogger(__name__)

# ── PredictionEngine singleton ─────────────────────────
# Load the ML model and SHAP explainer once at startup, not per request.
# The engine's internal DB is used for reads only; writes (e.g. insert_prediction)
# still go through the per-request DB provided by get_db().
_prediction_engine: PredictionEngine | None = None


def get_engine() -> PredictionEngine:
    global _prediction_engine
    if _prediction_engine is None:
        _prediction_engine = PredictionEngine(Database(DEFAULT_DB_PATH))
    return _prediction_engine


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

    engine = get_engine()
    use_ml = (model == "ml")
    try:
        prediction = engine.predict(
            home_team=req.home_team,
            away_team=req.away_team,
            game_id=req.game_id,
            apply_factors=req.apply_factors,
            use_ml=use_ml,
            current_season=req.current_season,
            is_playoff=req.is_playoff,
            week=req.week,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

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


# NOTE: This GET shortcut always uses is_playoff=False, week=0, current_season=None.
# For playoff games or week-specific predictions, use POST /api/predict with the full
# PredictionRequest body including is_playoff=True and week=N.
# The ML model's is_playoff and week_of_season features will be 0 for all GET predictions.
@app.get(
    "/api/predict/{away_team}/{home_team}",
    response_model=PredictionResponse,
    tags=["predictions"],
    description="Quick GET predict. Always uses is_playoff=False, week=0 — for playoff or week-specific predictions use POST /api/predict with the full request body.",
)
def predict_game_get(
    away_team: str,
    home_team: str,
    model: Optional[str] = Query(None, description="Model override: 'ml' to use ML model"),
    db: Database = Depends(get_db),
):
    """Predict via GET: /api/predict/{away_team}/{home_team}. Add ?model=ml for ML model."""
    engine = get_engine()
    use_ml = (model == "ml")
    try:
        prediction = engine.predict(
            home_team=home_team,
            away_team=away_team,
            use_ml=use_ml,
            current_season=None,
            is_playoff=False,
            week=0,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

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

    engine = get_engine()
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
    engine = get_engine()
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
    position: Optional[str] = Query(None, description="Position: QB, RB, WR, TE, K (omit for all)"),
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
            position=r["position"],
            team_abbr=r["team_abbr"],
            headshot_url=r["headshot_url"],
            games_played=r["games_played"] or 0,
            fantasy_points_ppr=r["fantasy_points_ppr"] or 0.0,
            fantasy_points_standard=r["fantasy_points_standard"] or 0.0,
            points_per_game_ppr=r["points_per_game_ppr"] or 0.0,
        )
        for r in rows
    ]
    return FantasyLeaderboardResponse(
        position=position.upper() if position else 'ALL',
        season=season,
        scoring=scoring,
        players=players,
        count=len(players),
    )


# ── Fantasy (extended) ──────────────────────────────────

def _proj_row_to_entry(r, week: int, season: int) -> FantasyProjectionEntry:
    """Convert a fantasy_projections DB row to FantasyProjectionEntry."""
    import json as _json
    d = dict(r)
    contribs = []
    raw = d.get('contributions_json')
    if raw:
        try:
            contribs = _json.loads(raw) or []
        except Exception:
            contribs = []
    return FantasyProjectionEntry(
        player_id=d['player_id'],
        full_name=d.get('full_name', ''),
        position=d.get('position'),
        team_abbr=d.get('team_abbr'),
        headshot_url=d.get('headshot_url'),
        week=d.get('week', week),
        season=d.get('season', season),
        projected_points_ppr=d.get('projected_points_ppr') or 0.0,
        projected_points_std=d.get('projected_points_std') or 0.0,
        matchup_score=d.get('matchup_score') or 1.0,
        opportunity_score=d.get('opportunity_score') or 0.0,
        confidence=d.get('confidence') or 'medium',
        injury_status=None,
        weather_impact=False,
        model_source=d.get('model_source') or 'heuristic',
        model_version=d.get('model_version'),
        floor_ppr=d.get('floor_ppr'),
        ceiling_ppr=d.get('ceiling_ppr'),
        contributions=contribs,
    )


@app.get("/api/fantasy/model-info", tags=["fantasy"])
def get_fantasy_model_info():
    """Which per-position ML fantasy models are available on disk."""
    from ..prediction.player_ml_model import model_info
    return model_info()


@app.get(
    "/api/fantasy/projections",
    response_model=List[FantasyProjectionEntry],
    tags=["fantasy"],
)
def get_fantasy_projections(
    week: int = Query(..., description="NFL week number"),
    season: int = Query(2024),
    position: str = Query("all"),
    scoring: str = Query("ppr"),
    db: Database = Depends(get_db),
):
    """Get weekly fantasy projections, generating them on-demand if not yet cached."""
    from ..prediction.fantasy_scorer import FantasyScorer
    rows = db.get_fantasy_projections(season, week, position, scoring)
    if not rows:
        scorer = FantasyScorer(db)
        scorer.generate_weekly_projections(season, week)
        rows = db.get_fantasy_projections(season, week, position, scoring)
    return [_proj_row_to_entry(r, week, season) for r in rows]


@app.get("/api/fantasy/start-sit", response_model=StartSitResponse, tags=["fantasy"])
def get_start_sit(
    player1_id: int = Query(...),
    player2_id: int = Query(...),
    week: int = Query(...),
    season: int = Query(2024),
    db: Database = Depends(get_db),
):
    """Compare two players and recommend which to start for the given week."""
    from ..prediction.fantasy_scorer import FantasyScorer
    scorer = FantasyScorer(db)
    result = scorer.start_sit_recommendation(player1_id, player2_id, week, season)
    if not result:
        raise HTTPException(status_code=404, detail="Could not generate recommendation")

    def _entry(d: dict) -> StartSitPlayerEntry:
        return StartSitPlayerEntry(
            player_id=d['player_id'],
            full_name=d['full_name'],
            position=d.get('position'),
            team_abbr=d.get('team_abbr'),
            headshot_url=d.get('headshot_url'),
            projected_points_ppr=d['projected_points_ppr'],
            matchup_score=d['matchup_score'],
            reasoning=d['reasoning'],
        )

    return StartSitResponse(
        start=_entry(result['start']),
        sit=_entry(result['sit']),
        confidence=result['confidence'],
    )


@app.get(
    "/api/fantasy/waiver",
    response_model=List[FantasyProjectionEntry],
    tags=["fantasy"],
)
def get_waiver_wire(
    week: int = Query(...),
    season: int = Query(2024),
    scoring: str = Query("ppr"),
    position: str = Query("all"),
    limit: int = Query(30, ge=1, le=100),
    db: Database = Depends(get_db),
):
    """Return waiver-wire targets sorted by opportunity score for the given week."""
    from ..prediction.fantasy_scorer import FantasyScorer
    rows = db.get_fantasy_projections(season, week, position, scoring)
    if not rows:
        scorer = FantasyScorer(db)
        scorer.generate_weekly_projections(season, week)
        rows = db.get_fantasy_projections(season, week, position, scoring)

    # Sort by opportunity_score descending
    sorted_rows = sorted(rows, key=lambda r: float(r['opportunity_score'] or 0), reverse=True)
    return [_proj_row_to_entry(r, week, season) for r in sorted_rows[:limit]]


@app.get(
    "/api/fantasy/draft-rankings",
    response_model=List[DraftRankingEntry],
    tags=["fantasy"],
)
def get_draft_rankings(
    season: int = Query(2025),
    scoring: str = Query("ppr"),
    position: str = Query("all"),
    db: Database = Depends(get_db),
):
    """Return draft rankings, generating them on-demand if not yet cached."""
    from ..prediction.fantasy_scorer import FantasyScorer
    rows = db.get_draft_rankings(season, scoring, position)
    if not rows:
        scorer = FantasyScorer(db)
        scorer.generate_draft_rankings(season, scoring)
        rows = db.get_draft_rankings(season, scoring, position)

    return [
        DraftRankingEntry(
            player_id=r['player_id'],
            full_name=r.get('full_name', ''),
            position=r.get('position'),
            team_abbr=r.get('team_abbr'),
            headshot_url=r.get('headshot_url'),
            overall_rank=r['overall_rank'],
            position_rank=r['position_rank'],
            tier=r['tier'],
            adp=r['adp'],
            projected_season_points=r['projected_season_points'],
            season=r['season'],
            scoring_format=r['scoring_format'],
        )
        for r in rows
    ]


@app.post("/api/fantasy/roster", tags=["fantasy"])
def set_fantasy_roster(
    req: FantasyRosterRequest,
    db: Database = Depends(get_db),
):
    """Upsert a set of players into a fantasy roster by league_id."""
    if len(req.player_ids) != len(req.slots):
        raise HTTPException(
            status_code=400,
            detail="player_ids and slots must have the same length",
        )
    for pid, slot in zip(req.player_ids, req.slots):
        db.upsert_fantasy_roster({'league_id': req.league_id, 'player_id': pid, 'slot': slot})
    db.commit()
    roster = db.get_fantasy_roster(req.league_id)
    return {"league_id": req.league_id, "count": len(roster)}


@app.post("/api/fantasy/trade-analyze", response_model=TradeAnalysisResponse, tags=["fantasy"])
def analyze_trade(
    req: TradeAnalyzeRequest,
    db: Database = Depends(get_db),
):
    """Analyze a trade by comparing rest-of-season projected points."""
    from ..prediction.fantasy_scorer import FantasyScorer
    scorer = FantasyScorer(db)
    result = scorer.analyze_trade(
        req.give_player_ids, req.get_player_ids, req.season, req.week
    )

    def _entry(d: dict) -> TradePlayerEntry:
        return TradePlayerEntry(
            player_id=d['player_id'],
            full_name=d['full_name'],
            position=d.get('position'),
            team_abbr=d.get('team_abbr'),
            headshot_url=d.get('headshot_url'),
            ros_projected=d['ros_projected'],
        )

    return TradeAnalysisResponse(
        give=[_entry(e) for e in result['give']],
        get=[_entry(e) for e in result['get']],
        give_total=result['give_total'],
        get_total=result['get_total'],
        verdict=result['verdict'],
        delta=result['delta'],
    )


# ── Playoff Picture ─────────────────────────────────────

@app.get("/api/seasons/{year}/playoff-picture", tags=["seasons"])
def get_playoff_picture(year: int, db: Database = Depends(get_db)):
    """Compute playoff standings for a season (pure DB computation, no scraping)."""
    from collections import defaultdict

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
        """
        SELECT home_team_id, away_team_id, home_score, away_score, winner_id, week
        FROM games WHERE season = ? AND game_type = 'regular'
        """,
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
    team_div  = {t["team_id"]: f"{t['conference']} {t['division']}" for t in teams_rows}
    max_week = 0

    for g in games_rows:
        if g["home_score"] is None:
            continue
        h_id, a_id = g["home_team_id"], g["away_team_id"]
        if h_id not in stats or a_id not in stats:
            continue

        hs, aws = stats[h_id], stats[a_id]
        hs["points_for"]  += g["home_score"]; hs["points_against"] += g["away_score"]; hs["games_played"] += 1
        aws["points_for"] += g["away_score"]; aws["points_against"] += g["home_score"]; aws["games_played"] += 1

        if g["winner_id"] == h_id:
            hs["wins"] += 1; aws["losses"] += 1
        elif g["winner_id"] == a_id:
            aws["wins"] += 1; hs["losses"] += 1
        else:
            hs["ties"] += 1; aws["ties"] += 1

        same_conf = team_conf.get(h_id) == team_conf.get(a_id)
        same_div  = team_div.get(h_id)  == team_div.get(a_id)
        if same_conf:
            if g["winner_id"] == h_id:   hs["conf_wins"] += 1;  aws["conf_losses"] += 1
            elif g["winner_id"] == a_id: aws["conf_wins"] += 1; hs["conf_losses"] += 1
            if same_div:
                if g["winner_id"] == h_id:   hs["div_wins"] += 1;  aws["div_losses"] += 1
                elif g["winner_id"] == a_id: aws["div_wins"] += 1; hs["div_losses"] += 1

        try:
            max_week = max(max_week, int(g["week"]))
        except (TypeError, ValueError):
            pass

    for s in stats.values():
        total = s["wins"] + s["losses"] + s["ties"]
        s["win_pct"]     = (s["wins"] + s["ties"] * 0.5) / total if total > 0 else 0.0
        s["conf_record"] = f"{s['conf_wins']}-{s['conf_losses']}"
        s["div_record"]  = f"{s['div_wins']}-{s['div_losses']}"
        s["point_diff"]  = s["points_for"] - s["points_against"]

    def sort_key(t: dict):
        return (t["win_pct"], t["conf_wins"] - t["conf_losses"], t["point_diff"])

    def make_row(t: dict) -> dict:
        return {
            "team_abbr": t["team_abbr"], "team_name": t["team_name"],
            "wins": t["wins"], "losses": t["losses"], "ties": t["ties"],
            "win_pct": round(t["win_pct"], 3),
            "conf_record": t["conf_record"], "div_record": t["div_record"],
            "points_for": t["points_for"], "points_against": t["points_against"],
            "point_diff": t["point_diff"],
            "clinched": t.get("clinched"), "is_division_leader": t.get("is_division_leader", False),
            "seed": t.get("seed"),
        }

    conf_data = {}
    for conf in ("AFC", "NFC"):
        conf_teams = [s for s in stats.values() if s["conference"] == conf and s["games_played"] > 0]
        div_map: dict = defaultdict(list)
        for t in conf_teams:
            div_map[t["division"]].append(t)
        for v in div_map.values():
            v.sort(key=sort_key, reverse=True)

        div_leaders = {div: teams[0] for div, teams in div_map.items() if teams}
        for i, leader in enumerate(sorted(div_leaders.values(), key=sort_key, reverse=True), start=1):
            leader["seed"] = i
            leader["is_division_leader"] = True
            leader["clinched"] = "division" if max_week >= 17 else None

        leader_ids  = {l["team_id"] for l in div_leaders.values()}
        non_leaders = sorted([t for t in conf_teams if t["team_id"] not in leader_ids], key=sort_key, reverse=True)
        for i, t in enumerate(non_leaders):
            t["is_division_leader"] = False
            if i < 3:   t["seed"] = 5 + i; t["clinched"] = "wildcard"  if max_week >= 17 else None
            else:        t["seed"] = 8 + (i - 3); t["clinched"] = "eliminated" if max_week >= 17 else None

        conf_data[conf.lower()] = {
            "divisions": {div: [make_row(t) for t in sorted(teams, key=sort_key, reverse=True)]
                          for div, teams in sorted(div_map.items())},
            "wildcard":  [make_row(t) for t in non_leaders[:3]],
            "bubble":    [make_row(t) for t in non_leaders[3:6]],
        }

    return {"season": year, "weeks_played": max_week, "has_playoff_picture": max_week >= 10, **conf_data}


# ── Team Upcoming Games ──────────────────────────────────

@app.get("/api/teams/{identifier}/upcoming", tags=["teams"])
def get_team_upcoming(
    identifier: str,
    season: int = Query(2025),
    limit: int = Query(4),
    db: Database = Depends(get_db),
):
    """Return the next N unplayed games for a team with opponent difficulty."""
    team = db.find_team(identifier)
    if not team:
        raise HTTPException(status_code=404, detail=f"Team '{identifier}' not found")

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
        is_home  = r["home_team_id"] == tid
        opp_abbr = r["away_abbr"] if is_home else r["home_abbr"]
        opp_id   = r["away_team_id"] if is_home else r["home_team_id"]

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
        opp_w = int(opp_stats["wins"] or 0)   if opp_stats else 0
        opp_l = int(opp_stats["losses"] or 0) if opp_stats else 0
        diff  = float(opp_stats["avg_diff"] or 0) if opp_stats else 0.0
        difficulty = "hard" if diff >= 7 else "easy" if diff <= -3 else "medium"

        games.append({
            "game_id": r["game_id"], "date": str(r["date"]),
            "week": str(r["week"]), "is_home": is_home,
            "opp_abbr": opp_abbr, "opp_team_id": opp_id,
            "opp_record": f"{opp_w}-{opp_l}", "opp_diff": round(diff, 1),
            "difficulty": difficulty,
        })

    return {"team_abbr": team["abbreviation"], "season": season, "games": games}


# ── Fantasy Power Rankings ─────────────────────────────────

@app.get("/api/fantasy/power-rankings", tags=["fantasy"])
def get_power_rankings(
    week: int = Query(...),
    season: int = Query(2024),
    db: Database = Depends(get_db),
):
    """Weekly team power rankings for fantasy context."""

    def _compute(target_week: int) -> dict:
        teams = db.fetchall(
            """
            SELECT team_id, name, city, abbreviation, conference
            FROM teams WHERE (active_from IS NULL OR active_from <= ?)
              AND (active_until IS NULL OR active_until >= ?)
            """,
            (season, season),
        )
        scored = []
        for t in teams:
            tid = t["team_id"]
            recent = db.fetchall(
                """
                SELECT home_team_id, away_team_id, home_score, away_score, winner_id
                FROM games WHERE season=? AND game_type='regular'
                  AND (home_team_id=? OR away_team_id=?) AND home_score IS NOT NULL
                  AND CAST(week AS INTEGER) < ?
                ORDER BY date DESC LIMIT 4
                """,
                (season, tid, tid, target_week),
            )
            wins = sum(1 for g in recent if g["winner_id"] == tid)
            form = wins / max(len(recent), 1) if recent else 0.5
            pt_diff = sum(
                (g["home_score"] or 0) - (g["away_score"] or 0) if g["home_team_id"] == tid
                else (g["away_score"] or 0) - (g["home_score"] or 0)
                for g in recent
            )
            pt_norm = max(-1.0, min(1.0, pt_diff / 60.0))

            adv = db.fetchone(
                "SELECT yards_per_play FROM team_advanced_stats WHERE team_id=? AND season=?",
                (tid, season),
            ) or db.fetchone(
                "SELECT yards_per_play FROM team_advanced_stats WHERE team_id=? ORDER BY season DESC LIMIT 1",
                (tid,),
            )
            adv_score = 0.5
            if adv and adv["yards_per_play"]:
                adv_score = min(1.0, max(0.0, (float(adv["yards_per_play"]) - 3.5) / 3.5))

            nxt = db.fetchone(
                """
                SELECT home_team_id, away_team_id FROM games
                WHERE season=? AND (home_team_id=? OR away_team_id=?)
                  AND CAST(week AS INTEGER) >= ? AND home_score IS NULL
                ORDER BY date ASC LIMIT 1
                """,
                (season, tid, tid, target_week),
            )
            opp_str = 0.5
            if nxt:
                opp_id = nxt["away_team_id"] if nxt["home_team_id"] == tid else nxt["home_team_id"]
                opp_r  = db.fetchall(
                    """
                    SELECT winner_id FROM games WHERE season=? AND game_type='regular'
                      AND (home_team_id=? OR away_team_id=?) AND home_score IS NOT NULL
                    ORDER BY date DESC LIMIT 4
                    """,
                    (season, opp_id, opp_id),
                )
                if opp_r:
                    opp_str = sum(1 for g in opp_r if g["winner_id"] == opp_id) / len(opp_r)

            composite = 0.40 * form + 0.20 * ((pt_norm + 1) / 2) + 0.20 * (1.0 - opp_str) + 0.20 * adv_score
            scored.append({
                "team_id": tid, "team_abbr": t["abbreviation"],
                "team_name": f"{t['city']} {t['name']}",
                "conference": t["conference"], "composite": composite,
                "recent_wins": wins, "recent_games": len(recent), "pt_diff_4g": pt_diff,
            })

        scored.sort(key=lambda x: x["composite"], reverse=True)
        return {s["team_id"]: {**s, "rank": i + 1} for i, s in enumerate(scored)}

    current = _compute(week)
    prev    = _compute(max(1, week - 1)) if week > 1 else {}

    result = []
    for tid, data in sorted(current.items(), key=lambda x: x[1]["rank"]):
        rank        = data["rank"]
        rank_change = (prev[tid]["rank"] - rank) if (prev and tid in prev) else 0
        trend       = "rising" if rank_change > 3 else "falling" if rank_change < -3 else "neutral"
        if rank <= 5:               implication = "Strong offense — start their skill players"
        elif rank >= 28:            implication = "Weak defense — target opposing players"
        elif trend == "rising":     implication = "Trending up — matchup-based starts"
        elif trend == "falling":    implication = "Struggling recently — proceed with caution"
        else:                       implication = "Mid-tier team — rely on matchup"

        result.append({
            "rank": rank, "rank_change": rank_change, "trend": trend,
            "team_abbr": data["team_abbr"], "team_name": data["team_name"],
            "conference": data["conference"],
            "composite_score": round(data["composite"], 3),
            "recent_wins": data["recent_wins"], "recent_games": data["recent_games"],
            "pt_diff_4g": data["pt_diff_4g"], "implication": implication,
        })

    return {"week": week, "season": season, "rankings": result}


# ── Fantasy Roster Import by Names ──────────────────────────

@app.post("/api/fantasy/roster/import-by-names", tags=["fantasy"])
def import_roster_by_names(req: ImportByNamesRequest, db: Database = Depends(get_db)):
    """Fuzzy-match player names and return matched/unmatched lists for confirmation."""
    matched, unmatched = [], []
    for raw in req.names:
        name = raw.strip()
        if not name:
            continue
        rows = db.fetchall(
            """
            SELECT p.player_id, p.full_name, p.position, t.abbreviation AS team_abbr
            FROM players p
            LEFT JOIN roster_entries re ON re.player_id = p.player_id AND re.season = ?
            LEFT JOIN teams t ON t.team_id = re.team_id
            WHERE LOWER(p.full_name) LIKE LOWER(?) ORDER BY re.season DESC LIMIT 1
            """,
            (req.season, f"%{name}%"),
        )
        if not rows:
            last = name.split()[-1]
            rows = db.fetchall(
                """
                SELECT p.player_id, p.full_name, p.position, t.abbreviation AS team_abbr
                FROM players p
                LEFT JOIN roster_entries re ON re.player_id = p.player_id AND re.season = ?
                LEFT JOIN teams t ON t.team_id = re.team_id
                WHERE LOWER(p.full_name) LIKE LOWER(?) ORDER BY re.season DESC LIMIT 1
                """,
                (req.season, f"%{last}%"),
            )
        if rows:
            r = rows[0]
            matched.append({
                "input_name": name, "player_id": r["player_id"],
                "full_name": r["full_name"], "position": r["position"], "team_abbr": r["team_abbr"],
            })
        else:
            unmatched.append(name)
    return {"matched": matched, "unmatched": unmatched}


# ── Fantasy Trade Values ─────────────────────────────────────

@app.get("/api/fantasy/trade-values", tags=["fantasy"])
def get_trade_values(week: int = Query(...), season: int = Query(2024), db: Database = Depends(get_db)):
    """ROS trade values: sum projected_points_ppr for weeks >= current_week."""
    rows = db.fetchall(
        """
        SELECT fp.player_id, p.full_name, p.position, p.headshot_url,
               t.abbreviation AS team_abbr,
               SUM(fp.projected_points_ppr) AS ros_projected,
               AVG(fp.matchup_score)        AS avg_matchup_score,
               COUNT(*)                     AS weeks_remaining
        FROM fantasy_projections fp
        JOIN players p ON p.player_id = fp.player_id
        LEFT JOIN roster_entries re ON re.player_id = fp.player_id AND re.season = fp.season
        LEFT JOIN teams t ON t.team_id = re.team_id
        WHERE fp.season = ? AND fp.week >= ?
        GROUP BY fp.player_id, p.full_name, p.position, p.headshot_url, t.abbreviation
        ORDER BY ros_projected DESC LIMIT 100
        """,
        (season, week),
    )
    result = []
    for i, r in enumerate(rows, start=1):
        avg_ms = float(r["avg_matchup_score"] or 1.0)
        result.append({
            "rank": i, "player_id": r["player_id"], "full_name": r["full_name"],
            "position": r["position"], "team_abbr": r["team_abbr"], "headshot_url": r["headshot_url"],
            "ros_projected": round(float(r["ros_projected"] or 0), 1),
            "avg_matchup_score": round(avg_ms, 3),
            "weeks_remaining": r["weeks_remaining"],
            "schedule_difficulty": "easy" if avg_ms >= 1.1 else "hard" if avg_ms <= 0.9 else "neutral",
        })
    return {"week": week, "season": season, "players": result, "count": len(result)}


# ── Value Picks ────────────────────────────────────────

@app.get("/api/picks/value", response_model=ValuePicksResponse, tags=["predictions"])
def get_value_picks(
    min_edge: float = Query(0.04, description="Minimum abs edge to include (default 0.04 = 4pp)"),
    db: Database = Depends(get_db),
):
    """
    Return upcoming games where the model's predicted probability disagrees with
    Vegas implied probability by ≥ min_edge. Sorted by abs_edge descending.
    Vegas odds are display-only enrichment — never used as prediction input.
    """
    from datetime import datetime, timezone

    engine = get_engine()

    # Fetch upcoming games that have Vegas odds
    rows = db.fetchall(
        """
        SELECT g.game_id, g.date, g.season, g.week, g.game_type,
               g.home_team_id, g.away_team_id,
               ht.abbreviation AS home_abbr, at.abbreviation AS away_abbr,
               ht.name AS home_name, at.name AS away_name,
               go.home_implied_prob, go.away_implied_prob, go.opening_spread AS spread
        FROM games g
        JOIN teams ht ON g.home_team_id = ht.team_id
        JOIN teams at ON g.away_team_id = at.team_id
        JOIN game_odds go ON go.game_id = g.game_id
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
                home_team=d["home_abbr"],
                away_team=d["away_abbr"],
                current_season=d["season"],
                is_playoff=(d["game_type"] != "regular"),
                week=d["week"],
                use_ml=False,
            )
        except Exception:
            continue

        model_prob = prediction.home_win_probability
        vegas_prob = float(d["home_implied_prob"])
        edge = round(model_prob - vegas_prob, 4)
        abs_edge = abs(edge)

        if abs_edge < min_edge:
            continue

        edge_side = "home" if edge > 0 else "away"
        picks.append(
            ValuePick(
                game_id=d["game_id"],
                game_date=str(d["date"])[:10],
                home_team=d["home_abbr"],
                away_team=d["away_abbr"],
                model_home_prob=round(model_prob, 4),
                vegas_home_implied_prob=round(vegas_prob, 4),
                edge=edge,
                edge_side=edge_side,
                model_confidence=prediction.confidence.upper(),
                vegas_spread=float(d["spread"]) if d["spread"] is not None else None,
            )
        )

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
