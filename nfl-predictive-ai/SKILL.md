---
name: nfl-predictive-ai
description: >
  NFL Game Prediction System project conventions, active improvement plan, and known gotchas.
  Auto-activates at session start for this project. Use when navigating architecture,
  reviewing code, planning changes, or debugging. Prevents re-discovering known traps.
  Trigger: any code work in this repo, or "what's the plan", "remind me", "project status".
---

# NFL Predictive AI — Project Conventions & Active State

## Stack Quick Reference

| Layer | Tech |
|-------|------|
| API | FastAPI + Uvicorn, `src/api/app.py` (~70 lines, CORS+observability middleware), 6 routers in `src/api/routers/` (teams, games, predictions, fantasy, matchup, misc) |
| DB | SQLite + WAL, `data/nfl.db`, `src/database/db.py`, schema in `schema.sql` |
| ML | GradientBoostingClassifier, **34 features** (docstrings corrected), trained 2013-2022; `load_model()` guards feature mismatch |
| Frontend | React 19 + TypeScript + Tailwind v4, `frontend/src/` |
| Tests | pytest, 258 backend tests across 13 files + 18 frontend (vitest), `tests/` & `frontend/src/**/*.test.*` |
| Infra | Docker Compose: api + frontend + cron |

## Critical Gotchas (from 2026-05 audit)

- **`sqlite3.Row`**: bracket access `r["col"]` only — `.get()` not supported
- **Feature count**: `feature_builder.py` FEATURE_NAMES has **34** entries, not 35; docstring stale
- **`explainer.py` FEATURE_LABELS**: ✅ FIXED 2026-06-24 — now derived from `FEATURE_NAMES` (`{name: pretty.get(name, ...) for name in FEATURE_NAMES}`), cannot drift. Guarded by `test_feature_labels_match_feature_names`.
- **`_fatal_error` in `weekly_scrape.py`**: never actually set — always reports success regardless of step failures
- **`player_ml_model.py`**: ✅ FIXED 2026-06-24 — now `TimeSeriesSplit` (was `KFold(shuffle=True)`). Training rows are chronologically ordered by `build_training_rows`. ✅ RETRAINED 2026-06-29 on the **16-feature** vector → `data/player_models/{QB,RB,WR,TE}_model.joblib` (meta records feature list).
- **Player feature vector**: ✅ 16 features as of 2026-06-29 (`player_features.py`; was 13). Phase-2 additions `opp_pace`, `opp_proe`, `opp_pos_dvp_6wk` lazy-import from `matchup_engine`. `test_player_ml.py` asserts `len(FEATURE_NAMES)==16`. (Distinct from the **34-feature game** vector in `feature_builder.py`.)
- **requirements / clean venv**: ✅ FIXED 2026-06-29 — `shap==0.46.0` (0.47+ forces numpy>=2, conflicting with the numpy<2 pin) + `httpx` added (starlette TestClient dep). A fresh `.venv` now installs and runs all 258 tests green; anaconda base numpy 2.x still fails player-ML tests, so always use the `.venv`.
- **`db.py` schema**: ✅ FIXED 2026-06-24 — `schema.sql` is now the single source; `connection` init runs `executescript(schema.sql)` + `run_migrations`. Inline duplicate deleted. Add new tables to `schema.sql`; add ALTERs to `MIGRATIONS` list in `db.py`.
- **`models.py`**: only has dataclasses for `Team, Game, GameFactor, TeamSeasonStats, Prediction` — all other entities (Player, RosterEntry, InjuryReport, etc.) are raw `sqlite3.Row` dicts
- **Scraper HTTP retry**: ✅ FIXED 2026-06-25 — use `src.scraper.http.get_with_retry(url, ..., session=optional)` for all new HTTP calls (backoff+jitter, retries 429/5xx/conn-errors, honours Retry-After). Don't call `requests.get` directly in scrapers.
- **Power rankings endpoint**: ✅ FIXED 2026-06-25 — bulk-loads games/adv-stats once (~256→~4 queries) in `src/api/routers/fantasy.py` `_compute()`.
- **`datetime.utcnow()`**: deprecated in Python 3.12 — used in `db.py` (3x), `injury_scraper.py`, `odds_scraper.py`
- **Port 8000**: currently exposed directly in `docker-compose.yml` — should route through nginx only
- **Hardcoded years**: ✅ FIXED 2026-06-25 — use `frontend/src/config.ts` (`CURRENT_SEASON`, `LAST_COMPLETED_SEASON`, `SEASON_RANGE_LABEL`, `recentSeasons(n)`, …). Don't hardcode years or `new Date().getFullYear()` (calendar ≠ NFL season).
- **Fantasy projections are cached**: `/api/fantasy/projections` reads persisted `fantasy_projections` rows first, only generating (and persisting) when empty. So `model_source`/points reflect **whatever server generated them** — a stale anaconda-base server (numpy 2.x, ML fails to load) bakes in `heuristic` rows that survive a restart. If projections look heuristic/zeroed: `DELETE FROM fantasy_projections WHERE season=? AND week=?` and regenerate from the `.venv`. Also: projections need a season with `roster_entries` (only **2025**); 2024 returns empty.
- **`opponent_team_id` on projections**: ✅ exposed 2026-06-29 — already stored in `fantasy_projections` + set by `fantasy_scorer`; flows `fp.*`→`FantasyProjectionEntry`→API→`types.ts`→`OptimizerTab` (correlation stacks). Don't reintroduce the `null` placeholder.

