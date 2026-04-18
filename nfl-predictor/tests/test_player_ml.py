"""Tests for the per-position player ML feature builder and model wrapper."""

import numpy as np
import pytest
from unittest.mock import MagicMock

from src.prediction.player_features import (
    FEATURE_NAMES,
    POSITIONS,
    _vegas_team_total,
    build_player_feature_vector,
    feature_dict_to_array,
)
from src.prediction import player_ml_model
from src.prediction.player_ml_model import (
    MODEL_VERSION,
    PlayerModelCache,
    explain_player_prediction,
    model_info,
    predict_player_points,
    train_position_model,
)


# ── Feature builder ──────────────────────────────────────────────────────────

def test_feature_names_length_matches_positions():
    assert len(FEATURE_NAMES) == 13
    assert POSITIONS == ('QB', 'RB', 'WR', 'TE')


def test_vegas_team_total_home_favorite():
    # spread -3 (home favored), O/U 48 → home implied 25.5
    assert _vegas_team_total(-3.0, 48.0, is_home=True) == pytest.approx(25.5)
    # away gets 22.5
    assert _vegas_team_total(-3.0, 48.0, is_home=False) == pytest.approx(22.5)


def test_vegas_team_total_fallback_when_missing():
    assert _vegas_team_total(None, None, is_home=True) == 22.0
    assert _vegas_team_total(-3.0, None, is_home=True) == 22.0


def test_build_player_feature_vector_shape_and_defaults():
    db = MagicMock()
    db.get_player_weekly_stats.return_value = []
    db.get_opponent_position_allowed.return_value = 0.0
    db.get_advanced_stats.return_value = None

    feats = build_player_feature_vector(
        db, player_id=1, position='WR', season=2024, week=5,
        opponent_team_id=42, is_home=True, spread=-3.0, over_under=48.0,
        weather_is_adverse=False,
    )
    assert set(feats.keys()) == set(FEATURE_NAMES)
    arr = feature_dict_to_array(feats)
    assert arr.shape == (len(FEATURE_NAMES),)
    # no historical rows → rolling metrics are 0.0, weeks_of_experience is 0
    assert feats['rolling_4wk_ppr'] == 0.0
    assert feats['weeks_of_experience'] == 0.0
    assert feats['is_home'] == 1.0
    assert feats['vegas_team_total'] == pytest.approx(25.5)
    # fallback YPP when no advanced stats
    assert feats['opp_yards_per_play'] == 5.5


def test_build_player_feature_vector_uses_rolling_averages():
    db = MagicMock()
    # 5 weeks of history — newest first convention
    db.get_player_weekly_stats.return_value = [
        {'fantasy_points_ppr': 20.0, 'snap_pct': 0.9, 'target_share': 0.28,
         'adot': 11.0, 'rush_attempts': 0},
        {'fantasy_points_ppr': 15.0, 'snap_pct': 0.85, 'target_share': 0.25,
         'adot': 10.0, 'rush_attempts': 0},
        {'fantasy_points_ppr': 10.0, 'snap_pct': 0.80, 'target_share': 0.22,
         'adot': 9.0, 'rush_attempts': 0},
        {'fantasy_points_ppr': 5.0, 'snap_pct': 0.75, 'target_share': 0.20,
         'adot': 8.0, 'rush_attempts': 0},
        {'fantasy_points_ppr': 25.0, 'snap_pct': 0.95, 'target_share': 0.30,
         'adot': 12.0, 'rush_attempts': 0},
    ]
    db.get_opponent_position_allowed.return_value = 14.5
    db.get_advanced_stats.return_value = {'yards_per_play': 6.2}

    feats = build_player_feature_vector(
        db, player_id=99, position='WR', season=2024, week=6,
        opponent_team_id=10, is_home=False, spread=None, over_under=None,
    )
    assert feats['rolling_4wk_ppr'] == pytest.approx((20 + 15 + 10 + 5) / 4)
    assert feats['rolling_8wk_ppr'] == pytest.approx((20 + 15 + 10 + 5 + 25) / 5)
    assert feats['season_ppg_ppr'] == pytest.approx(15.0)
    assert feats['opp_dvp_pts_4wk'] == 14.5
    assert feats['opp_yards_per_play'] == pytest.approx(6.2)
    assert feats['weeks_of_experience'] == 5.0
    assert feats['is_home'] == 0.0


# ── Model wrapper ────────────────────────────────────────────────────────────

def test_train_position_model_empty_raises():
    with pytest.raises(ValueError):
        train_position_model(np.zeros((0, len(FEATURE_NAMES))), np.zeros(0), 'QB')


def test_train_position_model_writes_artifacts(tmp_path, monkeypatch):
    # Redirect model dir to tmp
    monkeypatch.setattr(player_ml_model, '_DATA_DIR', tmp_path)

    rng = np.random.default_rng(42)
    n = 250
    X = rng.normal(size=(n, len(FEATURE_NAMES)))
    # Simple linear-ish relation so model learns something real
    y = (X[:, 0] * 2.5 + X[:, 2] * 1.5 + X[:, 9] * 0.8
         + rng.normal(scale=0.5, size=n) + 12.0)

    res = train_position_model(X, y, 'WR')
    assert res['n_training_samples'] == n
    assert res['position'] == 'WR'
    assert res['cv_mae'] > 0
    assert (tmp_path / 'WR_model.joblib').exists()
    assert (tmp_path / 'WR_meta.json').exists()


def test_predict_and_explain_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(player_ml_model, '_DATA_DIR', tmp_path)
    # Fresh cache per test run
    monkeypatch.setattr(player_ml_model, '_cache', PlayerModelCache())

    rng = np.random.default_rng(7)
    n = 250
    X = rng.normal(size=(n, len(FEATURE_NAMES)))
    y = X[:, 0] * 3.0 + rng.normal(scale=0.4, size=n) + 10.0
    train_position_model(X, y, 'QB')

    vec = np.zeros(len(FEATURE_NAMES), dtype=np.float64)
    vec[0] = 1.0
    pred = predict_player_points(vec, 'QB')
    assert pred is not None
    assert pred >= 0.0

    feat_dict = {name: float(vec[i]) for i, name in enumerate(FEATURE_NAMES)}
    contribs = explain_player_prediction(vec, feat_dict, 'QB', top_k=5)
    assert isinstance(contribs, list)
    assert len(contribs) <= 5
    if contribs:
        e = contribs[0]
        assert set(e.keys()) == {'feature', 'label', 'shap_value', 'direction', 'feature_value'}
        assert e['direction'] in ('up', 'down', 'neutral')


def test_predict_returns_none_without_model(tmp_path, monkeypatch):
    monkeypatch.setattr(player_ml_model, '_DATA_DIR', tmp_path)
    monkeypatch.setattr(player_ml_model, '_cache', PlayerModelCache())
    vec = np.zeros(len(FEATURE_NAMES), dtype=np.float64)
    assert predict_player_points(vec, 'TE') is None
    assert explain_player_prediction(vec, {}, 'TE') == []


def test_model_info_reports_version(tmp_path, monkeypatch):
    monkeypatch.setattr(player_ml_model, '_DATA_DIR', tmp_path)
    info = model_info()
    assert info['version'] == MODEL_VERSION
    assert set(info['positions'].keys()) == {'QB', 'RB', 'WR', 'TE'}
    # No models on disk → all not loaded
    for pos in ('QB', 'RB', 'WR', 'TE'):
        assert info['positions'][pos]['loaded'] is False
