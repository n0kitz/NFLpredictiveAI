"""Tests for Phase 2 — Advanced Matchup Engine."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from src.database.db import DEFAULT_DB_PATH
from src.prediction.matchup_engine import (
    opp_position_dvp,
    pace_adjusted_plays,
    pass_rate_over_expected,
    neutral_script_rates,
    matchup_grade,
    _sigmoid_score,
    _AVG_DVP,
)
from src.prediction.player_features import FEATURE_NAMES, build_player_feature_vector


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_db(**kwargs):
    """Minimal mock DB."""
    db = MagicMock()
    db.fetchall.return_value = []
    db.fetchone.return_value = None
    for k, v in kwargs.items():
        setattr(db, k, v)
    return db


db_available = DEFAULT_DB_PATH.exists()


@pytest.fixture(scope="module")
def real_db():
    if not db_available:
        pytest.skip("Real database not found — run scraper first")
    from src.database.db import Database
    d = Database(DEFAULT_DB_PATH)
    yield d
    d.close()


# ── Unit: _sigmoid_score ──────────────────────────────────────────────────────

class TestSigmoidScore:
    def test_league_average_is_50(self):
        assert _sigmoid_score(1.0) == 50.0

    def test_above_average_above_50(self):
        assert _sigmoid_score(1.2) > 50.0

    def test_below_average_below_50(self):
        assert _sigmoid_score(0.8) < 50.0

    def test_clamped_high(self):
        assert _sigmoid_score(5.0) == 100.0

    def test_clamped_low(self):
        assert _sigmoid_score(0.0) == 0.0


# ── Unit: opp_position_dvp ────────────────────────────────────────────────────

class TestOppPositionDvp:
    def test_returns_avg_dvp_when_no_data(self):
        db = _make_db()
        # Both queries return no data → fall back to league average
        db.fetchall.return_value = [{'avg_ppr': None}]
        result = opp_position_dvp(db, 1, 'WR', 2024, 10)
        assert result == _AVG_DVP['WR']

    def test_returns_query_result_when_data_present(self):
        db = _make_db()
        # First query has data
        db.fetchall.side_effect = [
            [{'avg_ppr': 14.5}],   # current season
        ]
        result = opp_position_dvp(db, 1, 'WR', 2024, 10)
        assert abs(result - 14.5) < 0.01

    def test_unknown_position_falls_back_gracefully(self):
        db = _make_db()
        db.fetchall.return_value = [{'avg_ppr': None}]
        result = opp_position_dvp(db, 1, 'LB', 2024, 10)
        assert result == 10.0  # default for unknown pos

    def test_prior_season_fallback(self):
        db = _make_db()
        # Current season → no data; prior season → data
        db.fetchall.side_effect = [
            [{'avg_ppr': None}],   # current season query
            [{'avg_ppr': 9.8}],    # prior season query
        ]
        result = opp_position_dvp(db, 1, 'RB', 2024, 10)
        assert abs(result - 9.8) < 0.01


# ── Unit: pace_adjusted_plays ─────────────────────────────────────────────────

class TestPaceAdjustedPlays:
    def test_league_average_pace_is_1(self):
        db = _make_db()
        # 44 total points per game → pace = 1.0
        db.fetchall.return_value = [{'avg_total': 44.0}]
        result = pace_adjusted_plays(db, 1, 2024)
        assert abs(result - 1.0) < 0.01

    def test_high_scoring_above_1(self):
        db = _make_db()
        db.fetchall.return_value = [{'avg_total': 55.0}]
        result = pace_adjusted_plays(db, 1, 2024)
        assert result > 1.0

    def test_low_scoring_below_1(self):
        db = _make_db()
        db.fetchall.return_value = [{'avg_total': 33.0}]
        result = pace_adjusted_plays(db, 1, 2024)
        assert result < 1.0

    def test_clamped_to_range(self):
        db = _make_db()
        db.fetchall.return_value = [{'avg_total': 999.0}]
        result = pace_adjusted_plays(db, 1, 2024)
        assert result <= 1.5

        db.fetchall.return_value = [{'avg_total': 0.0}]
        result2 = pace_adjusted_plays(db, 1, 2024)
        assert result2 >= 0.6

    def test_no_data_returns_1(self):
        db = _make_db()
        db.fetchall.return_value = [{'avg_total': None}]
        result = pace_adjusted_plays(db, 1, 2024)
        assert result == 1.0


# ── Unit: pass_rate_over_expected ─────────────────────────────────────────────

class TestPassRateOverExpected:
    def test_no_data_returns_0(self):
        db = _make_db()
        db.fetchone.return_value = None
        result = pass_rate_over_expected(db, 1, 2024)
        assert result == 0.0

    def test_positive_epa_gives_positive_proe(self):
        db = _make_db()
        db.fetchone.return_value = {'qb_epa_per_play': 0.15}
        result = pass_rate_over_expected(db, 1, 2024)
        assert result > 0.0

    def test_negative_epa_gives_negative_proe(self):
        db = _make_db()
        db.fetchone.return_value = {'qb_epa_per_play': -0.10}
        result = pass_rate_over_expected(db, 1, 2024)
        assert result < 0.0

    def test_clamped_to_bounds(self):
        db = _make_db()
        db.fetchone.return_value = {'qb_epa_per_play': 99.0}
        result = pass_rate_over_expected(db, 1, 2024)
        assert result <= 0.5

        db.fetchone.return_value = {'qb_epa_per_play': -99.0}
        result2 = pass_rate_over_expected(db, 1, 2024)
        assert result2 >= -0.5


# ── Unit: neutral_script_rates ───────────────────────────────────────────────

class TestNeutralScriptRates:
    def test_returns_dict_with_pass_rush_summing_to_1(self):
        db = _make_db()
        db.fetchall.return_value = []
        db.fetchone.return_value = None
        result = neutral_script_rates(db, 1, 2024)
        assert 'pass_rate' in result and 'rush_rate' in result
        assert abs(result['pass_rate'] + result['rush_rate'] - 1.0) < 0.001

    def test_pass_rate_in_reasonable_range(self):
        db = _make_db()
        db.fetchall.return_value = []
        db.fetchone.return_value = None
        result = neutral_script_rates(db, 1, 2024)
        assert 0.40 <= result['pass_rate'] <= 0.72


# ── Unit: matchup_grade ───────────────────────────────────────────────────────

_PATCH_DVP  = 'src.prediction.matchup_engine.opp_position_dvp'
_PATCH_PACE = 'src.prediction.matchup_engine.pace_adjusted_plays'
_PATCH_PROE = 'src.prediction.matchup_engine.pass_rate_over_expected'
_PATCH_RANK = 'src.prediction.matchup_engine._compute_league_rank'


def _grade_db(ypp=5.5):
    db = _make_db()
    db.fetchone.return_value = {'yards_per_play': ypp, 'qb_epa_per_play': 0.0}
    return db


class TestMatchupGrade:
    def test_grade_is_letter(self):
        db = _grade_db()
        with patch(_PATCH_DVP, return_value=11.0), \
             patch(_PATCH_PACE, return_value=1.0), \
             patch(_PATCH_PROE, return_value=0.0), \
             patch(_PATCH_RANK, return_value=16):
            result = matchup_grade(db, 1, 99, 'WR', 2024, 10)
        assert result['grade'] in ('A', 'B', 'C', 'D', 'F')

    def test_score_in_range(self):
        db = _grade_db()
        with patch(_PATCH_DVP, return_value=11.0), \
             patch(_PATCH_PACE, return_value=1.0), \
             patch(_PATCH_PROE, return_value=0.0), \
             patch(_PATCH_RANK, return_value=16):
            result = matchup_grade(db, 1, 99, 'WR', 2024, 10)
        assert 0.0 <= result['score'] <= 100.0

    def test_explanation_contains_grade(self):
        db = _grade_db()
        with patch(_PATCH_DVP, return_value=9.5), \
             patch(_PATCH_PACE, return_value=1.0), \
             patch(_PATCH_PROE, return_value=0.0), \
             patch(_PATCH_RANK, return_value=16):
            result = matchup_grade(db, 1, 99, 'RB', 2024, 10)
        assert 'Grade' in result['explanation']

    def test_high_dvp_gives_better_grade(self):
        """Opponent allowing 2× league avg PPR to WRs should score B or A."""
        high_dvp = _AVG_DVP['WR'] * 2.0
        db = _grade_db(ypp=6.5)
        with patch(_PATCH_DVP, return_value=high_dvp), \
             patch(_PATCH_PACE, return_value=1.15), \
             patch(_PATCH_PROE, return_value=0.1), \
             patch(_PATCH_RANK, return_value=1):
            result = matchup_grade(db, 1, 99, 'WR', 2024, 10)
        assert result['grade'] in ('A', 'B')

    def test_low_dvp_gives_worse_grade(self):
        """Opponent allowing 0.4× league avg PPR should score D or F."""
        low_dvp = _AVG_DVP['WR'] * 0.4
        db = _grade_db(ypp=4.5)
        with patch(_PATCH_DVP, return_value=low_dvp), \
             patch(_PATCH_PACE, return_value=0.85), \
             patch(_PATCH_PROE, return_value=-0.1), \
             patch(_PATCH_RANK, return_value=32):
            result = matchup_grade(db, 1, 99, 'WR', 2024, 10)
        assert result['grade'] in ('D', 'F')

    def test_rb_benefits_from_run_heavy_script(self):
        """Negative PROE (run-heavy) should help RB score vs pass-heavy."""
        dvp = _AVG_DVP['RB']
        db = _grade_db()
        with patch(_PATCH_DVP, return_value=dvp), \
             patch(_PATCH_PACE, return_value=1.0), \
             patch(_PATCH_PROE, return_value=0.15), \
             patch(_PATCH_RANK, return_value=16):
            pass_result = matchup_grade(db, 1, 99, 'RB', 2024, 10)

        with patch(_PATCH_DVP, return_value=dvp), \
             patch(_PATCH_PACE, return_value=1.0), \
             patch(_PATCH_PROE, return_value=-0.15), \
             patch(_PATCH_RANK, return_value=16):
            run_result = matchup_grade(db, 1, 99, 'RB', 2024, 10)

        assert run_result['score'] >= pass_result['score']

    def test_result_contains_all_expected_keys(self):
        db = _grade_db()
        with patch(_PATCH_DVP, return_value=8.0), \
             patch(_PATCH_PACE, return_value=1.0), \
             patch(_PATCH_PROE, return_value=0.0), \
             patch(_PATCH_RANK, return_value=16):
            result = matchup_grade(db, 1, 99, 'TE', 2024, 10)
        for key in ('grade', 'score', 'rank_vs_league', 'explanation', 'dvp_6wk',
                    'avg_league_dvp', 'opp_ypp', 'pace', 'proe', 'component_scores'):
            assert key in result, f"Missing key: {key}"


# ── Unit: feature vector has 16 features ─────────────────────────────────────

class TestFeatureVector16:
    def test_feature_names_count(self):
        assert len(FEATURE_NAMES) == 16

    def test_new_features_present(self):
        assert 'opp_pace' in FEATURE_NAMES
        assert 'opp_proe' in FEATURE_NAMES
        assert 'opp_pos_dvp_6wk' in FEATURE_NAMES

    def test_new_features_at_end(self):
        assert FEATURE_NAMES[-3] == 'opp_pace'
        assert FEATURE_NAMES[-2] == 'opp_proe'
        assert FEATURE_NAMES[-1] == 'opp_pos_dvp_6wk'

    def test_build_player_feature_vector_returns_16(self):
        db = MagicMock()
        db.get_player_weekly_stats.return_value = []
        db.get_opponent_position_allowed.return_value = 0.0
        db.get_advanced_stats.return_value = None
        # build_player_feature_vector call order: pace first, then dvp_6wk
        db.fetchall.side_effect = [
            [{'avg_total': 44.0}],  # pace current season (called first)
            [{'avg_ppr': None}],    # opp_pos_dvp_6wk current season
            [{'avg_ppr': None}],    # opp_pos_dvp_6wk prior season fallback
        ]
        db.fetchone.return_value = None  # proe + adv stats

        feats = build_player_feature_vector(
            db, player_id=1, position='WR', season=2024, week=5,
            opponent_team_id=10, is_home=True,
        )
        assert len(feats) == 16
        assert 'opp_pace' in feats
        assert 'opp_proe' in feats
        assert 'opp_pos_dvp_6wk' in feats


# ── Integration: real DB (skipped when DB absent) ────────────────────────────

@pytest.mark.skipif(not db_available, reason="Real database not found")
class TestMatchupEngineIntegration:
    def test_opp_position_dvp_real_db(self, real_db):
        teams = real_db.fetchall("SELECT team_id FROM teams LIMIT 1")
        if not teams:
            pytest.skip("No teams in DB")
        tid = teams[0]['team_id']
        result = opp_position_dvp(real_db, tid, 'WR', 2024, 10, lookback=6)
        assert isinstance(result, float)
        assert result >= 0.0

    def test_pace_real_db(self, real_db):
        teams = real_db.fetchall("SELECT team_id FROM teams LIMIT 1")
        if not teams:
            pytest.skip("No teams in DB")
        tid = teams[0]['team_id']
        result = pace_adjusted_plays(real_db, tid, 2024)
        assert 0.5 <= result <= 1.6

    def test_proe_real_db(self, real_db):
        teams = real_db.fetchall("SELECT team_id FROM teams LIMIT 1")
        if not teams:
            pytest.skip("No teams in DB")
        tid = teams[0]['team_id']
        result = pass_rate_over_expected(real_db, tid, 2024)
        assert isinstance(result, float)
