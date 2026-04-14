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
│   │   ├── team_mappings.py   # 32 current + historical teams
│   │   ├── roster_scraper.py  # ESPN roster API → players + roster_entries per team
│   │   ├── nfl_data_importer.py # nfl_data_py: QB EPA PBP, team advanced stats, player season stats
│   │   ├── injury_scraper.py  # ESPN public API — STADIUM_COORDS, ESPN_TEAM_MAP, InjuryScraper
│   │   ├── weather_scraper.py # Open-Meteo API — dome check, WMO codes, is_adverse
│   │   └── odds_scraper.py    # The Odds API — OddsScraper (ODDS_API_KEY required)
│   └── utils/helpers.py
├── frontend/
│   ├── src/
│   │   ├── api/client.ts      # Typed fetch wrapper for all endpoints
│   │   ├── api/types.ts       # TypeScript types matching Pydantic schemas
│   │   ├── hooks/useApi.ts    # React hooks: useTeams, useTeamProfile, usePrediction, useH2H, usePlayer
│   │   ├── theme/teamColors.ts # All 32 team colors, gradient/tint helpers
│   │   ├── components/        # Layout (+ PlayerSearch in navbar), PredictionCard, TeamSelector, Spinner, TrendChart, FactorPanel, PlayerModal, ExplanationPanel
│   │   └── pages/             # Dashboard, Predict, Teams, TeamDetail, Compare, Season, History, Playoffs, PlayerPage
│   ├── vite.config.ts         # Dev proxy /api → localhost:8000
│   └── package.json
├── tests/
│   ├── test_basic.py          # Team mappings, DB, metrics, helpers (14 tests)
│   ├── test_api.py            # All API endpoints via TestClient (33 tests, incl. roster/player/fantasy)
│   ├── test_prediction.py     # Prediction engine, metrics, backtester, feature builder, SHAP (20 tests)
│   ├── test_scraper.py        # HTML parsing, team mapping resolution (11 tests)
│   ├── test_roster.py         # Player upsert, roster entry, season stats, starters ordering (4 tests)
│   ├── test_injury_scraper.py # InjuryScraper, ESPN_TEAM_MAP, STADIUM_COORDS (10 tests)
│   ├── test_weather_scraper.py# WeatherScraper dome logic, WMO mapping (12 tests)
│   └── fixtures/              # Sample PFR HTML for scraper tests
├── scripts/weekly_scrape.py   # Wednesday cron scrape + enrichment + odds + conditions + roster update
├── scripts/fetch_conditions.py# One-off injury + weather fetch for upcoming games
├── scripts/import_rosters.py  # Step1: ESPN rosters → players+roster_entries; Step2: nfl_data_py → player_season_stats
├── scripts/import_advanced_stats.py # nfl_data_py PBP → team_advanced_stats + QB EPA
├── scripts/train_model.py     # Train GradientBoostingClassifier (35 features) + spread regressor
├── scripts/run_backtest.py    # Standalone backtest runner with report output
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
- `GET  /api/teams/{id}/roster` — Current roster with player stats (`?season=`)
- `GET  /api/games` — Games (filter by season/type, `?limit=` param, no limit when season is set)
- `GET  /api/games/{game_id}/odds` — Vegas odds for a game (404 if none; display-only)
- `GET  /api/games/{game_id}/conditions` — Injury reports + weather for a game
- `POST /api/predict` — Predict (JSON body, supports optional `factors` array; auto-saves; includes `vegas_context` + `conditions`)
- `GET  /api/predict/{away}/{home}` — Predict via URL; add `?model=ml` for ML model
- `GET  /api/h2h/{team1}/{team2}` — Head-to-head (default 10 games)
- `GET/POST/DELETE /api/factors` — Game factors CRUD
- `GET  /api/accuracy` — Backtest accuracy (`?seasons=2024,2025`)
- `GET  /api/predictions/history` — Prediction history with accuracy stats (`?limit=&offset=`)
- `POST /api/predictions/enrich` — Match unresolved predictions to completed game results
- `GET  /api/model/info` — Model info (active model, ML availability, OOS accuracy)
- `GET  /api/scrape/status` — Scraping progress
- `GET  /api/players/{player_id}` — Player detail + season stats (404 if not found)
- `GET  /api/players/search` — Search players by name (`?q=`)
- `GET  /api/fantasy/top` — Fantasy leaderboard (`?position=QB&season=2024`)
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
| `/teams/:abbr` | TeamDetail | Profile stats, SOS/HFA, 10-season trend charts (Recharts), recent games, clickable roster → PlayerModal |
| `/compare/:t1?/:t2?` | Compare | Side-by-side tug-of-war stat bars + H2H summary |
| `/seasons/:year?` | Season | Standings by division + games-by-week accordion (1990-2025) |
| `/history` | History | Auto-saved prediction log with accuracy tracking |
| `/playoffs` | Playoffs | Seed 14 teams → simulate WC/Div/Conf/SB bracket |
| `/players/:id` | PlayerPage | Full player detail: bio, position-specific stats, fantasy points |

