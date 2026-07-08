# NFL Predictor — Guidebook

> **The canonical answer to four questions: what is this project, what does "as good as it can possibly be" look like, how far along is it, and what do I do next?**
> Last updated: 2026-07-08 (calibration shipped; suite-runtime issue re-measured and resolved) · Supersedes `PROJECT_PLAN.md` · Dev setup: `README.md` · Data scraping: `SCRAPING_GUIDE.md` · Agent conventions: `../CLAUDE.md`

---

## 1. Mission

**Own the best NFL decision engine in your league — end to end.**

Every football decision you make — a draft pick, a start/sit call, a waiver claim, a trade, a "who wins Sunday?" argument — should be made with better information than anyone you're competing against, produced by software you built, understand, and control. No subscriptions, no black boxes, no rented opinions.

Two concrete scoreboards tell you whether the mission is being met:

1. **Win the fantasy.nfl.com league.** The fantasy stack (draft board, projections, waivers, trades, optimizer) exists to convert modeling into league championships.
2. **Beat the naive baselines, honestly.** The game model must outperform "always pick the home team" (~57%) and "always pick the favorite" — with its accuracy tracked, published by the app itself, and never inflated by leaking Vegas into the inputs.

---

## 2. The best-case picture

What this project looks like fully realized — the standard every piece of work should be measured against:

**🏆 The Fantasy Edge.** On draft night you open `/draft`, and while everyone else squints at a magazine cheat sheet, you have a live VBD board tuned to *your* league's exact size and scoring, tier-break alarms, positional-need weighting, and market-vs-model value gaps from real ADP. In season, Wednesday morning the system has already refreshed itself: projections regenerated, waiver targets ranked by value-over-replacement with your own roster excluded, matchup grades A–F on every player, and the MILP optimizer producing your best legal lineup in one click. Trades get an objective verdict before emotions do. **The league doesn't know what hit it.**

**📊 The Honest Model.** The prediction engine is a *trustworthy instrument*, not a hype machine. Every prediction auto-saves and self-grades when the game finishes. Every played game has a retrodiction page showing what the model *would* have said — hit or miss, in public. Vegas lines, injuries, and weather appear alongside predictions as context but are never smuggled into the game-model inputs, so when the model beats the market on a pick, that edge is real. Accuracy, calibration, and the model-vs-Vegas ledger are first-class UI, not buried logs.

**⚙️ The Self-Running Service.** The whole thing lives on a small host you control: Docker Compose, nginx in front, cron container firing every Wednesday at 06:00 UTC — games, rosters, weekly stats, odds, injuries, weather, projections, all refreshed with zero touches. CI gates every change; tagged releases publish images to GHCR; `/api/metrics` and JSON logs tell you it's healthy. Your league mates use it from a URL on their phones. When the season ends, one retrain command folds the new season into the models and the cycle starts again.

Three pillars. Each has a definition of done below. **The project is "done" when all three checklists are fully checked — and "alive" as long as the operating calendar (§4) keeps running.**

---

## 3. Definition of Done

Legend: ✅ done · 🟡 partial / needs action · ⬜ open

### Pillar 1 — Fantasy Edge

| # | Criterion | Status |
|---|-----------|--------|
| 1.1 | Draft rankings driven by **VBD over replacement**, parametric in league size (8–20) and scoring (standard / half-PPR / PPR) | ✅ |
| 1.2 | **All NFL.com roster positions** projectable: QB/RB/WR/TE ✅ ML, K/DST ✅ heuristic from real weekly data | ✅ |
| 1.3 | **Live draft board** (`/draft`): snake tracking, best-available by need-boosted VBD, tier-break alerts, refresh-proof | ✅ |
| 1.4 | **Real ADP** loaded so the board shows value-vs-market (`scripts/import_adp.py`) | 🟡 code done — `player_adp` is empty; import a FantasyPros CSV before draft night |
| 1.5 | League scoring **verified against the actual fantasy.nfl.com settings page** (esp. K/DST rules) | ⬜ user action, ~10 min, do before draft |
| 1.6 | In-season loop: projections → start/sit → waiver (own roster excluded, VBD-ranked) → trade analyzer → optimizer, all league-settings-aware | ✅ |
| 1.7 | 2026 rosters current on draft night (weekly `import_rosters.py --season 2026 --skip-stats` through August; final run day before draft) | 🟡 imported 2026-07-02 (2,957 entries); repeat weekly |
| 1.8 | **The league is won.** (The only criterion that matters; graded in January.) | ⬜ |

