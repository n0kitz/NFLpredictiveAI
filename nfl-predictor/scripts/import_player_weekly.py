"""Import weekly per-player stats from nfl_data_py into player_weekly_stats."""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.db import create_database
from src.scraper.player_weekly_importer import import_player_weekly_stats

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=int, default=2018)
    parser.add_argument('--end', type=int, default=2025)
    args = parser.parse_args()

    years = list(range(args.start, args.end + 1))
    db = create_database()
    rows = import_player_weekly_stats(db, years)
    print(f"Weekly stats: {rows} rows upserted for years {years}")
    db.close()


if __name__ == '__main__':
    main()