**PlayerModal**: overlay component on TeamDetail; shows headshot, position badge, jersey, bio, position-specific stats (QB/RB/WR/TE logic), fantasy points PPR+Standard.

**PlayerSearch**: debounced navbar search (250ms), renders dropdown, navigates to `/players/:id` on selection.

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
- Cron container runs weekly_scrape.py every Wednesday 06:00 UTC (enriches predictions + odds + conditions)
- Frontend uses Recharts for trend charts on TeamDetail page
- 104 pytest tests across 7 test files (API, prediction, scraper, basic, roster, injury_scraper, weather_scraper)
- ML model (GradientBoostingClassifier, **35 features**, trained 2013-2022): needs retraining after feature vector expansion
- Feature vector: 32 base + vegas_home_implied_prob + home_qb_epa_per_play + away_qb_epa_per_play = 35 total
- Weighted-sum default: 67.2% OOS accuracy on 2023-2024. ML only activates with `?model=ml`
- `sqlite3.Row` objects: use bracket access `r["col"]` not `.get()` — `.get()` is not supported

## Vegas Lines (The Odds API)
- **Key constraint**: Vegas odds are NEVER used as a prediction input — display-only enrichment.
- API key read from `ODDS_API_KEY` env var. If absent, everything works as before.
- `src/scraper/odds_scraper.py` — `OddsScraper` class: `fetch_upcoming_odds()`, `fetch_historical_odds()`, `american_odds_to_implied_prob()`, `map_team_name()`
- `scripts/fetch_odds.py` — standalone fetch script (prints summary + API quota)
- Weekly cron (`scripts/weekly_scrape.py`) calls odds fetch at end if key is set
- `GET /api/games/{game_id}/odds` — returns `GameOddsResponse` (404 if no odds)
- `POST /api/predict` response includes optional `vegas_context` field (spread, O/U, implied probs)
- `docker-compose.yml` passes `ODDS_API_KEY=${ODDS_API_KEY:-}` to api and cron services

## Injuries & Weather (Display-Only Enrichment)
- **Key constraint**: Injuries and weather are NEVER used as prediction inputs — display-only enrichment.
- `src/scraper/injury_scraper.py` — `InjuryScraper`: ESPN public API (no auth), `STADIUM_COORDS` (lat/lon/is_dome for all 32 stadiums), `ESPN_TEAM_MAP` (JAC→JAX, LA→LAR, WSH→WAS)
  - `fetch_injuries()` — flat list of all injuries from ESPN
  - `filter_key_players()` — keeps position in {QB,WR,RB,TE,OT,CB,DE,LB} AND status in {Out,Doubtful,IR,PUP}
- `src/scraper/weather_scraper.py` — `WeatherScraper`: Open-Meteo (no auth); dome check first (no HTTP call for dome teams)
  - `fetch_game_weather(home_abbr, game_date)` — returns `{is_dome, condition, temperature_c, wind_speed_kmh, precipitation_mm, weather_code, is_adverse}`
  - `is_adverse = wind>30 OR precip>5 OR snow WMO codes`
