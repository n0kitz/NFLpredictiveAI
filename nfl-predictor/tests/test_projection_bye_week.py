"""A player on bye projects zero, and advice paths know who the opponent is.

Measured 2026-11-14, week 10 (CHI/DEN/PHI/TB on bye): the projections cache
held Caleb Williams at 18.4 and Jalen Hurts at 16.0. The single-player path was
worse off — My Team, start/sit, FAAB and trade ROS all called
``calculate_projection(..., opponent_team_id=None)``, so they neither applied a
matchup nor noticed a bye, and would start a player whose team isn't playing.
"""

import pytest

from src.database.db import Database
from src.prediction.fantasy_scorer import FantasyScorer
from src.prediction.roster_advisor import build_roster_pool

SEASON = 2026
CHI, GB, DET = 1, 2, 3
BYE_QB, PLAYING_QB = 10, 11


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "bye.db")
    for tid, abbr in [(CHI, "CHI"), (GB, "GB"), (DET, "DET")]:
        database.execute(
            "INSERT INTO teams (team_id, name, abbreviation, city, conference, division) "
            "VALUES (?, ?, ?, 'X', 'NFC', 'NFC North')",
            (tid, abbr, abbr),
        )
    for pid, name, team, pts in [
        (BYE_QB, "Bye Quarterback", CHI, 180.0),
        (PLAYING_QB, "Playing Quarterback", GB, 120.0),
    ]:
        database.execute(
            "INSERT INTO players (player_id, full_name, position) VALUES (?, ?, 'QB')",
            (pid, name),
        )
        database.execute(
            "INSERT INTO roster_entries (player_id, team_id, season, is_starter) "
            "VALUES (?, ?, ?, 1)",
            (pid, team, SEASON),
        )
        database.execute(
            "INSERT INTO player_season_stats (player_id, team_id, season, games_played, "
            "fantasy_points_ppr, fantasy_points_standard) VALUES (?, ?, ?, 10, ?, ?)",
            (pid, team, SEASON, pts, pts),
        )
    yield database
    database.close()


def _game(db, week, home, away):
    db.execute(
        "INSERT INTO games (date, season, week, game_type, home_team_id, away_team_id) "
        "VALUES (?, ?, ?, 'regular', ?, ?)",
        (f"2026-11-{week:02d}", SEASON, str(week), home, away),
    )


def _schedule_with_chi_bye_in_week_10(db):
    _game(db, 9, CHI, GB)
    _game(db, 10, GB, DET)  # CHI idle
    _game(db, 11, DET, CHI)


class TestSinglePlayerProjection:
    def test_bye_week_projects_zero_and_says_so(self, db):
        _schedule_with_chi_bye_in_week_10(db)
        proj = FantasyScorer(db).calculate_projection(BYE_QB, 10, SEASON, None)
        assert proj["projected_points_std"] == 0.0
        assert proj["projected_points_ppr"] == 0.0
        assert proj["on_bye"] is True
        assert proj["opponent_team_id"] is None

    def test_opponent_is_resolved_from_the_schedule(self, db):
        _schedule_with_chi_bye_in_week_10(db)
        proj = FantasyScorer(db).calculate_projection(BYE_QB, 11, SEASON, None)
        assert proj["opponent_team_id"] == DET
        assert proj["on_bye"] is False
        assert proj["projected_points_std"] > 0

    def test_explicit_opponent_is_respected(self, db):
        _schedule_with_chi_bye_in_week_10(db)
        proj = FantasyScorer(db).calculate_projection(BYE_QB, 10, SEASON, GB)
        assert proj["opponent_team_id"] == GB
        assert proj["on_bye"] is False
        assert proj["projected_points_std"] > 0

    def test_season_without_a_schedule_is_not_a_bye(self, db):
        # Pre-schedule draft prep: no games loaded must not zero everyone.
        proj = FantasyScorer(db).calculate_projection(BYE_QB, 10, SEASON, None)
        assert proj["on_bye"] is False
        assert proj["projected_points_std"] == 18.0

    def test_week_after_the_teams_last_game_is_not_a_bye(self, db):
        _schedule_with_chi_bye_in_week_10(db)
        proj = FantasyScorer(db).calculate_projection(BYE_QB, 12, SEASON, None)
        assert proj["on_bye"] is False


class TestAdvicePaths:
    def test_roster_pool_values_the_bye_player_at_zero(self, db):
        _schedule_with_chi_bye_in_week_10(db)
        pool = build_roster_pool(FantasyScorer(db), [BYE_QB, PLAYING_QB], 10, SEASON)
        points = {p.player_id: p.projected_points for p in pool}
        # 18.0/game on bye must lose to 12.0/game who actually plays.
        assert points[BYE_QB] == 0.0
        assert points[PLAYING_QB] > 0

    def test_start_sit_sits_the_bye_player_and_explains_why(self, db):
        _schedule_with_chi_bye_in_week_10(db)
        result = FantasyScorer(db).rank_start_sit([BYE_QB, PLAYING_QB], 10, SEASON)
        by_id = {r["player_id"]: r for r in result["ranked"]}
        assert by_id[PLAYING_QB]["verdict"] == "start"
        assert by_id[BYE_QB]["verdict"] == "sit"
        assert "bye" in by_id[BYE_QB]["reasoning"].lower()


class TestBulkProjections:
    def test_bye_team_players_are_cached_at_zero(self, db):
        _schedule_with_chi_bye_in_week_10(db)
        rows = FantasyScorer(db).generate_weekly_projections(SEASON, 10)
        by_id = {r["player_id"]: r for r in rows}
        assert by_id[BYE_QB]["projected_points_std"] == 0.0
        assert by_id[BYE_QB]["floor_ppr"] == 0.0
        assert by_id[BYE_QB]["ceiling_ppr"] == 0.0
        assert by_id[BYE_QB]["on_bye"] is True
        assert by_id[PLAYING_QB]["projected_points_std"] > 0
        assert by_id[PLAYING_QB]["on_bye"] is False
