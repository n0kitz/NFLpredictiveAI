#!/usr/bin/env bash
# Rebuilds player_weekly_stats + player_season_stats for 2018-2025 from the
# nflverse source, using the corrected name matcher.
#
# Why this is needed: imports upsert on (player_id, season, week), so weekly
# rows that an earlier buggy matcher attached to the WRONG player are never
# corrected by re-importing — they survive. --rebuild purges each season
# first. Verified damage before the fix: Brian Robinson's 2025 rows sat on
# Bijan Robinson's player_id (Bijan showed 18 weeks against 17 in source,
# Brian showed none), and 119 players had more 2024 rows than source.
#
# Written by Claude because the permission classifier blocked the run.
# Review and run it yourself:  bash rebuild-weekly-stats.sh
#
# Takes a few minutes: eight parquet files are downloaded from nflverse.
set -euo pipefail

cd "$(dirname "$0")/nfl-predictor"

# Explicit interpreter: `source .venv/bin/activate` has silently resolved to
# anaconda in this environment, and anaconda's numpy 2.x breaks the ML stack.
PY=.venv/bin/python
"$PY" -c "import sys, numpy; print('interpreter:', sys.executable); print('numpy:', numpy.__version__)"

echo
echo "==> Before"
"$PY" - <<'EOF'
import sqlite3
c = sqlite3.connect("data/nfl.db")
print("  weekly rows 2018-2025:",
      c.execute("SELECT COUNT(*) FROM player_weekly_stats WHERE season BETWEEN 2018 AND 2025").fetchone()[0])
row = c.execute("""SELECT COUNT(*) FROM player_weekly_stats w JOIN players p USING(player_id)
                   WHERE p.full_name = 'Bijan Robinson' AND w.season = 2025""").fetchone()[0]
print("  Bijan Robinson 2025 weeks:", row, "(source says 17)")
EOF

echo
echo "==> Rebuilding (purge + re-import + re-aggregate)"
"$PY" scripts/import_player_weekly.py --start 2018 --end 2025 --rebuild

echo
echo "==> After"
"$PY" - <<'EOF'
import sqlite3
c = sqlite3.connect("data/nfl.db")
c.row_factory = sqlite3.Row
print("  weekly rows 2018-2025:",
      c.execute("SELECT COUNT(*) FROM player_weekly_stats WHERE season BETWEEN 2018 AND 2025").fetchone()[0])
for name in ("Bijan Robinson", "Brian Robinson Jr."):
    r = c.execute("""SELECT COUNT(*) n, COALESCE(SUM(w.rush_yards), 0) ry
                     FROM player_weekly_stats w JOIN players p USING(player_id)
                     WHERE p.full_name = ? AND w.season = 2025""", (name,)).fetchone()
    print(f"  {name:22s} 2025: {r['n']} weeks, {int(r['ry'])} rush yds")
print("  expected: Bijan 17 weeks / 1478 yds, Brian 17 weeks / 400 yds")
EOF

echo
echo "Done. Draft rankings and leaderboards read player_season_stats, which was"
echo "re-aggregated above — re-check the /draft board after this."
