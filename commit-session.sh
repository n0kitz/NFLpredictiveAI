#!/usr/bin/env bash
# Commits the 2026-08-20 and 2026-08-21 sessions in logical chunks, then
# pushes to origin/main. Written by Claude because the permission classifier
# blocked git and sqlite writes; review and run it yourself:
#
#     bash commit-session.sh
set -euo pipefail

cd "$(dirname "$0")"

TRAILER=$'\n\nCo-Authored-By: Claude <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_0113c2F3W2FCzbaFZpLLakUd'

# ── 0. Clean pytest artifacts out of the tracked DB ──────────────────────────
# The API tests POST predictions, which land in the git-tracked nfl.db. Those
# rows are test noise, not data. A plain `git restore` is NOT safe here: the
# same file also holds this session's real roster/schedule/aggregate work.
echo "==> Removing pytest-written prediction rows"
before=$(sqlite3 nfl-predictor/data/nfl.db "SELECT COUNT(*) FROM prediction_history;")
sqlite3 nfl-predictor/data/nfl.db \
  "DELETE FROM prediction_history WHERE predicted_at >= '2026-08-20';"
after=$(sqlite3 nfl-predictor/data/nfl.db "SELECT COUNT(*) FROM prediction_history;")
echo "    prediction_history: $before -> $after (expected 250)"
if [ "$after" != "250" ]; then
  echo "    !! expected 250 rows after cleanup — inspect before committing" >&2
  exit 1
fi

# ── 1. ESPN scraping fix ─────────────────────────────────────────────────────
git add nfl-predictor/src/scraper/roster_scraper.py \
        nfl-predictor/src/scraper/schedule_scraper.py \
        nfl-predictor/scripts/import_rosters.py \
        nfl-predictor/tests/test_espn_user_agent.py \
        nfl-predictor/tests/test_roster_import_result.py
git commit -m "fix: ESPN 403 on all roster/schedule fetches (custom User-Agent)" -m \
"site.api.espn.com now rejects custom and browser-spoofed User-Agents while
still serving honest client identifiers. Verified by probe: curl/8.7.1 and
python-requests/2.32.5 return 200; Mozilla/5.0, NFL-Predictor/1.0 and every
other custom string return 403.

Both ESPN scrapers sent a custom UA, so all 32 team fetches failed.
pfr_scraper is a different host that still needs its browser UA and is
deliberately untouched.

The roster importer also printed \"complete\" and exited 0 after upserting
nothing; evaluate_roster_import() now classifies the run and a total failure
exits 1 so cron and humans notice.$TRAILER"

# ── 2. Weekly importer: season aggregates + name matching ────────────────────
# player_weekly_importer.py carries both changes; git can't split one file
# across commits, so they land together and the message covers both.
git add nfl-predictor/src/scraper/player_weekly_importer.py \
        nfl-predictor/scripts/import_player_weekly.py \
        nfl-predictor/scripts/weekly_scrape.py \
        nfl-predictor/tests/test_offense_season_aggregate.py
git commit -m "fix: build offensive season stats from weekly rows" -m \
"nfl_data_py.import_seasonal_data 404s for 2025+, the same nflverse
retirement that already killed the weekly feed. player_season_stats
therefore had zero QB/RB/WR/TE rows for 2025, and since draft rankings
weight last season at 65%, the 2026 board silently fell back to 2024 alone.

aggregate_offense_season_stats() rolls the weekly parquet data up instead,
mirroring the existing K/DST aggregation, and runs from both the import
script and the weekly cron.

Effect on the 2026 board: Christian McCaffrey #255 -> #9 (he missed most of
2024), Puka Nacua #30 -> #5, Jaxon Smith-Njigba #74 -> #13.

Also hardens the shared name matcher in this file (tests arrive with the ADP
commit): accent- and suffix-tolerant fallback via normalize_player_name, and
the exact-name lookup now qualifies by position instead of taking whichever
duplicate row came first.$TRAILER"

# ── 3. scrape_log self-heal ──────────────────────────────────────────────────
git add nfl-predictor/src/database/schema.sql \
        nfl-predictor/tests/test_scrape_log_table.py
git commit -m "fix: recreate missing scrape_log table via schema.sql" -m \
"data/nfl.db reported db_version = 25 with every migration applied, yet the
scrape_log table from migration v7 did not exist, so write_scrape_log()
raised 'no such table' and a failed cron run would have left no trace.

