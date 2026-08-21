"""Season aggregates for offensive players, rolled up from weekly rows.

``nfl_data_py.import_seasonal_data`` 404s for 2025+ (nflverse retired that
release, exactly like the weekly one), so ``player_season_stats`` had no
QB/RB/WR/TE rows for 2025 at all. Draft rankings and leaderboards read that
table, so the 2026 board silently fell back to 2024-only data and the
leaderboard showed nothing but kickers.

Weekly data for 2025 *is* available (parquet importer), so the season totals are
derived from it — the same trick already used for K/DST.
"""

import pytest

from src.database.db import Database
from src.scraper.player_weekly_importer import aggregate_offense_season_stats


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "agg.db")
    database.execute(
        "INSERT INTO teams (team_id, name, abbreviation, city, conference, division) "
        "VALUES (1, 'Chiefs', 'KC', 'Kansas City', 'AFC', 'AFC West')"
    )
    database.execute(
        "INSERT INTO players (player_id, full_name, position) VALUES (10, 'Test Back', 'RB')"
    )
    yield database
    database.close()


def _week(db, week, *, ppr, std, snaps=40, rush_yards=0, rec_yards=0, rush_tds=0):
    db.execute(
        """
        INSERT INTO player_weekly_stats
            (player_id, season, week, team_id, position, snaps,
             rush_yards, rush_tds, rec_yards, fantasy_points_ppr, fantasy_points_standard)
        VALUES (10, 2025, ?, 1, 'RB', ?, ?, ?, ?, ?, ?)
        """,
        (week, snaps, rush_yards, rush_tds, rec_yards, ppr, std),
    )


class TestAggregation:
    def test_sums_points_and_counts_games(self, db):
        _week(db, 1, ppr=12.0, std=10.0, rush_yards=80, rush_tds=1)
        _week(db, 2, ppr=8.0, std=7.0, rush_yards=50)
        db.commit()

        assert aggregate_offense_season_stats(db, [2025]) == 1

        row = db.fetchone(
            "SELECT * FROM player_season_stats WHERE player_id=10 AND season=2025"
        )
        assert row["games_played"] == 2
        assert row["fantasy_points_ppr"] == pytest.approx(20.0)
        assert row["fantasy_points_standard"] == pytest.approx(17.0)
        assert row["rush_yards"] == 130
        assert row["rush_tds"] == 1

    def test_inactive_weeks_do_not_count_as_games(self, db):
        """A zero-snap, zero-point row is a healthy scratch, not a game."""
        _week(db, 1, ppr=12.0, std=10.0)
        _week(db, 2, ppr=0.0, std=0.0, snaps=0)
        db.commit()

        aggregate_offense_season_stats(db, [2025])

        row = db.fetchone(
            "SELECT games_played FROM player_season_stats WHERE player_id=10 AND season=2025"
        )
        assert row["games_played"] == 1, "inactive week must not dilute points-per-game"

    def test_scoring_week_without_snap_data_still_counts(self, db):
        """Some rows carry points but no snap counts — the player clearly played."""
        _week(db, 1, ppr=9.5, std=8.0, snaps=0)
        db.commit()

        aggregate_offense_season_stats(db, [2025])

        row = db.fetchone(
            "SELECT games_played FROM player_season_stats WHERE player_id=10 AND season=2025"
        )
        assert row["games_played"] == 1

    def test_rerun_is_idempotent(self, db):
        _week(db, 1, ppr=12.0, std=10.0)
        db.commit()

        aggregate_offense_season_stats(db, [2025])
        aggregate_offense_season_stats(db, [2025])

        rows = db.fetchall(
            "SELECT * FROM player_season_stats WHERE player_id=10 AND season=2025"
        )
        assert len(rows) == 1
        assert rows[0]["fantasy_points_ppr"] == pytest.approx(12.0)

    def test_returns_zero_when_season_has_no_weekly_rows(self, db):
        assert aggregate_offense_season_stats(db, [2019]) == 0
