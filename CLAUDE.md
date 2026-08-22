# NFL Predictor — Agent Operating Manual

## Skills

### /caveman
@caveman/SKILL.md

### /promptimprover
@promptimprover/SKILL.md

### /nfl-predictive-ai
@nfl-predictive-ai/SKILL.md

### /wissensdatenbank-capture
@wissensdatenbank-capture/SKILL.md

### /session-protocol (auto-active — start/end ritual + hygiene rules)
@session-protocol/SKILL.md

### /lessons-learned (auto-active — verified past mistakes, consult before fixing)
@lessons-learned/SKILL.md

### /season-ops (auto-active — calendar-driven duties, surface what's due)
@season-ops/SKILL.md

---

## What this project is — and where it's going

Full-stack NFL **game-prediction + fantasy-football decision engine**. Python 3.12 / FastAPI / SQLite backend (9,455 games 1990–2025, weighted + ML prediction engines, fantasy projections for QB/RB/WR/TE/K/DST, VBD draft rankings, MILP lineup optimizer). React 19 / TypeScript / Tailwind v4 frontend (12 pages incl. a 10-tab fantasy hub, a live draft board and a draft-strategy simulator). Docker Compose + weekly cron + GitHub Actions CI.

**The mission, definition of done, roadmap, and operating calendar live in `nfl-predictor/GUIDEBOOK.md` — read it before proposing new work.** Short version: (1) win the user's fantasy.nfl.com league, (2) keep the game model honest and baseline-beating, (3) make the service run itself. Judge every change against those three pillars.

## Non-negotiable invariants

