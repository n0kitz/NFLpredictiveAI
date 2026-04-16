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
