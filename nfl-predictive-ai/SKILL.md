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
| Tests | **510 backend** (pytest, 31 files) + **120 frontend** (vitest, run from `frontend/`) |
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
- **Never source roster advice from `fantasy_projections`.** For a future season the bulk generator is wrong — 2026 wk1 had a backup QB at 12.0 above an elite RB at 5.4, exactly inverted vs `calculate_projection` (1.65 / 17.16), with identical values repeating across unrelated players (constant feature vector). `roster_advisor.build_roster_pool()` projects each rostered player directly instead. **`generate_weekly_projections` for future seasons is a known open bug.**
- **Start/sit ranks in the league's scoring**, via `LeagueSettings.points_from_projection` — not PPR. `rank_start_sit(player_ids, week, season, slots, settings)` handles N players; the 2-player `start_sit_recommendation` delegates to it.
- **Projections cache**: `/api/fantasy/projections` serves persisted `fantasy_projections` rows first. Stale/heuristic rows → `DELETE FROM fantasy_projections WHERE season=? AND week=?` and regenerate from the `.venv`. Projections need the season to have `roster_entries`.
- **vitest**: run from `frontend/` (setup file + jsdom config only load there); localStorage is polyfilled in `src/test/setup.ts`.
- **`matchup_cache` / metrics TTL**: `calculate_team_metrics()` cached 1h keyed `(team_id, season)`, bypassed with `cutoff_date` (backtests/retrodictions rely on this).
- **Retrodiction contract**: `/api/games/{id}/retrodiction` mirrors backtester config (weighted-sum, cutoff-aware, no factors); 400 for unplayed games.

## Architecture Conventions

- CLI: singleton `Database()`; API: per-request via `Depends(get_db)`.
- Prediction weights: 25/20/15/15/15/10 (record/strength/form/SOS/splits/H2H); dynamic HFA 0–10%; bye-rest +1.5%.
- Draft value: 2-season ppg blend 65/35 + shrinkage (<8 games) + age/injury penalties → VBD vs `replacement_ranks()`.
- K scoring: FG 0-49 = 3, 50+ = 5, XP = 1. DST: NFL.com brackets (sack 1, INT 2, FR 2, safety 2, TD 6, block 2, points-allowed 10…−4). Verify vs the user's actual league page before draft (GUIDEBOOK DoD 1.5).
- Cron (`weekly_scrape.py`, Wed): data refresh + projection purge/regen; **model retraining is manual by design**.

## Season Context (rolls forward)

User's fantasy.nfl.com draft: **Aug/Sep 2026**, league size 8/10/12 (was 20), NFL.com Standard. Pre-draft ritual: weekly `import_rosters.py --season 2026 --skip-stats`, ADP CSV import, scoring verification. The `/draft` board is the draft-night tool.
