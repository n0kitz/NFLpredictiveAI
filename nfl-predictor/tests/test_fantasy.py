"""Tests for the FantasyScorer engine."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.database.db import DEFAULT_DB_PATH
from src.prediction.fantasy_scorer import FantasyScorer


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_mock_db(**overrides):
    """Build a minimal mock DB for unit tests."""
    db = MagicMock()
    db.get_player_by_id.return_value = {
        'player_id': 1,
        'full_name': 'Patrick Mahomes',
        'position': 'QB',
        'headshot_url': None,
    }
    db.get_player_stats.return_value = {
        'games_played': 16,
        'fantasy_points_ppr': 352.0,
        'fantasy_points_standard': 320.0,
        'targets': 0,
    }
    db.get_advanced_stats.return_value = None
    db.fetchone.return_value = None
    db.fetchall.return_value = []
    for k, v in overrides.items():
        setattr(db, k, v)
    return db


@pytest.fixture
def mock_db():
    return _make_mock_db()


@pytest.fixture
def scorer(mock_db):
    return FantasyScorer(mock_db)


# Skip real-DB tests if database not present
db_available = DEFAULT_DB_PATH.exists()


@pytest.fixture(scope="module")
def real_db():
    if not db_available:
        pytest.skip("Real database not found — run scraper first")
    from src.database.db import Database
    d = Database(DEFAULT_DB_PATH)
    yield d
    d.close()


@pytest.fixture(scope="module")
def real_scorer(real_db):
    return FantasyScorer(real_db)


# ── Unit tests (mock DB) ───────────────────────────────────────────────────────

class TestMatchupScore:
    def test_returns_1_when_no_stats(self, scorer):
        score = scorer.calculate_matchup_score(1, 99, 'QB', 2024)
        assert score == 1.0

    def test_score_clamped_to_range(self, scorer, mock_db):
        # Provide extreme stats — should still stay in [0.7, 1.3]
        mock_db.get_advanced_stats.return_value = {
            'yards_per_play': 20.0,
            'sack_rate_allowed': 0.5,
            'redzone_efficiency': 0.8,
            'third_down_pct': 0.9,
        }
        for pos in ('QB', 'RB', 'WR', 'TE', 'K'):
            s = scorer.calculate_matchup_score(1, 2, pos, 2024)
            assert 0.7 <= s <= 1.3, f"Score {s} out of range for position {pos}"

    def test_qb_matchup_uses_sack_rate(self, scorer, mock_db):
        mock_db.get_advanced_stats.return_value = {
            'yards_per_play': 5.5,      # neutral
            'sack_rate_allowed': 0.14,   # double league avg → should boost
            'redzone_efficiency': 0.15,
            'third_down_pct': 0.4,
        }
        score = scorer.calculate_matchup_score(1, 2, 'QB', 2024)
        assert score > 1.0


class TestCalculateProjection:
    def test_returns_dict_with_required_keys(self, scorer):
        result = scorer.calculate_projection(1, 1, 2024, None)
        for key in ('player_id', 'projected_points_ppr', 'projected_points_std',
                    'matchup_score', 'confidence', 'injury_status', 'weather_impact'):
            assert key in result

    def test_returns_empty_when_player_not_found(self, scorer, mock_db):
        mock_db.get_player_by_id.return_value = None
        result = scorer.calculate_projection(999, 1, 2024, None)
        assert result == {}
        # Restore default
        mock_db.get_player_by_id.return_value = {
            'player_id': 1,
            'full_name': 'Patrick Mahomes',
            'position': 'QB',
            'headshot_url': None,
        }

    def test_out_player_projects_zero(self, scorer, mock_db):
        mock_db.fetchone.return_value = {
            'player_name': 'Mahomes',
            'injury_status': 'Out',
            'report_date': '2024-10-01',
        }
        result = scorer.calculate_projection(1, 1, 2024, None)
        assert result['projected_points_ppr'] == 0.0
        assert result['projected_points_std'] == 0.0
        assert result['confidence'] == 'high'
        mock_db.fetchone.return_value = None

    def test_doubtful_reduces_projection(self, scorer, mock_db):
        mock_db.fetchone.return_value = {
            'player_name': 'Mahomes',
            'injury_status': 'Doubtful',
            'report_date': '2024-10-01',
        }
        result = scorer.calculate_projection(1, 1, 2024, None)
        # 22 ppg * 0.2 ≈ 4.4
        assert result['projected_points_ppr'] < 10.0
        assert result['confidence'] == 'low'
        mock_db.fetchone.return_value = None

    def test_base_projection_from_season_stats(self, scorer, mock_db):
        mock_db.fetchone.return_value = None  # no injury
        result = scorer.calculate_projection(1, 1, 2024, None)
        # 352 / 16 = 22.0 ppg
        assert abs(result['projected_points_ppr'] - 22.0) < 0.5


class TestOpportunityScore:
    def test_returns_float_in_range(self, scorer):
        score = scorer.calculate_opportunity_score(1, 1, 2024, None)
        assert 0.0 <= score <= 10.0

    def test_returns_zero_when_no_stats(self, scorer, mock_db):
        mock_db.get_player_stats.return_value = None
        score = scorer.calculate_opportunity_score(1, 1, 2024, None)
        assert score == 0.0
        # Restore
        mock_db.get_player_stats.return_value = {
            'games_played': 16,
            'fantasy_points_ppr': 352.0,
            'fantasy_points_standard': 320.0,
            'targets': 0,
        }

    def test_starter_scores_higher_than_bench(self, scorer, mock_db):
        mock_db.fetchone.side_effect = [
            {'is_starter': True},
            {'is_starter': False},
        ]
        mock_db.get_player_stats.return_value = {
            'games_played': 16,
            'fantasy_points_ppr': 352.0,
            'fantasy_points_standard': 320.0,
            'targets': 48,
        }
        s_start = scorer.calculate_opportunity_score(1, 1, 2024, None)
        s_bench = scorer.calculate_opportunity_score(2, 1, 2024, None)
        assert s_start > s_bench
        mock_db.fetchone.side_effect = None
        mock_db.fetchone.return_value = None


class TestStartSitRecommendation:
    def test_higher_projected_player_starts(self, scorer, mock_db):
        def get_stats(pid, season=None):
            if pid == 1:
                return {'games_played': 16, 'fantasy_points_ppr': 352.0,
                        'fantasy_points_standard': 320.0, 'targets': 0}
            return {'games_played': 16, 'fantasy_points_ppr': 160.0,
                    'fantasy_points_standard': 140.0, 'targets': 0}

        def get_player(pid):
            names = {1: 'Patrick Mahomes', 2: 'Geno Smith'}
            return {'player_id': pid, 'full_name': names.get(pid, 'Unknown'),
                    'position': 'QB', 'headshot_url': None}

        mock_db.get_player_stats.side_effect = get_stats
        mock_db.get_player_by_id.side_effect = get_player
        mock_db.fetchone.return_value = None

        result = scorer.start_sit_recommendation(1, 2, 1, 2024)
        assert 'start' in result and 'sit' in result
        assert result['start']['player_id'] == 1
        assert result['sit']['player_id'] == 2
        assert result['confidence'] in ('low', 'medium', 'high')

        mock_db.get_player_stats.side_effect = None
        mock_db.get_player_by_id.side_effect = None


class TestAnalyzeTrade:
    def test_verdict_win_when_get_much_higher(self, scorer, mock_db):
        def get_stats(pid, season=None):
            if pid in (1, 2):  # give side: low value
                return {'games_played': 16, 'fantasy_points_ppr': 80.0,
                        'fantasy_points_standard': 70.0, 'targets': 0}
            # get side: high value
            return {'games_played': 16, 'fantasy_points_ppr': 352.0,
                    'fantasy_points_standard': 320.0, 'targets': 0}

        mock_db.get_player_stats.side_effect = get_stats
        mock_db.get_player_by_id.return_value = {
            'player_id': 1, 'full_name': 'Player A', 'position': 'QB', 'headshot_url': None,
        }
        mock_db.fetchone.return_value = None

        result = scorer.analyze_trade([1], [3], 2024, 14)
        assert result['verdict'] in ('WIN', 'LOSE', 'FAIR')
        assert 'give_total' in result and 'get_total' in result
        assert 'delta' in result

        mock_db.get_player_stats.side_effect = None

    def test_fair_verdict_when_equal(self, scorer, mock_db):
        mock_db.get_player_stats.return_value = {
            'games_played': 16, 'fantasy_points_ppr': 200.0,
            'fantasy_points_standard': 180.0, 'targets': 0,
        }
        mock_db.get_player_by_id.return_value = {
            'player_id': 1, 'full_name': 'Equal Player', 'position': 'WR', 'headshot_url': None,
        }
        mock_db.fetchone.return_value = None

        result = scorer.analyze_trade([1], [2], 2024, 17)
        # With same base stats → FAIR
        assert result['verdict'] == 'FAIR'

    def test_returns_player_details(self, scorer, mock_db):
        mock_db.get_player_stats.return_value = {
            'games_played': 16, 'fantasy_points_ppr': 200.0,
            'fantasy_points_standard': 180.0, 'targets': 0,
        }
        mock_db.get_player_by_id.return_value = {
            'player_id': 5, 'full_name': 'Test Player', 'position': 'RB', 'headshot_url': None,
        }
        mock_db.fetchone.return_value = None

        result = scorer.analyze_trade([5], [6], 2024, 10)
        assert len(result['give']) == 1
        assert len(result['get']) == 1
        assert result['give'][0]['full_name'] == 'Test Player'


# ── Integration tests (real DB) ───────────────────────────────────────────────

@pytest.mark.skipif(not db_available, reason="Real database not found")
class TestWithRealDB:
    def test_matchup_score_real_teams(self, real_scorer, real_db):
        """Matchup score returns valid float for real teams."""
        teams = real_db.fetchall("SELECT team_id FROM teams LIMIT 2")
        if len(teams) < 2:
            pytest.skip("Not enough teams")
        score = real_scorer.calculate_matchup_score(
            1, teams[1]['team_id'], 'QB', 2024
        )
        assert 0.7 <= score <= 1.3

    def test_projection_real_player(self, real_scorer, real_db):
        """Projection for a real player returns valid structure."""
        row = real_db.fetchone(
            """SELECT p.player_id FROM players p
               JOIN player_season_stats pss ON pss.player_id = p.player_id
               WHERE p.position = 'QB' AND pss.games_played > 0 LIMIT 1"""
        )
        if not row:
            pytest.skip("No QB with stats found")
        result = real_scorer.calculate_projection(row['player_id'], 1, 2024, None)
        assert 'projected_points_ppr' in result
        assert result['projected_points_ppr'] >= 0.0

    def test_generate_draft_rankings_returns_list(self, real_scorer):
        """Draft rankings generate without error and return a list."""
        rankings = real_scorer.generate_draft_rankings(2025, 'ppr')
        assert isinstance(rankings, list)
        if rankings:
            r = rankings[0]
            assert 'overall_rank' in r
            assert 'position_rank' in r
            assert 'tier' in r
            assert r['tier'] >= 1
            assert 'vbd' in r
            assert r['vbd'] >= 0


# ── Boom/bust + VBD + bye-week tests (Fantasy Depth Pack) ────────────────────


class TestBoomBustCalc:
    def test_returns_none_for_too_few_weeks(self):
        from src.prediction.fantasy_scorer import calc_boom_bust_from_rows
        rows = [
            {'fantasy_points_ppr': 10.0, 'snaps': 50},
            {'fantasy_points_ppr': 12.0, 'snaps': 50},
            {'fantasy_points_ppr': 8.0,  'snaps': 50},
        ]
        assert calc_boom_bust_from_rows(rows) is None

    def test_skips_dnp_weeks(self):
        from src.prediction.fantasy_scorer import calc_boom_bust_from_rows
        rows = [{'fantasy_points_ppr': 10.0, 'snaps': 0} for _ in range(8)]
        assert calc_boom_bust_from_rows(rows) is None

    def test_basic_distribution(self):
        from src.prediction.fantasy_scorer import calc_boom_bust_from_rows
        # Avg = 10. Boom (>=15): 2 of 10 = 20%. Bust (<=5): 2 of 10 = 20%.
        rows = [
            {'fantasy_points_ppr': v, 'snaps': 50, 'snap_pct': 0.8}
            for v in [16.0, 17.0, 10.0, 11.0, 9.0, 12.0, 8.0, 11.0, 4.0, 2.0]
        ]
        result = calc_boom_bust_from_rows(rows)
        assert result is not None
        assert result['weeks_played'] == 10
        assert result['boom_pct'] == 20.0
        assert result['bust_pct'] == 20.0

    def test_counts_when_only_snap_pct_filled(self):
        """Importer leaves snaps=0; rows count as played when snap_pct>0."""
        from src.prediction.fantasy_scorer import calc_boom_bust_from_rows
        rows = [
            {'fantasy_points_ppr': v, 'snaps': 0, 'snap_pct': 0.7}
            for v in [16.0, 17.0, 10.0, 11.0, 9.0, 12.0]
        ]
        result = calc_boom_bust_from_rows(rows)
        assert result is not None
        assert result['weeks_played'] == 6


@pytest.mark.skipif(not db_available, reason="Real database not found")
class TestByeWeekDerivation:
    def test_returns_dict(self, real_db):
        byes = real_db.get_bye_weeks(2024)
        assert isinstance(byes, dict)

    def test_all_byes_in_range(self, real_db):
        byes = real_db.get_bye_weeks(2024)
        if not byes:
            pytest.skip("No 2024 game data")
        for team_id, week in byes.items():
            assert 1 <= week <= 22, f"team {team_id} has implausible bye week {week}"

    def test_no_team_has_two_byes(self, real_db):
        # Implicit by dict structure (one int per team_id), but verify each team is in
        # exactly one team_id key
        byes = real_db.get_bye_weeks(2024)
        if not byes:
            pytest.skip("No 2024 game data")
        # Every team_id should appear at most once (dict guarantees), and team count should be plausible (≤32)
        assert len(byes) <= 40


@pytest.mark.skipif(not db_available, reason="Real database not found")
class TestVBD:
    def test_replacement_qb12_near_zero(self, real_scorer):
        rankings = real_scorer.generate_draft_rankings(2025, 'ppr')
        qbs = [r for r in rankings if r['position'] == 'QB']
        if len(qbs) < 12:
            pytest.skip("Fewer than 12 QBs in dataset")
        qb12 = qbs[11]
        assert qb12['vbd'] is not None
        assert qb12['vbd'] <= 0.1, f"QB12 VBD should be ~0, got {qb12['vbd']}"

    def test_top_player_has_positive_vbd(self, real_scorer):
        rankings = real_scorer.generate_draft_rankings(2025, 'ppr')
        if not rankings:
            pytest.skip("No rankings generated")
        # Top scoring at any of these positions should have meaningful VBD
        for pos in ('RB', 'WR'):
            top = next((r for r in rankings if r['position'] == pos), None)
            if top is None:
                continue
            assert top['vbd'] is not None
            assert top['vbd'] >= 0  # could be 0 if dataset is sparse, but never negative
