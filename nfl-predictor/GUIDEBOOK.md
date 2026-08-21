# NFL Predictor — Guidebook

> **The canonical answer to four questions: what is this project, what does "as good as it can possibly be" look like, how far along is it, and what do I do next?**
> Last updated: 2026-08-21 (Phases 1-3 of the fantasy-advice wave all complete: bye/playoff-SOS planner, My Team advisor + N-way start/sit, streaming + FAAB waiver advisor + Weekly Briefing; injury pipeline fully repaired; 10 hardcoded season defaults replaced; 559 backend + 144 frontend tests) · Supersedes `PROJECT_PLAN.md` · Dev setup: `README.md` · Data scraping: `SCRAPING_GUIDE.md` · Agent conventions: `../CLAUDE.md`

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
| 1.3b | **Draft simulator** (`/draft/sim`): batch-compare 8 strategies over seeded mock drafts vs mixed-personality bots, plus an interactive mock draft to rehearse | ✅ |
| 1.4 | **Real ADP** loaded so the board shows value-vs-market (`scripts/import_adp.py`) | ✅ **216 rows** (214/214 matched) as of 2026-08-21 evening re-run, from Fantasy Football Calculator's public API (`python scripts/import_adp.py --season 2026`, no download). Re-run before draft night; the last run is the one that counts |
| 1.5 | League scoring **verified against the actual fantasy.nfl.com settings page** (esp. K/DST rules) | ⬜ user action, ~10 min, do before draft |
| 1.6 | In-season loop: projections → start/sit → waiver (own roster excluded, VBD-ranked) → trade analyzer → optimizer, all league-settings-aware | ✅ **+My Team tab**: give roster once → optimal lineup + swap list with reasons + injury flags; `rank_start_sit` ranks N players in Standard scoring. **+Streaming** + **+FAAB advisor** (value over your own replacement level, bid % tiers) on the Waiver tab. **+Weekly Briefing tab**: one composed "what do I change this week" view (2026-08-21) |
| 1.9 | **Draft-time roster planning**: bye-week collision warnings + fantasy-playoff (wk15-17) strength-of-schedule per player, so byes and brutal late stretches are visible before you draft, not after | ✅ 2026-08-21 — `/fantasy` → Schedule tab, `POST /api/fantasy/schedule-outlook`, derived from the loaded schedule (no hardcoded bye table) |
| 1.7 | 2026 rosters current on draft night (weekly `import_rosters.py --season 2026 --skip-stats` through August; final run day before draft) | 🟡 refreshed 2026-08-21 (3,207 entries, 32/32 teams); repeat weekly — **final run the day before the draft is mandatory** |
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
| 2.7 | Projection floors/ceilings from actual distributions (Monte-Carlo or quantile models) instead of ±25/35% placeholders | ✅ p20/p80 of each player's weekly points (≥4 weeks); placeholder only for ML rookies without history |
| 2.8 | Annual retrain ritual after the Super Bowl folds the finished season into game + player models | ⬜ recurring (first: Feb 2027) |

### Pillar 3 — Self-Running Service

| # | Criterion | Status |
|---|-----------|--------|
| 3.1 | **Deployed on an always-on host** (VPS/Fly/Render), frontend behind nginx, API internal, HTTPS | ⬜ **the** gap between "codebase" and "product" |
| 3.2 | Cron container verified firing Wednesdays on the host; a missed run is visible (`scrape_log`, `/api/metrics`) | ⬜ blocked by 3.1 |
| 3.3 | Enrichment live: `ODDS_API_KEY` set + `fetch_odds.py` / `fetch_conditions.py` populating | 🟡 **injuries flowing 2026-08-21** (95 fantasy-relevant rows, all 32 teams resolvable). `game_weather` waits on games inside the 14-day window (season starts 09-10); `game_odds` still needs `ODDS_API_KEY` |
| 3.4 | A `v*` tag published → GHCR images built by CI (pipeline ✅, first tag ⬜) | 🟡 |
| 3.5 | CI green on every push: ruff + black + mypy (blocking) + pytest / eslint + tsc + vitest; Docker job on tags | ✅ |
| 3.6 | Full test suite green: **559 backend + 144 frontend** | ✅ |
| 3.7 | Observability: JSON logs, `X-Request-ID`, `/api/metrics` | ✅ |
| 3.8 | Data pipeline survives upstream drift (nflverse URL scheme change of 2025 already absorbed; retry/backoff on all scrapers) | ✅ |

