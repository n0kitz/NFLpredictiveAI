"""Guards for the weekly cron's own bookkeeping.

Dry-run on 2026-11-14: ESPN delivered 137 game results, Pro-Football-Reference
answered 403 for both seasons, and the run was logged as a failure with
"no seasons scraped successfully" — a job that did its work reported red every
week. The same run also re-created 306 two-team players, because the cron's
roster step upserted without the snapshot purge ``import_rosters.py`` has.
"""

import pytest

from scripts.weekly_scrape import core_scrape_failed, refresh_rosters
from src.database.db import Database


class TestCoreScrapeFailed:
    def test_espn_alone_is_enough(self):
        assert core_scrape_failed(espn_games=272, pfr_seasons_ok=0) is False

    def test_pfr_alone_is_enough(self):
        assert core_scrape_failed(espn_games=0, pfr_seasons_ok=1) is False

    def test_both_sources_dead_is_fatal(self):
        assert core_scrape_failed(espn_games=0, pfr_seasons_ok=0) is True


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "cron.db")
    for tid in range(1, 33):
        database.execute(
            "INSERT INTO teams (team_id, name, abbreviation, city, conference, division) "
            "VALUES (?, ?, ?, 'X', 'AFC', 'AFC East')",
            (tid, f"Team{tid}", f"T{tid}"),
        )
    yield database
    database.close()


def _player(espn_id, name="Some Player", position="WR"):
    return {"espn_id": espn_id, "full_name": name, "position": position}


def _full_rosters(overrides=None):
    rosters = {f"T{tid}": [_player(f"e{tid}", f"Player {tid}")] for tid in range(1, 33)}
    rosters.update(overrides or {})
    return rosters


def _teams_of(db, espn_id):
    return sorted(
        r["team_id"]
        for r in db.fetchall(
            "SELECT re.team_id FROM roster_entries re JOIN players p USING (player_id) "
            "WHERE p.espn_id = ? AND re.season = 2026",
            (espn_id,),
        )
    )


class TestRefreshRosters:
    def test_traded_player_ends_up_on_one_team(self, db):
        refresh_rosters(db, _full_rosters(), 2026)
        # Player 1 moves from T1 to T2.
        moved = _full_rosters(
            {
                "T1": [_player("x1", "Replacement")],
                "T2": [_player("e2", "Player 2"), _player("e1", "Player 1")],
            }
        )
        result = refresh_rosters(db, moved, 2026)
        assert _teams_of(db, "e1") == [2]
        assert result["purged"] == 1

    def test_partial_run_never_purges(self, db):
        refresh_rosters(db, _full_rosters(), 2026)
        partial = {"T1": [_player("x1", "Replacement")]}
        result = refresh_rosters(db, partial, 2026)
        assert result["purged"] == 0
        assert _teams_of(db, "e5") == [5]  # untouched team keeps its roster

    def test_empty_team_counts_as_partial(self, db):
        refresh_rosters(db, _full_rosters(), 2026)
        result = refresh_rosters(db, _full_rosters({"T7": []}), 2026)
        assert result["purged"] == 0
        assert _teams_of(db, "e7") == [7]

    def test_reports_what_landed(self, db):
        result = refresh_rosters(db, _full_rosters(), 2026)
        assert result["entries"] == 32
        assert result["teams"] == 32
