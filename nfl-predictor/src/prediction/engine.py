"""Core prediction engine for NFL game predictions."""

import logging
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any

from ..database.db import Database, get_database
from ..database.models import Prediction, GameFactor
from .metrics import (
    TeamMetrics, calculate_team_metrics, calculate_head_to_head,
    calculate_form_rating, calculate_strength_rating
)
from .factors import apply_game_factors, FactorAdjuster

logger = logging.getLogger(__name__)

# Historical home field advantage (approximately 2.5-3 points)
# Translates to roughly 3-3.5% win probability advantage
HOME_FIELD_ADVANTAGE = 0.032


class PredictionEngine:
    """
    NFL Game Prediction Engine.

    Calculates win probabilities based on:
    - Overall win/loss record
    - Home/away performance splits
    - Points scored vs allowed (offensive/defensive strength)
    - Point differential trends
    - Head-to-head historical record
    - Recent form (last 5 games weighted highest)
    - Home field advantage (~3%)

    Weights:
    - Recent games weighted with exponential decay
    - Current season games weighted 3x vs previous seasons
    """

    def __init__(self, db: Optional[Database] = None):
        """
        Initialize the prediction engine.

        Args:
            db: Database instance (uses singleton if not provided)
        """
        self.db = db or get_database()
        self.factor_adjuster = FactorAdjuster(self.db)

    def predict(
        self,
        home_team: str,
        away_team: str,
        game_id: Optional[int] = None,
        apply_factors: bool = True
    ) -> Prediction:
        """
        Predict the outcome of a game between two teams.

        Args:
            home_team: Home team name, abbreviation, or city
            away_team: Away team name, abbreviation, or city
            game_id: Optional game ID for factor lookup
            apply_factors: Whether to apply game factors if available

        Returns:
            Prediction object with win probabilities and analysis
        """
        # Find teams in database
        home = self.db.find_team(home_team)
        away = self.db.find_team(away_team)

        if not home:
            raise ValueError(f"Home team not found: {home_team}")
        if not away:
            raise ValueError(f"Away team not found: {away_team}")

        home_id = home['team_id']
        away_id = away['team_id']
        home_name = f"{home['city']} {home['name']}"
        away_name = f"{away['city']} {away['name']}"

        # Calculate metrics for both teams
        home_metrics = calculate_team_metrics(self.db, home_id)
        away_metrics = calculate_team_metrics(self.db, away_id)

        # Calculate base win probability
        home_prob, away_prob, key_factors = self._calculate_probability(
            home_metrics, away_metrics, home_id, away_id
        )

        # Determine confidence level
        confidence = self._determine_confidence(home_metrics, away_metrics)

        # Create base prediction
        prediction = Prediction(
            home_team=home_name,
            away_team=away_name,
            home_team_id=home_id,
            away_team_id=away_id,
            home_win_probability=home_prob,
            away_win_probability=away_prob,
            confidence=confidence,
            key_factors=key_factors
        )

        # Apply game factors if available
        if apply_factors and game_id:
            factors = self.factor_adjuster.get_factors_for_game(game_id)
            if factors:
                prediction = apply_game_factors(prediction, factors)

        return prediction

    def _calculate_probability(
        self,
        home_metrics: TeamMetrics,
        away_metrics: TeamMetrics,
        home_id: int,
        away_id: int
    ) -> Tuple[float, float, List[str]]:
        """
        Calculate win probability based on team metrics.

        Uses a weighted combination of factors:
        - 25%: Weighted win percentage
        - 20%: Offensive/defensive strength
        - 15%: Recent form
        - 15%: Strength of schedule
        - 15%: Home/away splits
        - 10%: Head-to-head record

        Args:
            home_metrics: Home team metrics
            away_metrics: Away team metrics
            home_id: Home team ID
            away_id: Away team ID

        Returns:
            Tuple of (home_probability, away_probability, key_factors)
        """
        key_factors = []
        components = []

        # 1. Weighted win percentage (25%)
        home_win_pct = home_metrics.weighted_win_pct
        away_win_pct = away_metrics.weighted_win_pct

        win_pct_component = self._normalize_to_probability(
            home_win_pct, away_win_pct
        )
        components.append(('win_pct', win_pct_component, 0.25))

        key_factors.append(
            f"{home_metrics.team_abbr}: {home_metrics.current_season_wins}-"
            f"{home_metrics.current_season_losses} record, "
            f"{home_metrics.point_differential:+d} point diff"
        )
        key_factors.append(
            f"{away_metrics.team_abbr}: {away_metrics.current_season_wins}-"
            f"{away_metrics.current_season_losses} record, "
            f"{away_metrics.point_differential:+d} point diff"
        )

        # 2. Offensive/defensive strength (20%)
        home_strength = calculate_strength_rating(home_metrics)
        away_strength = calculate_strength_rating(away_metrics)

        strength_component = self._normalize_to_probability(
            home_strength, away_strength
        )
        components.append(('strength', strength_component, 0.20))

        # 3. Recent form (15%)
        home_form = calculate_form_rating(home_metrics)
        away_form = calculate_form_rating(away_metrics)

        form_component = self._normalize_to_probability(home_form, away_form)
        components.append(('form', form_component, 0.15))

        recent_total_home = home_metrics.recent_wins + home_metrics.recent_losses
        recent_total_away = away_metrics.recent_wins + away_metrics.recent_losses
        if recent_total_home > 0 and recent_total_away > 0:
            key_factors.append(
                f"Recent form: {home_metrics.team_abbr} "
                f"{home_metrics.recent_wins}-{home_metrics.recent_losses} last 5, "
                f"{away_metrics.team_abbr} "
                f"{away_metrics.recent_wins}-{away_metrics.recent_losses} last 5"
            )

        # 4. Strength of schedule (15%)
        home_sos = home_metrics.strength_of_schedule
        away_sos = away_metrics.strength_of_schedule

        sos_component = self._normalize_to_probability(home_sos, away_sos)
        components.append(('sos', sos_component, 0.15))

        key_factors.append(
            f"SOS: {home_metrics.team_abbr} {home_sos:.3f}, "
            f"{away_metrics.team_abbr} {away_sos:.3f}"
        )

        # 5. Home/away splits (15%)
        home_at_home = home_metrics.home_win_pct
        away_on_road = away_metrics.away_win_pct

        split_component = self._normalize_to_probability(
            home_at_home, away_on_road
        )
        components.append(('splits', split_component, 0.15))

        home_games = home_metrics.home_wins + home_metrics.home_losses
        if home_games > 0:
            key_factors.append(
                f"{home_metrics.team_abbr} home: "
                f"{home_metrics.home_wins}-{home_metrics.home_losses}"
            )

        # 6. Head-to-head record (10%)
        h2h = calculate_head_to_head(self.db, home_id, away_id, limit=10)
        if h2h['total_games'] >= 2:
            if h2h['total_games'] > 0:
                h2h_home_pct = h2h['team1_wins'] / h2h['total_games']
                h2h_away_pct = h2h['team2_wins'] / h2h['total_games']
            else:
                h2h_home_pct = 0.5
                h2h_away_pct = 0.5

            h2h_component = self._normalize_to_probability(
                h2h_home_pct, h2h_away_pct
            )
            components.append(('h2h', h2h_component, 0.10))

            key_factors.append(
                f"Head-to-head (last {h2h['total_games']}): "
                f"{home_metrics.team_abbr} {h2h['team1_wins']}-{h2h['team2_wins']}"
            )
        else:
            # Redistribute H2H weight (10%) to win_pct component
            components = [
                (name, prob, weight + 0.10) if name == 'win_pct' else (name, prob, weight)
                for name, prob, weight in components
            ]

        # Calculate weighted average
        total_weight = sum(w for _, _, w in components)
        home_prob = sum(p * w for _, p, w in components) / total_weight

        # Apply dynamic home field advantage
        hfa = home_metrics.dynamic_hfa
        home_prob += hfa
        key_factors.append(
            f"Home field advantage: +{hfa:.1%} to {home_metrics.team_abbr}"
        )

        # Bye week / rest advantage
        home_rest = home_metrics.rest_days
        away_rest = away_metrics.rest_days
        if home_rest >= 10 and away_rest <= 8:
            home_prob += 0.015
            key_factors.append(
                f"{home_metrics.team_abbr} coming off bye (+1.5%)"
            )
        elif away_rest >= 10 and home_rest <= 8:
            home_prob -= 0.015
            key_factors.append(
                f"{away_metrics.team_abbr} coming off bye (+1.5%)"
            )

        # Ensure probabilities are valid
        home_prob = max(0.02, min(0.98, home_prob))
        away_prob = 1.0 - home_prob

        return home_prob, away_prob, key_factors

    def _normalize_to_probability(
        self,
        home_value: float,
        away_value: float
    ) -> float:
        """
        Normalize two values to a probability for the home team.

        Args:
            home_value: Metric value for home team
            away_value: Metric value for away team

        Returns:
            Probability between 0 and 1 for home team
        """
        total = abs(home_value) + abs(away_value)
        if total == 0:
            return 0.5

        # If both are positive, simple ratio
        if home_value >= 0 and away_value >= 0:
            return home_value / total if total > 0 else 0.5

        # If mixed signs, shift to positive range
        min_val = min(home_value, away_value)
        home_shifted = home_value - min_val + 0.01
        away_shifted = away_value - min_val + 0.01

        return home_shifted / (home_shifted + away_shifted)

    def _determine_confidence(
        self,
        home_metrics: TeamMetrics,
        away_metrics: TeamMetrics
    ) -> str:
        """
        Determine confidence level based on data quality.

        Args:
            home_metrics: Home team metrics
            away_metrics: Away team metrics

        Returns:
            Confidence level: 'low', 'medium', or 'high'
        """
        min_games = min(home_metrics.games_analyzed, away_metrics.games_analyzed)

        if min_games >= 20:
            return 'high'
        elif min_games >= 8:
            return 'medium'
        else:
            return 'low'

    def get_team_summary(self, team: str, season: Optional[int] = None) -> str:
        """
        Get a summary of a team's performance.

        Args:
            team: Team name, abbreviation, or city
            season: Optional specific season

        Returns:
            Formatted summary string
        """
        team_row = self.db.find_team(team)
        if not team_row:
            return f"Team not found: {team}"

        team_id = team_row['team_id']
        team_name = f"{team_row['city']} {team_row['name']}"

        if season:
            stats = self.db.get_team_season_stats(team_id, season)
            if not stats:
                return f"No data for {team_name} in {season}"

            stat = stats[0]
            return (
                f"\n{team_name} ({season})\n"
                f"Record: {stat['wins']}-{stat['losses']}"
                f"{'-' + str(stat['ties']) if stat['ties'] else ''}\n"
                f"Points For: {stat['points_for']} "
                f"({stat['points_for']/stat['games_played']:.1f}/game)\n"
                f"Points Against: {stat['points_against']} "
                f"({stat['points_against']/stat['games_played']:.1f}/game)\n"
                f"Point Differential: {stat['point_differential']:+d}\n"
                f"Home: {stat['home_wins']}-{stat['home_losses']}\n"
                f"Away: {stat['away_wins']}-{stat['away_losses']}"
            )

        # Get recent metrics
        metrics = calculate_team_metrics(self.db, team_id)

        return (
            f"\n{team_name}\n"
            f"Current Season: {metrics.current_season_wins}-"
            f"{metrics.current_season_losses}"
            f"{'-' + str(metrics.current_season_ties) if metrics.current_season_ties else ''}\n"
            f"Win %: {metrics.win_percentage:.1%}\n"
            f"Avg Points: {metrics.avg_points_scored:.1f} scored, "
            f"{metrics.avg_points_allowed:.1f} allowed\n"
            f"Point Differential: {metrics.point_differential:+d}\n"
            f"Home: {metrics.home_wins}-{metrics.home_losses}\n"
            f"Away: {metrics.away_wins}-{metrics.away_losses}\n"
            f"Last 5: {metrics.recent_wins}-{metrics.recent_losses}"
        )

    def get_head_to_head_summary(
        self,
        team1: str,
        team2: str,
        limit: int = 10
    ) -> str:
        """
        Get head-to-head summary between two teams.

        Args:
            team1: First team
            team2: Second team
            limit: Maximum games to show

        Returns:
            Formatted summary string
        """
        t1 = self.db.find_team(team1)
        t2 = self.db.find_team(team2)

        if not t1:
            return f"Team not found: {team1}"
        if not t2:
            return f"Team not found: {team2}"

        t1_name = f"{t1['city']} {t1['name']}"
        t2_name = f"{t2['city']} {t2['name']}"

        h2h = calculate_head_to_head(self.db, t1['team_id'], t2['team_id'], limit)

        if h2h['total_games'] == 0:
            return f"No games found between {t1_name} and {t2_name}"

        lines = [
            f"\nHead-to-Head: {t1_name} vs {t2_name}",
            f"Overall: {t1['abbreviation']} {h2h['team1_wins']}-{h2h['team2_wins']}"
            f"{'-' + str(h2h['ties']) if h2h['ties'] else ''} {t2['abbreviation']}",
            f"\nRecent Games:"
        ]

        for game in h2h['games'][:limit]:
            winner_mark = ""
            if game['winner_id'] == t1['team_id']:
                winner_mark = f" <- {t1['abbreviation']} W"
            elif game['winner_id'] == t2['team_id']:
                winner_mark = f" <- {t2['abbreviation']} W"
            else:
                winner_mark = " (TIE)"

            lines.append(
                f"  {game['date']}: {game['away_abbr']} {game['away_score']} "
                f"@ {game['home_abbr']} {game['home_score']}{winner_mark}"
            )

        return "\n".join(lines)

    def get_recent_games(self, team: str, count: int = 10) -> str:
        """
        Get recent games for a team.

        Args:
            team: Team name, abbreviation, or city
            count: Number of games to return

        Returns:
            Formatted string with recent games
        """
        team_row = self.db.find_team(team)
        if not team_row:
            return f"Team not found: {team}"

        team_id = team_row['team_id']
        team_name = f"{team_row['city']} {team_row['name']}"
        team_abbr = team_row['abbreviation']

        games = self.db.get_team_games(team_id, limit=count)

        if not games:
            return f"No games found for {team_name}"

        lines = [f"\nLast {len(games)} games for {team_name}:"]

        for game in games:
            is_home = game['home_team_id'] == team_id

            if is_home:
                opp = game['away_abbr']
                team_score = game['home_score']
                opp_score = game['away_score']
                location = "vs"
            else:
                opp = game['home_abbr']
                team_score = game['away_score']
                opp_score = game['home_score']
                location = "@"

            if game['winner_id'] == team_id:
                result = "W"
            elif game['winner_id'] is None:
                result = "T"
            else:
                result = "L"

            ot = " (OT)" if game['overtime'] else ""

            lines.append(
                f"  {game['date']}: {result} {team_score}-{opp_score} "
                f"{location} {opp}{ot}"
            )

        return "\n".join(lines)

    def get_playoff_history(self, team: str) -> str:
        """
        Get playoff history for a team.

        Args:
            team: Team name, abbreviation, or city

        Returns:
            Formatted playoff history string
        """
        team_row = self.db.find_team(team)
        if not team_row:
            return f"Team not found: {team}"

        team_id = team_row['team_id']
        team_name = f"{team_row['city']} {team_row['name']}"
        team_abbr = team_row['abbreviation']

        games = self.db.get_playoff_games(team_id)

        if not games:
            return f"No playoff games found for {team_name}"

        # Group by season
        seasons: Dict[int, List] = {}
        for game in games:
            season = game['season']
            if season not in seasons:
                seasons[season] = []
            seasons[season].append(game)

        wins = sum(1 for g in games if g['winner_id'] == team_id)
        losses = len(games) - wins

        lines = [
            f"\nPlayoff History: {team_name}",
            f"Overall: {wins}-{losses}",
            ""
        ]

        for season in sorted(seasons.keys(), reverse=True):
            season_games = seasons[season]
            season_wins = sum(1 for g in season_games if g['winner_id'] == team_id)
            season_losses = len(season_games) - season_wins

            lines.append(f"{season} ({season_wins}-{season_losses}):")

            for game in sorted(season_games, key=lambda g: g['date']):
                is_home = game['home_team_id'] == team_id

                if is_home:
                    opp = game['away_abbr']
                    team_score = game['home_score']
                    opp_score = game['away_score']
                else:
                    opp = game['home_abbr']
                    team_score = game['away_score']
                    opp_score = game['home_score']

                result = "W" if game['winner_id'] == team_id else "L"
                ot = " (OT)" if game['overtime'] else ""

                lines.append(
                    f"  {game['week']}: {result} {team_score}-{opp_score} "
                    f"vs {opp}{ot}"
                )

        return "\n".join(lines)
