"""Game factors module for prediction adjustments (future use)."""

import csv
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple

from ..database.db import Database
from ..database.models import GameFactor, FactorType, Prediction

logger = logging.getLogger(__name__)


# Factor impact weights for each factor type
# These represent the expected impact on win probability adjustment
FACTOR_WEIGHTS = {
    FactorType.BETTER_DEFENSE: 0.03,
    FactorType.BAD_DEFENSE: -0.03,
    FactorType.BETTER_OFFENSE: 0.03,
    FactorType.BAD_OFFENSE: -0.03,
    FactorType.BETTER_QB: 0.04,
    FactorType.QB_STRUGGLES: -0.04,
    FactorType.TURNOVER_PRONE: -0.025,
    FactorType.TURNOVER_FORCING: 0.025,
    FactorType.NOT_EFFICIENT: -0.02,
    FactorType.HIGHLY_EFFICIENT: 0.02,
    FactorType.INJURY_IMPACT: -0.03,  # Usually negative for injured team
    FactorType.WEATHER_IMPACT: 0.0,   # Can be positive or negative
    FactorType.COACHING_ADVANTAGE: 0.02,
    FactorType.MOTIVATION_FACTOR: 0.015,
    FactorType.CUSTOM: 0.02,
}


@dataclass
class FactorAdjustment:
    """Represents an adjustment to be applied to a prediction."""
    team_id: int
    factor: GameFactor
    adjustment: float  # Adjustment to win probability (-1 to 1)


