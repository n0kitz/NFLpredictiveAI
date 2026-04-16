#!/usr/bin/env python3
"""
Comprehensive NFL prediction model backtest: seasons 2020-2024.

Run from nfl-predictor/ directory:
    python scripts/run_backtest.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Ensure nfl-predictor/src is importable
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.database.db import Database
from src.prediction.backtester import Backtester, BacktestReport, BacktestResult

SEASONS = [2020, 2021, 2022, 2023, 2024]

CALIBRATION_BUCKETS = [
    ('50-55%', 0.50, 0.55),
    ('55-60%', 0.55, 0.60),
    ('60-65%', 0.60, 0.65),
    ('65-70%', 0.65, 0.70),
    ('70-75%', 0.70, 0.75),
    ('75-80%', 0.75, 0.80),
    ('80%+',   0.80, 1.01),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def pct(n: int, d: int) -> str:
    if d == 0:
        return "N/A"
    return f"{n / d:.1%}"


def calibration_from_results(results: list[BacktestResult]) -> dict:
    buckets = {label: {'total': 0, 'correct': 0} for label, _, _ in CALIBRATION_BUCKETS}
    for r in results:
        winner_prob = max(r.home_prob, r.away_prob)
        for label, lo, hi in CALIBRATION_BUCKETS:
            if lo <= winner_prob < hi:
                buckets[label]['total'] += 1
                if r.correct:
                    buckets[label]['correct'] += 1
                break
    return buckets


def home_away_breakdown(results: list[BacktestResult]) -> dict:
    """Count how often the model picks the home vs away team and whether it's right."""
    home_predicted = {'total': 0, 'correct': 0}
    away_predicted = {'total': 0, 'correct': 0}
    for r in results:
        if r.home_prob >= r.away_prob:
            home_predicted['total'] += 1
            if r.correct:
                home_predicted['correct'] += 1
        else:
            away_predicted['total'] += 1
            if r.correct:
                away_predicted['correct'] += 1
    return {'home_predicted': home_predicted, 'away_predicted': away_predicted}


# ---------------------------------------------------------------------------
# Main backtest runner
# ---------------------------------------------------------------------------

