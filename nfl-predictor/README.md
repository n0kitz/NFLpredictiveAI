# NFL Predictor

**A self-hosted NFL decision engine: game predictions with honest, self-graded accuracy — and a full fantasy-football platform built to win your league.**

36 seasons of data (1990–2025, 9,400+ games), a leak-free prediction engine, per-player fantasy projections for every NFL.com roster position, a VBD draft war room, and a MILP lineup optimizer — wrapped in a dark-mode React UI and a Dockerized, cron-refreshed backend you run yourself.

> 📖 **Start here:** [`GUIDEBOOK.md`](GUIDEBOOK.md) — what this project is, its definition of done, roadmap, and operating runbook.

---

## Highlights

### Game prediction — honest by construction
- **Two engines**: a 7-factor weighted model (67.2% out-of-sample) and a 34-feature GradientBoosting ML model with SHAP explanations (`?model=ml`)
- **No leakage**: Vegas lines, injuries, and weather are shown *next to* predictions, never fed *into* them — so beating the market means something
- **Self-grading**: every prediction auto-saves and grades itself when the game finishes; every played game has a **retrodiction** page (what the model would have said — HIT or MISS, in public)
- **Value picks**: a model-vs-Vegas ledger surfaces where they disagree

### Fantasy football — the league-winning stack
- **Draft war room** (`/draft`): live snake-draft board for 8–20 team leagues — best-available by VBD, positional-need weighting, tier-break alarms, survives page refreshes
- **Rankings that adapt to *your* league**: standard / half-PPR / PPR scoring and league size change the replacement levels, tiers, and the whole board; real ADP (live from Fantasy Football Calculator's public API, or a CSV) exposes value vs. market
- **Every position**: QB/RB/WR/TE via per-position ML models (16 features), K and DST from real weekly data (FG distance buckets, points-allowed brackets)
- **My Team advisor**: give it your roster once and it returns the best legal lineup, the specific swaps to reach it with reasons, and bye-week collision + fantasy-playoff (weeks 15-17) strength-of-schedule warnings — all before it hits the in-season loop below
- **In-season loop**: weekly projections with A–F matchup grades → start/sit (N-way, ranked in your league's scoring) → waiver wire (your roster excluded) → trade analyzer with ROS values → **MILP lineup optimizer** (season-long + DraftKings/FanDuel salary modes)
- **Experimental**: read-only fantasy.nfl.com league sync (settings + rosters)

### Platform
- FastAPI + SQLite backend (51 endpoints across 7 domain routers, Swagger at `/docs`), React 19 + TypeScript + Tailwind v4 frontend (14 routes)
- Docker Compose: nginx frontend → internal API + weekly cron container (Wed 06:00 UTC full data refresh)
- GitHub Actions CI: lint + 573 backend / 144 frontend tests on every push; GHCR images on `v*` tags
- Observability: structured JSON logs, `X-Request-ID`, `GET /api/metrics`

---

## Quick start

### Prerequisites
Python 3.12, Node 20+, and a **clean venv** (requirements pin `numpy<2`; an anaconda base with numpy 2.x will break the ML stack).

### Development
```bash
cd nfl-predictor
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ENV=dev python run_api.py                 # API → http://localhost:8000

cd frontend
npm install && npm run dev                # UI → http://localhost:5173 (proxies /api)
```
The repo ships with `data/nfl.db` (all seasons loaded) — no scraping needed to start.

### Production (Docker)
```bash
cd nfl-predictor
export ODDS_API_KEY=<optional-the-odds-api-key>
docker compose up --build -d              # frontend :3000 (nginx) → api internal, cron scheduled
```

### Tests
```bash
python -m pytest -q                       # backend (573)
cd frontend && npm test && npm run build  # frontend (144) + typecheck
```

---

## Data pipeline

| Source | What | How |
|--------|------|-----|
| Pro Football Reference | Games 1990–2025 | Rate-limited scraper + cloudscraper fallback; manual `--from-file` HTML import when Cloudflare blocks (see [`SCRAPING_GUIDE.md`](SCRAPING_GUIDE.md)) |
| nflverse (`stats_player_week`) | Per-player weekly stats 2018+ incl. kickers + defense | Direct parquet reads (the legacy nfl_data_py weekly feed died after 2024) |
| ESPN | Rosters (all 32 teams), injuries | Public APIs, no auth |
| Open-Meteo | Game weather + dome handling | No auth |
| The Odds API | Vegas spreads / totals (display-only) | `ODDS_API_KEY` env var, optional |
| Fantasy Football Calculator | Real ADP for draft value | `scripts/import_adp.py --season <yr>` (public JSON, no key); `--file <csv>` also accepted |

The Wednesday cron (`scripts/weekly_scrape.py`) refreshes all of it and regenerates projections; model retraining is deliberately manual (`scripts/train_model.py`, `scripts/train_player_models.py`).

---

## Prediction methodology (game model)

Weighted engine: **25%** recency-weighted record · **20%** off/def strength vs league · **15%** last-5 form · **15%** strength of schedule · **15%** home/away splits · **10%** head-to-head — plus team-specific dynamic home-field advantage (0–10%) and a bye-week rest bonus. Confidence tiers by data depth. The ML model adds EPA, advanced team stats, and QB form on top; `load_model()` refuses any artifact whose feature list drifted from the builder.

Fantasy projections blend usage, efficiency, opponent DvP, pace, and PROE; draft value = projected points **above replacement at your league size**, with two-season blending and small-sample shrinkage.

---

## Project structure (short form)

```
nfl-predictor/
├── src/
│   ├── api/            # FastAPI: thin app.py + 7 domain routers + schemas
│   ├── prediction/     # engines, ML, features, SHAP, fantasy scorer, league settings,
│   │                   # matchup engine, lineup optimizer, backtester
│   ├── scraper/        # PFR, nflverse weekly, ESPN rosters/injuries, weather, odds,
│   │                   # DST + ADP importers, retrying HTTP helper
│   └── database/       # SQLite schema + migrations + CRUD
├── frontend/src/       # React app: pages/, pages/fantasy/, api/, components/, theme/
├── scripts/            # cron, imports, training, backtest
├── tests/              # 573 pytest across 39 files
└── data/nfl.db         # SQLite — ships loaded
```

Full structure, endpoint list, and conventions: [`../CLAUDE.md`](../CLAUDE.md). Vision and roadmap: [`GUIDEBOOK.md`](GUIDEBOOK.md).

---

## License

MIT
