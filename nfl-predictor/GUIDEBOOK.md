# NFL Predictor — Guidebook

> Single source of truth for **what this project is, whether it's "done", how to operate it, and how to get value out of it.**
> Last updated: 2026-06-29. Supersedes the (now stale) `PROJECT_PLAN.md` for planning purposes.
> For dev setup see `README.md`; for data scraping see `SCRAPING_GUIDE.md`.

---

## 1. What this project is

A full-stack NFL **game-prediction + fantasy-football** system:

- **Backend** — Python 3.12 / FastAPI / SQLite, 35 years of games (1990–2025), a 7-factor weighted prediction engine, a retrained ML game model (GradientBoosting, 34 features, ~66% OOS) and per-position fantasy ML models (16 features), an advanced matchup engine (A–F grades), and a MILP lineup optimizer.
- **Frontend** — React 19 / TypeScript / Tailwind v4: dashboards, team pages, prediction UI, a 7-tab fantasy hub (projections, waiver, draft, trades, power rankings, optimizer).
- **Infra** — Docker Compose (api + frontend + cron), a weekly cron, GitHub Actions CI, JSON logging + `/api/metrics`.

It is **display-only honest**: Vegas odds, injuries, and weather are shown but **never fed into predictions**.

---

## 2. Is it finished? — Honest verdict

**As an engineering artifact: ~95% done.** Architecture is clean and modular, 258 backend + 18 frontend tests pass, CI is green, ML is retrained and verified live, observability and Docker are in place. There is very little "code work" left.

**As an operational product: not finished.** It is a polished engine that is **not deployed and running on fresh data**. The blockers are operational, not architectural:

| Gap | Reality today | Impact |
|-----|---------------|--------|
| **Stale player data** | `player_weekly_stats` ends at **2024**; 2025 games exist (with scores) but no 2025 player weekly rows | Fantasy projections for the latest season are degenerate (only matchup features fire); player models trained through 2024 |
| **Not deployed** | Runs locally / in Docker on this machine only; the weekly cron isn't scheduled on any host | No live, always-on product; data never refreshes on its own |
| **Empty enrichment** | `game_odds` = 0 rows, `injury_reports` = 0 rows (no `ODDS_API_KEY` set, conditions fetch never run) | Vegas-context and injury/weather panels are empty |
| **Unpushed work** | 4 commits sit local on `main` | Collaborators / deploys don't see the latest |

**Bottom line:** the *software* is essentially complete; the *service* is not. To call the project "finished" you need to **deploy it and keep its data current** — see §3.

---

## 3. What to do to finish it (operational checklist)

> Always work from the clean venv: `cd nfl-predictor && source .venv/bin/activate` (anaconda base has numpy 2.x and breaks player-ML).

### 3a. Bring data current (do first — unblocks everything)
```bash
python scripts/import_schedule.py            # ensure latest season schedule/games
python scripts/import_rosters.py             # ESPN rosters + player_season_stats
python scripts/import_player_weekly.py       # weekly player stats (the stale piece → import 2025)
python scripts/import_advanced_stats.py      # team advanced stats + QB EPA
python scripts/train_model.py                # retrain game + spread model (34-feat)
python scripts/train_player_models.py        # retrain per-position fantasy models (16-feat)
```
Then regenerate any cached projections for the target season/week (the endpoint serves cached `fantasy_projections` rows first):
```sql
DELETE FROM fantasy_projections WHERE season=<S> AND week=<W>;  -- then hit /api/fantasy/projections to regenerate
```

### 3b. Wire up enrichment (optional but completes the UI)
```bash
export ODDS_API_KEY=<key>                    # The Odds API (free tier OK)
python scripts/fetch_odds.py
python scripts/fetch_conditions.py           # injuries (ESPN) + weather (Open-Meteo), no key needed
```

