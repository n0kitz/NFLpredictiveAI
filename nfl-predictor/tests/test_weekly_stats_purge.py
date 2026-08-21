"""Tests for rebuilding player_weekly_stats from scratch.

The importer upserts on (player_id, season, week), so rows written under a
buggy name match are not corrected by a re-import — they simply survive
attached to the wrong player. Rebuilding a season therefore has to purge it
first.
"""

import pytest

from src.database.db import Database
from src.scraper.player_weekly_importer import purge_weekly_stats


@pytest.fixture
def tmp_db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.execute(
        "INSERT INTO players (espn_id, full_name, last_name, position) "
        "VALUES ('1', 'Bijan Robinson', 'Robinson', 'RB')",
        (),
    )
    db.commit()
    pid = db.fetchone("SELECT player_id FROM players LIMIT 1", ())["player_id"]
    for season, week in [(2024, 1), (2024, 2), (2025, 1)]:
        db.execute(
            "INSERT INTO player_weekly_stats (player_id, season, week, position) "
            "VALUES (?, ?, ?, 'RB')",
            (pid, season, week),
        )
    db.commit()
    yield db
    db.close()


def _count(db, season):
    return db.fetchone(
        "SELECT COUNT(*) n FROM player_weekly_stats WHERE season = ?", (season,)
    )["n"]


class TestPurgeWeeklyStats:
    def test_removes_only_the_named_seasons(self, tmp_db):
        removed = purge_weekly_stats(tmp_db, [2024])
        assert removed == 2
        assert _count(tmp_db, 2024) == 0
        assert _count(tmp_db, 2025) == 1

    def test_multiple_seasons(self, tmp_db):
        assert purge_weekly_stats(tmp_db, [2024, 2025]) == 3
        assert _count(tmp_db, 2024) == 0
        assert _count(tmp_db, 2025) == 0

    def test_empty_season_list_is_a_no_op(self, tmp_db):
        assert purge_weekly_stats(tmp_db, []) == 0
        assert _count(tmp_db, 2024) == 2

    def test_unknown_season_removes_nothing(self, tmp_db):
        assert purge_weekly_stats(tmp_db, [1999]) == 0
        assert _count(tmp_db, 2024) == 2
