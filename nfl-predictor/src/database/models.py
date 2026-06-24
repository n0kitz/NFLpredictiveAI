"""Data models for NFL Prediction System."""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, List
from enum import Enum


class Conference(Enum):
    """NFL Conference."""
    AFC = "AFC"
    NFC = "NFC"


class GameType(Enum):
    """Type of NFL game."""
    REGULAR = "regular"
    PLAYOFF = "playoff"


class FactorType(Enum):
    """Types of game factors that can affect predictions."""
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


@dataclass
class Team:
    """NFL Team data model."""
    team_id: int
    name: str
    city: str
    conference: Conference
    division: str
    abbreviation: str
    franchise_id: Optional[str] = None
    active_from: Optional[int] = None
    active_until: Optional[int] = None

    @classmethod
    def from_row(cls, row) -> 'Team':
        """Create Team from database row."""
        return cls(
            team_id=row['team_id'],
            name=row['name'],
            city=row['city'],
            conference=Conference(row['conference']),
            division=row['division'],
            abbreviation=row['abbreviation'],
            franchise_id=row['franchise_id'],
            active_from=row['active_from'],
            active_until=row['active_until']
        )

    @property
    def full_name(self) -> str:
        """Return full team name (city + name)."""
        return f"{self.city} {self.name}"

    @property
    def is_active(self) -> bool:
        """Check if team is currently active."""
        return self.active_until is None


@dataclass
class Game:
    """NFL Game data model."""
    game_id: int
    date: date
    season: int
    week: str
    game_type: GameType
    home_team_id: int
    away_team_id: int
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    winner_id: Optional[int] = None
    venue: Optional[str] = None
    attendance: Optional[int] = None
    overtime: bool = False

    # Optional populated team data
    home_team: Optional[str] = None
    home_abbr: Optional[str] = None
    away_team: Optional[str] = None
    away_abbr: Optional[str] = None
    winner: Optional[str] = None
    winner_abbr: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> 'Game':
        """Create Game from database row."""
        return cls(
            game_id=row['game_id'],
            date=row['date'] if isinstance(row['date'], date) else date.fromisoformat(row['date']),
            season=row['season'],
            week=row['week'],
            game_type=GameType(row['game_type']),
            home_team_id=row['home_team_id'],
            away_team_id=row['away_team_id'],
            home_score=row['home_score'],
            away_score=row['away_score'],
            winner_id=row['winner_id'],
            venue=row.get('venue'),
            attendance=row.get('attendance'),
            overtime=bool(row.get('overtime', False)),
            home_team=row.get('home_team'),
            home_abbr=row.get('home_abbr'),
            away_team=row.get('away_team'),
            away_abbr=row.get('away_abbr'),
            winner=row.get('winner'),
            winner_abbr=row.get('winner_abbr')
        )

    @property
    def is_completed(self) -> bool:
        """Check if game has been played."""
        return self.home_score is not None and self.away_score is not None

    @property
    def is_tie(self) -> bool:
        """Check if game ended in a tie."""
        return self.is_completed and self.home_score == self.away_score

    @property
    def point_differential(self) -> Optional[int]:
        """Get point differential (home - away)."""
        if not self.is_completed:
            return None
        return self.home_score - self.away_score

    @property
    def total_points(self) -> Optional[int]:
        """Get total points scored."""
        if not self.is_completed:
            return None
        return self.home_score + self.away_score

    def get_team_score(self, team_id: int) -> Optional[int]:
        """Get score for a specific team."""
        if not self.is_completed:
            return None
        if team_id == self.home_team_id:
            return self.home_score
        elif team_id == self.away_team_id:
            return self.away_score
        return None

    def get_opponent_score(self, team_id: int) -> Optional[int]:
        """Get opponent's score for a specific team."""
        if not self.is_completed:
            return None
        if team_id == self.home_team_id:
            return self.away_score
        elif team_id == self.away_team_id:
            return self.home_score
        return None

    def team_won(self, team_id: int) -> Optional[bool]:
        """Check if a specific team won this game."""
        if not self.is_completed:
            return None
        return self.winner_id == team_id

    def team_was_home(self, team_id: int) -> bool:
        """Check if a specific team was the home team."""
        return team_id == self.home_team_id


@dataclass
class GameFactor:
    """Game factor that can affect predictions."""
    factor_id: int
    game_id: int
    team_id: int
    factor_type: FactorType
    factor_value: Optional[str] = None
    impact_rating: int = 0  # -5 to +5 scale
    team_name: Optional[str] = None
    team_abbr: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> 'GameFactor':
        """Create GameFactor from database row."""
        return cls(
            factor_id=row['factor_id'],
            game_id=row['game_id'],
            team_id=row['team_id'],
            factor_type=FactorType(row['factor_type']),
            factor_value=row.get('factor_value'),
            impact_rating=row['impact_rating'],
            team_name=row.get('team_name'),
            team_abbr=row.get('team_abbr')
        )

    @property
    def is_positive(self) -> bool:
        """Check if factor has positive impact."""
        return self.impact_rating > 0

    @property
    def is_negative(self) -> bool:
        """Check if factor has negative impact."""
        return self.impact_rating < 0


