# Season Ops — calendar-driven duties (auto-active)

This project is calendar-driven ("done is a rhythm, not a state" — GUIDEBOOK §4). At session start, map today's date to the phase below and **proactively tell the user what's due**, even if they asked about something else. One line is enough.

## Phase map

| Date window | Phase | Due |
|-------------|-------|-----|
| July–draft night | **Pre-draft** | Weekly `import_rosters.py --season <next> --skip-stats` · ADP CSV import once available · league scoring verification (DoD 1.5) · deploy + `v1.0.0` if still open |
| Draft week | **Draft** | Final roster refresh day before · dry-run `/draft` board · confirm league_size + scoring in UI settings |
| Sep–Jan, Wed | **In-season** | Cron should have fired 06:00 UTC — check `scrape_log` / `/api/scrape/status` if user reports stale data · waiver + lineup windows |
| Sep–Jan, Mon | **In-season** | Self-graded results land — `/history` worth a glance; calibration panel tracks drift |
| February | **Post-mortem** | Full retrain (`train_model.py` + `train_player_models.py`) · backtest report · GUIDEBOOK §7 snapshot + season-context updates · roll `CURRENT_SEASON`/`UPCOMING_SEASON` in `frontend/src/config.ts` |
| March–June | **Offseason** | Quiet. Refactors/v2 items only; no data chores |

## Rules

- **Season numbers are never derived from the calendar year** — `frontend/src/config.ts` backend `src/config.py` are the only sources. An NFL "2025 season" runs into calendar 2026.
- New season bootstrap each September: `python scripts/import_schedule.py`.
- Model retraining is **manual by design** — never add it to cron, never run it as a side effect.
- Roster/ADP chores are user-visible actions: remind, offer the exact command, but data imports that mutate the tracked DB need user awareness before running.
- After the draft: offer to adopt the draft-board roster into `myRoster` (one click exists for this).
