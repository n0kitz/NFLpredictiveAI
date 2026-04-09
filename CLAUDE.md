# NFL Game Prediction System

## Project Overview
Full-stack NFL game prediction application. Python FastAPI backend with 35 years of historical data (1990-2025) from Pro Football Reference. React + TypeScript frontend with dark-mode UI, team colors, and dual all-time/last-season stats. Dockerized with automated weekly data updates.

## Tech Stack
- **Backend**: Python 3.12, FastAPI, Uvicorn, SQLite
- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS v4
- **Infrastructure**: Docker Compose (api + frontend + cron)
- **Scraping**: requests + BeautifulSoup4 (4s rate limit), cloudscraper fallback for 403s
- **Testing**: pytest

## Project Structure
```
nfl-predictor/
├── src/
│   ├── api/
│   │   ├── app.py             # FastAPI app, all route handlers
│   │   ├── schemas.py         # Pydantic request/response models
│   │   └── deps.py            # Dependency injection (DB per request)
│   ├── cli/main.py            # CLI interface (still works standalone)
│   ├── database/
│   │   ├── db.py              # SQLite connection, CRUD, per-request factory
│   │   ├── models.py          # Dataclasses: Team, Game, GameFactor, Prediction
│   │   └── schema.sql         # Schema: teams, games, game_factors, team_season_stats, prediction_history
│   ├── prediction/
│   │   ├── engine.py          # Core prediction (weighted probability calc + bye week rest)
│   │   ├── metrics.py         # TeamMetrics, exponential decay, strength/form, SOS, dynamic HFA, rest_days
│   │   ├── factors.py         # GameFactor adjustments (-5 to +5 impact)
│   │   └── backtester.py      # Replay historical games to measure accuracy
│   ├── scraper/
│   │   ├── pfr_scraper.py     # PFR scraper with resumable progress + --from-file
│   │   └── team_mappings.py   # 32 current + historical teams
│   └── utils/helpers.py
├── frontend/
│   ├── src/
│   │   ├── api/client.ts      # Typed fetch wrapper for all endpoints
│   │   ├── api/types.ts       # TypeScript types matching Pydantic schemas
│   │   ├── hooks/useApi.ts    # React hooks: useTeams, useTeamProfile, usePrediction, useH2H
│   │   ├── theme/teamColors.ts # All 32 team colors, gradient/tint helpers
│   │   ├── components/        # Layout, PredictionCard, TeamSelector, Spinner, TrendChart, FactorPanel
│   │   └── pages/             # Dashboard, Predict, Teams, TeamDetail, Compare, Season, History, Playoffs
│   ├── vite.config.ts         # Dev proxy /api → localhost:8000
│   └── package.json
├── tests/
│   ├── test_basic.py          # Team mappings, DB, metrics, helpers (14 tests)
│   ├── test_api.py            # All API endpoints via TestClient (23 tests)
│   ├── test_prediction.py     # Prediction engine, metrics, backtester (16 tests)
│   ├── test_scraper.py        # HTML parsing, team mapping resolution (11 tests)
│   └── fixtures/              # Sample PFR HTML for scraper tests
├── scripts/weekly_scrape.py   # Wednesday cron scrape script + prediction enrichment
├── data/nfl.db                # SQLite database (9170+ games)
├── docker-compose.yml         # api + frontend + cron containers
├── Dockerfile.api             # Python API server
├── Dockerfile.frontend        # Node build → nginx
├── Dockerfile.cron            # Weekly scraper cron
├── nginx.conf                 # SPA routing + API proxy
├── run_api.py                 # Dev server entry point
└── requirements.txt
```

## Running

### Development (local)
```bash
cd nfl-predictor
pip install -r requirements.txt          # Backend deps
ENV=dev python run_api.py                # API on :8000

cd frontend
npm install                              # Frontend deps
npm run dev                              # Frontend on :5173 (proxies /api)
```

### Docker (production)
```bash
cd nfl-predictor
docker compose up --build                # API :8000, Frontend :3000
docker compose run scraper               # One-off data scrape
```

## API Endpoints
- `GET  /api/health` — DB status
- `GET  /api/teams` — All teams
- `GET  /api/teams/{id}` — Team by abbr/name/city
- `GET  /api/teams/{id}/stats` — Computed metrics (SOS, dynamic HFA, rest_days included)
- `GET  /api/teams/{id}/profile` — All-time + last season stats (used by TeamDetail page)
- `GET  /api/teams/{id}/season/{year}` — Season stats
- `GET  /api/teams/{id}/games` — Recent games
- `GET  /api/games` — Games (filter by season/type, `?limit=` param, no limit when season is set)
- `POST /api/predict` — Predict (JSON body, supports optional `factors` array for inline factors, auto-saves to prediction history)
- `GET  /api/predict/{away}/{home}` — Predict via URL
- `GET  /api/h2h/{team1}/{team2}` — Head-to-head (default 10 games)
- `GET/POST/DELETE /api/factors` — Game factors CRUD
- `GET  /api/accuracy` — Backtest accuracy (`?seasons=2024,2025`)
- `GET  /api/predictions/history` — Prediction history with accuracy stats (`?limit=&offset=`)
- `POST /api/predictions/enrich` — Match unresolved predictions to completed game results
- `GET  /api/scrape/status` — Scraping progress
- `GET  /docs` — Swagger UI

