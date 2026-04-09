"""Pydantic response/request schemas for the NFL API."""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


# ── Enums ──────────────────────────────────────────────

class ConferenceEnum(str, Enum):
    AFC = "AFC"
    NFC = "NFC"


class GameTypeEnum(str, Enum):
    REGULAR = "regular"
    PLAYOFF = "playoff"


class FactorTypeEnum(str, Enum):
    BETTER_DEFENSE = "better_defense"
    BAD_DEFENSE = "bad_defense"
    BETTER_OFFENSE = "better_offense"
    BAD_OFFENSE = "bad_offense"
    BETTER_QB = "better_qb"
    QB_STRUGGLES = "qb_struggles"
    TURNOVER_PRONE = "turnover_prone"
    TURNOVER_FORCING = "turnover_forcing"
    NOT_EFFICIENT = "not_efficient"
    HIGHLY_EFFICIENT = "highly_efficient"
    INJURY_IMPACT = "injury_impact"
    WEATHER_IMPACT = "weather_impact"
    COACHING_ADVANTAGE = "coaching_advantage"
    MOTIVATION_FACTOR = "motivation_factor"
    CUSTOM = "custom"


# ── Teams ──────────────────────────────────────────────

class TeamResponse(BaseModel):
    team_id: int
    name: str
    city: str
    conference: str
    division: str
    abbreviation: str
    franchise_id: Optional[str] = None
    active_from: Optional[int] = None
    active_until: Optional[int] = None

    class Config:
        from_attributes = True


class TeamListResponse(BaseModel):
    teams: List[TeamResponse]
    count: int


# ── Games ──────────────────────────────────────────────

class GameResponse(BaseModel):
    game_id: int
    date: str
    season: int
    week: str
    game_type: str
    home_team_id: int
    away_team_id: int
    home_team: Optional[str] = None
    home_abbr: Optional[str] = None
    away_team: Optional[str] = None
    away_abbr: Optional[str] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    winner: Optional[str] = None
    winner_abbr: Optional[str] = None
    winner_id: Optional[int] = None
    overtime: bool = False

    class Config:
        from_attributes = True


class GameListResponse(BaseModel):
    games: List[GameResponse]
    count: int
    team: Optional[str] = None


# ── Predictions ────────────────────────────────────────

class InlineFactor(BaseModel):
    factor_type: FactorTypeEnum
    team: str = Field(..., description="'home' or 'away'")
    impact_rating: int = Field(..., ge=-5, le=5)


class PredictionRequest(BaseModel):
    home_team: str = Field(..., description="Home team name, abbreviation, or city")
    away_team: str = Field(..., description="Away team name, abbreviation, or city")
    game_id: Optional[int] = Field(None, description="Game ID for factor lookup")
    apply_factors: bool = Field(True, description="Whether to apply game factors")
    factors: Optional[List[InlineFactor]] = Field(None, description="Inline factors to apply")


class AppliedFactor(BaseModel):
    factor_type: str
    team_abbr: Optional[str] = None
    impact_rating: int


class PredictionResponse(BaseModel):
    home_team: str
    away_team: str
    home_team_id: int
    away_team_id: int
    home_win_probability: float
    away_win_probability: float
    predicted_winner: str
    predicted_winner_probability: float
    confidence: str
    key_factors: List[str]
    factors_applied: List[AppliedFactor]


# ── Head-to-Head ───────────────────────────────────────

class H2HRequest(BaseModel):
    team1: str = Field(..., description="First team name/abbreviation")
    team2: str = Field(..., description="Second team name/abbreviation")
    limit: int = Field(10, description="Max games to return", ge=1, le=50)


class H2HResponse(BaseModel):
    team1_name: str
    team1_abbr: str
    team2_name: str
    team2_abbr: str
    team1_wins: int
    team2_wins: int
    ties: int
    total_games: int
    games: List[GameResponse]


# ── Team Stats ─────────────────────────────────────────

class TeamSeasonStatsResponse(BaseModel):
    team_id: int
    team_name: str
    season: int
    games_played: int
    wins: int
    losses: int
    ties: int
    win_percentage: float
    points_for: int
    points_against: int
    point_differential: int
    home_wins: int
    home_losses: int
    away_wins: int
    away_losses: int

    class Config:
        from_attributes = True


class TeamProfileStats(BaseModel):
    wins: int
    losses: int
    ties: int
    win_pct: float
    games_played: int
    points_for: int
    points_against: int
    point_differential: int
    home_wins: int
    home_losses: int
    away_wins: int
    away_losses: int
    ppg: float
    papg: float


class TeamProfileResponse(BaseModel):
    team_id: int
    team_name: str
    team_abbr: str
    all_time: TeamProfileStats
    last_season: Optional[TeamProfileStats] = None
    last_season_year: Optional[int] = None


class TeamMetricsResponse(BaseModel):
    team_id: int
    team_name: str
    team_abbr: str
    current_season_wins: int
    current_season_losses: int
    current_season_ties: int
    win_percentage: float
    avg_points_scored: float
    avg_points_allowed: float
    point_differential: int
    home_wins: int
    home_losses: int
    away_wins: int
    away_losses: int
    home_win_pct: float
    away_win_pct: float
    recent_wins: int
    recent_losses: int
    recent_win_pct: float
    offensive_strength: float
    defensive_strength: float
    strength_of_schedule: float
    dynamic_hfa: float
    rest_days: int
    games_analyzed: int


# ── Factors ────────────────────────────────────────────

class FactorRequest(BaseModel):
    game_id: int
    team_id: int
    factor_type: FactorTypeEnum
    description: Optional[str] = None
    impact_rating: int = Field(..., ge=-5, le=5)


class FactorResponse(BaseModel):
    factor_id: int
    game_id: int
    team_id: int
    team_name: Optional[str] = None
    factor_type: str
    description: Optional[str] = None
    impact_rating: int


class FactorListResponse(BaseModel):
    factors: List[FactorResponse]
    count: int


# ── Scraping ───────────────────────────────────────────

class ScrapeRequest(BaseModel):
    start_year: int = Field(1990, ge=1960, le=2030)
    end_year: int = Field(2025, ge=1960, le=2030)


class ScrapeStatusResponse(BaseModel):
    completed_seasons: int
    total_games: int
    incomplete: List[dict]


# ── Accuracy / Backtesting ─────────────────────────────

class AccuracyResponse(BaseModel):
    seasons: List[int]
    total_games: int
    correct_predictions: int
    accuracy: float
    by_confidence: dict
    calibration: dict
    season_accuracy: dict


# ── Prediction History ────────────────────────────────

class PredictionHistoryItem(BaseModel):
    id: int
    home_abbr: str
    away_abbr: str
    home_team: str
    away_team: str
    predicted_winner_abbr: str
    home_prob: float
    away_prob: float
    confidence: str
    predicted_at: str
    actual_winner_abbr: Optional[str] = None
    correct: Optional[bool] = None


class PredictionHistoryResponse(BaseModel):
    predictions: List[PredictionHistoryItem]
    total: int
    resolved: int
    correct: int
    accuracy: Optional[float] = None


# ── General ────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: str
    total_teams: int
    total_games: int
    database: str
