# NFL Game Prediction System

Respond like a caveman. No articles, no filler words. Short. Direct. Code speaks for itself. If me ask for code, give code. No explain unless me ask.

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
│   │   ├── backtester.py      # Replay historical games to measure accuracy
│   │   ├── fantasy_scorer.py  # FantasyScorer: projections, start-sit, trade analysis, draft rankings, power rankings, trade values
│   │   ├── feature_builder.py # Feature vector builder (35 features)
│   │   ├── ml_model.py        # ML wrapper (GradientBoostingClassifier + spread regressor)
│   │   └── explainer.py       # SHAP explainer for PredictionExplanation
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
│   │   ├── components/        # Layout (+ PlayerSearch in navbar), PredictionCard, TeamSelector, Spinner, TrendChart, FactorPanel, PlayerModal, ExplanationPanel, DataBadge
│   │   └── pages/             # Dashboard, Predict, Teams, TeamDetail, Compare, Season, History, Playoffs, PlayerPage, FantasyPage
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
│   ├── test_fantasy.py        # FantasyScorer: matchup, projections, start-sit, trade, draft (18 tests)
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
- `GET  /api/fantasy/projections` — Weekly projections (`?week=&season=&position=&scoring=`)
- `GET  /api/fantasy/start-sit` — Start/sit recommendation (`?player1_id=&player2_id=&week=&season=`)
- `GET  /api/fantasy/waiver` — Waiver wire suggestions (`?week=&season=&scoring=&position=&limit=`)
- `GET  /api/fantasy/draft-rankings` — Draft rankings (`?season=&scoring=&position=`)
- `POST /api/fantasy/trade-analyze` — Trade analysis (body: `{give_player_ids, get_player_ids, week, season}`)
- `GET  /api/fantasy/power-rankings` — Team power rankings (`?week=&season=`)
- `GET  /api/fantasy/trade-values` — ROS trade value board (`?week=&season=`)
- `POST /api/fantasy/roster/import-by-names` — Match roster names to DB players (body: `{names, season}`)
- `GET  /api/seasons/{year}/playoff-picture` — Playoff seeding by conference/division/wildcard
- `GET  /api/teams/{id}/upcoming` — Next N scheduled games with difficulty rating (`?season=&limit=`)
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
| `/compare/:t1?/:t2?` | Compare | RadarChart (6 dims) + H2H Timeline BarChart + QuickPredict inline + ScheduleColumn (next 4 games difficulty) |
| `/seasons/:year?` | Season | 3 tabs: Standings (by division), Games (by week accordion), Playoff Picture (AFC/NFC seeding) |
| `/history` | History | Auto-saved prediction log with accuracy tracking |
| `/playoffs` | Playoffs | Seed 14 teams → simulate WC/Div/Conf/SB bracket |
| `/players/:id` | PlayerPage | Full player detail: bio, position-specific stats, fantasy points |
| `/fantasy` | FantasyPage | 6 tabs: Dashboard, Leaderboards, Waiver Wire, Draft, Trade Analyzer, Power Rankings |

**PlayerModal**: overlay component on TeamDetail; shows headshot, position badge, jersey, bio, position-specific stats (QB/RB/WR/TE logic), fantasy points PPR+Standard.

**PlayerSearch**: debounced navbar search (250ms), renders dropdown, navigates to `/players/:id` on selection.

**DataBadge**: pill badge component (7 source types: espn, pfr, nfl-data-py, open-meteo, odds-api, calculated, ml-model) with inline hover tooltip. Used in FantasyPage to label data origins.

**FantasyPage tabs detail:**
- Dashboard: weekly projections list + DataBadge sources + confidence badges + matchup tooltips + RosterImportHelper
- Leaderboards: PPR/Standard top players by position + season
- Waiver Wire: low-ownership projections with matchup score tooltip
- Draft: draft rankings by ADP/tier with scoring format selector
- Trade Analyzer: PlayerSearchPanel give/get + TradeValueBoard sidebar (ROS value accordion, controlled by outer week selector via `externalWeek` prop)
- Power Rankings: composite score table (recent form 40% + pt diff 20% + opp strength 20% + adv stats 20%) with trend arrows

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
- 128 pytest tests across 8 test files (API, prediction, scraper, basic, roster, injury_scraper, weather_scraper, fantasy)
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

### Wave 1 — Core platform
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
- Factor management UI on Predict page (inline factors, no game_id required)
- Season browser with computed standings by division + games-by-week
- Prediction history: auto-save on predict, enrichment in weekly cron, History page
- Playoff bracket simulator: seed 14 teams, simulate through Super Bowl
- ML model: GradientBoostingClassifier, 32→35 feature vector; needs retraining (numpy mismatch on old model)
- Injury + weather enrichment: ESPN + Open-Meteo, display-only, `GET /api/games/{id}/conditions`, weekly cron auto-fetch
- `POST /api/predict` response now includes `conditions` (injuries + weather) and `vegas_context` fields
- `GET /api/model/info` endpoint: reports active model, ML availability, OOS accuracy comparison

