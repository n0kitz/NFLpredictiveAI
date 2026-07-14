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

## Appending

New row = one sentence lesson + one sentence rule. No essays. If it changes behavior every session, promote it to /session-protocol instead.