- `scripts/fetch_conditions.py` — one-off fetch of injuries (all 32 teams) + weather (next 14 days)
- Weekly cron fetches conditions automatically at end of `weekly_scrape.py`
- `GET /api/games/{game_id}/conditions` — returns `GameConditionsResponse` (home_injuries, away_injuries, weather)
- `POST /api/predict` response includes optional `conditions` field (populated for upcoming games ≤14 days)

## Database Tables
- `teams` — 32 active + historical teams with franchise tracking
- `games` — All games 1990-2025 (9170+), scores, winner, overtime
- `game_factors` — Manual adjustments (-5 to +5) linked to game+team
- `team_season_stats` — Pre-computed per-team per-season aggregates
- `team_advanced_stats` — nfl_data_py PBP aggregates per team-season (seasons 2010-2025)
- `scrape_progress` — Resumable scraping state
- `prediction_history` — Auto-saved predictions with optional enrichment (actual_winner, correct flag)
- `game_odds` — Vegas odds from The Odds API (spread, O/U, vig-adjusted implied probs, external_game_id)
- `injury_reports` — ESPN injury data (team_id, player_name, position, injury_status, report_date)
- `game_weather` — Open-Meteo weather (home_team_id, game_date, is_dome, temp, wind, precip, condition, is_adverse)
- `players` — Player bio: espn_id, full_name, position, height/weight, college, experience, headshot_url
- `roster_entries` — Player ↔ team ↔ season links: player_id, team_id, season, roster_status, fetched_at
- `player_season_stats` — Per-player per-season: pass/rush/rec stats, passer_rating, fantasy_points_ppr/standard

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
- Recharts trend charts on TeamDetail (win%, PPG, home/away across 10 seasons)
- Compare page with tug-of-war stat bars + H2H
- Factor management UI on Predict page (inline factors, no game_id required)
- Season browser with computed standings by division + games-by-week
- Prediction history: auto-save on predict, enrichment in weekly cron, History page
- Playoff bracket simulator: seed 14 teams, simulate through Super Bowl
- ML model: GradientBoostingClassifier, 32→35 feature vector; needs retraining (numpy mismatch on old model)
- Injury + weather enrichment: ESPN + Open-Meteo, display-only, `GET /api/games/{id}/conditions`, weekly cron auto-fetch
- `POST /api/predict` response now includes `conditions` (injuries + weather) and `vegas_context` fields
- `GET /api/model/info` endpoint: reports active model, ML availability, OOS accuracy comparison
- **Roster system (2026-04)**: players + roster_entries + player_season_stats tables; `RosterScraper` (ESPN API); `import_rosters.py` with 3-tier matching (exact/lastname/fuzzy); `/api/teams/{id}/roster`, `/api/players/{id}`, `/api/players/search`, `/api/fantasy/top` endpoints; PlayerModal overlay + PlayerPage + navbar PlayerSearch in frontend
- Feature vector expanded to 35: added vegas_home_implied_prob (#33), home_qb_epa_per_play (#34), away_qb_epa_per_play (#35)
- Fixed `import_player_season_stats`: now merges `import_seasonal_data` with `import_seasonal_rosters` (seasonal_data has no player names — merge on player_id+season to get names/positions)
- Fixed `search_players` API: `sqlite3.Row` uses bracket access `r["col"]`, not `.get()`
- Weekly cron now includes roster update step
- 104 pytest tests across 7 files; test_injury_scraper + test_weather_scraper skip without network

## Pending Data Operations (run after code changes)
```bash
cd nfl-predictor
python scripts/import_advanced_stats.py   # Populate QB EPA + team advanced stats
python scripts/train_model.py             # Retrain ML model with 35-feature vector
python scripts/import_rosters.py          # Import rosters + player season stats (Step1: ESPN, Step2: nfl_data_py)
# Review data/unmatched_players.txt after roster import to assess matching quality
```