### 3c. Deploy + schedule (the real "finish" step)
- Stand up `docker compose up -d` on a small host (VPS / Fly.io / Render). Frontend behind nginx, API internal, cron container running.
- Confirm the **cron** (`weekly_scrape.py`, Wednesdays 06:00 UTC) actually fires on the host — it refreshes games, rosters, weekly stats, odds/conditions, and regenerates projections. (Player-model **retrain is intentionally manual** — run §3a's last two commands when you want fresher models.)
- Set `ODDS_API_KEY` and `CORS_ORIGINS` in the host env.

### 3d. Ship the code
```bash
git push origin main                         # 4 commits waiting
git tag v1.0.0 && git push origin v1.0.0     # triggers the GHCR Docker image build/publish CI job
```

**Definition of done:** a public/owned URL where predictions and fantasy tools show **current-week** data, refreshed automatically each Wednesday, with images published on tag.

---

## 4. What to do next to utilize it

Once it's live and current, the value shows up in-season:

1. **Personal fantasy command center** — weekly projections, start/sit, waiver-wire targets, trade analyzer, and the **MILP lineup optimizer** (season-long + DraftKings/FanDuel salary modes). The **matchup engine** A–F grades tell you which players have soft/tough matchups at a glance.
2. **Game-prediction dashboard** — pick any matchup, get win probabilities with the factor breakdown and (display-only) Vegas context. Backtest accuracy is tracked, and predictions auto-save + self-grade once games complete.
3. **Vegas-edge finder** — `/api/picks/value` surfaces where the model disagrees with the market (display-only; a research/curiosity tool, not betting advice).
4. **Share it** — give a read-only URL to your fantasy league; the fantasy hub is genuinely useful to non-technical users.

### Highest-leverage enhancements (if you want to keep building)
- **Expose `opponent_team_id`** is done → now use it: turn on QB/bring-back **correlation stacks** in the optimizer UI and validate they improve DFS lineups.
- **Calibration + confidence intervals** on projections (Monte-Carlo floor/ceiling instead of the ±25/35% placeholders).
- **Mobile-responsive pass** on the fantasy hub (currently desktop-first).
- **Auth + multi-user rosters** if you ever want others to save their own lineups.
- **Tighten CI**: flip `black`/`mypy` from non-blocking to blocking after clearing the backlog (62 files / 55 type errors).

---

## 5. Operating runbook (steady state)

| Cadence | Action |
|---------|--------|
| **Automatic, weekly (Wed)** | Cron refreshes games, rosters, weekly stats, odds/conditions, regenerates projections |
| **Monthly (manual)** | `train_model.py` + `train_player_models.py` from the `.venv` to refresh models on new data |
| **Each new season** | Add the season HTML import if PFR blocks automated scraping (see `SCRAPING_GUIDE.md`); verify `roster_entries` populate for the new year (projections need a season with rosters) |
| **On any code change** | `python -m pytest -q` (258) + `cd frontend && npm run build && npm test` (18); commit per logical change |

### Common gotchas
- **Projections look heuristic/zeroed** → a stale or wrong-env server cached `heuristic` rows; `DELETE FROM fantasy_projections WHERE season=? AND week=?` and regenerate from the `.venv`.
- **Projections empty** → that season has no `roster_entries` (only the current roster season is populated).
- **Tests fail on player-ML** → you're on anaconda base (numpy 2.x); use the `.venv`.
- **`sqlite3.Row`** → bracket access `r["col"]`, never `.get()`.

---

## 6. Project state snapshot (2026-06-29)

- Tests: 258 backend + 18 frontend, all green in the clean `.venv`.
- ML: game model OOS 0.668 (weighted-sum 0.672 still the default); player models 16-feat, retrained, verified serving `model_source: ml`.
- CI: ruff + black/mypy (non-blocking) + pytest; eslint + build + vitest; Docker→GHCR on `v*` tags.
- Data: games through 2025 (complete); **player weekly stats only through 2024** (refresh needed); odds/injuries empty.
- Git: 4 commits unpushed on `main`.
