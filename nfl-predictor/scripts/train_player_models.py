"""
Train one ML fantasy-projection model per position (QB, RB, WR, TE).

Reads per-player per-week rows from player_weekly_stats for the specified
training seasons, builds feature vectors via player_features, and fits a
GradientBoostingRegressor for each position.

Usage:
    python scripts/train_player_models.py --start 2018 --end 2023
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.db import create_database
from src.prediction.player_features import POSITIONS, build_training_rows
from src.prediction.player_ml_model import train_position_model

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=int, default=2018)
    parser.add_argument('--end', type=int, default=2023)
    args = parser.parse_args()

    seasons = list(range(args.start, args.end + 1))
    db = create_database()
    logger.info("Training player models for seasons %s", seasons)

    results = []
    for pos in POSITIONS:
        logger.info("Building training data for %s …", pos)
        X, y = build_training_rows(db, seasons, pos)
        logger.info("%s: %d samples", pos, X.shape[0])
        if X.shape[0] < 100:
            logger.warning("%s: too few samples (%d) — skipping", pos, X.shape[0])
            continue
        res = train_position_model(X, y, pos)
        results.append(res)

    db.close()
    for r in results:
        print(f"{r['position']}: MAE {r['cv_mae']:.2f} ± {r['cv_std']:.2f} "
              f"(n={r['n_training_samples']})")


if __name__ == '__main__':
    main()