class FactorAdjuster:
    """
    Handles game factor adjustments for predictions.

    This is a stub implementation that will be expanded in future versions.
    Currently, it provides the framework for applying manual factors to predictions.
    """

    def __init__(self, db: Database):
        """
        Initialize the factor adjuster.

        Args:
            db: Database instance
        """
        self.db = db

    def get_factors_for_game(self, game_id: int) -> List[GameFactor]:
        """
        Get all factors associated with a game.

        Args:
            game_id: Game ID to look up factors for

        Returns:
            List of GameFactor objects
        """
        rows = self.db.get_game_factors(game_id)
        return [GameFactor.from_row(row) for row in rows]

    def add_factor(
        self,
        game_id: int,
        team_id: int,
        factor_type: str,
        description: Optional[str] = None,
        impact_rating: int = 0
    ) -> int:
        """
        Add a factor to a game.

        Args:
            game_id: Game ID
            team_id: Team ID the factor applies to
            factor_type: Type of factor (must be valid FactorType)
            description: Text description of the factor
            impact_rating: Impact rating from -5 to +5

        Returns:
            Factor ID of the created factor
        """
        # Validate factor type
        try:
            FactorType(factor_type)
        except ValueError:
            valid_types = [ft.value for ft in FactorType]
            raise ValueError(
                f"Invalid factor type: {factor_type}. "
                f"Valid types: {valid_types}"
            )

        # Validate impact rating
        if not -5 <= impact_rating <= 5:
            raise ValueError("Impact rating must be between -5 and +5")

        return self.db.insert_game_factor(
            game_id=game_id,
            team_id=team_id,
            factor_type=factor_type,
            factor_value=description,
            impact_rating=impact_rating
        )

    def remove_factor(self, factor_id: int) -> bool:
        """
        Remove a factor by ID.

        Args:
            factor_id: Factor ID to remove

        Returns:
            True if factor was removed, False if not found
        """
        return self.db.remove_game_factor(factor_id)

    def list_factors(self, game_id: int) -> List[Dict[str, Any]]:
        """
        List all factors for a game in a display-friendly format.

        Args:
            game_id: Game ID

        Returns:
            List of factor dictionaries
        """
        factors = self.get_factors_for_game(game_id)
        return [
            {
                'factor_id': f.factor_id,
                'team': f.team_abbr or f.team_name,
                'type': f.factor_type.value,
                'description': f.factor_value,
                'impact': f.impact_rating
            }
            for f in factors
        ]

    def bulk_import_factors(self, csv_path: str) -> Tuple[int, int]:
        """
        Import factors from a CSV file.

        CSV format:
        game_id,team_id,factor_type,description,impact_rating

        Args:
            csv_path: Path to CSV file

        Returns:
            Tuple of (imported_count, error_count)
        """
        imported = 0
        errors = 0

        try:
            with open(csv_path, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        self.add_factor(
                            game_id=int(row['game_id']),
                            team_id=int(row['team_id']),
                            factor_type=row['factor_type'],
                            description=row.get('description', ''),
                            impact_rating=int(row.get('impact_rating', 0))
                        )
                        imported += 1
                    except Exception as e:
                        logger.error(f"Error importing factor row: {e}")
                        errors += 1

        except FileNotFoundError:
            logger.error(f"CSV file not found: {csv_path}")
            raise

        return imported, errors

    def calculate_adjustment(self, factor: GameFactor) -> float:
        """
        Calculate the win probability adjustment for a single factor.

        Args:
            factor: GameFactor to calculate adjustment for

        Returns:
            Adjustment to win probability (-1 to 1)
        """
        # Get base weight for factor type
        base_weight = FACTOR_WEIGHTS.get(factor.factor_type, 0.02)

        # Scale by impact rating (-5 to +5 maps to -1 to +1 multiplier)
        impact_multiplier = factor.impact_rating / 5.0

        return base_weight * impact_multiplier


def apply_game_factors(
    base_prediction: Prediction,
    factors: List[GameFactor]
) -> Prediction:
    """
    Apply game factors to adjust a base prediction.

    Calculates per-factor probability adjustments and applies them
    symmetrically to the home/away win probabilities.

    Args:
        base_prediction: The initial prediction without factors
        factors: List of GameFactor objects to apply

    Returns:
        Adjusted Prediction object
    """
    if not factors:
        return base_prediction

    # Calculate adjustments for each team
    home_adjustment = 0.0
    away_adjustment = 0.0

    adjuster = FactorAdjuster(None)  # We don't need DB for calculation

    for factor in factors:
        adjustment = adjuster.calculate_adjustment(factor)

        if factor.team_id == base_prediction.home_team_id:
            home_adjustment += adjustment
        elif factor.team_id == base_prediction.away_team_id:
            away_adjustment += adjustment

    # Apply adjustments
    # The adjustment represents the change in win probability
    new_home_prob = base_prediction.home_win_probability + home_adjustment - away_adjustment
    new_away_prob = base_prediction.away_win_probability - home_adjustment + away_adjustment

    # Clamp to valid range and normalize
    new_home_prob = max(0.05, min(0.95, new_home_prob))
    new_away_prob = max(0.05, min(0.95, new_away_prob))

    # Normalize to sum to 1
    total = new_home_prob + new_away_prob
    new_home_prob /= total
    new_away_prob /= total

    # Create new prediction with adjustments
    adjusted = Prediction(
        home_team=base_prediction.home_team,
        away_team=base_prediction.away_team,
        home_team_id=base_prediction.home_team_id,
        away_team_id=base_prediction.away_team_id,
        home_win_probability=new_home_prob,
        away_win_probability=new_away_prob,
        confidence=base_prediction.confidence,
        key_factors=base_prediction.key_factors.copy(),
        factors_applied=factors
    )

    return adjusted


def get_factor_type_descriptions() -> Dict[str, str]:
    """
    Get descriptions for all factor types.

    Returns:
        Dictionary mapping factor type to description
    """
    return {
        'better_defense': 'Team has defensive advantage (scheme, personnel matchup)',
        'bad_defense': 'Team has defensive weakness',
        'better_offense': 'Team has offensive advantage (scheme, personnel matchup)',
        'bad_offense': 'Team has offensive weakness',
        'better_qb': 'Team has quarterback advantage',
        'qb_struggles': 'Quarterback is struggling or limited',
        'turnover_prone': 'Team has been turning the ball over frequently',
        'turnover_forcing': 'Team is good at forcing turnovers',
        'not_efficient': 'Team is inefficient (red zone, 3rd down, etc.)',
        'highly_efficient': 'Team is highly efficient in key situations',
        'injury_impact': 'Key injuries affecting team performance',
        'weather_impact': 'Weather conditions favor/hurt this team',
        'coaching_advantage': 'Coaching staff has advantage in this matchup',
        'motivation_factor': 'Extra motivation (revenge game, playoff implications, etc.)',
        'custom': 'Custom factor - specify in description'
    }
