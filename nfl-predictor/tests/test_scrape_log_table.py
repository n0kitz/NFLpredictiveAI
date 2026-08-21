"""``scrape_log`` must exist wherever the cron writes its run outcome.

The table was introduced as migration v7 but never added to ``schema.sql``, and
the tracked ``data/nfl.db`` ended up with ``db_version`` = 25 while the table
itself was missing — so ``write_scrape_log`` raised
``OperationalError: no such table: scrape_log`` and a failed cron run would have
left no trace at all (GUIDEBOOK 3.2).
"""

import src.database.db as db_module
from src.database.db import Database


def _table_exists(db, name: str) -> bool:
    return (
        db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
        )
        is not None
    )


class TestScrapeLogTable:
    def test_exists_on_a_fresh_database(self, tmp_path):
        db = Database(tmp_path / "fresh.db")
        assert _table_exists(db, "scrape_log")
        db.close()

    def test_write_and_read_round_trip(self, tmp_path):
        db = Database(tmp_path / "roundtrip.db")

        db.write_scrape_log(success=False, error_message="boom", seasons_scraped="2026")
        row = db.get_latest_scrape_log()

        assert row is not None
        assert row["success"] == 0
        assert row["error_message"] == "boom"
        assert row["seasons_scraped"] == "2026"
        db.close()

    def test_recreated_on_a_database_that_lost_it(self, tmp_path):
        """A DB already stamped at the latest version must still self-heal.

        Migrations won't rerun (db_version is current), so the repair has to come
        from schema.sql, which every fresh process replays on first open.
        """
        path = tmp_path / "lost.db"
        db = Database(path)
        db.execute("DROP TABLE scrape_log")
        db.commit()
        db.close()

        # Simulate a new process: schema init is memoised per path in-process.
        db_module._initialized_paths.discard(str(path))

        reopened = Database(path)
        assert _table_exists(reopened, "scrape_log")
        reopened.write_scrape_log(
            success=True, error_message=None, seasons_scraped="2026"
        )
        assert reopened.get_latest_scrape_log() is not None
        reopened.close()
