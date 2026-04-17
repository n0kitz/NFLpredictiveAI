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
    current_season: Optional[int] = None
    is_playoff: bool = False
    week: int = 0


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
    predicted_spread: Optional[float] = None
    vegas_context: Optional["VegasContext"] = None
    conditions: Optional["ConditionsSummary"] = None


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


# ── Vegas Odds ─────────────────────────────────────────

class GameOddsResponse(BaseModel):
    id: int
    game_id: Optional[int] = None
    external_game_id: Optional[str] = None
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    game_date: Optional[str] = None
    opening_spread: Optional[float] = None
    over_under: Optional[float] = None
    home_implied_prob: Optional[float] = None
    away_implied_prob: Optional[float] = None
    fetched_at: Optional[str] = None

    class Config:
        from_attributes = True


class VegasContext(BaseModel):
    spread: Optional[float] = Field(None, description="Home-team spread (negative = home favoured)")
    over_under: Optional[float] = None
    home_implied_prob: Optional[float] = None
    away_implied_prob: Optional[float] = None
    fetched_at: Optional[str] = None


# ── Model info ─────────────────────────────────────────

class ModelInfoResponse(BaseModel):
    model_type: str                         # always "weighted_sum" (default)
    active_model: str = "weighted_sum"
    ml_model_loaded: bool
    ml_available: bool = False
    feature_count: Optional[int] = None
    model_file_exists: bool
    ml_oos_accuracy: Optional[float] = None
    weighted_sum_oos_accuracy: Optional[float] = None
    recommendation: Optional[str] = None
    spread_model_loaded: bool = False
    spread_model_mae: Optional[float] = None
    vegas_feature_removed: bool = True


# ── Injuries / Weather / Conditions ────────────────────

class InjuryEntry(BaseModel):
    player_name: str
    position: str
    injury_status: str
    report_date: str


class WeatherResponse(BaseModel):
    is_dome: bool
    condition: str
    temperature_c: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    precipitation_mm: Optional[float] = None
    weather_code: Optional[int] = None
    is_adverse: bool = False


class ConditionsSummary(BaseModel):
    home_injuries: List[InjuryEntry] = []
    away_injuries: List[InjuryEntry] = []
    weather: Optional[WeatherResponse] = None


class GameConditionsResponse(BaseModel):
    game_id: int
    home_team: str
    away_team: str
    conditions: ConditionsSummary


# ── SHAP Explanation ───────────────────────────────────

class ExplanationEntry(BaseModel):
    feature: str
    label: str
    shap_value: float
    direction: str  # "home" | "away" | "neutral"
    feature_value: float


class ExplainPredictionResponse(PredictionResponse):
    explanation: List[ExplanationEntry] = []


# ── Roster / Players ───────────────────────────────────

class PlayerStatsEntry(BaseModel):
    games_played: int = 0
    pass_attempts: int = 0
    pass_completions: int = 0
    pass_yards: int = 0
    pass_tds: int = 0
    interceptions: int = 0
    passer_rating: float = 0.0
    rush_attempts: int = 0
    rush_yards: int = 0
    rush_tds: int = 0
    yards_per_carry: float = 0.0
    targets: int = 0
    receptions: int = 0
    rec_yards: int = 0
    rec_tds: int = 0
    yards_per_reception: float = 0.0
    fantasy_points_ppr: float = 0.0
    fantasy_points_standard: float = 0.0


class PlayerEntry(BaseModel):
    player_id: int
    espn_id: Optional[str] = None
    full_name: str
    position: Optional[str] = None
    jersey_number: Optional[str] = None
    depth_position: Optional[str] = None
    is_starter: bool = False
    roster_status: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    college: Optional[str] = None
    experience_years: int = 0
    headshot_url: Optional[str] = None
    stats: Optional[PlayerStatsEntry] = None


class TeamRosterResponse(BaseModel):
    team_id: int
    team_abbr: str
    season: int
    players: List[PlayerEntry]
    count: int


