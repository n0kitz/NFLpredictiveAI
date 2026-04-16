#!/usr/bin/env python3
"""
Train the NFL ML prediction model on seasons 2013-2022 and evaluate
out-of-sample (OOS) on seasons 2023-2024.

After training, the script:
  1. Prints CV results.
  2. Backtests 2023-2024 under both the new ML model and the weighted-sum
     fallback, then appends a comparison section to backtest_report.md.

Usage:
    cd nfl-predictor
    python scripts/train_model.py

This may take 5-10 minutes depending on your hardware.
"""

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.database.db import Database
from src.prediction.ml_model import train_model, train_spread_model
from src.prediction.backtester import Backtester
from src.prediction.engine import PredictionEngine

OOS_SEASONS = [2023, 2024]
REPORT_PATH = ROOT.parent / "backtest_report.md"


def _pct(n: int, d: int) -> str:
    if d == 0:
        return "N/A"
    return f"{n / d:.1%}"


def main():
    print("=" * 60)
    print("  NFL ML Model — Training & OOS Evaluation")
    print(f"  Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("  Training window: 2013-2021 (base) + 2022 (calibration holdout)")
    print("  OOS test window:  2023-2024")
    print("  Features: 34 (win%, form, strength, SOS, H2H, advanced, QB EPA)")
    print("  This may take 5-10 minutes.")
    print("=" * 60)

    db = Database()

    # ── 1. Train classifier ───────────────────────────────────────────────────
    print("\n[1/4] Training win-probability classifier…")
    result = train_model(db)

    # ── 1b. Train spread model ────────────────────────────────────────────────
    print("\n[2/4] Training point-spread regression model…")
    spread_result = train_spread_model(db)
    print(f"\n  ── Spread Model Results ──")
    print(f"  Samples:      {spread_result['n_training_samples']:,}")
    print(f"  CV MAE:       {spread_result['cv_mae']:.2f} ± {spread_result['cv_std']:.2f} pts")
    print(f"  Fold MAEs:    {spread_result['fold_maes']}")

    print("\n  ── Training Results ──")
    print(f"  Seasons:         {result['training_seasons']}")
    print(f"  Train samples:   {result['n_training_samples']:,}")
    print(f"  Cal samples:     {result['n_cal_samples']:,}")
    print(f"  CV accuracy:     {result['cv_accuracy']:.4f} ± {result['cv_std']:.4f}")
    print(f"  Fold accuracies: {result['fold_accuracies']}")

    # ── 2. OOS backtest with ML model ─────────────────────────────────────────
    print(f"\n[3/4] OOS backtest 2023-2024 with ML model…")
    # Engine will pick up the freshly saved model
    db_ml = Database()  # fresh connection so engine.load_model() sees the new file
    bt_ml = Backtester(db_ml)
    ml_reg  = bt_ml.run(seasons=OOS_SEASONS, game_type="regular")
    ml_po   = bt_ml.run(seasons=OOS_SEASONS, game_type="playoff")
    ml_all  = bt_ml.run(seasons=OOS_SEASONS, game_type=None)

    print(f"  ML regular season: {ml_reg.correct_predictions}/{ml_reg.total_games} "
          f"= {_pct(ml_reg.correct_predictions, ml_reg.total_games)}")
    print(f"  ML playoffs:       {ml_po.correct_predictions}/{ml_po.total_games} "
          f"= {_pct(ml_po.correct_predictions, ml_po.total_games)}")
    print(f"  ML all games:      {ml_all.correct_predictions}/{ml_all.total_games} "
          f"= {_pct(ml_all.correct_predictions, ml_all.total_games)}")

    # ── 3. OOS backtest with weighted-sum ─────────────────────────────────────
    print(f"\n[4/4] OOS backtest 2023-2024 with weighted-sum (no ML)…")
    # Temporarily disable ML by monkeypatching the engine after construction
    from src.prediction.engine import PredictionEngine

    class _WeightedSumEngine(PredictionEngine):
        def __init__(self, db):
            super().__init__(db)
            self._ml_model = None
            self._ml_features = None
            self._use_ml = False

    class _WSSBactester(Backtester):
        def __init__(self, db):
            self.db = db
            self.engine = _WeightedSumEngine(db)

    bt_ws = _WSSBactester(Database())
    ws_reg  = bt_ws.run(seasons=OOS_SEASONS, game_type="regular")
    ws_po   = bt_ws.run(seasons=OOS_SEASONS, game_type="playoff")
    ws_all  = bt_ws.run(seasons=OOS_SEASONS, game_type=None)

    print(f"  WS regular season: {ws_reg.correct_predictions}/{ws_reg.total_games} "
          f"= {_pct(ws_reg.correct_predictions, ws_reg.total_games)}")
    print(f"  WS playoffs:       {ws_po.correct_predictions}/{ws_po.total_games} "
          f"= {_pct(ws_po.correct_predictions, ws_po.total_games)}")
    print(f"  WS all games:      {ws_all.correct_predictions}/{ws_all.total_games} "
          f"= {_pct(ws_all.correct_predictions, ws_all.total_games)}")

    # ── 4. Append comparison to backtest_report.md ────────────────────────────
    def delta(ml_n, ml_d, ws_n, ws_d):
        if ml_d == 0 or ws_d == 0:
            return "N/A"
        diff = (ml_n / ml_d - ws_n / ws_d) * 100
        sign = "+" if diff >= 0 else ""
        return f"{sign}{diff:.1f} pp"

    per_season_lines = []
    for ssn in OOS_SEASONS:
        ml_s = ml_reg.season_accuracy.get(ssn, {})
        ws_s = ws_reg.season_accuracy.get(ssn, {})
        ml_acc = f"{ml_s.get('accuracy', 0):.1%}" if ml_s else "N/A"
        ws_acc = f"{ws_s.get('accuracy', 0):.1%}" if ws_s else "N/A"
        d_str  = delta(
            ml_s.get('correct', 0), ml_s.get('total', 0),
            ws_s.get('correct', 0), ws_s.get('total', 0),
        )
        per_season_lines.append(f"| {ssn} | {ws_acc} | {ml_acc} | {d_str} |")

    section = f"""
## ML Model vs Weighted Sum (2023–2024 OOS)

> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
>
> **Training**: GradientBoostingClassifier on seasons 2013-2021 ({result['n_training_samples']:,} games).
> **Calibration**: Isotonic regression on 2022 holdout ({result['n_cal_samples']:,} games, cv='prefit').
> **CV accuracy**: {result['cv_accuracy']:.1%} ± {result['cv_std']:.1%} (TimeSeriesSplit, 5 folds on 2013-2021).
> **OOS test seasons**: 2023, 2024 (never seen during training).

### Accuracy Comparison

| Metric | Weighted Sum | ML (GBM) | Delta |
|---|---|---|---|
| Regular season | {_pct(ws_reg.correct_predictions, ws_reg.total_games)} | {_pct(ml_reg.correct_predictions, ml_reg.total_games)} | {delta(ml_reg.correct_predictions, ml_reg.total_games, ws_reg.correct_predictions, ws_reg.total_games)} |
| Playoffs | {_pct(ws_po.correct_predictions, ws_po.total_games)} | {_pct(ml_po.correct_predictions, ml_po.total_games)} | {delta(ml_po.correct_predictions, ml_po.total_games, ws_po.correct_predictions, ws_po.total_games)} |
| All games | {_pct(ws_all.correct_predictions, ws_all.total_games)} | {_pct(ml_all.correct_predictions, ml_all.total_games)} | {delta(ml_all.correct_predictions, ml_all.total_games, ws_all.correct_predictions, ws_all.total_games)} |

### Per-Season Regular Season

| Season | Weighted Sum | ML (GBM) | Delta |
|---|---|---|---|
{chr(10).join(per_season_lines)}

### Feature Set (34 features)

The GBM uses a 34-feature vector built from `TeamMetrics` objects computed
with `cutoff_date=game_date` to ensure no future data leakage:
win%, weighted win%, PPG, PAG, point diff/game, SOS, form rating, strength
rating, home/away splits, H2H win%, rest days, turnover margin, 3rd-down %,
yards/play, red-zone efficiency, is_playoff, week, dynamic HFA,
**home/away QB EPA per play** (from nfl_data_py PBP, 2013+).

Model pipeline: GradientBoostingClassifier + isotonic CalibratedClassifierCV.

### Spread Model

Point-spread regressor (GradientBoostingRegressor, same feature set):
CV MAE: {spread_result['cv_mae']:.2f} pts ± {spread_result['cv_std']:.2f}

---
"""

    existing = REPORT_PATH.read_text() if REPORT_PATH.exists() else ""
    REPORT_PATH.write_text(existing + section)
    print(f"\nComparison appended to {REPORT_PATH}")
    print("\nDone. Restart the API server to activate the ML model.")


if __name__ == "__main__":
    main()
