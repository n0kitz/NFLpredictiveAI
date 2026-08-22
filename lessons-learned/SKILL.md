# Lessons Learned — verified past mistakes, don't repeat (auto-active)

Living table. Consult before "fixing" anything; append when a new lesson costs >15 min. Each row was real.

## Rule zero: evidence before belief

Docs, memories, and issue lists are **claims, not facts**. Re-measure before building a fix:
- 2026-07-08: GUIDEBOOK said "suite ~30 min, add TTL cache". Measured: **15.8 s**. The fix would have been wasted work for a poisoned-env artifact.
- 2026-07-08: "Calibration missing" — backend had computed it for months (`/api/accuracy` → backtester `CALIBRATION_BUCKETS`), even typed in frontend `types.ts`. Only the display was missing. **Grep for existing plumbing before building a feature.**

## The table

| Lesson | Rule derived |
|--------|--------------|
| nfl_data_py `import_weekly_data` 404s for 2025+ (nflverse retired the release) | Weekly data ONLY via `fetch_stats_player_week()` parquet. Never "fix" imports back |
| Anaconda base ran the same code and silently returned wrong results (0 floors vs 609) | Wrong env ≠ crash. Distrust any surprising result until reproduced inside `.venv` |
| pytest dirtied git-tracked `data/nfl.db` | Check `git status` before every commit; experiments on scratchpad DB copies |
| Joe Milton ranked QB8 from one 19.2-pt game ×17 | Any per-game extrapolation needs small-sample shrinkage (`min(1, games/8)`) |
| Draft board was a QB wall when sorted by raw points | Fantasy boards sort by **VBD**, never raw projected points |
| `getByText('KC')` broke when a second panel rendered the same abbr | Team abbrs/numbers repeat in UIs — `getAllByText(...).length > 0` for smoke tests |
| jsdom 25 ships no localStorage; vitest config only loads from `frontend/` | Both are silent failures — test "passes" or errors misleadingly. Trust the setup docs |
| `sqlite3.Row.get()` doesn't exist | Bracket access only; convert to dict when `.get()` semantics needed |
| Optimizer tests went infeasible after adding a DST slot (cap 46k < min 46.5k) | Changing roster slots changes MILP feasibility — re-derive test salary caps |
| ESPN sends kickers as `PK`; DST doesn't exist upstream | Position normalization + synthetic players happen at scrape time, nowhere else |
| Wrong-env server wrote heuristic rows into `fantasy_projections` cache | Cache poisoning outlives the bug: `DELETE` season/week rows, regenerate from `.venv` |
| `new Date().getFullYear()` crept into Dashboard despite documented rule | Grep for banned patterns when touching a file — rules erode silently |
| README claimed "60+ endpoints", reality 51 | Doc numbers drift optimistic. Count, don't trust; honest beats impressive |
| ESPN began 403ing custom UAs while `curl/*` and `python-requests/*` still got 200 | Anti-bot rules can invert intuition — the honest default UA beat the spoofed browser one. Probe a UA matrix before declaring an outage |
| `import_rosters.py` fetched 0/32 teams, printed "complete", exited 0 | An import that imported nothing must exit non-zero. Count what landed and assert on it — "no exception" ≠ "it worked" |
| `nfl_data_py.import_seasonal_data` was dead for 2025+ too, so `player_season_stats` had zero offensive rows and the draft board silently used 2024 alone (McCaffrey ranked #255) | When one feed of a source dies, test its siblings the same day. Derive season totals from the weekly rows you already trust |
| `LAST_COMPLETED_SEASON = CURRENT_SEASON - 1` was wrong Feb–Aug, serving two-year-old stats during draft prep | Season math needs a date-aware function with tests at each boundary, never a constant offset |
| `db_version` said 25 but `scrape_log` didn't exist, so cron logging raised `no such table` | A version stamp is not proof the DDL ran. `schema.sql` must list every table so reopening self-heals |
| I read the draft board with `.get('vbd_score', 0)` when the key is `vbd`, saw zeros, and called the board "completely broken" | A `.get()` default fabricates plausible data. Print real keys before concluding — and retract loudly when the measurement was the bug |
| Simulated "best available" drafted eight QBs: raw VBD rates QB1 and QB8 alike | Player value is relative to *your* roster. Any auto-drafter needs hard positional caps, not just a value ranking |
| A 0.02× saturation penalty didn't stop it — late in a draft everything is capped, so the shared factor cancels | A penalty applied to all candidates equally is not a penalty. Where you mean a rule, exclude; don't discount |
| "Biggest gap vs ADP" picked the worst player on the board (late ADP − early index = huge gap) | Market-value strategies must only compare players actually in range for the pick — window the candidate list |
| Recomputing `saturatedPositions()` per player comparison made 960 drafts take 33 s | Hoist per-pick state out of per-candidate loops; it was a 28× win for a one-line move |
| A roadmap item read "download the FantasyPros CSV" for weeks; FFC serves the same consensus ADP as free public JSON | Before writing a manual step into the runbook, check whether the data has a public API. A chore the user must remember is a chore that won't happen |
| ADP matching lost "Kenneth Walker" (we store "Kenneth Walker III") and "Eddy Piñeiro" (we store "Pineiro") — 2 silent drops | Name matching across feeds must fold accents and generational suffixes, and refuse to guess when normalized names collide |
| The exact-name lookup did `WHERE full_name = ? LIMIT 1` with no position, so one of two Mike Williamses won arbitrarily | `LIMIT 1` over a non-unique key is a coin flip. Qualify with everything you know before you take the first row |
| The last-name fallback matched "Brian Robinson" (we store "Brian Robinson Jr.") to **Bijan** Robinson, overwriting the #2 player's ADP with 107.0 — and had been doing the same to weekly stats | A fuzzy match that can bind to the wrong row is worse than no match: it silently overwrites real data. Every fuzzy step must require a unique *and* independently corroborated candidate |
| Making the last-name fallback "unique" still matched Russell Wilson → Zach Wilson, because our table only carries one QB Wilson | Uniqueness in *your* table says nothing about who the feed meant. Absence is a real answer — require positive evidence (first-name compatibility), don't infer identity from scarcity |
| The ADP import reported "211/211 matched" while writing only 210 rows | Count what actually landed, not what you attempted. Reconcile matched-count against rows-present; `INSERT OR REPLACE` hides collisions perfectly |
| Re-importing did not fix rows attached to the wrong player — upserts key on `(player_id, season, week)` | After a matching fix, re-import is not repair. Purge the affected range first (`--rebuild`), or the corruption is immortal |
| Injury lookups keyed on `name.split()[-1]`; for "Marvin Harrison Jr." that token is "Jr.", so `LIKE '%jr.%'` matched a stranger — 168 of 1013 rostered players inherited a wrong injury, and `Out` multiplies a projection by 0.0 | Never key an identity on a name fragment. Suffixes ("Jr.", "III") make last-token keys collide across unrelated people — normalize the full name |
| Filling an empty table armed a dormant bug: the matcher was harmless at 0 rows and catastrophic at 95 | Populating data is a code change in disguise. Before running an import that fills a long-empty table, audit every consumer of that table |
| The scraper dropped "Questionable" while the scorer defined a 0.7× rule for it — the rule could never fire | When a producer filters and a consumer switches on the same vocabulary, one test must assert the two sets match, or a branch quietly dies |
| Docs claimed draft rankings exclude ruled-out players; the code only applies a frequency penalty — and the code was right, since a preseason "Out" says nothing about Week 1 | Verify a claimed behaviour before "restoring" it. Sometimes the doc is wrong *and* the absent feature would have been a bug |
| Start/sit ranked on `projected_points_ppr` in a Standard league — the projection dict carries both totals and the wrong one was picked | When a value exists in two scoring formats, selecting between them belongs in `LeagueSettings`, not at each call site. Rank and explanation must quote the same number |
| The MILP produced a lineup whose swap list said "+-0.9 pts" while reporting 0 points gained | Pairing best-upgrade with worst-downgrade can yield a negative delta. Never emit a suggestion with a non-positive gain — a change worth nothing is noise, not advice |
| The optimizer correctly started a ruled-out TE at 0.00 because he was the only one rostered — silently | "Optimal" and "acceptable" differ. When the best legal answer is still bad, say so; the fix was a waiver claim, not a swap |
| Cached `fantasy_projections` for 2026 ranked a backup QB (12.0) above Bijan Robinson (5.4) while `calculate_projection` gave 1.65 and 17.16 | Two code paths computing the same quantity will diverge. Spot-check a bulk path against the single-item path on a name you can sanity-check by eye |
| `npx tsc --noEmit` passed while `npm run build` failed on the same files | Typecheck the way CI builds. A "clean" check with different config proves nothing |
| `source .venv/bin/activate` in a Bash call still ran anaconda's pytest | Don't trust activation — call `.venv/bin/python -m pytest` explicitly and assert on `sys.executable`/numpy version when it matters |
| I root-caused the constant-projection bug to a SQL join, wrote it into an approved plan, and only found on implementing that 966 of 1045 bad rows came from the **ML** path the join never touches | A root cause isn't confirmed until you've traced the *specific rows you're complaining about* to it. `model_source` was one query away and would have caught it before the plan. Check which code path produced the artifact, not which path could have |
| The degenerate week-1 feature vector affects **every** season, not just an unplayed one — Bijan's 2025 week-1 rolling averages are also all 0.0 | "This only breaks for future data" is a hypothesis, not a finding. Test the same code path against real historical data before scoping a fix around the future case |
| My roster purge deleted all 32 synthetic DST entries, because ESPN never returns them so their `fetched_at` is permanently stale | A delete-what-wasn't-refreshed sweep silently assumes every row has the same producer. Enumerate who writes to a table before purging by timestamp |
| `evaluate_roster_import` returns `ok=True` at 20/32 teams, so gating a destructive purge on `import_ok` would have wiped twelve rosters on any partial ESPN outage | A function named like a success check isn't necessarily a *sufficient* one. Read what a guard actually returns before making something irreversible depend on it |
| I reported "all green" for a feature wave after running pytest and the frontend build but never black or mypy — both blocking in CI — and pushed a red build | "Green" means every gate CI runs, not the subset you happened to run. Run the documented verification block in full, or say explicitly which parts you skipped |

## Appending

New row = one sentence lesson + one sentence rule. No essays. If it changes behavior every session, promote it to /session-protocol instead.