@dataclass
class TeamSeasonStats:
    """Aggregated team statistics for a season."""
    team_id: int
    season: int
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    ties: int = 0
    points_for: int = 0
    points_against: int = 0
    point_differential: int = 0
    home_wins: int = 0
    home_losses: int = 0
    home_ties: int = 0
    away_wins: int = 0
    away_losses: int = 0
    away_ties: int = 0
    win_percentage: float = 0.0

    @classmethod
    def from_row(cls, row) -> 'TeamSeasonStats':
        """Create TeamSeasonStats from database row."""
        return cls(
            team_id=row['team_id'],
            season=row['season'],
            games_played=row['games_played'],
            wins=row['wins'],
            losses=row['losses'],
            ties=row['ties'],
            points_for=row['points_for'],
            points_against=row['points_against'],
            point_differential=row['point_differential'],
            home_wins=row['home_wins'],
            home_losses=row['home_losses'],
            home_ties=row.get('home_ties', 0),
            away_wins=row['away_wins'],
            away_losses=row['away_losses'],
            away_ties=row.get('away_ties', 0),
            win_percentage=row['win_percentage']
        )

    @property
    def record_str(self) -> str:
        """Get record as string (W-L or W-L-T)."""
        if self.ties > 0:
            return f"{self.wins}-{self.losses}-{self.ties}"
        return f"{self.wins}-{self.losses}"

    @property
    def home_record_str(self) -> str:
        """Get home record as string."""
        if self.home_ties > 0:
            return f"{self.home_wins}-{self.home_losses}-{self.home_ties}"
        return f"{self.home_wins}-{self.home_losses}"

    @property
    def away_record_str(self) -> str:
        """Get away record as string."""
        if self.away_ties > 0:
            return f"{self.away_wins}-{self.away_losses}-{self.away_ties}"
        return f"{self.away_wins}-{self.away_losses}"

    @property
    def points_per_game(self) -> float:
        """Calculate average points scored per game."""
        if self.games_played == 0:
            return 0.0
        return self.points_for / self.games_played

    @property
    def points_allowed_per_game(self) -> float:
        """Calculate average points allowed per game."""
        if self.games_played == 0:
            return 0.0
        return self.points_against / self.games_played

    @property
    def home_win_percentage(self) -> float:
        """Calculate home win percentage."""
        home_games = self.home_wins + self.home_losses + self.home_ties
        if home_games == 0:
            return 0.0
        return (self.home_wins + 0.5 * self.home_ties) / home_games

    @property
    def away_win_percentage(self) -> float:
        """Calculate away win percentage."""
        away_games = self.away_wins + self.away_losses + self.away_ties
        if away_games == 0:
            return 0.0
        return (self.away_wins + 0.5 * self.away_ties) / away_games


@dataclass
class Prediction:
    """Prediction result for a game."""
    home_team: str
    away_team: str
    home_team_id: int
    away_team_id: int
    home_win_probability: float
    away_win_probability: float
    confidence: str  # 'low', 'medium', 'high'
    key_factors: List[str] = field(default_factory=list)
    factors_applied: List[GameFactor] = field(default_factory=list)
    predicted_spread: Optional[float] = None

    @property
    def predicted_winner(self) -> str:
        """Get the predicted winner."""
        if self.home_win_probability > self.away_win_probability:
            return self.home_team
        return self.away_team

    @property
    def predicted_winner_probability(self) -> float:
        """Get probability of predicted winner."""
        return max(self.home_win_probability, self.away_win_probability)

    def format_output(self) -> str:
        """Format prediction for display."""
        lines = [
            f"\n{self.away_team} @ {self.home_team}",
            f"Prediction: {self.home_team} {self.home_win_probability:.0%} | "
            f"{self.away_team} {self.away_win_probability:.0%}",
            f"Confidence: {self.confidence.capitalize()}",
            "Key Factors:"
        ]

        for i, factor in enumerate(self.key_factors):
            prefix = "\u251c\u2500" if i < len(self.key_factors) - 1 else "\u2514\u2500"
            lines.append(f"{prefix} {factor}")

        if self.factors_applied:
            lines.append("\nApplied Game Factors:")
            for factor in self.factors_applied:
                sign = "+" if factor.impact_rating > 0 else ""
                lines.append(
                    f"  - {factor.team_abbr}: {factor.factor_type.value} "
                    f"({sign}{factor.impact_rating})"
                )
        else:
            lines.append("\n[No custom game factors applied - add factors for refined predictions]")

        return "\n".join(lines)


