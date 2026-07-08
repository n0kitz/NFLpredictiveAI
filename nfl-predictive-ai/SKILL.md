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
| Tests | **349 backend** (pytest, 22 files) + **64 frontend** (vitest, run from `frontend/`) |
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

- **nfl_data_py `import_weekly_data` is DEAD for 2025+** — nflverse retired the `player_stats_{year}` release. Weekly data: `fetch_stats_player_week(years)` in `player_weekly_importer.py` (`stats_player_week_{year}.parquet`; renames: `interceptions`→`passing_interceptions`, `recent_team`→`team`; filter `season_type=='REG'`).
- **DST = synthetic players** (`espn_id='DST-{abbr}'`, position `DST`, per-season roster entries via `ensure_dst_players`). ESPN kickers arrive `PK` → normalized `K` in `roster_scraper`.
- **Draft rankings compute per request** (`?season=&scoring=&league_size=`), board ordered by **VBD**; `draft_rankings` table is only a last-request cache. Real ADP lives in `player_adp` and wins over synthetic rank ADP.
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