1. **No input leakage into game predictions.** Vegas odds, injuries, weather are display-only context for game predictions — never features. (Player *fantasy* projections may use Vegas team totals; that is deliberate and documented.)
2. **Honest accuracy.** Predictions auto-save and self-grade; retrodictions show HIT/MISS publicly. Never present unvalidated accuracy claims in code or UI.
3. **Standard scoring is the default** (user's league is NFL.com Standard). League size 8–20 is a parameter, never a constant. All fantasy math flows through `LeagueSettings`.
4. **Env**: always `cd nfl-predictor && source .venv/bin/activate` (numpy<2). Anaconda base (numpy 2.x) silently breaks player-ML and can poison the projections cache.
5. **Schema changes** go to `src/database/schema.sql` **and** the `MIGRATIONS` list in `db.py` (at v25). Both, always.
6. **TDD** per superpowers skill; verify with the commands below before claiming green.

## Verification

```bash
cd nfl-predictor && source .venv/bin/activate
python -m pytest -q                        # 573 tests (~15 s in a clean .venv)
cd frontend && npm run build && npm test   # tsc + vite build, 144 vitest tests (run from frontend/ — vitest setup needs that cwd)
```

## Running

```bash
# Dev
cd nfl-predictor && ENV=dev python run_api.py       # API :8000
cd nfl-predictor/frontend && npm run dev            # UI :5173 (proxies /api)

# Docker (prod-shaped)
cd nfl-predictor && docker compose up --build       # frontend :3000 (nginx) → api internal, + cron container
```

## Key file map

| Need | File |
|------|------|
| Add API endpoint | `src/api/routers/{domain}.py` + `src/api/schemas.py` (app.py is a thin ~70-line wrapper, 7 routers) |
| DB query / migration | `src/database/db.py` (+ `schema.sql`) |
| Game prediction logic | `src/prediction/engine.py` (weighted) · `ml_model.py` + `feature_builder.py` (34-feat ML) · `explainer.py` (SHAP) |
| Team metrics | `src/prediction/metrics.py` (TTL-cached 1h) |
| Fantasy scoring / rankings | `src/prediction/fantasy_scorer.py` (projections, VBD draft rankings, trades, waivers) |
| League config (backend) | `src/prediction/league_settings.py` (scoring, league_size, replacement ranks, tiers) |
| Matchup grades A–F | `src/prediction/matchup_engine.py` (DvP/pace/PROE) |
| Lineup optimizer | `src/prediction/lineup_optimizer.py` (MILP/PuLP, season + DK/FD) |
| Roster-aware advice | `src/prediction/roster_advisor.py` (`build_roster_pool`, `lineup_advice`, `swap_list`) + `frontend/src/pages/fantasy/MyTeamTab.tsx` |
| Bye/playoff-SOS planner | `src/prediction/schedule_outlook.py` (`build_schedule_outlook`; bye collisions ≥3, wk15-17 DvP difficulty) + `frontend/src/pages/fantasy/ScheduleTab.tsx` |
| Streaming DST/K/QB | `src/prediction/streaming.py` (`streaming_candidates`; deduped one-per-team, ranked by `matchup_grade`) + `frontend/src/pages/fantasy/StreamingPanel.tsx` (in Waiver tab) |
| FAAB waiver advisor | `src/prediction/waiver_advisor.py` (`faab_recommendations`; value over roster's own replacement level, bid % tiers) + `frontend/src/pages/fantasy/FaabPanel.tsx` (in Waiver tab) |
| Weekly briefing | `frontend/src/pages/fantasy/WeeklyBriefingTab.tsx` — pure composition of My Team + Schedule + Streaming + FAAB, no new backend logic |
| Player weekly data | `src/scraper/player_weekly_importer.py` (**nflverse `stats_player_week` parquet — nfl_data_py weekly is dead for 2025+**) |
| DST data | `src/scraper/dst_importer.py` (synthetic players `DST-{abbr}` + defteam aggregation) |
| ADP import | `src/scraper/adp_importer.py` (live `fetch_ffc_adp` **or** CSV) + `scripts/import_adp.py` → `player_adp` table |
| Player name matching | `normalize_player_name` + `_match_player_id` in `player_weekly_importer.py` (accent/suffix tolerant, position-aware) |
| NFL.com sync (experimental) | `src/scraper/nfl_fantasy_api.py` + `routers/nfl_league.py` (`NFL_FANTASY_COOKIE`) |
| Scraper HTTP | `src/scraper/http.py` (`get_with_retry` — never raw `requests.get` in scrapers) |
| Settings / env | `src/config.py` (backend) · `frontend/src/config.ts` (seasons: `CURRENT_SEASON`, `UPCOMING_SEASON`…) |
| League config (frontend) | `frontend/src/pages/fantasy/leagueSettings.ts` (`useLeagueSettings` localStorage hook) |
| Draft board logic | `frontend/src/pages/fantasy/draftBoard.ts` (pure: snake, needs, tier breaks) + `pages/DraftBoardPage.tsx` |
| Draft simulator | `frontend/src/pages/fantasy/draftSim.ts` (pure: seeded RNG, 8 strategies, bot archetypes, batch compare) + `pages/DraftSimulatorPage.tsx` |
| API client / types | `frontend/src/api/client.ts` + `types.ts` |
| Weekly cron | `scripts/weekly_scrape.py` (Wed 06:00 UTC; fcntl-locked; purges stale projections before regen) |
| Observability | `src/observability.py` → `/api/metrics`, JSON logs, `X-Request-ID` |
| CI | `.github/workflows/ci.yml` (ruff+black+mypy+pytest / eslint+tsc+vitest; GHCR images on `v*` tags) |

## API surface (by router)

- **teams**: `/api/teams`, `/{id}`, `/{id}/stats|profile|season/{year}|games|roster|starters|upcoming`
- **games**: `/api/games`, `/{id}` (detail: odds+weather+factors+box score 2018+), `/{id}/retrodiction` (cutoff-aware HIT/MISS), `/{id}/odds`, `/{id}/conditions`
- **predictions**: `POST /api/predict` (auto-saves; `vegas_context`+`conditions` display-only), `/predict/explain` (SHAP), `GET /predict/{away}/{home}?model=ml`, `/h2h/{t1}/{t2}`, `/predictions/history`, `POST /predictions/enrich`
- **fantasy**: `/api/fantasy/top|projections|start-sit|waiver|draft-rankings|trade-analyze|power-rankings|trade-values|roster/import-by-names|model-info` (GET) + `POST /start-sit/rank` (N-way), `POST /my-team/lineup` (roster-constrained), `POST /schedule-outlook` (byes + wk15-17 SOS), `POST /streaming` (best DST/K/QB by matchup grade), `POST /waiver/faab` (bid % vs. roster replacement level) — `scoring=standard` default, `half_ppr` accepted; `draft-rankings` takes `league_size=8..20`, is **computed per request, VBD-ordered**
- **matchup**: `/api/fantasy/matchup/{player_id}` (A–F grade), `POST /api/fantasy/optimize`, `/optimize/dfs`
- **nfl_league**: `GET /api/nfl-league/{id}` (experimental sync; 503 without cookie)
- **misc**: `/api/health`, `/metrics`, `/accuracy`, `/factors`, `/model/info`, `/scrape/status`, `/players/{id}`, `/players/search`, `/players/{id}/weekly-stats`, `/seasons/{year}/playoff-picture`, `/picks/value`, `/picks/history`
- `GET /docs` — Swagger

## Frontend routes

`/` Dashboard · `/predict` · `/teams` · `/teams/:abbr` (+ `/schedule`) · `/compare/:t1?/:t2?` · `/seasons/:year?` (standings/games/playoff picture) · `/history` (self-graded prediction log) · `/playoffs` (bracket sim) · `/players/:id` (+ game log) · `/games/:id` (scoreboard, retrodiction HIT/MISS, ATS cover, box score) · `/fantasy` (10 tabs: Weekly Briefing, My Team, Schedule, Dashboard, Leaderboards, Waiver, Draft, Trade, Power Rankings, Optimizer) · `/draft` (live draft board) · `/draft/sim` (strategy simulator: batch compare + mock draft)

## Architecture notes that prevent rework

- API = per-request DB via `Depends(get_db)`; CLI = singleton. Lazy schema init per DB path.
- Prediction weights: 25% record, 20% strength, 15% form, 15% SOS, 15% splits, 10% H2H; dynamic HFA (0–10%); bye-week rest +1.5%. Weighted-sum 67.2% OOS is the default; ML (0.668) opt-in via `?model=ml`; `load_model()` refuses a stale feature list.
- `calculate_team_metrics()` TTL-cached 1h keyed `(team_id, season)`, bypassed with `cutoff_date` (backtests/retrodictions).
- Fantasy projections are **cached** in `fantasy_projections` per (season, week); the endpoint serves cache first. Wrong rows → `DELETE` + regenerate from `.venv`. Projections require the season to have `roster_entries`.
- Draft rankings: two-season ppg blend 65/35 + small-sample shrinkage (<8 games) + age/injury penalties → VBD vs `LeagueSettings.replacement_ranks()` → **board ordered by VBD** (never raw points). Real ADP from `player_adp` beats synthetic rank ADP.
- DST = 32 synthetic players; ESPN kickers `PK`→`K` normalized at scrape; K scoring FG 0-49=3 / 50+=5 / XP=1; DST points-allowed brackets per NFL.com defaults.
- `sqlite3.Row`: bracket access only — `.get()` doesn't exist.
- **ESPN 403s custom User-Agents** (since 2026-08-20). `roster_scraper`/`schedule_scraper` must send the default `python-requests/x.y.z` — a `Mozilla/…` or app-branded UA gets every team rejected. Guarded by `tests/test_espn_user_agent.py`. (PFR still *needs* a browser UA — don't touch `pfr_scraper`.)
- **`player_season_stats` is built from weekly rows**, not `nfl_data_py` — its seasonal feed 404s for 2025+ exactly like the weekly one. `aggregate_offense_season_stats()` + `aggregate_kicker_dst_season_stats()` in `player_weekly_importer.py`. Draft rankings and leaderboards read this table, so a missing season silently degrades both.
- `LAST_COMPLETED_SEASON` ≠ `CURRENT_SEASON - 1` in the offseason — see `lastCompletedSeason()` in `frontend/src/config.ts`.
- **ADP**: `python scripts/import_adp.py --season <yr>` fetches live consensus ADP (Fantasy Football Calculator, public JSON, no key); `--file` still takes a CSV. FFC echoes `teams` but returns **the same pooled ADP for every league size** — league size enters through VBD, not ADP. Positions arrive as `PK`/`DEF` and are normalized to `K`/`DST`; defenses match by team abbr to the synthetic `DST-{abbr}` player, not by name.
- Frontend: ErrorBoundary wraps routes; all pages lazy; team theming via `teamColors.ts` + CSS vars; Recharts for charts; no state library — localStorage hooks (`useLeagueSettings`, `myRoster`, draft board) are the persistence layer.
- Frontend tests: vitest **must run from `frontend/`** (setup + jsdom config), localStorage is polyfilled in `src/test/setup.ts`.

## Database tables (beyond the obvious)

`teams` · `games` · `game_factors` · `team_season_stats` · `team_advanced_stats` (PBP aggregates 2010+) · `prediction_history` (self-grading, `game_id`-linked) · `game_odds` · `injury_reports` · `game_weather` · `players` (incl. synthetic DST) · `roster_entries` (per season; 2026 loaded) · `player_season_stats` (2018+ offense/K/DST, aggregated from weekly) · `player_weekly_stats` (2018+, offense + kicker FG buckets + `dst_*` columns) · `fantasy_projections` (cache) · `draft_rankings` (last-request cache) · `player_adp` · `fantasy_leagues`/`user_rosters` · `matchup_cache` · `scrape_progress` (resumable scraping) · `scrape_log` (cron run outcomes)

## Data operations cheat sheet

```bash
# Pre-draft ritual (July–Sept, weekly)
python scripts/import_rosters.py --season 2026 --skip-stats
python scripts/import_adp.py --file <FantasyPros.csv> --season 2026

# Weekly stats (offense + K + DST, nflverse) — cron does this in season
python scripts/import_player_weekly.py --start 2025 --end 2025

# Models (manual by design — never in cron)
python scripts/train_model.py && python scripts/train_player_models.py

# Enrichment (needs ODDS_API_KEY; conditions are keyless)
python scripts/fetch_odds.py && python scripts/fetch_conditions.py

# New season bootstrap (each September)
python scripts/import_schedule.py
```

## History

The 2026 waves (core platform → rosters → fantasy module → security/modularization → Wave-5 hardening → ML retrain → matchup engine → fantasy upgrade wave → game-detail/retrodiction) are all merged to `main`. Details live in git history and `~/.claude/plans/` (`immutable-munching-elephant`, `nfl-next-steps`, `swift-growing-wombat`). Don't re-audit solved problems: temporal leakage, schema drift, N+1s, cron failure-masking, and the numpy<2 pin are **fixed and test-guarded**.

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)
