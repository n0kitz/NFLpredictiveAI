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
| API | FastAPI + Uvicorn, `src/api/app.py` (~40 lines), 5 routers in `src/api/routers/` |
| DB | SQLite + WAL, `data/nfl.db`, `src/database/db.py`, schema in `schema.sql` |
| ML | GradientBoostingClassifier, **34 features** (not 35 — docstring stale), trained 2013-2022 |
| Frontend | React 19 + TypeScript + Tailwind v4, `frontend/src/` |
| Tests | pytest, 183 tests across 9 files, `tests/` |
| Infra | Docker Compose: api + frontend + cron |

## Critical Gotchas (from 2026-05 audit)

- **`sqlite3.Row`**: bracket access `r["col"]` only — `.get()` not supported
- **Feature count**: `feature_builder.py` FEATURE_NAMES has **34** entries, not 35; docstring stale
- **`explainer.py` FEATURE_LABELS**: stale — references old names (`home_qb_epa_per_play`) not matching current feature names (`home_starter_qb_epa_l4`) — causes silent SHAP label mismatches
- **`_fatal_error` in `weekly_scrape.py`**: never actually set — always reports success regardless of step failures
- **`player_ml_model.py`**: uses `KFold` (temporal leakage) — should be `TimeSeriesSplit`
- **`db.py` schema**: ✅ FIXED 2026-06-24 — `schema.sql` is now the single source; `connection` init runs `executescript(schema.sql)` + `run_migrations`. Inline duplicate deleted. Add new tables to `schema.sql`; add ALTERs to `MIGRATIONS` list in `db.py`.
- **`models.py`**: only has dataclasses for `Team, Game, GameFactor, TeamSeasonStats, Prediction` — all other entities (Player, RosterEntry, InjuryReport, etc.) are raw `sqlite3.Row` dicts
- **No retry on scrapers**: transient HTTP failures cause silent data gaps
- **Power rankings endpoint**: ~256 DB queries per request (N+1 pattern) — `src/api/routers/fantasy.py` `_compute()`
- **`datetime.utcnow()`**: deprecated in Python 3.12 — used in `db.py` (3x), `injury_scraper.py`, `odds_scraper.py`
- **Port 8000**: currently exposed directly in `docker-compose.yml` — should route through nginx only
- **Hardcoded years**: `2024`/`2025` in 6+ frontend files — will go stale

## Architecture Conventions

- CLI: singleton `Database()`; API: per-request via `FastAPI Depends → get_db()`
- Prediction weights: 25% record, 20% strength, 15% form, 15% SOS, 15% splits, 10% H2H
- Vegas/injuries/weather: display-only enrichment, NEVER prediction inputs
- Ensemble blend (when `?model=ensemble`): 60% weighted-sum + 40% ML
- `calculate_team_metrics()`: TTL-cached 1h, keyed `(team_id, season)`, bypassed when `cutoff_date` given
- All `Query(ge=1, le=N)` bounds on limit params; `Field(max_length=)` on list fields
- `sqlite3.Row` everywhere in DB layer — no ORM

## Active Improvement Plan (Wave 5, started 2026-05)

Plan file: `/Users/normenkitzmann/.claude/plans/immutable-munching-elephant.md`

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Config centralization + quick security wins | ✅ Done 2026-06-24 — `src/config.py`; cron `_fatal_error` fixed; `utcnow` removed; port 8000 unpublished; nginx CSP |
| 2 | DB layer hardening (schema dedup, transactions, N+1) | ✅ Done 2026-06-24 — schema.sql single source (fixes fresh-DB bug), power-rankings N+1 256→4, 5 dataclasses, f-string SQL whitelisted |
| 3 | ML pipeline correctness (TimeSeriesSplit, versioning, SHAP) | Pending |
| 4 | Scraper resilience + cron safety | Pending |
| 5 | Frontend quality + component library | Pending |
| 6 | Performance + observability | Pending |
| 7 | Documentation + CI/CD | Pending |

Check plan file for granular sub-tasks. Update Status as phases complete.

## Test Coverage Notes

- 183 tests, 9 files — all pass when `data/nfl.db` present
- Tests with `pytestmark = pytest.mark.skipif(not DEFAULT_DB_PATH.exists(), ...)` skip silently without DB
- No frontend tests at all (zero vitest/jest setup)
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
| Weekly cron | `scripts/weekly_scrape.py` |
| Frontend API calls | `frontend/src/api/client.ts` + `types.ts` |
| React hooks | `frontend/src/hooks/useApi.ts` |
