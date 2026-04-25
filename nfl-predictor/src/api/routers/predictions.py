"""Prediction-related API endpoints."""

import logging
from typing import Optional
from datetime import date as _date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..deps import get_db, get_engine
from ..helpers import row_to_game, build_injury_list, build_weather_response
from ..schemas import (
    PredictionRequest, PredictionResponse, AppliedFactor,
    H2HResponse, ExplainPredictionResponse, ExplanationEntry,
    PredictionHistoryItem, PredictionHistoryResponse,
    VegasContext, ConditionsSummary, WeatherResponse,
)
from ...database.models import GameFactor, FactorType
from ...prediction.metrics import calculate_head_to_head

logger = logging.getLogger(__name__)
router = APIRouter(tags=["predictions"])
limiter = Limiter(key_func=get_remote_address)


def _build_factors_applied(prediction):
    return [
        AppliedFactor(
            factor_type=f.factor_type.value,
            team_abbr=f.team_abbr,
            impact_rating=f.impact_rating,
        )
        for f in prediction.factors_applied
    ]


@router.post("/api/predict", response_model=PredictionResponse)
@limiter.limit("30/minute")
def predict_game(
    request: Request,
    req: PredictionRequest,
    model: Optional[str] = Query(None),
    db=Depends(get_db),
):
    from ..schemas import InlineFactor
    from ...prediction.factors import apply_game_factors as _apply_factors

    engine = get_engine()
    use_ml = (model == "ml")
    use_ensemble = (model == "ensemble")
    try:
        prediction = engine.predict(
            home_team=req.home_team,
            away_team=req.away_team,
            game_id=req.game_id,
            apply_factors=req.apply_factors,
            use_ml=use_ml,
            use_ensemble=use_ensemble,
            current_season=req.current_season,
            is_playoff=req.is_playoff,
            week=req.week,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    if req.factors:
        inline_game_factors = []
        for f in req.factors:
            team_id = prediction.home_team_id if f.team == "home" else prediction.away_team_id
            inline_game_factors.append(
                GameFactor(
                    factor_id=0, game_id=0, team_id=team_id,
                    factor_type=FactorType(f.factor_type.value),
                    impact_rating=f.impact_rating,
                )
            )
        if inline_game_factors:
            prediction = _apply_factors(prediction, inline_game_factors)

    factors_applied = _build_factors_applied(prediction)

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
    except Exception as e:
        logger.warning("Failed to save prediction history: %s", e)

    vegas_context: Optional[VegasContext] = None
    try:
        today = str(_date.today())
        odds_row = db.get_odds_for_teams(prediction.home_team_id, prediction.away_team_id, today)
        if odds_row:
            odds_d = dict(odds_row)
            vegas_context = VegasContext(
                spread=odds_d.get("opening_spread"),
                over_under=odds_d.get("over_under"),
                home_implied_prob=odds_d.get("home_implied_prob"),
                away_implied_prob=odds_d.get("away_implied_prob"),
                fetched_at=odds_d.get("fetched_at"),
            )
    except Exception as e:
        logger.warning("Failed to load vegas context: %s", e)

    conditions = None
    try:
        today_str = str(_date.today())
        window_end = str(_date.today() + timedelta(days=14))
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
                w_row = db.get_weather_for_teams(prediction.home_team_id, str(upcoming["date"]))
            if w_row:
                weather = build_weather_response(w_row)

        if home_inj or away_inj or weather:
            conditions = ConditionsSummary(
                home_injuries=build_injury_list(home_inj),
                away_injuries=build_injury_list(away_inj),
                weather=weather,
            )
    except Exception as e:
        logger.warning("Failed to load game conditions: %s", e)

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


@router.get("/api/predict/{away_team}/{home_team}", response_model=PredictionResponse)
def predict_game_get(
    away_team: str = Path(..., max_length=10),
    home_team: str = Path(..., max_length=10),
    model: Optional[str] = Query(None),
    db=Depends(get_db),
):
    engine = get_engine()
    use_ml = (model == "ml")
    use_ensemble = (model == "ensemble")
    try:
        prediction = engine.predict(
            home_team=home_team, away_team=away_team,
            use_ml=use_ml, use_ensemble=use_ensemble,
            current_season=None, is_playoff=False, week=0,
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


@router.post("/api/predict/explain", response_model=ExplainPredictionResponse)
def explain_prediction_endpoint(req: PredictionRequest, db=Depends(get_db)):
    from ...prediction.factors import apply_game_factors as _apply_factors

    engine = get_engine()
    try:
        prediction = engine.predict(
            home_team=req.home_team, away_team=req.away_team,
            game_id=req.game_id, apply_factors=req.apply_factors, use_ml=False,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if req.factors:
        inline_game_factors = []
        for f in req.factors:
            team_id = prediction.home_team_id if f.team == "home" else prediction.away_team_id
            inline_game_factors.append(
                GameFactor(
                    factor_id=0, game_id=0, team_id=team_id,
                    factor_type=FactorType(f.factor_type.value),
                    impact_rating=f.impact_rating,
                )
            )
        if inline_game_factors:
            prediction = _apply_factors(prediction, inline_game_factors)

    factors_applied = _build_factors_applied(prediction)

    try:
        explanation_data = engine.explain_prediction(
            home_team=req.home_team, away_team=req.away_team,
        )
    except Exception as e:
        logger.warning("SHAP explanation failed: %s", e)
        explanation_data = []

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
        explanation=[
            ExplanationEntry(
                feature=e["feature"], label=e["label"],
                shap_value=e["shap_value"], direction=e["direction"],
                feature_value=e["feature_value"],
            )
            for e in explanation_data
        ],
    )


@router.get("/api/h2h/{team1}/{team2}", response_model=H2HResponse, tags=["head-to-head"])
def head_to_head(
    team1: str = Path(..., max_length=10),
    team2: str = Path(..., max_length=10),
    limit: int = Query(10, ge=1, le=50),
    db=Depends(get_db),
):
    t1 = db.find_team(team1)
    t2 = db.find_team(team2)
    if not t1:
        raise HTTPException(status_code=404, detail=f"Team not found: {team1}")
    if not t2:
        raise HTTPException(status_code=404, detail=f"Team not found: {team2}")

    h2h = calculate_head_to_head(db, t1["team_id"], t2["team_id"], limit)
    return H2HResponse(
        team1_name=f"{t1['city']} {t1['name']}", team1_abbr=t1["abbreviation"],
        team2_name=f"{t2['city']} {t2['name']}", team2_abbr=t2["abbreviation"],
        team1_wins=h2h["team1_wins"], team2_wins=h2h["team2_wins"],
        ties=h2h["ties"], total_games=h2h["total_games"],
        games=[row_to_game(g) for g in h2h["games"]],
    )


@router.get("/api/predictions/history", response_model=PredictionHistoryResponse)
def prediction_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db=Depends(get_db),
):
    rows = db.get_prediction_history(limit=limit, offset=offset)
    stats = db.get_prediction_history_stats()

    predictions = []
    for r in rows:
        d = dict(r)
        predictions.append(PredictionHistoryItem(
            id=d["id"],
            home_abbr=d["home_abbr"], away_abbr=d["away_abbr"],
            home_team=d["home_team"], away_team=d["away_team"],
            predicted_winner_abbr=d["predicted_winner_abbr"],
            home_prob=round(d["home_prob"], 4), away_prob=round(d["away_prob"], 4),
            confidence=d["confidence"],
            predicted_at=str(d["predicted_at"]),
            actual_winner_abbr=d.get("actual_winner_abbr"),
            correct=bool(d["correct"]) if d["correct"] is not None else None,
        ))

    total = stats["total"] if stats else 0
    resolved = stats["resolved"] if stats else 0
    correct = stats["correct"] if stats else 0

    return PredictionHistoryResponse(
        predictions=predictions, total=total, resolved=resolved, correct=correct,
        accuracy=round(correct / resolved, 4) if resolved > 0 else None,
    )


@router.post("/api/predictions/enrich")
def enrich_predictions(db=Depends(get_db)):
    count = db.enrich_prediction_history()
    return {"enriched": count}
