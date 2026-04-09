"""Prediction engine and metrics tests against the real database."""

import pytest

from src.database.db import Database, DEFAULT_DB_PATH
from src.prediction.engine import PredictionEngine
from src.prediction.metrics import calculate_team_metrics
from src.prediction.backtester import Backtester

# Skip if database doesn't exist
pytestmark = pytest.mark.skipif(
    not DEFAULT_DB_PATH.exists(),
    reason="Real database not found — run scraper first",
)


@pytest.fixture(scope="module")
def db():
    d = Database(DEFAULT_DB_PATH)
    yield d
    d.close()


@pytest.fixture(scope="module")
def engine(db):
    return PredictionEngine(db)


# ── TeamMetrics ───────────────────────────────────────


class TestTeamMetrics:
    def test_metrics_returns_valid(self, db):
        team = db.find_team("KC")
        assert team is not None
        m = calculate_team_metrics(db, team["team_id"])
        assert m.team_abbr == "KC"
        assert m.games_analyzed > 0
        assert 0 <= m.win_percentage <= 1
        assert m.avg_points_scored > 0
        assert m.avg_points_allowed > 0

    def test_sos_range(self, db):
        team = db.find_team("KC")
        m = calculate_team_metrics(db, team["team_id"])
        assert 0 <= m.strength_of_schedule <= 1

    def test_dynamic_hfa_range(self, db):
        team = db.find_team("KC")
        m = calculate_team_metrics(db, team["team_id"])
        assert 0 <= m.dynamic_hfa <= 0.10

    def test_rest_days_positive(self, db):
        team = db.find_team("KC")
        m = calculate_team_metrics(db, team["team_id"])
        assert m.rest_days >= 0

    def test_metrics_for_multiple_teams(self, db):
        for abbr in ["PHI", "BUF", "SF", "DAL"]:
            team = db.find_team(abbr)
            assert team is not None
            m = calculate_team_metrics(db, team["team_id"])
            assert m.games_analyzed > 0
            assert 0 <= m.win_percentage <= 1

    def test_metrics_invalid_team(self, db):
        with pytest.raises(ValueError):
            calculate_team_metrics(db, 999999)


# ── PredictionEngine ──────────────────────────────────


class TestPredictionEngine:
    def test_predict_kc_vs_phi(self, engine):
        pred = engine.predict("KC", "PHI")
        assert 0 < pred.home_win_probability < 1
        assert 0 < pred.away_win_probability < 1
        assert abs(pred.home_win_probability + pred.away_win_probability - 1.0) < 0.001
        assert pred.confidence in ("low", "medium", "high")

    def test_predict_symmetry(self, engine):
        """Swapping home/away should change probabilities."""
        p1 = engine.predict("KC", "PHI")
        p2 = engine.predict("PHI", "KC")
        # Home team gets an advantage, so they shouldn't be identical
        assert p1.home_win_probability != p2.home_win_probability

    def test_predict_key_factors_non_empty(self, engine):
        pred = engine.predict("BUF", "MIA")
        assert len(pred.key_factors) >= 3

    def test_predict_invalid_team(self, engine):
        with pytest.raises(ValueError):
            engine.predict("ZZZZZ", "KC")

    def test_normalize_to_probability_both_zero(self, engine):
        result = engine._normalize_to_probability(0, 0)
        assert result == 0.5

    def test_normalize_to_probability_equal(self, engine):
        result = engine._normalize_to_probability(5, 5)
        assert result == 0.5

    def test_normalize_to_probability_mixed_signs(self, engine):
        result = engine._normalize_to_probability(0.1, -0.3)
        assert 0 < result < 1

    def test_normalize_to_probability_positive_only(self, engine):
        result = engine._normalize_to_probability(0.7, 0.3)
        assert result == 0.7


# ── Backtester ────────────────────────────────────────


class TestBacktester:
    def test_backtest_2025_sanity(self, db):
        bt = Backtester(db)
        report = bt.run(seasons=[2025])
        assert report.total_games > 0
        assert report.accuracy > 0.52  # Sanity: better than coin flip

    def test_backtest_report_structure(self, db):
        bt = Backtester(db)
        report = bt.run(seasons=[2025])
        d = report.to_dict()
        assert "seasons" in d
        assert "accuracy" in d
        assert "by_confidence" in d
        assert "calibration" in d
        assert "season_accuracy" in d