## Architecture Conventions

- CLI: singleton `Database()`; API: per-request via `FastAPI Depends → get_db()`
- Prediction weights: 25% record, 20% strength, 15% form, 15% SOS, 15% splits, 10% H2H
- Vegas/injuries/weather: display-only enrichment, NEVER prediction inputs
- Ensemble blend (when `?model=ensemble`): 60% weighted-sum + 40% ML
- `calculate_team_metrics()`: TTL-cached 1h, keyed `(team_id, season)`, bypassed when `cutoff_date` given
- All `Query(ge=1, le=N)` bounds on limit params; `Field(max_length=)` on list fields
- `sqlite3.Row` everywhere in DB layer — no ORM

## ▶️ NEXT STEPS — ALL DONE (2026-06-29 sess2)

**Plan file:** `/Users/normenkitzmann/.claude/plans/nfl-next-steps.md` (full detail). All 5 roadmap steps complete. ⚠️ **4 commits sit local on `main`, UNPUSHED** (`c09fdda`, `1c58cbc`, `a02c60b`, `89b00a5`) — `git push origin main` was blocked, needs explicit user OK.

- **Env first:** `cd nfl-predictor && source .venv/bin/activate` (never anaconda base — numpy 2.x). requirements is self-consistent (numpy<2, shap 0.46, httpx).
1. ✅ **Retrain verified live** — `/api/model/info` shows ML loaded (game OOS 0.668); player projections serve `model_source: ml`; matchup engine grades A–F. ⚠️ Gotcha: a stale anaconda-base `run_api.py` had cached **heuristic** rows in `fantasy_projections` (endpoint serves cache first). Fix: kill stale server, run from `.venv`, `DELETE FROM fantasy_projections WHERE season=? AND week=?`, regenerate. Projections need a season with roster data (only 2025 has roster_entries).
2. ✅ **`opponent_team_id` exposed on projections** (commit `c09fdda`) — was already stored/set by scorer; surfaced via `fp.*`→schema→API→`types.ts`→OptimizerTab.
3. ✅ **Cron retrain → MANUAL** (commit `1c58cbc`) — cron WAS retraining weekly; user chose manual, removed the block. Cron now only refreshes stats + regenerates projections. Retrain manually: `scripts/train_player_models.py`.
4. ✅ **CI hardening** (commit `89b00a5`) — `black`/`mypy` non-blocking on backend; `docker` job builds+pushes api/frontend/cron → GHCR on `v*` tags only. eslint already present.
5. ✅ **Frontend tests** (commit `a02c60b`) — 9→18 vitest: fantasy helper colours, MatchupGradePill, OptimizerTab (opponent_team_id pass-through).

