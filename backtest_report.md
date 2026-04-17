# NFL Prediction Model — Backtest Report 2020–2024

> Generated: 2026-04-17 01:38:15

NFL PREDICTION MODEL — BACKTEST REPORT 2020-2024
Generated: 2026-04-17 01:38:15
Seasons analysed: [2020, 2021, 2022, 2023, 2024]
1. OVERALL ACCURACY (2020-2024)
  Regular season games                   1339
  Regular season correct                 898  (67.1%)

  Playoff games                          65
  Playoff correct                        42  (64.6%)

  ALL GAMES total                        1404
  ALL GAMES correct                      940  (67.0%)
2. PER-SEASON BREAKDOWN (Regular Season)
  Season    Games  Correct   Accuracy
  2020        255      178      69.8%
  2021        271      179      66.1%
  2022        269      180      66.9%
  2023        272      174      64.0%
  2024        272      187      68.8%
3. PER-SEASON BREAKDOWN (Playoffs)
  Season    Games  Correct   Accuracy
  2020         13        8      61.5%
  2021         13        7      53.8%
  2022         13       10      76.9%
  2023         13        8      61.5%
  2024         13        9      69.2%
4. REGULAR SEASON vs PLAYOFFS
  Regular season accuracy                67.1%
  Playoff accuracy                       64.6%
  Delta (reg - playoff)                  +2.4 pp
5. HOME vs AWAY PREDICTION BREAKDOWN
  All games — predicted home wins          832 predictions  →  67.8% accurate
  All games — predicted away wins          572 predictions  →  65.7% accurate

  Regular season — predicted home wins     779 predictions  →  67.5% accurate
  Regular season — predicted away wins     560 predictions  →  66.4% accurate

  Playoffs — predicted home wins            53 predictions  →  71.7% accurate
  Playoffs — predicted away wins            12 predictions  →  33.3% accurate
6. ACCURACY BY CONFIDENCE LEVEL (All Games)
  Level       Games  Correct   Accuracy
  HIGH          591      413      69.9%
  MEDIUM        575      380      66.1%
  LOW           238      147      61.8%
## Regular season only:

  Level       Games  Correct   Accuracy
  HIGH          526      371      70.5%
  MEDIUM        575      380      66.1%
  LOW           238      147      61.8%
7. PROBABILITY CALIBRATION (All Games 2020-2024)
  Ideal calibration: a bucket showing X% should win roughly X% of the time.

  Prob bucket   Predictions  Actual wins   Actual %   Ideal mid     Delta
  50-55%                269          153      56.9%       52.5%  +   4.4pp  ###########
  55-60%                283          167      59.0%       57.5%  +   1.5pp  ############
  60-65%                240          164      68.3%       62.5%  +   5.8pp  ##############
  65-70%                228          159      69.7%       67.5%  +   2.2pp  ##############
  70-75%                172          136      79.1%       72.5%  +   6.6pp  ################
  75-80%                120           83      69.2%       77.5%    -8.3pp  ##############
  80%+                   92           78      84.8%       85.0%    -0.2pp  #################
8. METHODOLOGY NOTES
  * TRUE OUT-OF-SAMPLE: each game is predicted using only data available
    BEFORE that game's date. The 3-season analysis window is anchored to the
    season under test (current_season=game_season), so no future data leaks in.

  * Rest days are computed relative to the game date (not today), and search
    across all prior seasons so week-1 teams get their correct bye/off-season rest.

  * Tied games are excluded from accuracy calculations (winner_id IS NULL).

  * Confidence level thresholds (based on current-season games played):
      HIGH   = both teams have ≥ 10 current-season games (week 11+)
      MEDIUM = both teams have ≥  3 current-season games (weeks 4–10)
      LOW    = fewer than 3 current-season games (weeks 1–3)

  * Prediction weights used by the engine:
      15% weighted win-pct  |  15% offensive/defensive strength
      15% recent form       |  15% strength of schedule
      15% home/away splits  |  10% head-to-head record
      15% advanced stats (turnover margin, yards/play, 3rd-down %, red-zone %)
    + dynamic home-field advantage (team-specific, capped 0-10%)
    + bye-week rest bonus (+1.5%)
    Note: if advanced stats unavailable, their 15% is redistributed to win-pct.

## ML vs Weighted Sum — Post-Fix Comparison (2023–2024)

> Generated: 2026-04-17 10:49:02  
> Seasons: [2023, 2024] | All game types (regular + playoffs)

### Overall Accuracy

| Model | Games | Correct | Accuracy |
|-------|------:|--------:|---------:|
| Weighted Sum | 570 | 378 | 66.3% |
| ML (calibrated GBM + rolling QB EPA) | 570 | 367 | 64.4% |
| **Delta (ML − WS)** | — | **-11** | **-1.9pp** |

### Per-Season Breakdown (All Games)

| Season | WS Games | WS Correct | WS Acc | ML Correct | ML Acc | Delta |
|-------:|---------:|-----------:|-------:|-----------:|-------:|------:|
| 2023 | 285 | 182 | 63.9% | 182 | 63.9% | +0.0pp |
| 2024 | 285 | 196 | 68.8% | 185 | 64.9% | -3.9pp |

### ML Model — Probability Calibration (All Games)

> Ideal: a bucket showing X% should actually win ~X% of the time.

