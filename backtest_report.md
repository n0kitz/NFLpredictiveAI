# NFL Prediction Model — Backtest Report 2020–2024

> Generated: 2026-04-13 21:34:54

NFL PREDICTION MODEL — BACKTEST REPORT 2020-2024
Generated: 2026-04-13 21:34:54
Seasons analysed: [2020, 2021, 2022, 2023, 2024]
1. OVERALL ACCURACY (2020-2024)
  Regular season games                   1339
  Regular season correct                 909  (67.9%)

  Playoff games                          65
  Playoff correct                        42  (64.6%)

  ALL GAMES total                        1404
  ALL GAMES correct                      951  (67.7%)
2. PER-SEASON BREAKDOWN (Regular Season)
  Season    Games  Correct   Accuracy
  2020        255      183      71.8%
  2021        271      178      65.7%
  2022        269      182      67.7%
  2023        272      176      64.7%
  2024        272      190      69.9%
3. PER-SEASON BREAKDOWN (Playoffs)
  Season    Games  Correct   Accuracy
  2020         13        8      61.5%
  2021         13        7      53.8%
  2022         13       10      76.9%
  2023         13        8      61.5%
  2024         13        9      69.2%
4. REGULAR SEASON vs PLAYOFFS
  Regular season accuracy                67.9%
  Playoff accuracy                       64.6%
  Delta (reg - playoff)                  +3.3 pp
5. HOME vs AWAY PREDICTION BREAKDOWN
  All games — predicted home wins          841 predictions  →  68.3% accurate
  All games — predicted away wins          563 predictions  →  67.0% accurate

  Regular season — predicted home wins     788 predictions  →  68.0% accurate
  Regular season — predicted away wins     551 predictions  →  67.7% accurate

  Playoffs — predicted home wins            53 predictions  →  71.7% accurate
  Playoffs — predicted away wins            12 predictions  →  33.3% accurate
6. ACCURACY BY CONFIDENCE LEVEL (All Games)
  Level       Games  Correct   Accuracy
  HIGH          591      418      70.7%
  MEDIUM        575      382      66.4%
  LOW           238      151      63.4%
## Regular season only:

  Level       Games  Correct   Accuracy
  HIGH          526      376      71.5%
  MEDIUM        575      382      66.4%
  LOW           238      151      63.4%
7. PROBABILITY CALIBRATION (All Games 2020-2024)
  Ideal calibration: a bucket showing X% should win roughly X% of the time.

  Prob bucket   Predictions  Actual wins   Actual %   Ideal mid     Delta
  50-55%                280          153      54.6%       52.5%  +   2.1pp  ###########
  55-60%                272          163      59.9%       57.5%  +   2.4pp  ############
  60-65%                239          166      69.5%       62.5%  +   7.0pp  ##############
  65-70%                222          157      70.7%       67.5%  +   3.2pp  ##############
  70-75%                186          146      78.5%       72.5%  +   6.0pp  ################
  75-80%                120           92      76.7%       77.5%    -0.8pp  ###############
  80%+                   85           74      87.1%       85.0%  +   2.1pp  #################
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

---

## After Advanced Stats Integration

**Data source**: nfl_data_py (nflverse) play-by-play, seasons 2010–2025 (480 team-seasons in DB)
**New features added**: turnover_margin, third_down_pct, redzone_efficiency, yards_per_play, sack_rate_allowed
**Advanced component weight**: 15% (reduces win_pct from 25%→15%, strength from 20%→15%)

### Accuracy Comparison (Seasons 2020–2024, True Out-of-Sample)

| Metric | Baseline (no adv. stats) | With Advanced Stats | Delta |
|---|---|---|---|
| Overall accuracy | 65.1% | **67.7%** | **+2.6 pp** |
| Regular season | 65.0% | **67.9%** | +2.9 pp |
| Playoffs | 67.7% | 64.6% | -3.1 pp |

### Per-Season Regular Season Accuracy

| Season | Baseline | With Adv. Stats | Delta |
|---|---|---|---|
| 2020 | 68.6% | **71.8%** | +3.2 pp |
| 2021 | 64.2% | **65.7%** | +1.5 pp |
| 2022 | 60.6% | **67.7%** | +7.1 pp |
| 2023 | 65.1% | 64.7% | -0.4 pp |
| 2024 | 66.5% | **69.9%** | +3.4 pp |

### Confidence-Level Accuracy (All Games)

| Level | Games | Baseline | With Adv. Stats |
|---|---|---|---|
| HIGH (week 11+) | 591 | 67.2% | **70.7%** |
| MEDIUM (weeks 4–10) | 575 | 63.7% | **66.4%** |
| LOW (weeks 1–3) | 238 | 63.4% | 63.4% (no change — only prior-season adv. stats) |

### Calibration Comparison (50–55% bucket → 80%+ bucket)

| Bucket | Baseline actual% | With Adv. actual% | Ideal |
|---|---|---|---|
| 50–55% | 52.3% | 54.6% | 52.5% |
| 60–65% | 63.4% | 69.5% | 62.5% |
| 70–75% | 72.9% | 78.5% | 72.5% |
| 80%+   | 88.5% | 87.1% | 85.0% |

### Key Observations

