"""Game-related API endpoints."""

import logging
import math
import random
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from ..deps import get_db, get_engine
from ..helpers import row_to_game, build_injury_list, build_weather_response
from ..schemas import (
    GameListResponse, GameOddsResponse,
    GameConditionsResponse, ConditionsSummary, WeatherResponse,
    GameDetailResponse, GameBoxScorePlayer, GameFactorEntry,
    GameRetrodictionResponse,
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


def _box_player(row, home_team_id: int) -> GameBoxScorePlayer:
    """Build a box-score entry from a player_weekly_stats join row."""
    r = dict(row)
    return GameBoxScorePlayer(
        player_id=r["player_id"],
        full_name=r.get("full_name") or "",
        position=r.get("position"),
        team_id=r["team_id"],
        team_abbr=r.get("team_abbr"),
        headshot_url=r.get("headshot_url"),
        is_home=(r["team_id"] == home_team_id),
        pass_completions=int(r.get("pass_completions") or 0),
        pass_attempts=int(r.get("pass_attempts") or 0),
        pass_yards=int(r.get("pass_yards") or 0),
        pass_tds=int(r.get("pass_tds") or 0),
        interceptions=int(r.get("interceptions") or 0),
        rush_attempts=int(r.get("rush_attempts") or 0),
        rush_yards=int(r.get("rush_yards") or 0),
        rush_tds=int(r.get("rush_tds") or 0),
        targets=int(r.get("targets") or 0),
        receptions=int(r.get("receptions") or 0),
        rec_yards=int(r.get("rec_yards") or 0),
        rec_tds=int(r.get("rec_tds") or 0),
        fantasy_points_ppr=float(r.get("fantasy_points_ppr") or 0.0),
    )


@router.get("/api/games/{game_id}", response_model=GameDetailResponse)
def get_game_detail(
    game_id: int = Path(..., ge=1, le=9_223_372_036_854_775_807),
    db=Depends(get_db),
):
    """Full detail for a single game: meta + odds + weather + factors + box score.

    Odds/weather/box-score are display-only enrichment. The box score comes from
    player_weekly_stats (regular-season weeks, 2018+); other games return empty
    box lists with ``box_score_available=False``.
    """
    game = db.get_game_detail(game_id)
    if not game:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

    g = dict(game)
    home_id = g["home_team_id"]
    away_id = g["away_team_id"]
    base = row_to_game(game)

    # Odds (game_id match first, then team+date window)
    odds_row = db.get_odds_for_game(game_id)
    if not odds_row:
        odds_row = db.get_odds_for_teams(home_id, away_id, str(g.get("date", "")))
    odds = GameOddsResponse(**dict(odds_row)) if odds_row else None

    # Weather (game_id match first, then home-team+date)
    weather_row = db.get_weather_for_game(game_id)
    if not weather_row:
        weather_row = db.get_weather_for_teams(home_id, str(g.get("date", "")))
    weather = build_weather_response(weather_row) if weather_row else None

    # Manual game factors
    factors = [
        GameFactorEntry(
            team_abbr=r["team_abbr"],
            team_name=r["team_name"],
            factor_type=r["factor_type"],
            factor_value=r["factor_value"],
            impact_rating=r["impact_rating"],
        )
        for r in db.get_game_factors(game_id)
    ]

    # Box score — only for numeric (regular-season) weeks present in player_weekly_stats
    home_box: list = []
    away_box: list = []
    box_available = False
    week_raw = str(g.get("week", ""))
    if week_raw.isdigit():
        rows = db.get_game_box_score(g["season"], int(week_raw), home_id, away_id)
        box_available = len(rows) > 0
        for r in rows:
            entry = _box_player(r, home_id)
            (home_box if r["team_id"] == home_id else away_box).append(entry)

    return GameDetailResponse(
        **base.model_dump(),
        odds=odds,
        weather=weather,
        factors=factors,
        home_box=home_box,
        away_box=away_box,
        box_score_available=box_available,
    )


@router.get("/api/games/{game_id}/retrodiction", response_model=GameRetrodictionResponse)
def get_game_retrodiction(
    game_id: int = Path(..., ge=1, le=9_223_372_036_854_775_807),
    db=Depends(get_db),
):
    """Run the prediction engine as-of game day for a played game.

    Uses cutoff_date = game date so only pre-game data feeds the metrics —
    the exact configuration the backtester measures OOS accuracy with
    (weighted-sum, no manual factors, no ML). Compares against the actual
    winner to report a hit/miss.
    """
    game = db.get_game_detail(game_id)
    if not game:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    g = dict(game)
    if g.get("home_score") is None:
        raise HTTPException(
            status_code=400,
            detail="Game not played yet — use /api/predict for upcoming games",
        )

    engine = get_engine()
    game_date = str(g.get("date", ""))[:10]
    try:
        pred = engine.predict(
            home_team=g["home_abbr"],
            away_team=g["away_abbr"],
            apply_factors=False,
            current_season=g["season"],
            cutoff_date=game_date or None,
            is_playoff=(g.get("game_type", "regular") != "regular"),
            week=g.get("week", 0),
            use_ml=False,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    home_predicted = pred.home_win_probability > pred.away_win_probability
    predicted_winner_id = g["home_team_id"] if home_predicted else g["away_team_id"]
    predicted_winner_abbr = g["home_abbr"] if home_predicted else g["away_abbr"]

    winner_id = g.get("winner_id")
    actual_winner_abbr = None
    correct = None
    if winner_id is not None:
        actual_winner_abbr = g["home_abbr"] if winner_id == g["home_team_id"] else g["away_abbr"]
        correct = predicted_winner_id == winner_id

    return GameRetrodictionResponse(
        game_id=game_id,
        season=g["season"],
        week=str(g.get("week", "")),
        cutoff_date=game_date,
        home_abbr=g["home_abbr"],
        away_abbr=g["away_abbr"],
        home_prob=round(pred.home_win_probability, 4),
        away_prob=round(pred.away_win_probability, 4),
        predicted_winner_abbr=predicted_winner_abbr,
        predicted_winner_prob=round(pred.predicted_winner_probability, 4),
        confidence=pred.confidence,
        predicted_spread=pred.predicted_spread,
        actual_winner_abbr=actual_winner_abbr,
        actual_margin=int(g["home_score"]) - int(g["away_score"]),
        correct=correct,
        key_factors=list(pred.key_factors or [])[:6],
    )


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