| Bucket | Games | Actual Wins | Actual % | Ideal Mid | Delta |
|--------|------:|------------:|---------:|----------:|------:|
| 50-55% | 217 | 113 | 52.1% | 52.5% | -0.4pp |
| 55-60% | 0 | 0 | 0.0% | 57.5% | -57.5pp |
| 60-65% | 51 | 35 | 68.6% | 62.5% | +6.1pp |
| 65-70% | 29 | 20 | 69.0% | 67.5% | +1.5pp |
| 70-75% | 65 | 44 | 67.7% | 72.5% | -4.8pp |
| 75-80% | 48 | 33 | 68.8% | 77.5% | -8.8pp |
| 80%+ | 160 | 122 | 76.2% | 85.0% | -8.8pp |

### Conclusion

Weighted-sum wins by 1.9pp (378/570 vs 367/570). Exceeds ±1.5pp noise threshold. **Keep weighted-sum as default.**

## ML Model vs Weighted Sum (2023–2024 OOS)

> Generated: 2026-04-17 11:19:45
>
> **Training**: CalibratedClassifierCV(isotonic, cv=5) on seasons 2013-2022 (2,696 games).
> **Calibration**: Internal 5-fold (~539 games/fold) — no separate holdout.
> **CV accuracy**: 65.9% ± 1.4% (TimeSeriesSplit, 5 folds on 2013-2022).
> **OOS test seasons**: 2023, 2024 (never seen during training).

### Accuracy Comparison

| Metric | Weighted Sum | ML (GBM) | Delta |
|---|---|---|---|
| Regular season | 66.4% | 66.4% | +0.0 pp |
| Playoffs | 65.4% | 65.4% | +0.0 pp |
| All games | 66.3% | 66.3% | +0.0 pp |

### Per-Season Regular Season

| Season | Weighted Sum | ML (GBM) | Delta |
|---|---|---|---|
| 2023 | 64.0% | 64.0% | +0.0 pp |
| 2024 | 68.8% | 68.8% | +0.0 pp |

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
CV MAE: 10.15 pts ± 0.35

---

## ML vs Weighted Sum — Post-Fix Comparison (2023–2024)

> Generated: 2026-04-17 11:20:17  
> Seasons: [2023, 2024] | All game types (regular + playoffs)

### Overall Accuracy

| Model | Games | Correct | Accuracy |
|-------|------:|--------:|---------:|
| Weighted Sum | 570 | 378 | 66.3% |
| ML (calibrated GBM + rolling QB EPA) | 570 | 381 | 66.8% |
| **Delta (ML − WS)** | — | **+3** | **+0.5pp** |

### Per-Season Breakdown (All Games)

| Season | WS Games | WS Correct | WS Acc | ML Correct | ML Acc | Delta |
|-------:|---------:|-----------:|-------:|-----------:|-------:|------:|
| 2023 | 285 | 182 | 63.9% | 178 | 62.5% | -1.4pp |
| 2024 | 285 | 196 | 68.8% | 203 | 71.2% | +2.5pp |

### ML Model — Probability Calibration (All Games)

> Ideal: a bucket showing X% should actually win ~X% of the time.

| Bucket | Games | Actual Wins | Actual % | Ideal Mid | Delta |
|--------|------:|------------:|---------:|----------:|------:|
| 50-55% | 99 | 48 | 48.5% | 52.5% | -4.0pp |
| 55-60% | 74 | 45 | 60.8% | 57.5% | +3.3pp |
| 60-65% | 91 | 57 | 62.6% | 62.5% | +0.1pp |
| 65-70% | 73 | 54 | 74.0% | 67.5% | +6.5pp |
| 70-75% | 93 | 67 | 72.0% | 72.5% | -0.5pp |
| 75-80% | 79 | 62 | 78.5% | 77.5% | +1.0pp |
| 80%+ | 61 | 48 | 78.7% | 85.0% | -6.3pp |

### Conclusion

Delta of +0.5pp is within noise (±1.5pp threshold, ~570 games). **No statistically significant difference — keep weighted-sum as default** (simpler, no model file dependency).

## Calibration Fix — Isotonic cv=5 (2026-04-17)

**Problem:** `CalibratedClassifierCV(method='isotonic', cv='prefit')` on a 282-game
holdout (2022 only) produced stairstep predictions: the 55–60% bucket had 0 games
and the 80%+ bucket showed −8.8pp under-confidence. Isotonic regression needs
1000+ samples; 282 games is not enough.

**Fix:** Replaced `cv='prefit'` with `cv=5` (internal 5-fold CV on all 2013–2022 data,
~540 games per calibration fold). Removed the explicit `clf.fit(X_train)` call.

### Before vs After Calibration

| Bucket | Before (cv='prefit') | After (cv=5) |
|--------|---------------------:|-------------:|
| 50–55% | 217 games, 52.1% | 99 games, 48.5% |
| 55–60% | **0 games (EMPTY)** | 74 games, 60.8% |
| 60–65% | 51 games, 68.6% | 91 games, 62.6% |
| 70–75% | 65 games, 67.7% | 93 games, 72.0% |
| 75–80% | 48 games, 68.8% | 79 games, 78.5% |
| 80%+ | 160 games, 76.2% (−8.8pp) | 61 games, 78.7% (−6.3pp) |

### ML vs Weighted Sum After Fix

| Model | Games | Correct | Accuracy |
|-------|------:|--------:|---------:|
| Weighted Sum | 570 | 378 | 66.3% |
| ML (cv=5 isotonic) | 570 | 381 | 66.8% |
| **Delta** | — | **+3** | **+0.5pp** |

### Conclusion

Delta of +0.5pp is within the ±1.5pp noise threshold (~570 games).
**Weighted-sum remains the default.** ML is now properly calibrated and
statistically tied with weighted-sum on 2023–2024 OOS data.
The 55–60% bucket is populated, the gap is gone, and the 80%+ under-confidence
improved from −8.8pp to −6.3pp.