# ── Roster / enrichment entities ────────────────────────────────────────────
# The DB layer returns these as raw ``sqlite3.Row`` for performance and to keep
# bracket-access call sites unchanged. The dataclasses below are opt-in typed
# wrappers (``from_row``) for callers that want structured access / type hints.
# Note: ``sqlite3.Row`` has no ``.get()`` — use the helper for optional columns.


def _row_get(row, key, default=None):
    """Safe optional-column access for sqlite3.Row (which lacks ``.get()``)."""
    try:
        return row[key]
    except (IndexError, KeyError):
        return default


@dataclass
class Player:
    """Player bio (ESPN roster API)."""
    player_id: int
    full_name: str
    espn_id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    position: Optional[str] = None
    jersey_number: Optional[str] = None
    date_of_birth: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    college: Optional[str] = None
    experience_years: int = 0
    status: str = "Active"
    headshot_url: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> 'Player':
        return cls(
            player_id=row['player_id'],
            full_name=row['full_name'],
            espn_id=_row_get(row, 'espn_id'),
            first_name=_row_get(row, 'first_name'),
            last_name=_row_get(row, 'last_name'),
            position=_row_get(row, 'position'),
            jersey_number=_row_get(row, 'jersey_number'),
            date_of_birth=_row_get(row, 'date_of_birth'),
            height_cm=_row_get(row, 'height_cm'),
            weight_kg=_row_get(row, 'weight_kg'),
            college=_row_get(row, 'college'),
            experience_years=_row_get(row, 'experience_years', 0) or 0,
            status=_row_get(row, 'status', 'Active') or 'Active',
            headshot_url=_row_get(row, 'headshot_url'),
        )


@dataclass
class RosterEntry:
    """Player ↔ team ↔ season link."""
    player_id: int
    team_id: int
    season: int
    depth_position: Optional[str] = None
    is_starter: bool = False
    roster_status: Optional[str] = None
    fetched_at: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> 'RosterEntry':
        return cls(
            player_id=row['player_id'],
            team_id=row['team_id'],
            season=row['season'],
            depth_position=_row_get(row, 'depth_position'),
            is_starter=bool(_row_get(row, 'is_starter', 0)),
            roster_status=_row_get(row, 'roster_status'),
            fetched_at=_row_get(row, 'fetched_at'),
        )


@dataclass
class InjuryReport:
    """ESPN injury report row."""
    team_id: int
    player_name: str
    position: str
    injury_status: str
    report_date: str

    @classmethod
    def from_row(cls, row) -> 'InjuryReport':
        return cls(
            team_id=row['team_id'],
            player_name=row['player_name'],
            position=row['position'],
            injury_status=row['injury_status'],
            report_date=row['report_date'],
        )


@dataclass
class GameWeather:
    """Open-Meteo weather snapshot for a game (display-only enrichment)."""
    home_team_id: int
    game_date: str
    is_dome: bool = False
    temperature_c: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    precipitation_mm: Optional[float] = None
    weather_code: Optional[int] = None
    condition: Optional[str] = None
    is_adverse: bool = False
    game_id: Optional[int] = None

    @classmethod
    def from_row(cls, row) -> 'GameWeather':
        return cls(
            home_team_id=row['home_team_id'],
            game_date=row['game_date'],
            is_dome=bool(_row_get(row, 'is_dome', 0)),
            temperature_c=_row_get(row, 'temperature_c'),
            wind_speed_kmh=_row_get(row, 'wind_speed_kmh'),
            precipitation_mm=_row_get(row, 'precipitation_mm'),
            weather_code=_row_get(row, 'weather_code'),
            condition=_row_get(row, 'condition'),
            is_adverse=bool(_row_get(row, 'is_adverse', 0)),
            game_id=_row_get(row, 'game_id'),
        )


@dataclass
class GameOdds:
    """Vegas odds for a game (The Odds API; display-only enrichment)."""
    external_game_id: Optional[str] = None
    game_id: Optional[int] = None
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    game_date: Optional[str] = None
    opening_spread: Optional[float] = None
    over_under: Optional[float] = None
    home_implied_prob: Optional[float] = None
    away_implied_prob: Optional[float] = None
    fetched_at: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> 'GameOdds':
        return cls(
            external_game_id=_row_get(row, 'external_game_id'),
            game_id=_row_get(row, 'game_id'),
            home_team_id=_row_get(row, 'home_team_id'),
            away_team_id=_row_get(row, 'away_team_id'),
            game_date=_row_get(row, 'game_date'),
            opening_spread=_row_get(row, 'opening_spread'),
            over_under=_row_get(row, 'over_under'),
            home_implied_prob=_row_get(row, 'home_implied_prob'),
            away_implied_prob=_row_get(row, 'away_implied_prob'),
            fetched_at=_row_get(row, 'fetched_at'),
        )
