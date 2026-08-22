"""Bye-week + playoff-strength-of-schedule outlook — draft-time roster planning.

Two questions the app couldn't answer before this: does my roster stack
byes across too few weeks, and which of my players face a brutal stretch in
the fantasy playoffs (weeks 15-17)? Both derive from the schedule already
loaded (via ``get_bye_weeks`` and the ``games`` table), not a hardcoded bye
table, so a new season needs no manual update.
"""

from unittest.mock import MagicMock, patch

from src.prediction.schedule_outlook import (
    DEFAULT_PLAYOFF_WEEKS,
    BYE_COLLISION_THRESHOLD,
    build_schedule_outlook,
)


def _db():
    db = MagicMock()
    db.get_bye_weeks.return_value = {}
    db.get_player_by_id.return_value = None
    db.get_player_team_id.return_value = None
    db.fetchall.return_value = []
    db.fetchone.return_value = None
    return db


class TestConstants:
    def test_default_weeks_are_fantasy_playoffs(self):
        assert DEFAULT_PLAYOFF_WEEKS == (15, 16, 17)

    def test_collision_threshold_is_three(self):
        assert BYE_COLLISION_THRESHOLD == 3


class TestUnknownPlayers:
    def test_unknown_player_is_skipped_not_errored(self):
        db = _db()
        result = build_schedule_outlook(db, [999], season=2026)
        assert result["players"] == []

    def test_player_without_a_team_has_no_schedule(self):
        db = _db()
        db.get_player_by_id.return_value = {"full_name": "FA", "position": "WR"}
        result = build_schedule_outlook(db, [1], season=2026)
        p = result["players"][0]
        assert p["bye_week"] is None
        assert p["playoff_weeks"] == []
        assert p["playoff_sos_score"] is None


class TestByeWeek:
    def test_bye_week_comes_from_the_team(self):
        db = _db()
        db.get_player_by_id.return_value = {"full_name": "Josh Allen", "position": "QB"}
        db.get_player_team_id.return_value = 5
        db.get_bye_weeks.return_value = {5: 7}
        db.fetchone.return_value = {"abbreviation": "BUF"}
        result = build_schedule_outlook(db, [1], season=2026, weeks=())
        p = result["players"][0]
        assert p["bye_week"] == 7
        assert p["team_abbr"] == "BUF"


