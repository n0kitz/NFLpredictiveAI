"""Prediction engine and metrics tests against the real database."""

import pytest
from pathlib import Path

from src.database.db import Database, DEFAULT_DB_PATH
from src.prediction.engine import PredictionEngine
from src.prediction.metrics import calculate_team_metrics
from src.prediction.backtester import Backtester
from src.prediction.feature_builder import FEATURE_NAMES, build_feature_vector, feature_dict_to_array
from src.prediction.explainer import generate_shap_explanation, get_explainer

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


# ── Feature builder ────────────────────────────────────


class TestFeatureBuilder:
    def _make_metrics(self, db, abbr: str) -> "calculate_team_metrics":
        team = db.find_team(abbr)
        return calculate_team_metrics(db, team["team_id"])

    def test_feature_builder_shape(self, db):
        """Feature array must have exactly 34 elements (32 base + 2x QB EPA; vegas removed)."""
        hm = self._make_metrics(db, "KC")
        am = self._make_metrics(db, "PHI")
        h2h = {"team1_wins": 3, "team2_wins": 2, "total_games": 5}
        feat = build_feature_vector(hm, am, h2h, is_playoff=False, week=10)
        arr = feature_dict_to_array(feat)
        assert arr.shape == (34,), f"Expected shape (34,), got {arr.shape}"

    def test_feature_builder_keys(self, db):
        """All FEATURE_NAMES must appear in the feature dict."""
        hm = self._make_metrics(db, "BUF")
        am = self._make_metrics(db, "MIA")
        h2h = {"team1_wins": 1, "team2_wins": 1, "total_games": 2}
        feat = build_feature_vector(hm, am, h2h, is_playoff=True, week="Wild Card")
        for name in FEATURE_NAMES:
            assert name in feat, f"Missing feature key: {name}"

    def test_ml_model_fallback(self, db):
        """Engine._use_ml is consistent with whether the model actually loaded."""
        from src.prediction.ml_model import MODEL_PATH, load_model

        engine = PredictionEngine(db)
        model, _ = load_model()
        if model is None:
            # File absent OR failed to load (e.g. numpy mismatch) — must fall back
            assert not engine._use_ml, "Engine should use weighted-sum when model unavailable"
        else:
            assert engine._use_ml
            assert engine._ml_model is not None

    def test_model_info_endpoint(self):
        """GET /api/model/info returns 200 with a model_type field."""
        from fastapi.testclient import TestClient
        from src.api.app import app

        client = TestClient(app)
        r = client.get("/api/model/info")
        assert r.status_code == 200
        data = r.json()
        assert "model_type" in data
        assert data["model_type"] in ("ml", "weighted_sum")


# ── SHAP Explainer ─────────────────────────────────────


class TestExplainer:
    def _make_metrics(self, db, abbr: str):
        team = db.find_team(abbr)
        return calculate_team_metrics(db, team["team_id"])

    def test_explainer_no_model(self, db):
        """generate_shap_explanation returns [] when model is None."""
        result = generate_shap_explanation(
            self._make_metrics(db, "KC"),
            self._make_metrics(db, "PHI"),
            h2h={"team1_wins": 3, "team2_wins": 2, "total_games": 5},
            is_playoff=False,
            week=10,
            model=None,
            feature_names=None,
        )
        assert result == []

    def test_explainer_returns_list(self, db):
        """With ML model loaded, generate_shap_explanation returns a list."""
        from src.prediction.ml_model import MODEL_PATH
        engine = PredictionEngine(db)
        if not MODEL_PATH.exists():
            pytest.skip("ML model not trained — run scripts/train_model.py")

        hm = self._make_metrics(db, "KC")
        am = self._make_metrics(db, "PHI")
        h2h = {"team1_wins": 3, "team2_wins": 2, "total_games": 5}
        result = generate_shap_explanation(
            hm, am, h2h,
            is_playoff=False, week=10,
            model=engine._ml_model,
            feature_names=engine._ml_features,
        )
        assert isinstance(result, list)
        assert len(result) <= 8

    def test_explanation_entry_schema(self, db):
        """Each explanation entry has all required keys."""
        from src.prediction.ml_model import MODEL_PATH
        engine = PredictionEngine(db)
        if not MODEL_PATH.exists():
            pytest.skip("ML model not trained — run scripts/train_model.py")

        hm = self._make_metrics(db, "BUF")
        am = self._make_metrics(db, "MIA")
        h2h = {"team1_wins": 2, "team2_wins": 3, "total_games": 5}
        result = generate_shap_explanation(
            hm, am, h2h,
            is_playoff=False, week=8,
            model=engine._ml_model,
            feature_names=engine._ml_features,
        )
        if result:
            required_keys = {"feature", "label", "shap_value", "direction", "feature_value"}
            for entry in result:
                assert required_keys == set(entry.keys()), f"Missing keys in entry: {entry}"

    def test_direction_logic(self, db):
        """Direction is derived correctly from shap_value thresholds."""
        from src.prediction.ml_model import MODEL_PATH
        engine = PredictionEngine(db)
        if not MODEL_PATH.exists():
            pytest.skip("ML model not trained — run scripts/train_model.py")

        hm = self._make_metrics(db, "KC")
        am = self._make_metrics(db, "SF")
        h2h = {"team1_wins": 4, "team2_wins": 1, "total_games": 5}
        result = generate_shap_explanation(
            hm, am, h2h,
            is_playoff=False, week=14,
            model=engine._ml_model,
            feature_names=engine._ml_features,
        )
        for entry in result:
            sv = entry["shap_value"]
            if sv > 0.005:
                assert entry["direction"] == "home", f"Expected home for sv={sv}"
            elif sv < -0.005:
                assert entry["direction"] == "away", f"Expected away for sv={sv}"
            else:
                assert entry["direction"] == "neutral", f"Expected neutral for sv={sv}"
