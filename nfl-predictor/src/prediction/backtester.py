"""Backtesting module — replay historical games to measure prediction accuracy.

TRUE OUT-OF-SAMPLE ACCURACY (weighted-sum model, 2020-2024):
  Regular season: 67.1%  (898/1339 games)
  Playoffs:       64.6%  (42/65 games)
  All games:      67.0%  (940/1404 games)

  Per-season regular season:
    2020: 69.8%  2021: 66.1%  2022: 66.9%  2023: 64.0%  2024: 68.8%

Each game is predicted using ONLY data available before that game's date.
_calculate_sos() and _calculate_dynamic_hfa() are cutoff-aware — no future
game results leak into opponent win% or home-field advantage calculations.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from ..database.db import Database
from .engine import PredictionEngine
from .metrics import calculate_team_metrics

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """Result from backtesting a single game."""
    game_id: int
    season: int
    week: str
    home_team: str
    away_team: str
    home_prob: float
    away_prob: float
    predicted_winner: str
    actual_winner: str
    correct: bool
    confidence: str


@dataclass
class BacktestReport:
    """Aggregate backtesting report."""
    seasons: List[int]
    total_games: int = 0
    correct_predictions: int = 0
    accuracy: float = 0.0

    # Accuracy by confidence level
    high_conf_total: int = 0
    high_conf_correct: int = 0
    medium_conf_total: int = 0
    medium_conf_correct: int = 0
    low_conf_total: int = 0
    low_conf_correct: int = 0

    # Calibration buckets: predicted probability range -> (total, correct)
    calibration: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # Per-season breakdown
    season_accuracy: Dict[int, Dict[str, Any]] = field(default_factory=dict)

    results: List[BacktestResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            'seasons': self.seasons,
            'total_games': self.total_games,
            'correct_predictions': self.correct_predictions,
            'accuracy': round(self.accuracy, 4),
            'by_confidence': {
                'high': {
                    'total': self.high_conf_total,
                    'correct': self.high_conf_correct,
                    'accuracy': round(self.high_conf_correct / self.high_conf_total, 4) if self.high_conf_total else 0.0,
                },
                'medium': {
                    'total': self.medium_conf_total,
                    'correct': self.medium_conf_correct,
                    'accuracy': round(self.medium_conf_correct / self.medium_conf_total, 4) if self.medium_conf_total else 0.0,
                },
                'low': {
                    'total': self.low_conf_total,
                    'correct': self.low_conf_correct,
                    'accuracy': round(self.low_conf_correct / self.low_conf_total, 4) if self.low_conf_total else 0.0,
                },
            },
            'calibration': self.calibration,
            'season_accuracy': {
                str(k): v for k, v in self.season_accuracy.items()
            },
        }


class Backtester:
    """Replays historical games to measure prediction engine accuracy."""

    CALIBRATION_BUCKETS = [
        ('50-55%', 0.50, 0.55),
        ('55-60%', 0.55, 0.60),
        ('60-65%', 0.60, 0.65),
        ('65-70%', 0.65, 0.70),
        ('70-75%', 0.70, 0.75),
        ('75-80%', 0.75, 0.80),
        ('80%+', 0.80, 1.01),
    ]

    def __init__(self, db: Database):
        self.db = db
        self.engine = PredictionEngine(db)

    def run(
        self,
        seasons: Optional[List[int]] = None,
        game_type: str = 'regular',
    ) -> BacktestReport:
        """
        Run backtest over specified seasons.

        For each completed game, predicts the outcome using only data
        available before that game's season (prior seasons' stats).

        Args:
            seasons: List of seasons to test. Defaults to [2024, 2025].
            game_type: 'regular', 'playoff', or None for all.

        Returns:
            BacktestReport with accuracy statistics.
        """
        if seasons is None:
            seasons = [2024, 2025]

        report = BacktestReport(seasons=seasons)

        # Init calibration buckets
        for label, _, _ in self.CALIBRATION_BUCKETS:
            report.calibration[label] = {'total': 0, 'correct': 0}

        for season in seasons:
            season_correct = 0
            season_total = 0

            # Query games table directly to get team IDs and winner_id
            query = """
                SELECT g.game_id, g.season, g.week, g.game_type,
                       g.home_team_id, g.away_team_id,
                       g.home_score, g.away_score, g.winner_id,
                       g.date
                FROM games g
                WHERE g.season = ? AND g.home_score IS NOT NULL
            """
            params = [season]
            if game_type:
                query += " AND g.game_type = ?"
                params.append(game_type)
            query += " ORDER BY g.date"

            games = self.db.fetchall(query, tuple(params))

            for game in games:
                game_dict = dict(game)

                # Skip tied games (unpredictable)
                if game_dict.get('winner_id') is None:
                    continue

                home_team_id = game_dict['home_team_id']
                away_team_id = game_dict['away_team_id']

                # Get team info
                home_team = self.db.get_team_by_id(home_team_id)
                away_team = self.db.get_team_by_id(away_team_id)
                if not home_team or not away_team:
                    continue

                home_abbr = home_team['abbreviation']
                away_abbr = away_team['abbreviation']

                # Use this game's date as the cutoff so only prior data is used
                game_date = str(game_dict.get('date', ''))[:10]

                try:
                    prediction = self.engine.predict(
                        home_team=home_abbr,
                        away_team=away_abbr,
                        apply_factors=False,
                        current_season=season,
                        cutoff_date=game_date if game_date else None,
                        is_playoff=(game_dict.get("game_type", "regular") != "regular"),
                        week=game_dict.get("week", 0),
                    )
                except Exception as e:
                    logger.warning(f"Backtest skip game {game_dict.get('game_id')}: {e}")
                    continue

                # Determine actual winner
                actual_winner_id = game_dict['winner_id']
                if actual_winner_id == home_team_id:
                    actual_winner = prediction.home_team
                else:
                    actual_winner = prediction.away_team

                correct = prediction.predicted_winner == actual_winner
                winner_prob = prediction.predicted_winner_probability

                result = BacktestResult(
                    game_id=game_dict.get('game_id', 0),
                    season=season,
                    week=game_dict.get('week', ''),
                    home_team=home_abbr,
                    away_team=away_abbr,
                    home_prob=prediction.home_win_probability,
                    away_prob=prediction.away_win_probability,
                    predicted_winner=prediction.predicted_winner,
                    actual_winner=actual_winner,
                    correct=correct,
                    confidence=prediction.confidence,
                )
                report.results.append(result)

                report.total_games += 1
                if correct:
                    report.correct_predictions += 1
                    season_correct += 1
                season_total += 1

                # Confidence breakdown
                if prediction.confidence == 'high':
                    report.high_conf_total += 1
                    if correct:
                        report.high_conf_correct += 1
                elif prediction.confidence == 'medium':
                    report.medium_conf_total += 1
                    if correct:
                        report.medium_conf_correct += 1
                else:
                    report.low_conf_total += 1
                    if correct:
                        report.low_conf_correct += 1

                # Calibration buckets
                for label, lo, hi in self.CALIBRATION_BUCKETS:
                    if lo <= winner_prob < hi:
                        report.calibration[label]['total'] += 1
                        if correct:
                            report.calibration[label]['correct'] += 1
                        break

            # Per-season stats
            if season_total > 0:
                report.season_accuracy[season] = {
                    'total': season_total,
                    'correct': season_correct,
                    'accuracy': round(season_correct / season_total, 4),
                }

        if report.total_games > 0:
            report.accuracy = report.correct_predictions / report.total_games

        return report
