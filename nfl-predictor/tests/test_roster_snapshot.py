"""A roster import is a snapshot, not an accumulating union.

``roster_entries`` is keyed UNIQUE(player_id, team_id, season), so a player who
changes teams mid-preseason keeps **both** rows. Measured on live data before
this fix: 3,207 entries for 3,164 distinct players, with 15 players sitting on
two teams at once (Caedan Wallace MIA+NE, Deven Thompkins BUF+LV, ...).

That ambiguity is not cosmetic — ``db.get_player_team_id()`` resolves it with
``ORDER BY id DESC LIMIT 1``, effectively arbitrary, and it feeds both
``schedule_outlook`` and ``streaming``. A wrong team means a wrong opponent,
hence a wrong DvP, hence a wrong SOS grade and streaming rank.

Same lesson as ``purge_weekly_stats``: upserts never correct stale rows, so a
snapshot import has to purge what it no longer sees.
"""

import pytest

from src.database.db import Database

BEFORE = "2026-08-01T00:00:00"
RUN_START = "2026-08-22T12:00:00"
AFTER = "2026-08-22T12:05:00"


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "roster.db")
    for tid, name, abbr, city in [
        (1, "Patriots", "NE", "New England"),
        (2, "Dolphins", "MIA", "Miami"),
    ]:
        database.execute(
            "INSERT INTO teams (team_id, name, abbreviation, city, conference, division) "
            "VALUES (?, ?, ?, ?, 'AFC', 'AFC East')",
            (tid, name, abbr, city),
        )
    database.execute(
        "INSERT INTO players (player_id, full_name, position) VALUES (10, 'Moved Player', 'WR')"
    )
    database.execute(
        "INSERT INTO players (player_id, full_name, position) VALUES (11, 'Stable Player', 'RB')"
    )
    yield database
    database.close()


def _entry(db, player_id, team_id, fetched_at, season=2026):
    db.execute(
        "INSERT INTO roster_entries (player_id, team_id, season, is_starter, fetched_at) "
        "VALUES (?, ?, ?, 1, ?)",
        (player_id, team_id, season, fetched_at),
    )


def _teams_for(db, player_id, season=2026):
    return sorted(
        r["team_id"]
        for r in db.fetchall(
            "SELECT team_id FROM roster_entries WHERE player_id = ? AND season = ?",
            (player_id, season),
        )
    )


class TestPurgeStaleRosterEntries:
    def test_moved_player_keeps_only_the_new_team(self, db):
        _entry(db, 10, 1, BEFORE)  # old team, stale
        _entry(db, 10, 2, AFTER)  # new team, this run
        db.purge_stale_roster_entries(2026, RUN_START)
        assert _teams_for(db, 10) == [2]

    def test_current_rows_survive(self, db):
        _entry(db, 11, 1, AFTER)
        db.purge_stale_roster_entries(2026, RUN_START)
        assert _teams_for(db, 11) == [1]

    def test_returns_removed_count(self, db):
        _entry(db, 10, 1, BEFORE)
        _entry(db, 11, 1, BEFORE)
        _entry(db, 11, 2, AFTER)
        assert db.purge_stale_roster_entries(2026, RUN_START) == 2

    def test_null_fetched_at_is_treated_as_stale(self, db):
        _entry(db, 10, 1, None)
        _entry(db, 10, 2, AFTER)
        db.purge_stale_roster_entries(2026, RUN_START)
        assert _teams_for(db, 10) == [2]

    def test_other_seasons_are_untouched(self, db):
        _entry(db, 10, 1, BEFORE, season=2025)
        _entry(db, 10, 2, AFTER)
        db.purge_stale_roster_entries(2026, RUN_START)
        assert _teams_for(db, 10, season=2025) == [1]

    def test_synthetic_dst_entries_survive(self, db):
        """DST players are synthetic and never appear in an ESPN fetch.

        ensure_dst_players() creates them separately, so their fetched_at is
        always older than an ESPN run. Purging them wiped all 32 defenses out
        of the 2026 draft board -- caught by
        tests/test_league_settings.py::test_rankings_include_k_and_dst.
        """
        db.execute(
            "INSERT INTO players (player_id, espn_id, full_name, position) "
            "VALUES (99, 'DST-NE', 'New England Patriots DST', 'DST')"
        )
        _entry(db, 99, 1, BEFORE)  # stale by timestamp, but must survive
        db.purge_stale_roster_entries(2026, RUN_START)
        assert _teams_for(db, 99) == [1]


class TestPartialRunSafety:
    """The dangerous case: purging after an incomplete fetch deletes real teams.

    ``evaluate_roster_import`` returns ok=True on partial coverage -- it only
    hard-fails when *nothing* was upserted. So `import_ok` alone must never
    gate the purge, or a 20/32 run silently wipes 12 teams' rosters.
    """

    def test_evaluate_roster_import_is_ok_on_partial_coverage(self):
        from src.scraper.roster_scraper import evaluate_roster_import

        ok, _msg = evaluate_roster_import(teams_fetched=20, entries_upserted=1800)
        assert ok is True, (
            "if this ever returns False the purge guard below can be simplified "
            "-- until then, full coverage must be checked separately"
        )

    def test_should_purge_requires_full_coverage(self):
        from scripts.import_rosters import should_purge_stale

        assert should_purge_stale(teams_with_players=32, expected_teams=32) is True
        assert should_purge_stale(teams_with_players=31, expected_teams=32) is False
        assert should_purge_stale(teams_with_players=0, expected_teams=32) is False
