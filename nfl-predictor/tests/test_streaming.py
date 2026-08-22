"""Streaming recommendations: best available DST/K/QB for a week.

matchup_grade() scores a position vs. an opponent, not an individual player
— every QB on the same team facing the same defense gets an identical
grade. So the candidate pool is deduplicated to one player per team before
grading, rather than grading (and then ranking side by side) every backup
on the depth chart, which would just be noise.

roster_entries carries no depth-chart or starter flag (verified empty on
live data), so "who's actually playing" is approximated by games played —
this season if any exist yet, else the prior season as a preseason
fallback, mirroring the fallback pattern already used elsewhere
(calculate_projection, opp_position_dvp).
"""

from unittest.mock import MagicMock, patch

import pytest

from src.prediction.streaming import STREAMABLE_POSITIONS, streaming_candidates


def _db():
    db = MagicMock()
    db.fetchall.return_value = []
    db.fetchone.return_value = None
    db.get_player_by_id.return_value = None
    return db


def _grade(score):
    return {"grade": "B", "score": score, "explanation": f"score={score}"}


class TestPositionValidation:
    def test_rejects_non_streamable_position(self):
        db = _db()
        with pytest.raises(ValueError):
            streaming_candidates(db, "WR", week=1, season=2026)

    def test_streamable_positions_are_qb_k_dst(self):
        assert STREAMABLE_POSITIONS == {"QB", "K", "DST"}


class TestDeduplication:
    @patch("src.prediction.streaming.matchup_grade")
    def test_only_one_candidate_per_team(self, mock_grade):
        db = _db()
        # Two QBs on team 1: the backup (fewer games) must not also appear.
        db.fetchall.side_effect = [
            [  # _team_candidates roster query
                {"team_id": 1, "player_id": 10, "gp_cur": 15, "gp_prev": 16},
                {"team_id": 1, "player_id": 11, "gp_cur": 2, "gp_prev": 0},
            ],
            [
                {"week_int": 1, "home_team_id": 1, "away_team_id": 9}
            ],  # schedule for team 1
        ]
        db.fetchone.return_value = {"abbreviation": "BUF"}
        db.get_player_by_id.return_value = {"full_name": "Josh Allen"}
        mock_grade.return_value = _grade(80.0)

        result = streaming_candidates(db, "QB", week=1, season=2026)
        assert [c["player_id"] for c in result] == [10]

    @patch("src.prediction.streaming.matchup_grade")
    def test_falls_back_to_prior_season_games_played(self, mock_grade):
        db = _db()
        # Preseason: no games played yet this season, but last season's
        # starter had 16 games and the backup had 0.
        db.fetchall.side_effect = [
            [
                {"team_id": 1, "player_id": 10, "gp_cur": 0, "gp_prev": 16},
                {"team_id": 1, "player_id": 11, "gp_cur": 0, "gp_prev": 0},
            ],
            [{"week_int": 1, "home_team_id": 1, "away_team_id": 9}],
        ]
        db.fetchone.return_value = {"abbreviation": "BUF"}
        db.get_player_by_id.return_value = {"full_name": "Josh Allen"}
        mock_grade.return_value = _grade(80.0)

        result = streaming_candidates(db, "QB", week=1, season=2026)
        assert [c["player_id"] for c in result] == [10]


class TestFiltering:
    @patch("src.prediction.streaming.matchup_grade")
    def test_excludes_rostered_players(self, mock_grade):
        db = _db()
        db.fetchall.side_effect = [
            [{"team_id": 1, "player_id": 10, "gp_cur": 10, "gp_prev": 10}],
            [{"week_int": 1, "home_team_id": 1, "away_team_id": 9}],
        ]
        db.fetchone.return_value = {"abbreviation": "BUF"}
        db.get_player_by_id.return_value = {"full_name": "Josh Allen"}
        mock_grade.return_value = _grade(80.0)

        result = streaming_candidates(
            db, "QB", week=1, season=2026, exclude_player_ids=[10]
        )
        assert result == []
        mock_grade.assert_not_called()

    def test_team_on_bye_this_week_is_excluded(self):
        db = _db()
        db.fetchall.side_effect = [
            [{"team_id": 1, "player_id": 10, "gp_cur": 10, "gp_prev": 10}],
            [],  # no game found for the requested week -> bye
        ]
        db.fetchone.return_value = {"abbreviation": "BUF"}
        db.get_player_by_id.return_value = {"full_name": "Josh Allen"}

        result = streaming_candidates(db, "QB", week=1, season=2026)
        assert result == []


class TestRankingAndLimit:
    @patch("src.prediction.streaming.matchup_grade")
    def test_sorted_best_matchup_first(self, mock_grade):
        db = _db()
        db.fetchall.side_effect = [
            [
                {"team_id": 1, "player_id": 10, "gp_cur": 10, "gp_prev": 10},
                {"team_id": 2, "player_id": 20, "gp_cur": 10, "gp_prev": 10},
            ],
            [{"week_int": 1, "home_team_id": 1, "away_team_id": 9}],  # team 1
            [{"week_int": 1, "home_team_id": 2, "away_team_id": 8}],  # team 2
        ]
        db.fetchone.return_value = {"abbreviation": "XX"}
        db.get_player_by_id.side_effect = lambda pid: {"full_name": f"P{pid}"}
        mock_grade.side_effect = [_grade(60.0), _grade(90.0)]

        result = streaming_candidates(db, "QB", week=1, season=2026)
        assert [c["player_id"] for c in result] == [20, 10]

    @patch("src.prediction.streaming.matchup_grade")
    def test_limit_truncates(self, mock_grade):
        db = _db()
        db.fetchall.side_effect = [
            [
                {"team_id": 1, "player_id": 10, "gp_cur": 10, "gp_prev": 10},
                {"team_id": 2, "player_id": 20, "gp_cur": 10, "gp_prev": 10},
            ],
            [{"week_int": 1, "home_team_id": 1, "away_team_id": 9}],
            [{"week_int": 1, "home_team_id": 2, "away_team_id": 8}],
        ]
        db.fetchone.return_value = {"abbreviation": "XX"}
        db.get_player_by_id.side_effect = lambda pid: {"full_name": f"P{pid}"}
        mock_grade.return_value = _grade(70.0)

        result = streaming_candidates(db, "QB", week=1, season=2026, limit=1)
        assert len(result) == 1


class TestCandidateShape:
    @patch("src.prediction.streaming.matchup_grade")
    def test_includes_grade_and_opponent(self, mock_grade):
        db = _db()
        db.fetchall.side_effect = [
            [{"team_id": 1, "player_id": 10, "gp_cur": 10, "gp_prev": 10}],
            [{"week_int": 1, "home_team_id": 1, "away_team_id": 9}],
        ]
        db.fetchone.side_effect = lambda query, params: (
            {"abbreviation": "BUF"} if params == (1,) else {"abbreviation": "NE"}
        )
        db.get_player_by_id.return_value = {"full_name": "Josh Allen"}
        mock_grade.return_value = {
            "grade": "A",
            "score": 92.5,
            "explanation": "Great matchup",
        }

        result = streaming_candidates(db, "QB", week=1, season=2026)
        assert result == [
            {
                "player_id": 10,
                "full_name": "Josh Allen",
                "team_abbr": "BUF",
                "opponent_team_abbr": "NE",
                "grade": "A",
                "score": 92.5,
                "explanation": "Great matchup",
            }
        ]
