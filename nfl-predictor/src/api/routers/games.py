"""Game-related API endpoints."""

import logging
import math
import random
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..deps import get_db, get_engine
from ..helpers import row_to_game, build_injury_list, build_weather_response
from ..schemas import (
    GameListResponse, GameOddsResponse,
    GameConditionsResponse, ConditionsSummary, WeatherResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["games"])

# Average NFL game total ~44 pts, std dev ~10 pts
_AVG_TOTAL = 44.0
_TOTAL_STD = 10.0
_HOME_SHARE = 0.536   # home teams score ~53.6% of points historically


class SimulateRequest(BaseModel):
    home_team: str = Field(..., max_length=50)
    away_team: str = Field(..., max_length=50)
    n: int = Field(1000, ge=100, le=5000)


@router.get("/api/games", response_model=GameListResponse)
def list_games(
    season: Optional[int] = Query(None),
    game_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db=Depends(get_db),
):
    if season:
        games = db.get_games_by_season(season, game_type)
    elif game_type:
        games = db.fetchall(
            "SELECT * FROM game_details WHERE game_type = ? ORDER BY date DESC LIMIT ?",
            (game_type, limit),
        )
    else:
        games = db.fetchall(
            "SELECT * FROM game_details ORDER BY date DESC LIMIT ?",
            (limit,),
        )
    return GameListResponse(games=[row_to_game(g) for g in games], count=len(games))


@router.get("/api/games/{game_id}/odds", response_model=GameOddsResponse)
def get_game_odds(game_id: int, db=Depends(get_db)):
    odds = db.get_odds_for_game(game_id)
    if not odds:
        raise HTTPException(status_code=404, detail=f"No odds found for game {game_id}")
    return GameOddsResponse(**dict(odds))


@router.post("/api/games/simulate")
def simulate_game(req: SimulateRequest, db=Depends(get_db)):
    """
    Monte Carlo simulation: run N games between two teams.

    Each simulation:
    1. Gets base home_win_probability from the prediction engine (weighted-sum).
    2. Adds Gaussian noise (σ=0.06) to model uncertainty.
    3. Samples a winner, then samples a total score from N(avg_total, total_std)
       and splits it proportionally to the win probability.

    Returns win rates, average scores, and std deviations.
    """
    engine = get_engine()
    try:
        base_pred = engine.predict(
            home_team=req.home_team, away_team=req.away_team, use_ml=False
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    base_home_prob = base_pred.home_win_probability
    home_name = base_pred.home_team
    away_name = base_pred.away_team

    # Find team abbreviations
    home_team = db.find_team(req.home_team)
    away_team = db.find_team(req.away_team)
    home_abbr = home_team["abbreviation"] if home_team else req.home_team
    away_abbr = away_team["abbreviation"] if away_team else req.away_team

    # Use predicted spread to calibrate scoring if available
    predicted_spread = base_pred.predicted_spread  # home-relative (negative = home favored)

    home_wins = 0
    home_scores: list[float] = []
    away_scores: list[float] = []

    rng = random.Random()  # local RNG for reproducibility independence

    for _ in range(req.n):
        # Add model uncertainty noise
        noisy_prob = max(0.05, min(0.95, base_home_prob + rng.gauss(0, 0.06)))

        # Sample total from game score distribution
        total = rng.gauss(_AVG_TOTAL, _TOTAL_STD)
        total = max(14, total)  # minimum realistic total

        # If spread model gave a prediction, use it to calibrate score split
        if predicted_spread is not None:
            # spread = home_score - away_score (negative means home favored)
            half = total / 2.0
            home_s = half - predicted_spread / 2.0
            away_s = half + predicted_spread / 2.0
        else:
            # Split proportional to win probability
            home_s = total * noisy_prob
            away_s = total * (1.0 - noisy_prob)

        # Add game-level variance
        home_s = max(0, home_s + rng.gauss(0, 4))
        away_s = max(0, away_s + rng.gauss(0, 4))

        # Round to whole points
        home_int = round(home_s)
        away_int = round(away_s)

        home_scores.append(home_int)
        away_scores.append(away_int)
        if home_int > away_int:
            home_wins += 1
        elif away_int > home_int:
            pass  # away win
        else:
            # Tie — overtime; slight edge to home team
            if rng.random() < 0.52:
                home_wins += 1

    n = req.n
    home_win_pct = home_wins / n
    avg_home = sum(home_scores) / n
    avg_away = sum(away_scores) / n
    std_home = math.sqrt(sum((s - avg_home) ** 2 for s in home_scores) / n)
    std_away = math.sqrt(sum((s - avg_away) ** 2 for s in away_scores) / n)

    return {
        "home_team": home_name,
        "away_team": away_name,
        "home_team_abbr": home_abbr,
        "away_team_abbr": away_abbr,
        "n_simulations": n,
        "home_wins": home_wins,
        "away_wins": n - home_wins,
        "home_win_pct": round(home_win_pct, 4),
        "away_win_pct": round(1.0 - home_win_pct, 4),
        "avg_home_score": round(avg_home, 1),
        "avg_away_score": round(avg_away, 1),
        "std_home_score": round(std_home, 1),
        "std_away_score": round(std_away, 1),
    }


@router.get("/api/games/{game_id}/conditions", response_model=GameConditionsResponse)
def get_game_conditions(game_id: int, db=Depends(get_db)):
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

    home_injuries = build_injury_list(db.get_key_injuries_for_team(home_team_id))
    away_injuries = build_injury_list(db.get_key_injuries_for_team(away_team_id))

    weather_row = db.get_weather_for_game(game_id)
    if not weather_row:
        weather_row = db.get_weather_for_teams(home_team_id, str(game_d["date"]))

    weather: Optional[WeatherResponse] = None
    if weather_row:
        weather = build_weather_response(weather_row)

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