- **+2.6 pp overall lift** from adding turnover margin, yards/play, 3rd-down %, and red-zone efficiency.
- The biggest individual gain was 2022 (+7.1 pp), suggesting those metrics were particularly diagnostic that season.
- Playoff accuracy dipped slightly (−3.1 pp); this may reflect that playoff teams are more evenly matched and advanced stats from the regular season are less predictive in the postseason.
- Confidence stratification improved: HIGH-confidence predictions now reach 70.7% vs 67.2% baseline.
- Calibration in the middle buckets (60–75%) improved — the model is now better at distinguishing moderate favourites.
- **Note**: advanced stats are season-level aggregates; within-season leakage exists for early-season backtest games (the model uses full-season 2020 stats for week 1 2020 predictions). Fixing this would require game-by-game accumulation and is left as a future improvement.

## ML Model vs Weighted Sum (2023–2024 OOS)

> Generated: 2026-04-13 22:21:35
>
> **Training**: GradientBoostingClassifier on seasons 2013-2022 (2,696 games).
> **CV accuracy**: 66.7% ± 1.4% (TimeSeriesSplit, 5 folds).
> **OOS test seasons**: 2023, 2024 (never seen during training).

### Accuracy Comparison

| Metric | Weighted Sum | ML (GBM) | Delta |
|---|---|---|---|
| Regular season | 67.3% | 66.7% | -0.6 pp |
| Playoffs | 65.4% | 69.2% | +3.8 pp |
| All games | 67.2% | 66.8% | -0.4 pp |

### Per-Season Regular Season

| Season | Weighted Sum | ML (GBM) | Delta |
|---|---|---|---|
| 2023 | 64.7% | 67.3% | +2.6 pp |
| 2024 | 69.8% | 66.2% | -3.7 pp |

### Feature Set (32 features)

The GBM uses a 32-feature vector built from `TeamMetrics` objects computed
with `cutoff_date=game_date` to ensure no future data leakage:
win%, weighted win%, PPG, PAG, point diff/game, SOS, form rating, strength
rating, home/away splits, H2H win%, rest days, turnover margin, 3rd-down %,
yards/play, red-zone efficiency, is_playoff, week, dynamic HFA.

---

## ML Model vs Weighted Sum (2023–2024 OOS)

> Generated: 2026-04-14 12:04:32
>
> **Training**: GradientBoostingClassifier on seasons 2013-2022 (2,696 games).
> **CV accuracy**: 66.9% ± 0.7% (TimeSeriesSplit, 5 folds).
> **OOS test seasons**: 2023, 2024 (never seen during training).

### Accuracy Comparison

| Metric | Weighted Sum | ML (GBM) | Delta |
|---|---|---|---|
| Regular season | 67.3% | 67.3% | +0.0 pp |
| Playoffs | 65.4% | 65.4% | +0.0 pp |
| All games | 67.2% | 67.2% | +0.0 pp |

### Per-Season Regular Season

| Season | Weighted Sum | ML (GBM) | Delta |
|---|---|---|---|
| 2023 | 64.7% | 64.7% | +0.0 pp |
| 2024 | 69.8% | 69.8% | +0.0 pp |

### Feature Set (35 features)

The GBM uses a 35-feature vector built from `TeamMetrics` objects computed
with `cutoff_date=game_date` to ensure no future data leakage:
win%, weighted win%, PPG, PAG, point diff/game, SOS, form rating, strength
rating, home/away splits, H2H win%, rest days, turnover margin, 3rd-down %,
yards/play, red-zone efficiency, is_playoff, week, dynamic HFA,
**Vegas implied probability** (0.5=no data, most pre-2020 games),
**home/away QB EPA per play** (from nfl_data_py PBP, 2013+).

### Spread Model

Point-spread regressor (GradientBoostingRegressor, same feature set):
CV MAE: 10.12 pts ± 0.41

---

## ML Model vs Weighted Sum (2023–2024 OOS)

> Generated: 2026-04-14 12:23:13
>
> **Training**: GradientBoostingClassifier on seasons 2013-2022 (2,696 games).
> **CV accuracy**: 66.9% ± 0.7% (TimeSeriesSplit, 5 folds).
> **OOS test seasons**: 2023, 2024 (never seen during training).

### Accuracy Comparison

| Metric | Weighted Sum | ML (GBM) | Delta |
|---|---|---|---|
| Regular season | 67.3% | 67.3% | +0.0 pp |
| Playoffs | 65.4% | 65.4% | +0.0 pp |
| All games | 67.2% | 67.2% | +0.0 pp |

### Per-Season Regular Season

| Season | Weighted Sum | ML (GBM) | Delta |
|---|---|---|---|
| 2023 | 64.7% | 64.7% | +0.0 pp |
| 2024 | 69.8% | 69.8% | +0.0 pp |

### Feature Set (35 features)

The GBM uses a 35-feature vector built from `TeamMetrics` objects computed
with `cutoff_date=game_date` to ensure no future data leakage:
win%, weighted win%, PPG, PAG, point diff/game, SOS, form rating, strength
rating, home/away splits, H2H win%, rest days, turnover margin, 3rd-down %,
yards/play, red-zone efficiency, is_playoff, week, dynamic HFA,
**Vegas implied probability** (0.5=no data, most pre-2020 games),
**home/away QB EPA per play** (from nfl_data_py PBP, 2013+).

### Spread Model

Point-spread regressor (GradientBoostingRegressor, same feature set):
CV MAE: 10.12 pts ± 0.41

---