A version stamp is not proof the DDL ran. schema.sql is replayed on every
fresh open, so listing the table there repairs existing databases.$TRAILER"

# ── 4. Season off-by-one ─────────────────────────────────────────────────────
git add nfl-predictor/frontend/src/config.ts \
        nfl-predictor/frontend/src/config.test.ts
git commit -m "fix: LAST_COMPLETED_SEASON was a year behind in the offseason" -m \
"CURRENT_SEASON - 1 is only correct while a season is running. From February
to August the season labelled CURRENT_SEASON has already finished, so the
constant pointed at 2024 while 2025 was fully played -- serving two-year-old
stats to Leaderboards, Waiver, Power Rankings and Trade values in the middle
of draft prep.

lastCompletedSeason() derives it from the date, with tests at each boundary.$TRAILER"

# ── 5. Data refresh ──────────────────────────────────────────────────────────
git add nfl-predictor/data/nfl.db
git commit -m "data: 2026 rosters + schedule, 2025 season aggregates" -m \
"Roster refresh 2026-08-20 (32/32 teams, 3,202 entries; the first successful
run since the ESPN 403 started). 2026 schedule imported: 272 games, kickoff
2026-09-10, every team on exactly 17 games with coherent byes in weeks 5-14.
2,146 offensive season rows rebuilt from weekly data for 2018-2025.$TRAILER"

# ── 6. Draft simulator ───────────────────────────────────────────────────────
git add nfl-predictor/frontend/src/pages/fantasy/draftSim.ts \
        nfl-predictor/frontend/src/pages/fantasy/draftSim.test.ts \
        nfl-predictor/frontend/src/pages/DraftSimulatorPage.tsx \
        nfl-predictor/frontend/src/pages/DraftSimulatorPage.test.tsx \
        nfl-predictor/frontend/src/App.tsx \
        nfl-predictor/frontend/src/components/Layout.tsx
git commit -m "feat: draft strategy simulator (/draft/sim)" -m \
"Batch-compare eight drafting strategies over seeded mock drafts against
four bot archetypes, plus an interactive mock draft for rehearsing draft
night. The engine is pure and reuses the live board's snake order and
positional-need logic, so simulator and board cannot drift apart.

Positional caps stop VBD-only strategies hoarding a position -- without them
'best available' finished a draft holding eight quarterbacks. Value-vs-ADP
compares only players in range, and the UI says so when ADP is synthetic
(player_adp is empty), rather than implying the strategy is bad.

Real 2026 data, 50 drafts per strategy: Hero-RB wins from slots 1 and 5,
Robust-RB and Late-QB from slot 10. 400 drafts run in ~1.2 s.$TRAILER"

# ── 7. Live ADP fetch ────────────────────────────────────────────────────────
git add nfl-predictor/src/scraper/adp_importer.py \
        nfl-predictor/scripts/import_adp.py \
        nfl-predictor/scripts/import_player_weekly.py \
        nfl-predictor/tests/test_adp_fetch.py \
        nfl-predictor/tests/test_player_name_matching.py
git commit -m "feat: fetch real ADP from a public API instead of a manual CSV" -m \
"DoD 1.4 had sat at 'download a FantasyPros CSV' for weeks, which is why
player_adp was still empty with the draft close. Fantasy Football Calculator
publishes the same consensus ADP as free JSON, so:

    python scripts/import_adp.py --season 2026

now fills the table in one command, re-runnable as the market moves, for
standard / half-PPR / PPR. The CSV path stays available via --file.

Positions arrive as PK/DEF and are normalized to K/DST; team defenses match
by abbreviation to the synthetic DST-{abbr} players rather than by name.
An import that matches nothing exits 1 -- otherwise the board silently falls
back to synthetic rank ADP and every value-vs-market number is fiction.

Name normalization (impl in the weekly-importer commit) takes the 2026 match
rate from 209/211 to 211/211: 'Kenneth Walker' -> 'Kenneth Walker III',
'Eddy Pineiro' with and without the tilde.

Note: FFC echoes the teams parameter but returns identical pooled ADP for
8- and 14-team leagues, so ADP is not league-size-tuned. League size enters
through VBD.$TRAILER"

# ── 7b. Name-matching repair ─────────────────────────────────────────────────
git add nfl-predictor/tests/test_weekly_stats_purge.py \
        rebuild-weekly-stats.sh