class TestPlayoffWeeks:
    @patch("src.prediction.schedule_outlook.opp_position_dvp")
    def test_tough_matchup_below_league_average_is_hard(self, mock_dvp):
        db = _db()
        db.get_player_by_id.return_value = {"full_name": "CMC", "position": "RB"}
        db.get_player_team_id.return_value = 1
        db.fetchone.return_value = {"abbreviation": "SF"}
        db.fetchall.return_value = [
            {"week_int": 15, "home_team_id": 1, "away_team_id": 9}
        ]
        mock_dvp.return_value = 6.0  # league_avg_dvp("RB") == 9.5
        result = build_schedule_outlook(db, [1], season=2026, weeks=(15,))
        wk = result["players"][0]["playoff_weeks"][0]
        assert wk == {
            "week": 15,
            "opponent_team_id": 9,
            "opponent_team_abbr": "SF",
            "dvp": 6.0,
            "difficulty": "hard",
        }

    @patch("src.prediction.schedule_outlook.opp_position_dvp")
    def test_generous_matchup_above_league_average_is_easy(self, mock_dvp):
        db = _db()
        db.get_player_by_id.return_value = {"full_name": "CMC", "position": "RB"}
        db.get_player_team_id.return_value = 1
        db.fetchone.return_value = {"abbreviation": "SF"}
        db.fetchall.return_value = [
            {"week_int": 15, "home_team_id": 1, "away_team_id": 9}
        ]
        mock_dvp.return_value = 13.0  # well above 9.5
        result = build_schedule_outlook(db, [1], season=2026, weeks=(15,))
        assert result["players"][0]["playoff_weeks"][0]["difficulty"] == "easy"

    @patch("src.prediction.schedule_outlook.opp_position_dvp")
    def test_near_average_matchup_is_medium(self, mock_dvp):
        db = _db()
        db.get_player_by_id.return_value = {"full_name": "CMC", "position": "RB"}
        db.get_player_team_id.return_value = 1
        db.fetchone.return_value = {"abbreviation": "SF"}
        db.fetchall.return_value = [
            {"week_int": 15, "home_team_id": 1, "away_team_id": 9}
        ]
        mock_dvp.return_value = 9.5  # exactly league average
        result = build_schedule_outlook(db, [1], season=2026, weeks=(15,))
        assert result["players"][0]["playoff_weeks"][0]["difficulty"] == "medium"

    @patch("src.prediction.schedule_outlook.opp_position_dvp")
    def test_non_skill_position_skips_dvp_but_keeps_opponent(self, mock_dvp):
        db = _db()
        db.get_player_by_id.return_value = {"full_name": "SF DST", "position": "DST"}
        db.get_player_team_id.return_value = 1
        db.fetchone.return_value = {"abbreviation": "SF"}
        db.fetchall.return_value = [
            {"week_int": 15, "home_team_id": 1, "away_team_id": 9}
        ]
        result = build_schedule_outlook(db, [1], season=2026, weeks=(15,))
        wk = result["players"][0]["playoff_weeks"][0]
        assert wk["opponent_team_id"] == 9
        assert wk["dvp"] is None
        assert wk["difficulty"] is None
        mock_dvp.assert_not_called()

    def test_bye_during_a_requested_week_produces_no_entry(self):
        db = _db()
        db.get_player_by_id.return_value = {"full_name": "X", "position": "WR"}
        db.get_player_team_id.return_value = 1
        db.fetchone.return_value = {"abbreviation": "X"}
        db.fetchall.return_value = []  # team has no game in any requested week
        result = build_schedule_outlook(db, [1], season=2026, weeks=(15, 16, 17))
        assert result["players"][0]["playoff_weeks"] == []
        assert result["players"][0]["playoff_sos_score"] is None

    @patch("src.prediction.schedule_outlook.opp_position_dvp")
    def test_sos_score_averages_the_evaluated_weeks(self, mock_dvp):
        db = _db()
        db.get_player_by_id.return_value = {"full_name": "X", "position": "WR"}
        db.get_player_team_id.return_value = 1
        db.fetchone.return_value = {"abbreviation": "X"}
        db.fetchall.return_value = [
            {"week_int": 15, "home_team_id": 1, "away_team_id": 2},
            {"week_int": 16, "home_team_id": 3, "away_team_id": 1},
        ]
        mock_dvp.side_effect = [8.0, 12.0]
        result = build_schedule_outlook(db, [1], season=2026, weeks=(15, 16))
        assert result["players"][0]["playoff_sos_score"] == 10.0


class TestByeCollisions:
    def test_three_or_more_sharing_a_bye_is_flagged(self):
        db = _db()
        db.get_player_by_id.side_effect = lambda pid: {
            "full_name": f"P{pid}",
            "position": "WR",
        }
        db.get_player_team_id.side_effect = lambda pid, season: {
            1: 10,
            2: 10,
            3: 10,
            4: 20,
        }[pid]
        db.get_bye_weeks.return_value = {10: 7, 20: 7}
        db.fetchone.return_value = {"abbreviation": "X"}
        result = build_schedule_outlook(db, [1, 2, 3, 4], season=2026, weeks=())
        assert result["bye_collisions"] == {7: [1, 2, 3, 4]}

    def test_two_sharing_a_bye_is_not_flagged(self):
        db = _db()
        db.get_player_by_id.side_effect = lambda pid: {
            "full_name": f"P{pid}",
            "position": "WR",
        }
        db.get_player_team_id.side_effect = lambda pid, season: {1: 10, 2: 20}[pid]
        db.get_bye_weeks.return_value = {10: 7, 20: 8}
        db.fetchone.return_value = {"abbreviation": "X"}
        result = build_schedule_outlook(db, [1, 2], season=2026, weeks=())
        assert result["bye_collisions"] == {}
