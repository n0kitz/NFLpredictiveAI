# NFL Predictive AI — Project Conventions & Active State

> Status, definition of done, roadmap: **`nfl-predictor/GUIDEBOOK.md`** (canonical).
> Structure, endpoint map, architecture notes: **root `CLAUDE.md`**.
> This file: the working conventions + gotchas an agent needs in every session.

## Stack Quick Reference

| Layer | Tech |
|-------|------|
| API | FastAPI + Uvicorn, thin `src/api/app.py`, 7 routers (teams, games, predictions, fantasy, matchup, nfl_league, misc) |
| DB | SQLite + WAL, `data/nfl.db`, schema in `schema.sql` + `MIGRATIONS` in `db.py` (v25) |
| ML | Game: GradientBoosting **34 feat** (OOS 0.668; weighted-sum 0.672 default). Player: per-position **16 feat** (QB/RB/WR/TE). K/DST heuristic |
| Fantasy | `fantasy_scorer.py` + `league_settings.py` (scoring **standard default**, league_size 8–20) + `matchup_engine.py` + `lineup_optimizer.py` |
| Frontend | React 19 + TS + Tailwind v4; localStorage hooks are the state layer (`leagueSettings`, `myRoster`, `draftBoard`) |
| Tests | **573 backend** (pytest, 39 files) + **144 frontend** (vitest, run from `frontend/`) |
| Infra | Docker Compose (nginx frontend → internal api + cron); CI in `.github/workflows/ci.yml`; GHCR on `v*` tags |

## Hard Rules

1. **Env first**: `cd nfl-predictor && source .venv/bin/activate` — anaconda base (numpy 2.x) breaks player-ML and poisons the projections cache.
2. **No leakage**: Vegas/injuries/weather never become game-prediction inputs (player projections may use Vegas totals — deliberate).
3. **Schema**: every change → `schema.sql` **and** `MIGRATIONS` list. Never inline DDL elsewhere.
4. **`sqlite3.Row`**: bracket access `r["col"]` only — `.get()` does not exist.
5. **Scraper HTTP**: `src/scraper/http.get_with_retry` — never raw `requests.get` in scrapers.
6. **Frontend seasons**: use `frontend/src/config.ts` (`CURRENT_SEASON`, `UPCOMING_SEASON`, …) — never `new Date().getFullYear()` (calendar ≠ NFL season).
7. **Fantasy defaults**: scoring `'standard'`, league size parametric via `LeagueSettings` — never hardcode `'ppr'` or 12-team cutoffs.

## Live Gotchas

