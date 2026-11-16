"""The cron saves a pick for every game of the upcoming week.

Predictions are only graded by games played after they were made, so the
self-graded ledger grows solely from picks saved before kickoff. Until now that
needed a click in the UI per game; 2026 had one honest grade by week 10.
"""

from datetime import date
from types import SimpleNamespace

import pytest

from src.database.db import Database
from src.prediction.weekly_picks import save_upcoming_picks

TODAY = date(2026, 11, 18)  # a Wednesday


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "picks.db")
    for tid in range(1, 7):
        database.execute(
            "INSERT INTO teams (team_id, name, abbreviation, city, conference, division) "
            "VALUES (?, ?, ?, 'X', 'AFC', 'AFC East')",
            (tid, f"Team{tid}", f"T{tid}"),
        )
    yield database
    database.close()


def _game(db, home, away, day, week=11, played=False):
    score = (24, 17, home) if played else (None, None, None)
    db.execute(
        "INSERT INTO games (date, season, week, game_type, home_team_id, away_team_id, "
        "home_score, away_score, winner_id) VALUES (?, 2026, ?, 'regular', ?, ?, ?, ?, ?)",
        (day, str(week), home, away, *score),
    )


class FakeEngine:
    """Home wins 60/40; records how it was called."""

    def __init__(self, fail_for=None):
        self.calls = []
        self.fail_for = fail_for

    def predict(self, home_team, away_team, **kwargs):
        self.calls.append((home_team, away_team, kwargs))
        if home_team == self.fail_for:
            raise ValueError("no data")
        home_id = int(home_team[1:])
        away_id = int(away_team[1:])
        return SimpleNamespace(
            home_team_id=home_id,
            away_team_id=away_id,
            home_win_probability=0.6,
            away_win_probability=0.4,
            confidence="medium",
        )


def _picks(db):
    return [
        tuple(r)
        for r in db.fetchall(
            "SELECT home_team_id, away_team_id, predicted_winner_id, home_prob, confidence "
            "FROM prediction_history ORDER BY home_team_id"
        )
    ]


class TestSaveUpcomingPicks:
    def test_saves_one_pick_per_game_of_the_week(self, db):
        _game(db, 1, 2, "2026-11-19")
        _game(db, 3, 4, "2026-11-22")
        _game(db, 5, 6, "2026-11-29", week=12)
        result = save_upcoming_picks(db, FakeEngine(), 2026, 11, today=TODAY)
        assert result == {"saved": 2, "skipped": 0, "failed": 0}
        assert _picks(db) == [(1, 2, 1, 0.6, "medium"), (3, 4, 3, 0.6, "medium")]

    def test_rerun_does_not_duplicate(self, db):
        _game(db, 1, 2, "2026-11-22")
        save_upcoming_picks(db, FakeEngine(), 2026, 11, today=TODAY)
        result = save_upcoming_picks(db, FakeEngine(), 2026, 11, today=TODAY)
        assert result == {"saved": 0, "skipped": 1, "failed": 0}
        assert len(_picks(db)) == 1

    def test_picks_are_marked_as_cron(self, db):
        _game(db, 1, 2, "2026-11-22")
        save_upcoming_picks(db, FakeEngine(), 2026, 11, today=TODAY)
        assert db.fetchone("SELECT source FROM prediction_history")["source"] == "cron"

    def test_a_manual_pick_does_not_replace_the_cron_pick(self, db):
        # The ledger's one-pick-per-game is the cron's; a click in the UI
        # earlier that day must not leave the game without it.
        _game(db, 1, 2, "2026-11-22")
        db.insert_prediction(1, 2, 2, 0.4, 0.6, "low")
        result = save_upcoming_picks(db, FakeEngine(), 2026, 11, today=TODAY)
        assert result["saved"] == 1

    def test_an_old_pick_for_the_pairing_does_not_block_this_week(self, db):
        _game(db, 1, 2, "2026-11-22")
        pred = db.insert_prediction(1, 2, 1, 0.7, 0.3, "low")
        db.execute(
            "UPDATE prediction_history SET predicted_at = '2026-04-09 10:00:00' WHERE id = ?",
            (pred,),
        )
        result = save_upcoming_picks(db, FakeEngine(), 2026, 11, today=TODAY)
        assert result["saved"] == 1

    def test_never_picks_a_game_that_already_kicked_off(self, db):
        _game(db, 1, 2, "2026-11-19", played=True)
        # Played yesterday, score not imported yet: still not a prediction.
        _game(db, 3, 4, "2026-11-17")
        result = save_upcoming_picks(db, FakeEngine(), 2026, 11, today=TODAY)
        assert result["saved"] == 0
        assert _picks(db) == []

    def test_mirrors_the_backtested_model(self, db):
        # Weighted-sum default, no factors -- the configuration whose accuracy
        # is published. Factors/Vegas/injuries must never leak into the ledger.
        _game(db, 1, 2, "2026-11-22")
        engine = FakeEngine()
        save_upcoming_picks(db, engine, 2026, 11, today=TODAY)
        home, away, kwargs = engine.calls[0]
        assert (home, away) == ("T1", "T2")
        assert kwargs["apply_factors"] is False
        assert kwargs["current_season"] == 2026
        assert not kwargs.get("use_ml") and not kwargs.get("use_ensemble")

    def test_one_failing_game_does_not_stop_the_rest(self, db):
        _game(db, 1, 2, "2026-11-22")
        _game(db, 3, 4, "2026-11-22")
        result = save_upcoming_picks(
            db, FakeEngine(fail_for="T1"), 2026, 11, today=TODAY
        )
        assert result == {"saved": 1, "skipped": 0, "failed": 1}

    def test_saved_pick_is_graded_once_the_game_is_played(self, db):
        _game(db, 1, 2, "2026-11-22")
        save_upcoming_picks(db, FakeEngine(), 2026, 11, today=TODAY)
        db.execute("UPDATE games SET home_score = 10, away_score = 20, winner_id = 2")
        assert db.enrich_prediction_history() == 1
        row = db.fetchone("SELECT correct FROM prediction_history")
        assert row["correct"] == 0