class PlayerProfile(BaseModel):
    player_id: int
    espn_id: Optional[str] = None
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    position: Optional[str] = None
    jersey_number: Optional[str] = None
    date_of_birth: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    college: Optional[str] = None
    experience_years: int = 0
    status: Optional[str] = None
    headshot_url: Optional[str] = None
    team_abbr: Optional[str] = None
    current_stats: Optional[PlayerStatsEntry] = None


class PlayerSearchResult(BaseModel):
    player_id: int
    full_name: str
    position: Optional[str] = None
    team_abbr: Optional[str] = None
    jersey_number: Optional[str] = None
    headshot_url: Optional[str] = None


# ── Fantasy ────────────────────────────────────────────

class FantasyPlayerEntry(BaseModel):
    player_id: int
    full_name: str
    position: Optional[str] = None
    team_abbr: Optional[str] = None
    headshot_url: Optional[str] = None
    games_played: int = 0
    fantasy_points_ppr: float = 0.0
    fantasy_points_standard: float = 0.0
    points_per_game_ppr: float = 0.0


class FantasyLeaderboardResponse(BaseModel):
    position: str
    season: int
    scoring: str
    players: List[FantasyPlayerEntry]
    count: int


# ── Fantasy (extended) ─────────────────────────────────

class FantasyProjectionEntry(BaseModel):
    player_id: int
    full_name: str
    position: Optional[str] = None
    team_abbr: Optional[str] = None
    headshot_url: Optional[str] = None
    week: int
    season: int
    projected_points_ppr: float = 0.0
    projected_points_std: float = 0.0
    matchup_score: float = 1.0
    opportunity_score: float = 0.0
    confidence: str = 'medium'
    injury_status: Optional[str] = None
    weather_impact: bool = False


class StartSitPlayerEntry(BaseModel):
    player_id: int
    full_name: str
    position: Optional[str] = None
    team_abbr: Optional[str] = None
    headshot_url: Optional[str] = None
    projected_points_ppr: float
    matchup_score: float
    reasoning: str


class StartSitResponse(BaseModel):
    start: StartSitPlayerEntry
    sit: StartSitPlayerEntry
    confidence: str


class DraftRankingEntry(BaseModel):
    player_id: int
    full_name: str
    position: Optional[str] = None
    team_abbr: Optional[str] = None
    headshot_url: Optional[str] = None
    overall_rank: int
    position_rank: int
    tier: int
    adp: float
    projected_season_points: float
    season: int
    scoring_format: str


class TradePlayerEntry(BaseModel):
    player_id: int
    full_name: str
    position: Optional[str] = None
    team_abbr: Optional[str] = None
    headshot_url: Optional[str] = None
    ros_projected: float


class TradeAnalysisResponse(BaseModel):
    give: List[TradePlayerEntry]
    get: List[TradePlayerEntry]
    give_total: float
    get_total: float
    verdict: str  # 'WIN', 'LOSE', or 'FAIR'
    delta: float


class FantasyRosterRequest(BaseModel):
    league_id: int
    player_ids: List[int]
    slots: List[str]


class TradeAnalyzeRequest(BaseModel):
    give_player_ids: List[int]
    get_player_ids: List[int]
    week: int
    season: int = 2024


class ImportByNamesRequest(BaseModel):
    names: List[str]
    season: int = 2024


# ── Value Picks ────────────────────────────────────────

class ValuePick(BaseModel):
    game_id: int
    game_date: str
    home_team: str
    away_team: str
    model_home_prob: float
    vegas_home_implied_prob: float
    edge: float
    edge_side: str           # "home" or "away"
    model_confidence: str    # "HIGH" / "MEDIUM" / "LOW"
    vegas_spread: Optional[float] = None


class ValuePicksResponse(BaseModel):
    picks: List[ValuePick]
    generated_at: str
    note: str


# ── General ────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: str
    total_teams: int
    total_games: int
    database: str