### Wave 2 — Roster system
- players + roster_entries + player_season_stats tables added
- `RosterScraper` (ESPN API); `import_rosters.py` with 3-tier matching (exact/lastname/fuzzy)
- `/api/teams/{id}/roster`, `/api/players/{id}`, `/api/players/search`, `/api/fantasy/top` endpoints
- PlayerModal overlay + PlayerPage + navbar PlayerSearch in frontend
- Feature vector expanded to 35: added vegas_home_implied_prob (#33), home_qb_epa_per_play (#34), away_qb_epa_per_play (#35)
- Fixed `import_player_season_stats`: merges `import_seasonal_data` with `import_seasonal_rosters` on player_id+season
- Fixed `search_players` API: `sqlite3.Row` uses bracket access `r["col"]`, not `.get()`
- Weekly cron now includes roster update step

### Wave 3 — Fantasy module + enhancements (last session, 2026-04-17)
- **`src/prediction/fantasy_scorer.py`** — `FantasyScorer` class: `generate_weekly_projections`, `start_sit_recommendation`, `analyze_trade`, `generate_draft_rankings`, `get_power_rankings`, `get_trade_values`
- **`tests/test_fantasy.py`** — 18 tests (MagicMock unit tests + real-DB integration); 128 total tests now
- **`weekly_scrape.py`** — added fantasy projection generation step before `db.close()`
- **`schemas.py`** — added `ImportByNamesRequest(names: List[str], season: int)`
- **New API endpoints** (all appended to `app.py`): fantasy projections, start-sit, waiver, draft-rankings, trade-analyze, power-rankings, trade-values, roster/import-by-names, playoff-picture, teams/{id}/upcoming
- **`DataBadge.tsx`** — new component: pill + inline hover tooltip for 7 data source labels
- **`Compare.tsx`** — full rewrite: RadarChart (6 dims), H2H Timeline BarChart, QuickPredict inline panel, ScheduleColumn (next 4 games with easy/medium/hard difficulty badge)
- **`Season.tsx`** — added 3rd tab "Playoff Picture": AFC/NFC conference blocks, division leaders, wildcard, bubble rows; fetches `/api/seasons/{year}/playoff-picture`
- **`FantasyPage.tsx`** — full fantasy hub: 6 tabs, RosterImportHelper (paste names → match → confirm), TradeValueBoard sidebar (collapsible ROS ranked list), DataBadge source labels, confidence badges, matchup tooltips
- **`TradeTab` fix** — now accepts `externalWeek?: number` prop; internal week selector hidden when prop provided; controlled by `TradeTabWithValues` wrapper
- **`RosterImportHelper` fix** — removed invalid `api.post && null` no-op; `handleConfirm` calls `onImported(ids)` directly
- **Bug fix** — `fantasy_scorer.py` line 365: `r.get('team_abbr')` → `r['team_abbr']` (sqlite3.Row doesn't support `.get()`)
- **Bug fix** — `get_fantasy_top` endpoint in `app.py`: all `r.get()` calls replaced with `r["field"] or default`
- **TypeScript types** — appended: `PlayoffTeamEntry`, `PlayoffConference`, `PlayoffPicture`, `UpcomingGame`, `TeamUpcoming`, `PowerRanking`, `PowerRankings`, `TradeValue`, `TradeValues`, `RosterMatchEntry`, `RosterImportResult`
- **`client.ts`** — added: `getPlayoffPicture`, `getTeamUpcoming`, `getFantasyPowerRankings`, `getFantasyTradeValues`, `importRosterByNames`, plus all other fantasy extended methods

### Phase 2 — Advanced Matchup Engine (2026-04-18)
- **`src/prediction/matchup_engine.py`** — new module: `opp_position_dvp` (6wk PPR allowed by position), `pace_adjusted_plays` (game-tempo proxy via avg total pts), `pass_rate_over_expected` (PROE via qb_epa_per_play deviation), `neutral_script_rates` (pass/rush balance in close games), `matchup_grade` (A–F + 0–100 composite: 45% DvP, 25% YPP, 20% pace, 10% PROE)
- **`src/prediction/player_features.py`** — expanded to 16 features: added `opp_pace` (#14), `opp_proe` (#15), `opp_pos_dvp_6wk` (#16); `build_training_rows` pads legacy 13-feature arrays to width 16
- **`src/prediction/player_ml_model.py`** — bumped `MODEL_VERSION` to `"ml-v2"` (triggers model cache invalidation; retrain required)
- **`src/api/schemas.py`** — added `MatchupComponentScores` + `MatchupGradeResponse` Pydantic models
- **`src/api/app.py`** — new `GET /api/fantasy/matchup/{player_id}?week=&season=` endpoint; resolves team/opponent from schedule automatically
- **`src/database/schema.sql`** — added `matchup_cache` table (player/opp/season/week, grade, score, rank, dvp_6wk, pace, proe, component_scores_json)
- **`src/database/db.py`** — MIGRATIONS v7: `CREATE TABLE matchup_cache`
- **`frontend/src/api/types.ts`** — added `MatchupComponentScores` + `MatchupGrade` interfaces
- **`frontend/src/api/client.ts`** — added `getMatchupGrade(playerId, week, season)` method
- **`frontend/src/pages/FantasyPage.tsx`** — added `gradeColor()`, `MatchupGradePill` component (lazy-fetches per player, shows A–F pill with tooltip: score/100, explanation, rank vs league); pill added to Dashboard projection rows alongside MLBadge
- **`tests/test_matchup_engine.py`** — 34 new tests (unit + integration); 175 total tests now
- **`tests/test_player_ml.py`** — updated `test_feature_names_length_matches_positions` from 13 → 16

## Pending Data Operations (run after code changes)
```bash
cd nfl-predictor
python scripts/import_advanced_stats.py   # Populate QB EPA + team advanced stats
python scripts/train_model.py             # Retrain ML model with 35-feature vector
python scripts/import_rosters.py          # Import rosters + player season stats (Step1: ESPN, Step2: nfl_data_py)
# Review data/unmatched_players.txt after roster import to assess matching quality
```