**Nothing mandatory left.** Optional follow-ups: tighten black/mypy to blocking once backlog clean (black 62 files, mypy 55 errors); push a `v*` tag to publish images; more frontend coverage.

## Active Improvement Plan (Wave 5 — COMPLETE)

Plan file: `/Users/normenkitzmann/.claude/plans/immutable-munching-elephant.md` (all 7 phases ✅)

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Config centralization + quick security wins | ✅ Done 2026-06-24 — `src/config.py`; cron `_fatal_error` fixed; `utcnow` removed; port 8000 unpublished; nginx CSP |
| 2 | DB layer hardening (schema dedup, transactions, N+1) | ✅ Done 2026-06-24 — schema.sql single source (fixes fresh-DB bug), power-rankings N+1 256→4, 5 dataclasses, f-string SQL whitelisted |
| 3 | ML pipeline correctness (TimeSeriesSplit, versioning, SHAP) | ✅ Done — code 2026-06-24; **retrain done 2026-06-29** (game 34-feat OOS 66.3%; player models 16-feat in clean `.venv`); **verified live sess2** (`/api/model/info` ML loaded OOS 0.668, projections `model_source: ml`). requirements numpy<2 conflict fixed (shap 0.46 + httpx) |
| 4 | Scraper resilience + cron safety | ✅ Done 2026-06-25 — shared `get_with_retry` (backoff+jitter+Retry-After) on all scrapers; cron `fcntl` singleton lock; 6 retry tests |
| 5 | Frontend quality + component library | ✅ Done 2026-06-25 — vitest+RTL (9 tests), `src/config.ts` season config (de-hardcoded), FantasyPage 1213→67 lines (pages/fantasy/ modules) |
| 6 | Performance + observability | ✅ Done 2026-06-26 — `src/observability.py` (JSON logs + request-id/timing middleware + Metrics), cache hit/miss stats, `GET /api/metrics` |
| 7 | Documentation + CI/CD | ✅ Done 2026-06-26 — `.github/workflows/ci.yml` (ruff+pytest / eslint+build+vitest); README Testing/CI/Observability sections |

Check plan file for granular sub-tasks. Update Status as phases complete.

## Test Coverage Notes

- 258 backend tests, 14 files — **all pass** in a clean `.venv` (`pip install -r requirements.txt`: numpy<2, shap 0.46, httpx) with `data/nfl.db` present. Anaconda base (numpy 2.x) fails the player-ML tests.
- Tests with `pytestmark = pytest.mark.skipif(not DEFAULT_DB_PATH.exists(), ...)` skip silently without DB
- Frontend tests: ✅ vitest + RTL set up 2026-06-25 (`npm test` / `npm run test:watch`); config in `vitest.config.ts` (separate from vite.config). **18 tests** (config, DataBadge, fantasy helpers, MatchupGradePill, OptimizerTab) — expand coverage.
- `test_roster.py` inserts test data into real DB, never cleans up

## Key File Map

| Need | File |
|------|------|
| Add API endpoint | `src/api/routers/{domain}.py` + schema in `schemas.py` |
| DB query | `src/database/db.py` |
| Prediction logic | `src/prediction/engine.py` |
| Team metrics | `src/prediction/metrics.py` |
| Feature vector | `src/prediction/feature_builder.py` (34 features) |
| Fantasy scoring | `src/prediction/fantasy_scorer.py` |
| Matchup grades | `src/prediction/matchup_engine.py` (DvP/pace/PROE → A–F) |
| Lineup optimizer | `src/prediction/lineup_optimizer.py` (MILP/PuLP; `routers/matchup.py`) |
| Settings / env | `src/config.py` (backend), `frontend/src/config.ts` (seasons) |
| Logging / metrics | `src/observability.py` (`/api/metrics`) |
| Scraper HTTP | `src/scraper/http.py` (`get_with_retry`) |
| Weekly cron | `scripts/weekly_scrape.py` |
| Frontend API calls | `frontend/src/api/client.ts` + `types.ts` |
| React hooks | `frontend/src/hooks/useApi.ts` |
| CI | `.github/workflows/ci.yml` |
