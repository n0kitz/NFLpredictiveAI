"""Import weekly per-player stats (offense, kickers, DST) into player_weekly_stats."""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.db import create_database
from src.scraper.player_weekly_importer import (
    aggregate_kicker_dst_season_stats,
    aggregate_offense_season_stats,
    fetch_stats_player_week,
    import_kicker_weekly_stats,
    import_player_weekly_stats,
    purge_weekly_stats,
)
from src.scraper.dst_importer import import_dst_weekly_stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=2018)
    parser.add_argument("--end", type=int, default=2025)
    parser.add_argument(
        "--skip-offense", action="store_true", help="Only import kickers + DST"
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help=(
            "Delete the seasons' weekly rows before importing. Needed after a "
            "name-matching fix: upserts key on (player_id, season, week), so "
            "rows attached to the wrong player are not corrected by a re-import."
        ),
    )
    args = parser.parse_args()

    years = list(range(args.start, args.end + 1))
    db = create_database()
    if args.rebuild:
        removed = purge_weekly_stats(db, years)
        print(f"Purged {removed} existing weekly rows for years {years}")
    df = fetch_stats_player_week(years)
    if not args.skip_offense:
        rows = import_player_weekly_stats(db, years, df=df)
        print(f"Offense weekly stats: {rows} rows upserted for years {years}")
    k_rows = import_kicker_weekly_stats(db, years, df=df)
    print(f"Kicker weekly stats: {k_rows} rows upserted")
    dst_rows = import_dst_weekly_stats(db, years, df=df)
    print(f"DST weekly stats: {dst_rows} rows upserted")
    agg = aggregate_kicker_dst_season_stats(db, years)
    print(f"K/DST season aggregates: {agg} rows")
    if not args.skip_offense:
        # nfl_data_py's seasonal feed 404s for 2025+, so offensive season totals
        # have to come from the weekly rows too — draft rankings read them.
        off_agg = aggregate_offense_season_stats(db, years)
        print(f"Offense season aggregates: {off_agg} rows")
    db.close()


if __name__ == "__main__":
    main()