git commit -m "fix: stop the name matcher binding feed names to the wrong player" -m \
"The last-name fallback took the first row matching last_name + position, so
any player sharing a surname within a position could capture another's data.
Found when the 2026 ADP import reported 211/211 matched but wrote 210 rows:
'Brian Robinson' (we store 'Brian Robinson Jr.') resolved to Bijan Robinson
and replaced the #2 overall player's ADP of 2.2 with 107.0.

The same matcher feeds player_weekly_stats, where the damage is real: Bijan
carried 18 weekly rows for 2025 against 17 in source while Brian Robinson had
none, and 119 players held more 2024 rows than the source contains.

Matching is now ordered strongest-evidence-first (exact name+position, exact
name, normalized comparison, last name+position) and every fuzzy step needs a
unique candidate. The last-name step additionally needs a compatible first
name, because uniqueness alone still matched Russell Wilson to Zach Wilson --
our table simply carries no Russell. Collisions across the 2025 feed: 9 -> 0,
with unmatched rising 203 -> 220, which is the correct trade.

Re-importing does NOT repair existing rows (upserts key on player_id, season,
week), so purge_weekly_stats + a --rebuild flag do. rebuild-weekly-stats.sh
runs the repair for 2018-2025.$TRAILER"

# ── 7c. Injury pipeline ──────────────────────────────────────────────────────
git add nfl-predictor/src/scraper/injury_scraper.py \
        nfl-predictor/src/prediction/fantasy_scorer.py \
        nfl-predictor/scripts/fetch_conditions.py \
        nfl-predictor/tests/test_injury_scraper.py \
        nfl-predictor/tests/test_injury_matching.py \
        nfl-predictor/tests/test_fantasy.py
git commit -m "fix: injury reports never stored, and matched the wrong player" -m \
"injury_reports had sat at 0 rows. ESPN's payload carries no 'team' object --
each of the 32 entries is {id, displayName, injuries} -- so every row got
team_abbr='' and fetch_conditions.py grouped them all under one unusable key.
Teams now resolve from displayName; a row we cannot attribute is dropped with
a count rather than stored blank. 800 fetched -> 95 stored across 30 teams.

The scraper also filtered out 'Questionable' while _INJURY_RULES defines a
0.7x discount for it, so that rule was unreachable and questionable starters
projected as fully healthy. Positions narrowed to QB/RB/WR/TE/K: kickers were
missing despite being a scoring slot, defensive positions were noise.

The serious bug is the matching. Every injury lookup keyed on the last token
of the name, and \"Marvin Harrison Jr.\".split()[-1] is \"Jr.\", so a
LIKE '%jr.%' query returned whichever Jr. came first. Measured against live
data: 168 of 1013 rostered fantasy players inherited a stranger's injury, and
an 'Out' row multiplies a projection by 0.0. Filling the table would have
armed this. Matching now uses the normalized full name via build_injury_index
/ lookup_injury and returns None on ambiguity instead of guessing.
Result: 168 wrong -> 0, and 95 rows map to exactly 95 players.

Note: draft rankings still do not exclude ruled-out players, only penalise
injury frequency. That is deliberate -- a preseason 'Out' says nothing about
Week 1. Injuries bite in weekly projections, verified live: George Kittle
-> 0.0, Khalil Shakir (Questionable) -> 7.28.\$TRAILER"

# ── 7d. Season constants ─────────────────────────────────────────────────────
git add nfl-predictor/src/config.py \
        nfl-predictor/src/api/routers/fantasy.py \
        nfl-predictor/src/api/routers/teams.py \
        nfl-predictor/src/api/routers/matchup.py \
        nfl-predictor/src/api/schemas.py \
        nfl-predictor/tests/test_season_config.py
git commit -m "fix: replace 10 hardcoded season defaults with date-derived constants" -m \
"src/config.py had no season constants at all, so routers carried
Query(2024) defaults long after 2024 stopped being relevant -- the backend
twin of the LAST_COMPLETED_SEASON bug already fixed in the frontend.

Adds current_nfl_season / last_completed_season / active_season, mirroring
frontend/src/config.ts. ACTIVE_SEASON is last_completed + 1 rather than the
frontend's CURRENT_SEASON + 1, which would roll to 2027 the moment September
2026 arrives even though 2026 is the season being played.

