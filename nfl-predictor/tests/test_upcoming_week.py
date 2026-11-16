"""The week fantasy advice is *for* is the next one to be played.

``get_current_week()`` returns the most recently **completed** week. The cron
runs on Wednesday, when that week is already history — so projections were
regenerated for games that had been played, and every fantasy tab opened on
week 1 in mid-November. ``get_upcoming_week()`` is the week still to play.
"""

import pytest
from fastapi.testclient import TestClient

from src.database.db import Database


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "weeks.db")
    for tid, name, abbr in [(1, "Patriots", "NE"), (2, "Dolphins", "MIA")]:
        database.execute(
            "INSERT INTO teams (team_id, name, abbreviation, city, conference, division) "
            "VALUES (?, ?, ?, 'X', 'AFC', 'AFC East')",
            (tid, name, abbr),
        )
    yield database
    database.close()


def _game(db, week, played, season=2026, game_type="regular", day=1):
    score = (21, 14, 1) if played else (None, None, None)
    db.execute(
        "INSERT INTO games (date, season, week, game_type, home_team_id, away_team_id, "
        "home_score, away_score, winner_id) VALUES (?, ?, ?, ?, 1, 2, ?, ?, ?)",
        (f"2026-09-{day:02d}", season, str(week), game_type, *score),
    )


class TestGetUpcomingWeek:
    def test_first_week_with_an_unplayed_game(self, db):
        _game(db, 9, played=True, day=1)
        _game(db, 10, played=False, day=8)
        _game(db, 11, played=False, day=15)
        assert db.get_upcoming_week(2026) == 10

    def test_partially_played_week_is_still_the_upcoming_one(self, db):
        # Thursday night is done, Sunday isn't: lineups for week 10 still matter.
        _game(db, 9, played=True, day=1)
        _game(db, 10, played=True, day=5)
        _game(db, 10, played=False, day=8)
        assert db.get_upcoming_week(2026) == 10
        # ...whereas the completed-week helper keeps its old meaning.
        assert db.get_current_week(2026) == 10

    def test_weeks_compare_numerically_not_as_text(self, db):
        _game(db, 2, played=True, day=1)
        _game(db, 9, played=False, day=8)
        _game(db, 10, played=False, day=15)
        assert db.get_upcoming_week(2026) == 9

    def test_finished_regular_season_returns_last_week(self, db):
        _game(db, 17, played=True, day=1)
        _game(db, 18, played=True, day=8)
        _game(db, "Wild Card", played=False, game_type="playoff", day=15)
        assert db.get_upcoming_week(2026) == 18

    def test_season_without_games_is_week_one(self, db):
        assert db.get_upcoming_week(2026) == 1

    def test_other_seasons_are_ignored(self, db):
        _game(db, 5, played=False, season=2025, day=1)
        _game(db, 3, played=False, season=2026, day=8)
        assert db.get_upcoming_week(2026) == 3


class TestCurrentWeekEndpoint:
    def test_shape_and_bounds(self):
        from src.api.app import app

        r = TestClient(app).get("/api/fantasy/current-week")
        assert r.status_code == 200
        body = r.json()
        assert body["season"] > 2000
        assert 1 <= body["week"] <= 18


class TestResultsThroughWeek:
    def test_none_before_any_game_is_played(self, db):
        _game(db, 1, played=False)
        assert db.get_results_through_week(2026) is None

    def test_last_week_with_a_played_regular_season_game(self, db):
        _game(db, 9, played=True, day=1)
        _game(db, 10, played=True, day=5)
        _game(db, 10, played=False, day=8)
        assert db.get_results_through_week(2026) == 10

    def test_playoff_games_do_not_count_as_week_zero(self, db):
        _game(db, 18, played=True, day=1)
        _game(db, "Wild Card", played=True, game_type="playoff", day=8)
        assert db.get_results_through_week(2026) == 18


class TestHealthReportsResultFreshness:
    def test_health_exposes_result_and_upcoming_week(self):
        from src.api.app import app

        body = TestClient(app).get("/api/health").json()
        assert "results_through_week" in body
        assert body["results_season"] > 2000
        assert 1 <= body["upcoming_week"] <= 18