- **nfl_data_py is DEAD for 2025+ — weekly AND seasonal.** `import_weekly_data` and `import_seasonal_data` both 404 (nflverse retired those releases). Weekly data: `fetch_stats_player_week(years)` in `player_weekly_importer.py` (`stats_player_week_{year}.parquet`; renames: `interceptions`→`passing_interceptions`, `recent_team`→`team`; filter `season_type=='REG'`). **Season totals: `aggregate_offense_season_stats()` + `aggregate_kicker_dst_season_stats()`** roll the weekly rows up into `player_season_stats` — which draft rankings and leaderboards both read, so a season missing there degrades the board without any error.
- **ESPN 403s custom User-Agents** (since 2026-08-20). `roster_scraper` + `schedule_scraper` send the default `python-requests/…` UA on purpose — setting `Mozilla/…` or an app-branded UA makes all 32 team fetches fail. `pfr_scraper` (different host) still needs its browser UA. Guarded by `tests/test_espn_user_agent.py`.
- **`LAST_COMPLETED_SEASON` is not `CURRENT_SEASON - 1`** in the offseason — `lastCompletedSeason()` in `frontend/src/config.ts` returns the current label Feb–Aug and one behind Sep–Jan.
- **DST = synthetic players** (`espn_id='DST-{abbr}'`, position `DST`, per-season roster entries via `ensure_dst_players`). ESPN kickers arrive `PK` → normalized `K` in `roster_scraper`.
- **Draft rankings compute per request** (`?season=&scoring=&league_size=`), board ordered by **VBD**; `draft_rankings` table is only a last-request cache. Real ADP lives in `player_adp` and wins over synthetic rank ADP.
- **ADP needs no download**: `python scripts/import_adp.py --season 2026` fetches live consensus ADP from Fantasy Football Calculator (public JSON, standard/half_ppr/ppr). `--file` still imports a CSV. FFC echoes the `teams` param but serves **identical pooled ADP for every league size** — don't claim league-size-tuned ADP. `PK`→`K`, `DEF`→`DST`; defenses resolve by team abbr to `DST-{abbr}`, never by name.
- **Name matching, strongest evidence first**: `_match_player_id` tries exact name+position → exact name → accent/suffix-folded normalized comparison → last name+position. Every fuzzy step needs a **unique** candidate, and the last-name step additionally needs a compatible first name (`_first_names_compatible`: equal, or a prefix of ≥3 chars, so Josh/Joshua matches but Brian/Bijan and Russell/Zach don't). Returns `None` rather than guessing. A wrong match silently overwrites another player's row — this bug put Brian Robinson's stats on Bijan Robinson and gave Bijan an ADP of 107.0.
- **Injury matching is full-name only.** `build_injury_index()` / `lookup_injury()` in `fantasy_scorer.py` key on `normalize_player_name`, never the last token — `"Marvin Harrison Jr.".split()[-1]` is `"Jr."`, which mis-attributed 168 of 1013 rostered players (an `Out` row zeroes a projection). Ambiguous collisions return `None` rather than guess. Never reintroduce a `player_name LIKE '%…%'` lookup.
- **Injuries come from ESPN's `displayName`**, not a `team` object (there isn't one) — `TEAM_NAME_TO_ABBR` in `injury_scraper.py`. Unresolvable rows are dropped with a count, never stored blank. Filter keeps `QB/RB/WR/TE/K` and `Out/Doubtful/IR/PUP/Questionable`; the status set must stay in step with `_INJURY_RULES` or a rule becomes unreachable.
- **Draft rankings deliberately do NOT exclude ruled-out players** — only an injury-frequency penalty applies. A preseason "Out" says nothing about Week 1. Injuries bite in weekly projections instead.
- **Backend seasons come from `src/config.py`** (`CURRENT_SEASON`, `LAST_COMPLETED_SEASON`, `ACTIVE_SEASON` — the last is `last_completed + 1`, the season being drafted/played). Never hardcode `Query(2024)`; `tests/test_season_config.py` greps `src/api/` and fails the build if a literal returns.
- **After any matching change, re-import is not repair.** Weekly upserts key on `(player_id, season, week)`, so rows on the wrong player survive forever. Use `python scripts/import_player_weekly.py --start 2018 --end 2025 --rebuild` (purges the range first via `purge_weekly_stats`).
- **Week 1 has no in-season history, so ML is skipped by design** (fixed 2026-08-22; was the "constant feature vector" bug). `build_player_feature_vector` reads weekly rows only from *within* the requested season, so at week 1 every rolling/usage feature is 0.0 — **for a played season too**, not just a future one (verified: Bijan 2025 wk1 rolling averages 0.0; 2025 wk10 = 20.1/21.1). The model then can't separate an elite back from a backup and emits one constant per position — that's how four QBs ended up tied at 12.04 on top of the board. `generate_weekly_projections` now prefetches `players_with_history` and **skips the ML override** for anyone without prior in-season rows, falling through to the heuristic. Two consequences: (a) week-1 `model_source` is legitimately `heuristic`, not a bug; (b) if you ever add a prior-season fallback *inside* the feature builder, the models must be retrained — they were trained on week-1 rows containing zeros.
- **`fantasy_projections` is trustworthy again**, but `roster_advisor.build_roster_pool()` still projects each rostered player directly via `calculate_projection`. That's deliberate: a roster is ~25 players, per-player projection is cheap, and it keeps lineup advice consistent with start/sit (same call). Don't "optimize" it into a cache read.
- **The bulk projection query falls back across seasons.** It joins the most recent `player_season_stats` season **at-or-before** the requested one (`ROW_NUMBER() … WHERE season <= ?`), mirroring `get_player_stats`' fallback. The exact-season join it replaced zeroed every base for an unplayed season. The `season <= ?` bound is load-bearing — it keeps backtests leak-free.
- **Start/sit ranks in the league's scoring**, via `LeagueSettings.points_from_projection` — not PPR. `rank_start_sit(player_ids, week, season, slots, settings)` handles N players; the 2-player `start_sit_recommendation` delegates to it.
- **Projections cache**: `/api/fantasy/projections` serves persisted `fantasy_projections` rows first. Stale/heuristic rows → `DELETE FROM fantasy_projections WHERE season=? AND week=?` and regenerate from the `.venv`. Projections need the season to have `roster_entries`.
- **vitest**: run from `frontend/` (setup file + jsdom config only load there); localStorage is polyfilled in `src/test/setup.ts`.
- **`matchup_cache` / metrics TTL**: `calculate_team_metrics()` cached 1h keyed `(team_id, season)`, bypassed with `cutoff_date` (backtests/retrodictions rely on this).
- **Retrodiction contract**: `/api/games/{id}/retrodiction` mirrors backtester config (weighted-sum, cutoff-aware, no factors); 400 for unplayed games.
- **Bye/playoff-SOS planner** (`schedule_outlook.py`): bye weeks from `db.get_bye_weeks()`, opponent schedule from the `games` table (never a hardcoded bye table). `opp_position_dvp()` is PPR-based regardless of league scoring — it's a *relative* difficulty signal (hard/medium/easy vs `league_avg_dvp()`), not a scoring-aware point projection; don't present it as one. Bye collisions (`BYE_COLLISION_THRESHOLD = 3`) are counted across the **whole roster passed in**, not a given week's starters — "starter" only exists relative to one week's optimal lineup, which shifts weekly.
- **Streaming DST/K/QB** (`streaming.py`): `matchup_grade()` scores a position vs. an opponent, not an individual player — every teammate at that position facing the same defense gets an identical grade. The candidate pool is deduped to **one player per team** before grading (never grade a whole depth chart, it's redundant). `roster_entries` has no starter/depth flag, so the "who's actually playing" pick uses games played this season, falling back to last season for the preseason window when this season has none yet.
- **Roster import is a snapshot — it purges, it doesn't accumulate** (fixed 2026-08-22). `roster_entries` is keyed `UNIQUE(player_id, team_id, season)`, so a player who changed teams used to keep *both* rows; 15 players sat on two teams at once and `get_player_team_id`'s `ORDER BY id DESC` picked arbitrarily, feeding a wrong opponent into `schedule_outlook` and `streaming`. `import_rosters.py` now calls `db.purge_stale_roster_entries(season, fetched_at)` after the import gate. **Two guards you must not remove**: (1) it only runs when `should_purge_stale(teams_with_players)` sees all 32 teams, because `evaluate_roster_import` returns `ok=True` on partial coverage and purging a 20/32 run would delete twelve real rosters; (2) synthetic `DST` players are exempt — ESPN never returns them, so their `fetched_at` is always stale and a naive purge wipes all 32 defenses off the draft board (caught by `test_rankings_include_k_and_dst`).
- **Tua Tagovailoa resolves to ATL, not MIA** (2026-08-21, still unexplained). *Not* the duplicate-entry bug above — he has exactly one entry. Either genuinely correct upstream data or an ESPN quirk; verify against a real depth chart before treating it as a defect.
- **FAAB advisor** (`waiver_advisor.py`): ranks a candidate against the *roster's own* weakest player at that position, not league-wide VBD — a player who'd be a bench-warmer on a stacked roster can be a must-add on a thin one. `build_roster_pool` is reused for both the roster side and the candidate side (same cache-independent projection path), and a position absent from the roster entirely gets a `0.0` replacement level, so any positive projection there is pure delta. Non-positive delta is filtered out, same rule as `swap_list`.
- **Weekly Briefing tab** (`WeeklyBriefingTab.tsx`) is UI-only composition — it calls `getMyTeamLineup`, `getScheduleOutlook` (scoped to the single selected week, not the default 15-17 playoff window), `getStreamingCandidates('DST', ...)`, and `getFaabRecommendations`, each independently swallowed to `null` on failure. Never add backend logic here; if a briefing number looks wrong, the bug is in one of those four endpoints, not this component.

## Architecture Conventions

- CLI: singleton `Database()`; API: per-request via `Depends(get_db)`.
- Prediction weights: 25/20/15/15/15/10 (record/strength/form/SOS/splits/H2H); dynamic HFA 0–10%; bye-rest +1.5%.
- Draft value: 2-season ppg blend 65/35 + shrinkage (<8 games) + age/injury penalties → VBD vs `replacement_ranks()`.
- K scoring: FG 0-49 = 3, 50+ = 5, XP = 1. DST: NFL.com brackets (sack 1, INT 2, FR 2, safety 2, TD 6, block 2, points-allowed 10…−4). Verify vs the user's actual league page before draft (GUIDEBOOK DoD 1.5).
- Cron (`weekly_scrape.py`, Wed): data refresh + projection purge/regen; **model retraining is manual by design**.

## Season Context (rolls forward)

User's fantasy.nfl.com draft: **Aug/Sep 2026**, league size 8/10/12 (was 20), NFL.com Standard. Pre-draft ritual: weekly `import_rosters.py --season 2026 --skip-stats`, ADP CSV import, scoring verification. The `/draft` board is the draft-night tool.