## Data Scraping

### Automated scraping
```bash
cd nfl-predictor
python -m src.cli.main --scrape --start 1990 --end 2025
```

### Manual HTML import (when PFR blocks automated requests)
PFR uses Cloudflare bot protection and returns 403 for automated requests.
To work around this, download the page manually and use `--from-file`:

1. Open `https://www.pro-football-reference.com/years/YYYY/games.htm` in your browser
2. Save the page as HTML (Cmd+S → "Web Page, HTML Only")
3. Run:
```bash
cd nfl-predictor
python -m src.cli.main --from-file ~/Downloads/games.htm --start YYYY
```
Replace `YYYY` with the season year (e.g. 2025).

## Frontend Pages
| Route | Page | Description |
|---|---|---|
| `/` | Dashboard | Featured matchups, model accuracy stats |
| `/predict` | Predict | Team selectors + factor panel + prediction results + H2H |
| `/teams` | Teams | Grid of all 32 teams |
| `/teams/:abbr` | TeamDetail | Profile stats, SOS/HFA, 10-season trend charts (Recharts), recent games |
| `/compare/:t1?/:t2?` | Compare | Side-by-side tug-of-war stat bars + H2H summary |
| `/seasons/:year?` | Season | Standings by division + games-by-week accordion (1990-2025) |
| `/history` | History | Auto-saved prediction log with accuracy tracking |
| `/playoffs` | Playoffs | Seed 14 teams → simulate WC/Div/Conf/SB bracket |

## Architecture Notes
- CLI uses singleton DB; API uses per-request DB via FastAPI Depends
- Prediction weights: 25% record, 20% strength, 15% form, 15% SOS, 15% splits, 10% H2H
- Dynamic home field advantage: team-specific HFA from historical home/away win rate differential (capped 0-10%)
- Bye week rest: +1.5% bonus when a team has ≥10 rest days vs opponent's ≤8
- `/stats` endpoint uses `calculate_team_metrics()` (3-season window, tuned for predictions)
- `/profile` endpoint aggregates `team_season_stats` table directly (correct all-time totals)
- `POST /api/predict` accepts optional `factors` array for inline game factors (no game_id needed)
- Predictions auto-save to `prediction_history` table; weekly cron enriches them with actual results
- Theme system: CSS variables for dark mode, teamColors.ts for team-specific styling
- All team colors/styling are independent from component logic (swap theme without touching pages)
- Scraper has cloudscraper fallback: if requests gets 403, it retries with cloudscraper automatically
- Cron container runs weekly_scrape.py every Wednesday 06:00 UTC (also enriches prediction history)
- Frontend uses Recharts for trend charts on TeamDetail page
- 64 pytest tests across 4 test files (API, prediction, scraper, basic)

## Database Tables
- `teams` — 32 active + historical teams with franchise tracking
- `games` — All games 1990-2025 (9170+), scores, winner, overtime
- `game_factors` — Manual adjustments (-5 to +5) linked to game+team
- `team_season_stats` — Pre-computed per-team per-season aggregates
- `scrape_progress` — Resumable scraping state
- `prediction_history` — Auto-saved predictions with optional enrichment (actual_winner, correct flag)

## Recent Changes (2026-04)
- Added `/api/teams/{id}/profile` endpoint with all-time + last season stats
- Fixed TeamDetail page: stats now consistent (home+away = overall record)
- H2H in predictions shows 10 games instead of 5
- Scraper defaults updated to include 2025 season
- Added `--from-file` CLI option for manual HTML import
- Added cloudscraper as 403 fallback
- Full frontend UI redesign: sticky nav, hero dashboard, team badges, dual stat boxes, visual H2H bar
- SOS, Dynamic HFA, rest_days exposed on `/stats` endpoint and TeamDetail page
- Bye week rest advantage (+1.5%) added to prediction engine
- Comprehensive test suite: 64 tests across test_api, test_prediction, test_scraper, test_basic
- Recharts trend charts on TeamDetail (win%, PPG, home/away across 10 seasons)
- Compare page with tug-of-war stat bars + H2H
- Factor management UI on Predict page (inline factors, no game_id required)
- Season browser with computed standings by division + games-by-week
- Prediction history: auto-save on predict, enrichment in weekly cron, History page
- Playoff bracket simulator: seed 14 teams, simulate through Super Bowl