### Pillar 2 — Honest Model

| # | Criterion | Status |
|---|-----------|--------|
| 2.1 | Game model beats naive baselines out-of-sample (weighted-sum 67.2%, ML 66.8% vs ~57% home-pick) | ✅ |
| 2.2 | **No input leakage**: Vegas/injuries/weather display-only for game predictions (player projections may use Vegas totals — documented, deliberate) | ✅ |
| 2.3 | Predictions auto-save, self-grade on completion, and link to their game (`/history` → `/games/:id`) | ✅ |
| 2.4 | Every played game has a **retrodiction** (cutoff-aware HIT/MISS, `/api/games/{id}/retrodiction`) | ✅ |
| 2.5 | Model-vs-Vegas ledger (`/api/picks/value` + history) surfaces where the model disagrees with the market | ✅ code — empty until odds flow (see 3.3) |
| 2.6 | **Calibration**: predicted 60% wins ≈ 60% of the time, measured and displayed (reliability curve or bucketed table) | ✅ bucketed reliability panel on Dashboard (from `/api/accuracy` backtest calibration) |
| 2.7 | Projection floors/ceilings from actual distributions (Monte-Carlo or quantile models) instead of ±25/35% placeholders | ⬜ |
| 2.8 | Annual retrain ritual after the Super Bowl folds the finished season into game + player models | ⬜ recurring (first: Feb 2027) |

### Pillar 3 — Self-Running Service

| # | Criterion | Status |
|---|-----------|--------|
| 3.1 | **Deployed on an always-on host** (VPS/Fly/Render), frontend behind nginx, API internal, HTTPS | ⬜ **the** gap between "codebase" and "product" |
| 3.2 | Cron container verified firing Wednesdays on the host; a missed run is visible (`scrape_log`, `/api/metrics`) | ⬜ blocked by 3.1 |
| 3.3 | Enrichment live: `ODDS_API_KEY` set + `fetch_odds.py` / `fetch_conditions.py` populating (today: `game_odds` = 0, `injury_reports` = 0) | ⬜ key + two commands |
| 3.4 | A `v*` tag published → GHCR images built by CI (pipeline ✅, first tag ⬜) | 🟡 |
| 3.5 | CI green on every push: ruff + pytest / eslint + tsc + vitest; Docker job on tags | ✅ |
| 3.6 | Full test suite green: **337 backend + 64 frontend** | ✅ |
| 3.7 | Observability: JSON logs, `X-Request-ID`, `/api/metrics` | ✅ |
| 3.8 | Data pipeline survives upstream drift (nflverse URL scheme change of 2025 already absorbed; retry/backoff on all scrapers) | ✅ |

**Score today: Pillar 1 ~85% · Pillar 2 ~80% · Pillar 3 ~55%.**
The software is nearly done; the *service* and the *pre-draft data chores* are what remain. Nothing left is hard — it's a deploy, an API key, a CSV, and a ten-minute settings check.

---

## 4. The operating calendar

This project is calendar-driven. "Done" is not a state, it's a rhythm:

| When | What | Tooling |
|------|------|---------|
| **July (now)** | Import real ADP · verify league scoring · weekly 2026 roster refresh · deploy (§5 Now) | `import_adp.py`, `import_rosters.py` |
| **Aug/Sep — draft night** | Final roster refresh the day before · run the draft from `/draft` | Draft board |
| **In season, Wed AM** | Cron refreshes everything; you check waivers + set lineup | `weekly_scrape.py` (auto) |
| **In season, Sunday** | Watch the model's picks self-grade; check `/history` accuracy | auto |
| **Monthly (optional)** | Refresh models on new weeks of data | `train_player_models.py` |
| **February** | Season post-mortem: accuracy report, calibration check, full retrain, GUIDEBOOK update | `run_backtest.py`, `train_model.py` |

---

## 5. Roadmap

### Now — before the draft (highest leverage, days not weeks)
1. **Deploy** (3.1/3.2): `docker compose up -d` on a small host; confirm cron fires; set `ODDS_API_KEY` + `CORS_ORIGINS`. Tag `v1.0.0` → images publish.
2. **Load ADP** (1.4): download FantasyPros 2026 ADP CSV → `python scripts/import_adp.py --file <csv> --season 2026`.
3. **Verify league scoring** (1.5): screenshot the league's scoring settings; diff against `kicker_fantasy_points` / `dst_importer.py` defaults; encode any deltas.
4. **Weekly roster refresh** (1.7) until draft.

