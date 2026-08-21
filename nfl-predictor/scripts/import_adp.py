"""Import real ADP into player_adp.

Two sources. The live fetch is the default because it needs no download:

    # Consensus ADP from Fantasy Football Calculator (recommended, re-runnable)
    python scripts/import_adp.py --season 2026
    python scripts/import_adp.py --season 2026 --scoring half_ppr

    # A specific CSV (FantasyPros cheat sheet, or a simple name,adp file)
    python scripts/import_adp.py --season 2026 --file ~/Downloads/FantasyPros_2026_ADP.csv

Exits non-zero when nothing matched — otherwise the draft board silently
falls back to synthetic rank ADP and every value-vs-market number is fiction.
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.db import create_database
from src.scraper.adp_importer import (
    FFC_SCORING,
    evaluate_adp_import,
    fetch_ffc_adp,
    import_adp,
    import_adp_entries,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument(
        "--file",
        help="Path to an ADP CSV. Omit to fetch live consensus ADP instead.",
    )
    parser.add_argument(
        "--scoring",
        default="standard",
        choices=sorted(FFC_SCORING),
        help="Scoring format for the live fetch (default: standard).",
    )
    parser.add_argument(
        "--teams",
        type=int,
        default=10,
        help="League size passed to the ADP source (default: 10).",
    )
    parser.add_argument("--source", default=None, help="Override the source label.")
    args = parser.parse_args()

    db = create_database()

    if args.file:
        text = Path(args.file).expanduser().read_text()
        matched, unmatched = import_adp(db, text, args.season, args.source or "csv")
    else:
        entries = fetch_ffc_adp(
            season=args.season, scoring=args.scoring, teams=args.teams
        )
        print(f"Fetched {len(entries)} players ({args.scoring}, {args.teams}-team)")
        matched, unmatched = import_adp_entries(
            db, entries, args.season, args.source or f"ffc-{args.scoring}"
        )

    ok, message = evaluate_adp_import(matched, matched + len(unmatched))
    print(f"  {message}")
    if unmatched:
        print(f"Unmatched ({len(unmatched)}):")
        for name in unmatched[:40]:
            print(f"  - {name}")
        if len(unmatched) > 40:
            print(f"  … and {len(unmatched) - 40} more")

    db.close()
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
