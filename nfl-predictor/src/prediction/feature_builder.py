"""Convert TeamMetrics + H2H + game metadata into a fixed-length feature vector."""

from typing import Any, Dict, Union

import numpy as np

from .metrics import TeamMetrics, calculate_form_rating, calculate_strength_rating

# Fixed feature order — used for both training and inference.
# Any change to this list invalidates existing saved models.
# 32 features total.
FEATURE_NAMES: list[str] = [
    "home_win_pct",
    "away_win_pct",
    "home_weighted_win_pct",
    "away_weighted_win_pct",
    "home_ppg",
    "away_ppg",
    "home_pag",
    "away_pag",
    "home_point_diff_per_game",
    "away_point_diff_per_game",
    "home_sos",
    "away_sos",
    "home_form_rating",
    "away_form_rating",
    "home_strength",
    "away_strength",
    "home_home_win_pct",
    "away_away_win_pct",
    "h2h_home_win_pct",
    "home_rest_days",
    "away_rest_days",
    "home_turnover_margin",
    "away_turnover_margin",
    "home_third_down_pct",
    "away_third_down_pct",
    "home_yards_per_play",
    "away_yards_per_play",
    "home_redzone_efficiency",
    "away_redzone_efficiency",
    "is_playoff",
    "week_of_season",
    "home_dynamic_hfa",          # 32nd: team-specific home field advantage
    "vegas_home_implied_prob",   # 33rd: Vegas market implied prob (0.5 = no data)
    "home_qb_epa_per_play",      # 34th: home QB EPA per pass play
    "away_qb_epa_per_play",      # 35th: away QB EPA per pass play
]

assert len(FEATURE_NAMES) == 35, f"Expected 35 features, got {len(FEATURE_NAMES)}"


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    return a / b if b != 0 else default


def build_feature_vector(
    home_metrics: TeamMetrics,
    away_metrics: TeamMetrics,
    h2h: Dict[str, Any],
    is_playoff: Union[bool, int] = False,
    week: Union[str, int] = 0,
    vegas_implied_prob: float = 0.5,
) -> Dict[str, float]:
    """
    Build a feature dict from two TeamMetrics objects plus game context.

    Args:
        home_metrics: Metrics for the home team (computed with cutoff_date).
        away_metrics: Metrics for the away team (computed with cutoff_date).
        h2h: Dict with keys team1_wins, team2_wins, total_games (home perspective).
        is_playoff: 1/True for playoff game, 0/False for regular season.
        week: Integer week of season (1-22), or string ('Wild Card', etc.).
        vegas_implied_prob: Vegas market home-win implied probability (0.5 = no data).

    Returns:
        Dict mapping each FEATURE_NAME to a float value.
    """
    home_games = home_metrics.games_analyzed or 1
    away_games = away_metrics.games_analyzed or 1

    h2h_total = h2h.get("total_games", 0)
    if h2h_total >= 2:
        h2h_home_pct = _safe_div(h2h.get("team1_wins", 0), h2h_total, 0.5)
    else:
        h2h_home_pct = 0.5

    week_int = _parse_week(week)

    return {
        "home_win_pct":              home_metrics.win_percentage,
        "away_win_pct":              away_metrics.win_percentage,
        "home_weighted_win_pct":     home_metrics.weighted_win_pct,
        "away_weighted_win_pct":     away_metrics.weighted_win_pct,
        "home_ppg":                  home_metrics.avg_points_scored,
        "away_ppg":                  away_metrics.avg_points_scored,
        "home_pag":                  home_metrics.avg_points_allowed,
        "away_pag":                  away_metrics.avg_points_allowed,
        "home_point_diff_per_game":  _safe_div(home_metrics.point_differential, home_games),
        "away_point_diff_per_game":  _safe_div(away_metrics.point_differential, away_games),
        "home_sos":                  home_metrics.strength_of_schedule,
        "away_sos":                  away_metrics.strength_of_schedule,
        "home_form_rating":          calculate_form_rating(home_metrics),
        "away_form_rating":          calculate_form_rating(away_metrics),
        "home_strength":             calculate_strength_rating(home_metrics),
        "away_strength":             calculate_strength_rating(away_metrics),
        "home_home_win_pct":         home_metrics.home_win_pct,
        "away_away_win_pct":         away_metrics.away_win_pct,
        "h2h_home_win_pct":          h2h_home_pct,
        "home_rest_days":            float(home_metrics.rest_days),
        "away_rest_days":            float(away_metrics.rest_days),
        "home_turnover_margin":      home_metrics.turnover_margin,
        "away_turnover_margin":      away_metrics.turnover_margin,
        "home_third_down_pct":       home_metrics.third_down_pct,
        "away_third_down_pct":       away_metrics.third_down_pct,
        "home_yards_per_play":       home_metrics.yards_per_play,
        "away_yards_per_play":       away_metrics.yards_per_play,
        "home_redzone_efficiency":   home_metrics.redzone_efficiency,
        "away_redzone_efficiency":   away_metrics.redzone_efficiency,
        "is_playoff":                float(int(is_playoff)),
        "week_of_season":            float(week_int),
        "home_dynamic_hfa":          home_metrics.dynamic_hfa,
        "vegas_home_implied_prob":   float(vegas_implied_prob),
        "home_qb_epa_per_play":      home_metrics.qb_epa_per_play,
        "away_qb_epa_per_play":      away_metrics.qb_epa_per_play,
    }


def feature_dict_to_array(feature_dict: Dict[str, float]) -> np.ndarray:
    """
    Convert a feature dict (from build_feature_vector) to a 1-D ndarray.

    Values are placed in the canonical FEATURE_NAMES order.
    Missing keys default to 0.0.

    Returns:
        np.ndarray of shape (35,), dtype float64.
    """
    return np.array([feature_dict.get(name, 0.0) for name in FEATURE_NAMES], dtype=np.float64)


# ── Private helpers ──────────────────────────────────────────────────────────

_PLAYOFF_WEEK_MAP: Dict[str, int] = {
    "wild card":   19,
    "wildcard":    19,
    "divisional":  20,
    "division":    20,
    "conference":  21,
    "championship": 21,
    "super bowl":  22,
    "superbowl":   22,
}


def _parse_week(week: Union[str, int]) -> int:
    """Convert a week value (str or int) to an integer 1-22, or 0 if unknown."""
    if isinstance(week, int):
        return week
    try:
        return int(week)
    except (ValueError, TypeError):
        key = str(week).lower().strip()
        return _PLAYOFF_WEEK_MAP.get(key, 0)
