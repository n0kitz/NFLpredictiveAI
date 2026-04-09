# NFL Predictor — Project Plan & Next Steps

## Current State (as of 2026-04)

**What's done:**
- Backend API with 15+ endpoints (FastAPI + SQLite)
- Prediction engine with 5 weighted factors (record, strength, form, splits, H2H)
- PFR scraper with 1990-2024 data loaded (9,170+ games)
- React frontend: Dashboard, Predict, Teams, TeamDetail pages
- Team profile endpoint with all-time + last season stats
- Docker setup (api + frontend + cron)
- Manual HTML import (`--from-file`) for when PFR blocks requests
- Basic test suite (14 tests)

**What's missing:**
- 2025 season data (PFR blocking — needs manual HTML download)
- Prediction accuracy validation
- Comprehensive tests
- Frontend error boundaries
- Factor system not wired into predictions from the UI

---

## Phase 1: Data & Accuracy (You + Claude)

### You (manual tasks):
- [ ] Download 2025 season HTML from PFR in your browser (see SCRAPING_GUIDE.md)
- [ ] Import it: `python -m src.cli.main --from-file ~/Downloads/games.htm --start 2025`
- [ ] Verify in browser: check TeamDetail for a 2025 team, confirm stats look right

### Claude (code tasks):
- [ ] Build a backtesting system that replays 2024 games and measures prediction accuracy
- [ ] Add accuracy stats to the Dashboard (e.g., "72% correct on 2024 season")
- [ ] Tune prediction weights if backtesting reveals better configurations
- [ ] Add point spread predictions (not just win probability)

---

## Phase 2: Test Coverage (Claude)

- [ ] API endpoint tests (pytest + FastAPI TestClient)
  - All team endpoints, prediction, H2H, factors, profile
  - Error cases (404s, invalid input)
- [ ] Prediction engine unit tests
  - Known matchups with expected probability ranges
  - Edge cases (same team, defunct teams)
- [ ] Scraper tests (mock HTML fixtures)
  - Parsing a known HTML page produces correct game count
  - `--from-file` integration test
- [ ] Frontend tests (Vitest)
  - Component rendering
  - API hook behavior with mocked responses

---

## Phase 3: Frontend Polish (Claude)

- [ ] Error boundaries — catch and display API failures gracefully per component
- [ ] Skeleton loading states (replace spinners with content-shaped placeholders)
- [ ] Season selector on TeamDetail (browse any historical season)
- [ ] Game factors UI on Predict page (add/remove factors before running prediction)
- [ ] Mobile responsive pass (currently desktop-first, needs touch-friendly controls)
- [ ] Team logos/images (if a free source is available)
- [ ] Animate probability bars and stat transitions

---

## Phase 4: Prediction Engine Improvements (Claude)

- [ ] Strength of schedule factor (who did they beat?)
- [ ] Injuries/roster changes integration (manual factor input or external API)
- [ ] Playoff-specific adjustments (home field means more, experience matters)
- [ ] Conference/division rivalry weighting
- [ ] Rest days advantage (Thursday/Monday games, bye weeks)
- [ ] Historical trend detection (teams that start slow but finish strong)

---

## Phase 5: Production Hardening (Claude + You)

### Claude:
- [ ] Add health check endpoints to docker-compose
- [ ] API rate limiting middleware
- [ ] Request logging + structured JSON logs
- [ ] Database backup script (daily SQLite copy)
- [ ] CI pipeline (GitHub Actions: lint, test, build)

### You:
- [ ] Set up hosting (VPS, Fly.io, Railway, etc.)
- [ ] Configure domain + SSL
- [ ] Set up monitoring/alerting (Uptime Kuma, Grafana, etc.)

---

## Phase 6: Stretch Goals

- [ ] Live game tracking during NFL season (real-time score updates)
- [ ] User accounts + saved predictions
- [ ] Prediction leaderboard (track accuracy over time)
- [ ] Slack/Discord bot for predictions
- [ ] Export predictions to CSV/PDF
- [ ] Multi-model comparison (add ML-based predictor alongside the current weighted model)

---

## Priority Order

Start with **Phase 1** (data + accuracy) — this is the highest-value work because
the whole app is only as good as its predictions. Then **Phase 2** (tests) to lock
in correctness before adding features. **Phase 3** (frontend) and **Phase 4** (engine)
can run in parallel after that.