**Score today: Pillar 1 ~90% (every coded criterion done; only 1.5 user verification, 1.7 weekly discipline and 1.8 the actual league outcome remain) · Pillar 2 ~90% (only the Feb-2027 retrain ritual remains) · Pillar 3 ~55%.**
The software is nearly done; the *service* and the *pre-draft data chores* are what remain. Nothing left is hard — it's a deploy, an API key, a CSV, and a ten-minute settings check.

---

## 4. The operating calendar

This project is calendar-driven. "Done" is not a state, it's a rhythm:

| When | What | Tooling |
|------|------|---------|
| **August (now — draft is weeks away)** | Import real ADP · verify league scoring · weekly 2026 roster refresh · deploy (§5 Now) | `import_adp.py`, `import_rosters.py` |
| **Aug/Sep — draft night** | Final roster refresh the day before · run the draft from `/draft` | Draft board |
| **In season, Wed AM** | Cron refreshes everything; you check waivers + set lineup | `weekly_scrape.py` (auto) |
| **In season, Sunday** | Watch the model's picks self-grade; check `/history` accuracy | auto |
| **Monthly (optional)** | Refresh models on new weeks of data | `train_player_models.py` |
| **February** | Season post-mortem: accuracy report, calibration check, full retrain, GUIDEBOOK update | `run_backtest.py`, `train_model.py` |

---

## 5. Roadmap

### Now — before the draft (highest leverage, days not weeks)
1. **Deploy** (3.1/3.2): `docker compose up -d` on a small host; confirm cron fires; set `ODDS_API_KEY` + `CORS_ORIGINS`. Tag `v1.0.0` → images publish.
2. ~~**Load ADP** (1.4)~~ ✅ 216 rows (214/214 matched) as of 2026-08-21 via `python scripts/import_adp.py --season 2026`. Re-run before draft night; the last run is the one that counts.
2b. **Rebuild weekly stats** — `bash rebuild-weekly-stats.sh`. One-time repair of wrong-player rows; see the ⚠️ block in §7.
3. **Verify league scoring** (1.5): screenshot the league's scoring settings; diff against `kicker_fantasy_points` / `dst_importer.py` defaults; encode any deltas.
4. **Weekly roster refresh** (1.7) until draft.

### Next — in-season quality
- **Mobile pass** on the fantasy hub + draft board (draft night happens on couches, not desks). First code pass done 2026-07-08 (tables scroll horizontally instead of clipping, dashboards stack on small screens) — still needs a check on a real phone.
- ~~Flip `black`/`mypy` to blocking~~ ✅ 2026-07-17: backlog cleared (73 files formatted, 55 type errors → 0), both CI steps blocking. Frontend eslint stays non-blocking (react-hooks findings, tracked separately).

### Next — draft prep
- **Use the simulator before draft night** (`/draft/sim`): run 100+ drafts from your actual slot and league size to see which strategy wins. Early results from slot 1 favour Hero-RB / Best-Available; slot 10 favours Robust-RB / Late-QB — but re-run it once real ADP is loaded, because that changes the bots' behaviour and makes "Value vs ADP" meaningful.
- ~~**Bye + playoff-SOS planner**~~ ✅ 2026-08-21 — Schedule tab flags roster-wide bye collisions (≥3 players) and grades each player's weeks 15-17 matchups (hard/medium/easy vs league-average DvP). Check it once the roster is drafted, not just before.