### Next — in-season quality
- **Real floors/ceilings** (2.7): quantile regression or Monte-Carlo from weekly variance instead of fixed ±%.
- **Mobile pass** on the fantasy hub + draft board (draft night happens on couches, not desks).
- Flip `black`/`mypy` from non-blocking to blocking once the backlog (62 files / 55 errors) is cleared.

### Later — v2 ambitions (only if the itch strikes)
- **Season simulator**: Monte-Carlo the remaining schedule → playoff odds per team, magic numbers on the Season page.
- **Multi-league / multi-user**: auth + per-user rosters; the NFL.com sync (`NFL_FANTASY_COOKIE`, experimental) graduates from cookie hack to real onboarding.
- **Notification layer**: Discord/Telegram bot — Wednesday waiver digest, injury-news pings for rostered players, "you're on the clock" relays.
- **LLM analyst**: a weekly natural-language brief ("bench X, stream Y against Z's bottom-5 pass D") generated from the data the system already has.
- **Live scoring**: in-game win-probability updates on game day.

---

## 6. Runbook

> **Always** `cd nfl-predictor && source .venv/bin/activate` first — anaconda base has numpy 2.x and breaks the player-ML stack.

### Steady state (weekly, automated by cron)
`weekly_scrape.py`: games + enrich predictions → rosters → weekly player stats (offense/K/DST via nflverse) → season aggregates → odds (if key) → conditions → stale-projection purge → regenerate projections. Singleton-locked (`fcntl`), failures accumulate to `scrape_log` + exit 1.

### Manual rituals
```bash
# Pre-draft (July–Sep)
python scripts/import_rosters.py --season 2026 --skip-stats   # weekly roster churn
python scripts/import_adp.py --file <FantasyPros.csv> --season 2026

# Model refresh (monthly in-season; mandatory each February)
python scripts/train_model.py              # game + spread (34-feat)
python scripts/train_player_models.py      # QB/RB/WR/TE (16-feat)

# Enrichment (once ODDS_API_KEY is set)
python scripts/fetch_odds.py
python scripts/fetch_conditions.py

# Backtest / accuracy report
python scripts/run_backtest.py

# New season bootstrap (each September)
python scripts/import_schedule.py          # load the new season's schedule/games
```

### Verification (before any "it works" claim)
```bash
python -m pytest -q                         # 337 backend (~16 s in a clean .venv)
cd frontend && npm run build && npm test    # tsc + 64 vitest
```

### Gotchas (the ones that actually bite)
- **nfl_data_py `import_weekly_data` is dead for 2025+** — nflverse retired that release. Weekly data comes from `fetch_stats_player_week()` (`src/scraper/player_weekly_importer.py`). Don't "fix" imports back to nfl_data_py.
- **Projections look heuristic/zeroed** → stale cached rows from a wrong-env server. `DELETE FROM fantasy_projections WHERE season=? AND week=?`, regenerate from the `.venv`. (Cron now purges before regenerating.)
- **Projections empty for a season** → that season has no `roster_entries`.
- **`sqlite3.Row`**: bracket access only, `.get()` doesn't exist.
- **DST are synthetic players** (`espn_id='DST-{abbr}'`); ESPN kickers arrive as `PK` and are normalized to `K`.
- **Schema changes** go to `schema.sql` **and** the `MIGRATIONS` list in `db.py` (currently at v25).

---

## 7. State snapshot — 2026-07-07 (re-verified)

- **Data**: 9,455 games (1990–2025) · player weekly stats 2018–2025 incl. K + DST · 2,957 roster entries for 2026 · `game_odds` 0 · `injury_reports` 0 · `player_adp` 0 (the three empties are §5-Now items).
- **Models**: game GradientBoosting 34-feat OOS 0.668 (weighted-sum 0.672 remains default; ML opt-in via `?model=ml`) · player models 16-feat, MAE QB 6.48 / RB 5.66 / WR 5.50 / TE 4.26 · K/DST heuristic.
- **Tests**: 337 backend + 64 frontend, all green.
- **Git/CI**: main in sync with origin · CI green · no release tag yet.
- **Deployment**: none — local/Docker only. This is the top of the list.
