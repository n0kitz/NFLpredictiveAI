"""A prediction may only be graded by a game played after it was made.

Measured 2026-11-14: enrichment matched each prediction to the *most recent
completed* game of that pairing, whenever it was played. 230 of 231 graded rows
were "predictions" of games already in the model's own history, so /history
reported ~99.6% accuracy. Honest accuracy is a project invariant.
"""

import pytest

from src.database.db import Database

HOME, AWAY = 1, 2


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "grading.db")
    for tid, abbr in [(HOME, "NE"), (AWAY, "MIA")]:
        database.execute(
            "INSERT INTO teams (team_id, name, abbreviation, city, conference, division) "
            "VALUES (?, ?, ?, 'X', 'AFC', 'AFC East')",
            (tid, abbr, abbr),
        )
    yield database
    database.close()


def _game(db, date, winner=HOME, home=HOME, away=AWAY):
    """Insert a game; winner=None leaves it unplayed. Returns game_id."""
    score = (
        (None, None) if winner is None else ((27, 20) if winner == home else (20, 27))
    )
    cur = db.execute(
        "INSERT INTO games (date, season, week, game_type, home_team_id, away_team_id, "
        "home_score, away_score, winner_id) VALUES (?, 2026, '1', 'regular', ?, ?, ?, ?, ?)",
        (date, home, away, *score, winner),
    )
    return cur.lastrowid


def _prediction(db, predicted_at, winner=HOME, home=HOME, away=AWAY):
    pred_id = db.insert_prediction(home, away, winner, 0.6, 0.4, "low")
    db.execute(
        "UPDATE prediction_history SET predicted_at = ? WHERE id = ?",
        (predicted_at, pred_id),
    )
    return pred_id


def _row(db, pred_id):
    return db.fetchone(
        "SELECT game_id, actual_winner_id, correct FROM prediction_history WHERE id = ?",
        (pred_id,),
    )


class TestEnrichOnlyGradesFutureGames:
    def test_game_played_before_the_prediction_never_grades_it(self, db):
        _game(db, "2026-01-10")
        pred = _prediction(db, "2026-04-09 10:00:00")
        assert db.enrich_prediction_history() == 0
        assert _row(db, pred)["correct"] is None

    def test_game_played_after_the_prediction_grades_it(self, db):
        game = _game(db, "2026-09-13", winner=AWAY)
        pred = _prediction(db, "2026-09-10 10:00:00", winner=HOME)
        assert db.enrich_prediction_history() == 1
        row = _row(db, pred)
        assert (row["game_id"], row["actual_winner_id"], row["correct"]) == (
            game,
            AWAY,
            0,
        )

    def test_game_on_the_day_of_the_prediction_counts(self, db):
        # No kickoff time is stored; a game-day pick is the normal case.
        game = _game(db, "2026-09-13")
        pred = _prediction(db, "2026-09-13 15:00:00")
        db.enrich_prediction_history()
        assert _row(db, pred)["game_id"] == game

    def test_graded_by_the_next_meeting_not_the_latest(self, db):
        first = _game(db, "2026-09-13", winner=AWAY)
        _game(db, "2027-09-12", winner=HOME)
        pred = _prediction(db, "2026-09-10 10:00:00", winner=HOME)
        db.enrich_prediction_history()
        row = _row(db, pred)
        assert (row["game_id"], row["correct"]) == (first, 0)

    def test_waits_while_the_next_meeting_is_unplayed(self, db):
        _game(db, "2026-01-10")
        _game(db, "2026-11-22", winner=None)
        pred = _prediction(db, "2026-09-10 10:00:00")
        assert db.enrich_prediction_history() == 0
        assert _row(db, pred)["correct"] is None

    def test_home_and_away_must_match(self, db):
        _game(db, "2026-09-13", winner=AWAY, home=AWAY, away=HOME)
        pred = _prediction(db, "2026-09-10 10:00:00")
        assert db.enrich_prediction_history() == 0
        assert _row(db, pred)["correct"] is None


class TestResetRetroactiveGrades:
    def _graded(self, db, predicted_at, game_id):
        pred = _prediction(db, predicted_at)
        db.execute(
            "UPDATE prediction_history SET game_id = ?, actual_winner_id = ?, correct = 1 "
            "WHERE id = ?",
            (game_id, HOME, pred),
        )
        return pred

    def test_clears_a_grade_from_an_earlier_game(self, db):
        old = _game(db, "2026-01-10")
        pred = self._graded(db, "2026-04-09 10:00:00", old)
        assert db.reset_retroactive_prediction_grades() == 1
        row = _row(db, pred)
        assert (row["game_id"], row["actual_winner_id"], row["correct"]) == (
            None,
            None,
            None,
        )

    def test_keeps_a_grade_from_a_later_game(self, db):
        later = _game(db, "2026-09-13")
        pred = self._graded(db, "2026-09-10 10:00:00", later)
        assert db.reset_retroactive_prediction_grades() == 0
        assert _row(db, pred)["correct"] == 1

    def test_enrich_heals_old_rows_and_does_not_regrade_them(self, db):
        old = _game(db, "2026-01-10")
        pred = self._graded(db, "2026-04-09 10:00:00", old)
        db.enrich_prediction_history()
        assert _row(db, pred)["correct"] is None
        # ...and it stays that way on the next run.
        db.enrich_prediction_history()
        assert _row(db, pred)["correct"] is None


class TestAccuracyCountsEachGameOnce:
    """Clicking Predict five times must not weigh a game five times."""

    def _graded(self, db, game_id, correct, predicted_at, source="manual"):
        pred = db.insert_prediction(HOME, AWAY, HOME, 0.6, 0.4, "low", source=source)
        db.execute(
            "UPDATE prediction_history SET predicted_at = ?, game_id = ?, "
            "actual_winner_id = ?, correct = ? WHERE id = ?",
            (predicted_at, game_id, HOME, correct, pred),
        )
        return pred

    def test_source_defaults_to_manual(self, db):
        pred = db.insert_prediction(HOME, AWAY, HOME, 0.6, 0.4, "low")
        row = db.fetchone("SELECT source FROM prediction_history WHERE id = ?", (pred,))
        assert row["source"] == "manual"

    def test_repeat_picks_for_one_game_count_once(self, db):
        game = _game(db, "2026-09-13")
        for hour in (9, 10, 11):
            self._graded(db, game, 1, f"2026-09-10 {hour}:00:00")
        stats = db.get_prediction_history_stats()
        assert (stats["total"], stats["resolved"], stats["correct"]) == (3, 1, 1)

    def test_the_cron_pick_represents_the_game(self, db):
        game = _game(db, "2026-09-13")
        self._graded(db, game, 0, "2026-09-09 06:00:00", source="cron")
        self._graded(db, game, 1, "2026-09-12 20:00:00")  # later manual pick
        stats = db.get_prediction_history_stats()
        assert (stats["resolved"], stats["correct"]) == (1, 0)

    def test_without_a_cron_pick_the_latest_one_counts(self, db):
        game = _game(db, "2026-09-13")
        self._graded(db, game, 1, "2026-09-09 06:00:00")
        self._graded(db, game, 0, "2026-09-12 20:00:00")
        stats = db.get_prediction_history_stats()
        assert (stats["resolved"], stats["correct"]) == (1, 0)

    def test_different_games_count_separately(self, db):
        self._graded(db, _game(db, "2026-09-13"), 1, "2026-09-10 10:00:00")
        self._graded(db, _game(db, "2026-11-22"), 0, "2026-11-18 10:00:00")
        stats = db.get_prediction_history_stats()
        assert (stats["resolved"], stats["correct"]) == (2, 1)