### Phase 3 — in-season loop — ✅ complete 2026-08-21
- ~~**Streaming recommendations**~~ ✅ Waiver tab has a DST|K|QB panel ranked by `matchup_grade()`, deduped to one (presumed-starter) candidate per team since teammates at a position share an identical grade, excluding the roster you pass in.
- ~~**Waiver FAAB advisor**~~ ✅ Waiver tab has a FAAB panel: candidates ranked by value over the *roster's own* weakest player at that position (not league-wide VBD), with a 4-tier bid-% suggestion (speculative 3% / solid 10% / priority 20% / must-add 30%). Reuses `roster_advisor.build_roster_pool` for both sides — the same cache-independent projection path as My Team.
- ~~**Weekly briefing**~~ ✅ `/fantasy` opens on a Weekly Briefing tab: one click composes My Team's lineup/swaps, this-week bye warnings (from Schedule outlook scoped to the current week), the top streaming DST, and the top FAAB target. Pure composition — no new backend math, and each source fails independently (each call swallowed to `null` on rejection) so one bad call doesn't blank the page.

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
python scripts/import_adp.py --season 2026                    # live consensus ADP
python scripts/import_adp.py --season 2026 --file <FantasyPros.csv>   # or a specific CSV

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
python -m pytest -q                         # 559 backend (~15 s in a clean .venv)
cd frontend && npm run build && npm test    # tsc + 144 vitest
```

### Gotchas (the ones that actually bite)
- **nfl_data_py is dead for 2025+ — both feeds.** `import_weekly_data` *and* `import_seasonal_data` 404 (nflverse retired those releases). Weekly data comes from `fetch_stats_player_week()`; season totals are aggregated from those weekly rows by `aggregate_offense_season_stats()` / `aggregate_kicker_dst_season_stats()`. Don't "fix" imports back to nfl_data_py.
- **ESPN 403s custom User-Agents** (since 2026-08-20) — `roster_scraper` and `schedule_scraper` must send the default `python-requests/…` UA. A browser-spoofed or app-branded UA fails all 32 teams. `pfr_scraper` is a different host and still needs its browser UA.
- **Empty or kicker-only leaderboards / a draft board that ignores last season** → `player_season_stats` has no offensive rows for that season. Rebuild: `python scripts/import_player_weekly.py --start <yr> --end <yr>`.
- **Projections look heuristic/zeroed** → stale cached rows from a wrong-env server. `DELETE FROM fantasy_projections WHERE season=? AND week=?`, regenerate from the `.venv`. (Cron now purges before regenerating.)
- **Projections empty for a season** → that season has no `roster_entries`.
- **`sqlite3.Row`**: bracket access only, `.get()` doesn't exist.
- **DST are synthetic players** (`espn_id='DST-{abbr}'`); ESPN kickers arrive as `PK` and are normalized to `K`.
- **Schema changes** go to `schema.sql` **and** the `MIGRATIONS` list in `db.py` (currently at v25).
- **ADP `teams` is not segmented.** FFC echoes the `teams` parameter but returns identical pooled ADP for 8- and 14-team leagues (verified 2026-08-21). Never present ADP as tuned to league size — VBD is what carries league size.

---

## 7. State snapshot — 2026-08-21 (re-verified)

- **Data**: 9,727 games (1990–2026 — the 2026 schedule is loaded: 272 games, kickoff 2026-09-10, all unplayed) · player weekly stats 2018–2025 incl. K + DST · `player_season_stats` now covers 2018–2025 for offense too (2,146 rows rebuilt from weekly; 2025 previously had **zero** QB/RB/WR/TE rows) · 3,207 roster entries for 2026 (32/32 teams, refreshed 2026-08-21) · `game_odds` 0 · `injury_reports` 0 · **`player_adp` 216, 214/214 matched (refreshed 2026-08-21)**. `player_weekly_stats` needs the one-time rebuild flagged above.
- **Models**: game GradientBoosting 34-feat OOS 0.668 (weighted-sum 0.672 remains default; ML opt-in via `?model=ml`) · player models 16-feat, MAE QB 6.48 / RB 5.66 / WR 5.50 / TE 4.26 · K/DST heuristic.
- **Tests**: 559 backend (37 files) + 144 frontend, all green (~15 s backend).
- **Git/CI**: CI green (ruff + black + mypy all clean).
- **⚠️ Unverified anomaly (2026-08-21)**: `roster_entries` has Tua Tagovailoa on ATL for both 2025 and 2026, not MIA. Spot-checked 4 other well-known players (Allen, Mahomes, Flacco, Dart) and all resolved correctly, so this looks isolated rather than systemic — but not yet root-caused. Worth a `roster_entries` sanity pass (e.g. cross-check a sample against each team's real depth chart) before trusting streaming/My-Team output for edge-case players.
- **Deployment**: none — local/Docker only. This is the top of the list.

### ⚠️ Open repair — run before trusting the draft board
**`player_weekly_stats` holds rows attached to the wrong player** and needs one rebuild:

```bash
bash ../rebuild-weekly-stats.sh      # or: python scripts/import_player_weekly.py --start 2018 --end 2025 --rebuild
```

The old name matcher fell back to last-name-within-position and took the first row it found, so e.g. **Brian Robinson's 2025 stats were written onto Bijan Robinson** (Bijan: 18 weekly rows vs 17 in source; Brian: none at all). 2024 is worse — 119 players carried more rows than the source has. The matcher is fixed and test-guarded, but **re-importing does not repair this**: upserts key on `(player_id, season, week)`, so wrong-player rows survive. `--rebuild` purges the range first. Re-aggregation of `player_season_stats` happens in the same run, which is what draft rankings read.

(Some over-counts are a second, milder cause: older imports didn't filter `season_type=='REG'`, so playoff weeks leaked in. The rebuild fixes both.)

### Added 2026-08-21 (third pass — the "My Team" advisor)
- **`/fantasy` now opens on a "My Team" tab.** Give it your roster once and it returns the best legal lineup under *your* league settings, the specific swaps to get there (with reasons, not just numbers), injury warnings on your own players, and a per-position "who should I start?" ranking.
- **Start/sit ranked on PPR in a Standard league** — a correctness bug in the exact feature being asked about. `calculate_projection` returns both totals but the comparison used `projected_points_ppr`, systematically over-valuing high-reception players. Now goes through `LeagueSettings.points_from_projection`, and the explanation quotes the same number it ranked on. Live: Chase leads Nacua by **+1.0 in standard but +3.2 in PPR**.
- **Start/sit generalised from 2 players to N** (`rank_start_sit`, `POST /api/fantasy/start-sit/rank`) — "which of my three WRs?" now has an answer. The old two-player endpoint delegates to it, so nothing regressed.
- **Roster-constrained optimizer** (`src/prediction/roster_advisor.py`, `POST /api/fantasy/my-team/lineup`). The Optimizer tab searches every player in the league (a DFS question); this is limited to the roster you own. Reuses the MILP solver with `correlations=False` and no per-team cap — both are DFS constructs that distort a season-long roster.

> **Do not source lineup advice from `fantasy_projections`.** For an upcoming season those cached rows are unreliable: for 2026 wk1 the bulk generator put Jake Haener (backup QB) at 12.0 and Bijan Robinson at 5.4, while `calculate_projection` gives 1.65 and 17.16 — inverted. `build_roster_pool()` therefore projects each rostered player directly (≤25 players, cheap) and that is the verified path. **The bulk `generate_weekly_projections` path is still wrong for future seasons and needs its own investigation** — identical values repeat across unrelated players, which points at a constant feature vector.

### Fixed 2026-08-21 (second pass — injuries)
- **Injury pipeline was dead at the team level.** ESPN's payload carries no `team` object (only `displayName`), so every row got `team_abbr=""` and `fetch_conditions.py` grouped them all under one unusable key — the real reason `injury_reports` sat at 0. Now resolved via `TEAM_NAME_TO_ABBR`; unresolvable rows are **dropped with a count**, never blanked. 800 fetched → 95 stored across 30 teams.
- **`Questionable` was unreachable.** The scraper filtered it out while `_INJURY_RULES` defined a 0.7× discount for it, so questionable starters projected as fully healthy. Filter now matches the rules; positions narrowed to `QB/RB/WR/TE/K` (K was missing, defensive positions were noise). 88 of the 95 stored rows are Questionable.
- **Injury→player matching was the worst bug of the day.** Every lookup keyed on the last *token* of a name — and `"Marvin Harrison Jr.".split()[-1]` is `"Jr."`, so `LIKE '%jr.%'` returned an unrelated player. Measured on live data: **168 of 1013 rostered fantasy players inherited a stranger's injury**, and an `Out` row multiplies a projection by 0.0. Populating the table would have armed this. Matching now uses the normalized full name and refuses to guess on collisions: **168 wrong → 0**, 95 rows → exactly 95 players.
- **10 hardcoded season defaults** (`Query(2024)`, `= 2024`) across `fantasy.py`, `teams.py`, `matchup.py`, `schemas.py` replaced with date-derived constants in a new season block in `src/config.py` (`CURRENT_SEASON`, `LAST_COMPLETED_SEASON`, `ACTIVE_SEASON`). A regex guard test fails the build if a literal returns.

> **Note on draft rankings:** `generate_draft_rankings` applies only an injury-*frequency* penalty; it does **not** exclude ruled-out players — and that is correct. A preseason "Out" (George Kittle in August) says nothing about Week 1, so dropping him from a draft board would be a mistake. Injuries bite in *weekly* projections, verified live: Kittle → 0.0, Khalil Shakir (Q) → 7.28 (0.7×).

### Added 2026-08-21
- **Live ADP fetch** (`fetch_ffc_adp` in `adp_importer.py`): `python scripts/import_adp.py --season 2026` pulls consensus ADP from Fantasy Football Calculator's public API — no CSV download, re-runnable as the market moves, and available for standard / half-PPR / PPR. The CSV path still works via `--file`. An import that matches nothing now exits 1 instead of quietly leaving synthetic rank ADP in place.
- **Name matching rewritten, strongest evidence first** — exact name+position → exact name → accent/suffix-folded normalized comparison → last name+position. Every fuzzy step now requires a *unique* candidate, and the last-name step also requires a compatible first name. This took the 2026 ADP match rate to **211/211** and, more importantly, stopped three classes of wrong match: shared last names ("Brian Robinson" → Bijan), players we don't carry inheriting a namesake's row ("Russell Wilson" → Zach Wilson, because ours was the only QB Wilson), and position-blind exact matches (two Mike Williamses). Collisions across the full 2025 feed: 9 → **0**.
- **`purge_weekly_stats` + `--rebuild`** on `import_player_weekly.py`, because a matching fix is not retroactive without one.

### Added 2026-08-20
- **Draft simulator** (`/draft/sim`, `frontend/src/pages/fantasy/draftSim.ts`): seeded-RNG mock drafts against four bot archetypes, eight selectable strategies, batch comparison ranked by best-legal-lineup points, plus an interactive mock draft. Reuses the live board's snake/needs logic so the two can't drift. 400 drafts run in ~1.2 s.

### Fixed this session (were silently wrong)
- **ESPN 403** — both ESPN scrapers sent a custom User-Agent; ESPN now serves only honest client UAs, so all 32 roster fetches failed. The roster importer reported "complete" and exited 0 on 0 upserts; it now exits 1.
- **2025 season stats missing** — `nfl_data_py.import_seasonal_data` 404s for 2025+ (same retirement as the weekly feed), so the draft board fell back to 2024-only data. Rebuilt from weekly rows: Christian McCaffrey moved from #255 to #9 on the 2026 board, Puka Nacua #30→#5.
- **`LAST_COMPLETED_SEASON` off by one in the offseason** — four fantasy tabs were requesting 2024 while 2025 was fully played.
- **`scrape_log` table missing** from the tracked DB despite `db_version` = 25, so cron failure logging raised `no such table`. Added to `schema.sql`, which self-heals on next open.