def main():
    db = Database()
    backtester = Backtester(db)

    print("=" * 60)
    print("  NFL PREDICTION MODEL — COMPREHENSIVE BACKTEST 2020-2024")
    print(f"  Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # -----------------------------------------------------------------------
    # 1. Per-season regular season
    # -----------------------------------------------------------------------
    print("\n[1/4] Running per-season regular season backtests...")
    per_season_reg: dict[int, BacktestReport] = {}
    for season in SEASONS:
        print(f"  Season {season}...", end=" ", flush=True)
        report = backtester.run(seasons=[season], game_type='regular')
        per_season_reg[season] = report
        n = report.total_games
        c = report.correct_predictions
        print(f"{c}/{n} = {pct(c, n)}")

    # -----------------------------------------------------------------------
    # 2. Per-season playoffs
    # -----------------------------------------------------------------------
    print("\n[2/4] Running per-season playoff backtests...")
    per_season_po: dict[int, BacktestReport] = {}
    for season in SEASONS:
        print(f"  Season {season} playoffs...", end=" ", flush=True)
        report = backtester.run(seasons=[season], game_type='playoff')
        per_season_po[season] = report
        n = report.total_games
        c = report.correct_predictions
        print(f"{c}/{n} = {pct(c, n)}")

    # -----------------------------------------------------------------------
    # 3. Overall combined report (all game types, all seasons at once)
    # -----------------------------------------------------------------------
    print("\n[3/4] Running combined all-seasons backtest...")
    combined_reg   = backtester.run(seasons=SEASONS, game_type='regular')
    combined_po    = backtester.run(seasons=SEASONS, game_type='playoff')
    # All game types: pass game_type=None to skip filtering
    combined_all   = backtester.run(seasons=SEASONS, game_type=None)

    all_results      = combined_all.results
    reg_results      = combined_reg.results
    playoff_results  = combined_po.results

    # -----------------------------------------------------------------------
    # 4. Derived statistics
    # -----------------------------------------------------------------------
    print("\n[4/4] Computing derived statistics...")

    calib_all   = calibration_from_results(all_results)
    ha_all      = home_away_breakdown(all_results)
    ha_reg      = home_away_breakdown(reg_results)
    ha_po       = home_away_breakdown(playoff_results)

    # -----------------------------------------------------------------------
    # Build report text
    # -----------------------------------------------------------------------
    lines = []

    def h(text, char='='):
        lines.append(f"\n{char * len(text)}")
        lines.append(text)
        lines.append(char * len(text))

    def row(label, value):
        lines.append(f"  {label:<38} {value}")

    h("NFL PREDICTION MODEL — BACKTEST REPORT 2020-2024")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Seasons analysed: {SEASONS}")

    # --- Overall Summary ---
    h("1. OVERALL ACCURACY (2020-2024)", "-")

    reg_n, reg_c   = combined_reg.total_games, combined_reg.correct_predictions
    po_n, po_c     = combined_po.total_games,  combined_po.correct_predictions
    all_n, all_c   = combined_all.total_games, combined_all.correct_predictions

    row("Regular season games",   f"{reg_n}")
    row("Regular season correct", f"{reg_c}  ({pct(reg_c, reg_n)})")
    row("",                        "")
    row("Playoff games",           f"{po_n}")
    row("Playoff correct",         f"{po_c}  ({pct(po_c, po_n)})")
    row("",                        "")
    row("ALL GAMES total",         f"{all_n}")
    row("ALL GAMES correct",       f"{all_c}  ({pct(all_c, all_n)})")

    # --- Per-Season Breakdown ---
    h("2. PER-SEASON BREAKDOWN (Regular Season)", "-")
    lines.append(f"  {'Season':<8} {'Games':>6} {'Correct':>8} {'Accuracy':>10}")
    lines.append(f"  {'-'*8} {'-'*6} {'-'*8} {'-'*10}")
    for season in SEASONS:
        r = per_season_reg[season]
        lines.append(
            f"  {season:<8} {r.total_games:>6} {r.correct_predictions:>8} "
            f"{pct(r.correct_predictions, r.total_games):>10}"
        )

    h("3. PER-SEASON BREAKDOWN (Playoffs)", "-")
    lines.append(f"  {'Season':<8} {'Games':>6} {'Correct':>8} {'Accuracy':>10}")
    lines.append(f"  {'-'*8} {'-'*6} {'-'*8} {'-'*10}")
    for season in SEASONS:
        r = per_season_po[season]
        lines.append(
            f"  {season:<8} {r.total_games:>6} {r.correct_predictions:>8} "
            f"{pct(r.correct_predictions, r.total_games):>10}"
        )

    # --- Regular vs Playoff ---
    h("4. REGULAR SEASON vs PLAYOFFS", "-")
    row("Regular season accuracy",  pct(reg_c, reg_n))
    row("Playoff accuracy",         pct(po_c, po_n))
    delta = (reg_c / reg_n - po_c / po_n) * 100 if reg_n and po_n else 0
    sign  = "+" if delta >= 0 else ""
    row("Delta (reg - playoff)",    f"{sign}{delta:.1f} pp")

    # --- Home vs Away Prediction ---
    h("5. HOME vs AWAY PREDICTION BREAKDOWN", "-")

    def ha_rows(label_prefix, ha):
        hp = ha['home_predicted']
        ap = ha['away_predicted']
        row(f"{label_prefix} — predicted home wins",
            f"{hp['total']:>5} predictions  →  {pct(hp['correct'], hp['total'])} accurate")
        row(f"{label_prefix} — predicted away wins",
            f"{ap['total']:>5} predictions  →  {pct(ap['correct'], ap['total'])} accurate")

    ha_rows("All games", ha_all)
    lines.append("")
    ha_rows("Regular season", ha_reg)
    lines.append("")
    ha_rows("Playoffs", ha_po)

    # --- Confidence Level Breakdown ---
    h("6. ACCURACY BY CONFIDENCE LEVEL (All Games)", "-")
    lines.append(f"  {'Level':<10} {'Games':>6} {'Correct':>8} {'Accuracy':>10}")
    lines.append(f"  {'-'*10} {'-'*6} {'-'*8} {'-'*10}")
    for level, total, correct in [
        ('HIGH',   combined_all.high_conf_total,   combined_all.high_conf_correct),
        ('MEDIUM', combined_all.medium_conf_total, combined_all.medium_conf_correct),
        ('LOW',    combined_all.low_conf_total,    combined_all.low_conf_correct),
    ]:
        lines.append(
            f"  {level:<10} {total:>6} {correct:>8} {pct(correct, total):>10}"
        )

    # Repeat for regular season
    lines.append(f"\n  Regular season only:")
    lines.append(f"  {'Level':<10} {'Games':>6} {'Correct':>8} {'Accuracy':>10}")
    lines.append(f"  {'-'*10} {'-'*6} {'-'*8} {'-'*10}")
    for level, total, correct in [
        ('HIGH',   combined_reg.high_conf_total,   combined_reg.high_conf_correct),
        ('MEDIUM', combined_reg.medium_conf_total, combined_reg.medium_conf_correct),
        ('LOW',    combined_reg.low_conf_total,    combined_reg.low_conf_correct),
    ]:
        lines.append(
            f"  {level:<10} {total:>6} {correct:>8} {pct(correct, total):>10}"
        )

    # --- Calibration ---
    h("7. PROBABILITY CALIBRATION (All Games 2020-2024)", "-")
    lines.append(
        "  Ideal calibration: a bucket showing X% should win roughly X% of the time."
    )
    lines.append("")
    lines.append(f"  {'Prob bucket':<12} {'Predictions':>12} {'Actual wins':>12} {'Actual %':>10}  {'Ideal mid':>10}  {'Delta':>8}")
    lines.append(f"  {'-'*12} {'-'*12} {'-'*12} {'-'*10}  {'-'*10}  {'-'*8}")

    bucket_midpoints = {
        '50-55%': 52.5, '55-60%': 57.5, '60-65%': 62.5,
        '65-70%': 67.5, '70-75%': 72.5, '75-80%': 77.5, '80%+': 85.0,
    }
    for label, _, _ in CALIBRATION_BUCKETS:
        b = calib_all[label]
        total   = b['total']
        correct = b['correct']
        actual  = correct / total * 100 if total else 0
        ideal   = bucket_midpoints[label]
        delta   = actual - ideal
        sign    = "+" if delta >= 0 else ""
        bar     = "#" * int(round(actual / 5)) if total else ""
        lines.append(
            f"  {label:<12} {total:>12} {correct:>12} {actual:>9.1f}%  {ideal:>9.1f}%  {sign}{delta:>6.1f}pp  {bar}"
        )

    # --- Observations & Caveats ---
    h("8. METHODOLOGY NOTES", "-")
    lines.append(
        "  * TRUE OUT-OF-SAMPLE: each game is predicted using only data available\n"
        "    BEFORE that game's date. The 3-season analysis window is anchored to the\n"
        "    season under test (current_season=game_season), so no future data leaks in.\n"
    )
    lines.append(
        "  * Rest days are computed relative to the game date (not today), and search\n"
        "    across all prior seasons so week-1 teams get their correct bye/off-season rest.\n"
    )
    lines.append(
        "  * Tied games are excluded from accuracy calculations (winner_id IS NULL).\n"
    )
    lines.append(
        "  * Confidence level thresholds (based on current-season games played):\n"
        "      HIGH   = both teams have ≥ 10 current-season games (week 11+)\n"
        "      MEDIUM = both teams have ≥  3 current-season games (weeks 4–10)\n"
        "      LOW    = fewer than 3 current-season games (weeks 1–3)\n"
    )
    lines.append(
        "  * Prediction weights used by the engine:\n"
        "      15% weighted win-pct  |  15% offensive/defensive strength\n"
        "      15% recent form       |  15% strength of schedule\n"
        "      15% home/away splits  |  10% head-to-head record\n"
        "      15% advanced stats (turnover margin, yards/play, 3rd-down %, red-zone %)\n"
        "    + dynamic home-field advantage (team-specific, capped 0-10%)\n"
        "    + bye-week rest bonus (+1.5%)\n"
        "    Note: if advanced stats unavailable, their 15% is redistributed to win-pct.\n"
    )

    report_text = "\n".join(lines)

    # -----------------------------------------------------------------------
    # Print to console
    # -----------------------------------------------------------------------
    print("\n")
    print(report_text)

    # -----------------------------------------------------------------------
    # Save as markdown
    # -----------------------------------------------------------------------
    md_path = ROOT.parent / "backtest_report.md"
    md_lines = ["# NFL Prediction Model — Backtest Report 2020–2024\n"]
    md_lines.append(f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Convert the plain-text report to slightly nicer markdown
    for line in lines:
        stripped = line.strip()
        if not stripped:
            md_lines.append("")
        elif stripped.startswith("===") or stripped.startswith("---"):
            continue  # separator lines become part of the heading above
        elif line.startswith("\n") and stripped and not stripped[0].isspace():
            # Section headers
            md_lines.append(f"## {stripped}\n")
        else:
            md_lines.append(line)

    md_text = "\n".join(md_lines)
    md_path.write_text(md_text)
    print(f"\n\nReport saved to: {md_path}")


if __name__ == "__main__":
    main()
