"""Import real ADP from a CSV export (FantasyPros cheat sheet or name,adp).

Usage:
    python scripts/import_adp.py --file ~/Downloads/FantasyPros_2026_ADP.csv --season 2026
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.db import create_database
from src.scraper.adp_importer import import_adp

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', required=True, help='Path to the ADP CSV')
    parser.add_argument('--season', type=int, required=True)
    parser.add_argument('--source', default='csv')
    args = parser.parse_args()

    text = Path(args.file).expanduser().read_text()
    db = create_database()
    matched, unmatched = import_adp(db, text, args.season, args.source)
    print(f"ADP import: {matched} players matched")
    if unmatched:
        print(f"Unmatched ({len(unmatched)}):")
        for name in unmatched[:40]:
            print(f"  - {name}")
        if len(unmatched) > 40:
            print(f"  … and {len(unmatched) - 40} more")
    db.close()


if __name__ == '__main__':
    main()