A regex guard test scans src/api/ and fails the build if a season literal
returns, which is what stops this rotting back in.\$TRAILER"

# ── 7e. My Team advisor ──────────────────────────────────────────────────────
git add nfl-predictor/src/prediction/roster_advisor.py \
        nfl-predictor/src/prediction/league_settings.py \
        nfl-predictor/tests/test_roster_advisor.py \
        nfl-predictor/tests/test_start_sit.py \
        nfl-predictor/tests/test_my_team_api.py \
        nfl-predictor/frontend/src/pages/fantasy/MyTeamTab.tsx \
        nfl-predictor/frontend/src/pages/fantasy/MyTeamTab.test.tsx \
        nfl-predictor/frontend/src/pages/FantasyPage.tsx \
        nfl-predictor/frontend/src/api/client.ts \
        nfl-predictor/frontend/src/api/types.ts \
        nfl-predictor/frontend/src/config.ts \
        nfl-predictor/frontend/src/config.test.ts
git commit -m "feat: roster-aware lineup advice and N-player start/sit" -m \
"Adds the question the app could not answer: given MY roster, what should I
change this week. /fantasy now opens on a My Team tab that returns the best
legal lineup under the configured league settings, the specific swaps to
reach it with reasons, injury warnings on your own players, and a
per-position 'who should I start' ranking.

Three parts:

1. Start/sit ranked on projected_points_ppr even though the default league is
   NFL.com Standard, systematically over-valuing high-reception players. It
   now goes through LeagueSettings.points_from_projection, and the reasoning
   quotes the number it ranked on. Live check: Chase leads Nacua by +1.0 in
   standard but +3.2 in PPR.

2. start_sit_recommendation compared exactly two players. rank_start_sit takes
   any number, marks the top N as starts, and reports the margin over the next
   option; the old endpoint delegates to it so nothing regressed.

3. roster_advisor constrains the existing MILP to the roster you own, with
   slots from LeagueSettings and correlations/per-team caps disabled (DFS
   constructs that distort a season-long roster). swap_list diffs the optimal
   lineup against either your current starters or a greedy baseline.

Two behaviours worth keeping: a swap with a non-positive delta is never
emitted (pairing best-upgrade with worst-downgrade could produce '+-0.9 pts'
alongside zero points gained), and a forced starter projecting zero -- the
only rostered TE being ruled out -- raises a warning instead of silently
appearing in the lineup.

Note: the pool is built by projecting each rostered player directly rather
than reading fantasy_projections. For 2026 wk1 those cached rows put a backup
QB at 12.0 above Bijan Robinson at 5.4, inverted against calculate_projection
(1.65 / 17.16). The bulk generator is a separate open bug.\$TRAILER"

# ── 8. Docs ──────────────────────────────────────────────────────────────────
git add CLAUDE.md lessons-learned/SKILL.md nfl-predictive-ai/SKILL.md \
        session-protocol/SKILL.md nfl-predictor/GUIDEBOOK.md \
        nfl-predictor/README.md
git commit -m "docs: sync guidebook, conventions and lessons for 2026-08-20/21" -m \
"Test counts 510 backend (31 files) / 120 frontend (14 files). DoD 1.3b for
the simulator, 1.4 down to a single command, 1.6 updated with My Team
advisor and N-way start/sit, 3.3 showing 95 injury rows flowing, 3.6 updated
test counts, last-updated 2026-08-21. Pillar scores unchanged: ~85/90/55.

New lessons: ESPN's inverted UA policy, imports that succeed while importing
nothing, sibling data feeds dying together, position hoarding under raw VBD,
a penalty applied to every candidate being no penalty, manual runbook steps
that have a public API, LIMIT 1 over a non-unique key, two code paths
computing the same quantity diverging, tsc vs npm run build config mismatch,
scoring column selection belongs in LeagueSettings not at each call site,
non-positive swap delta is noise not advice, forced-out starter needs a
warning not silence.

Promoted to session-protocol: 'source .venv/bin/activate' is not proof the
venv is active -- call .venv/bin/python explicitly.$TRAILER"

echo
echo "==> Commits created:"
git log --oneline -8
echo
read -r -p "Push these to origin/main? [y/N] " reply
[[ "$reply" == "y" || "$reply" == "Y" ]] && git push origin main && echo "Pushed." || echo "Not pushed."
