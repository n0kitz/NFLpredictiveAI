# Session Protocol — start/end ritual (auto-active every session)

Always on. No invocation needed. Applies to every session in this repo.

## Session start (before first change)

1. `git status` + `git log origin/main..HEAD --oneline` — know sync state. Unpushed commits exist? Tell user in first reply.
2. Read `nfl-predictor/GUIDEBOOK.md` **§5 Roadmap + §4 Calendar** before proposing work. Pick from "Now" > "Next" > "Later". Never invent work the roadmap doesn't need.
3. Check date vs. operating calendar (see /season-ops skill) — surface due chores proactively.

## During work — hard hygiene rules (each one cost a real session once)

- **Every Bash call**: `cd nfl-predictor && source .venv/bin/activate && …` inline. Shell state does NOT persist between calls. Anaconda base silently breaks player-ML and returns wrong results without erroring (2026-07-08: sanity check returned 0 floors under anaconda, 609 under .venv — same code).
- **Never run experiments against `data/nfl.db`** — it is git-tracked. Copy to scratchpad first, point `Database(Path(...))` at the copy (needs `Path`, not str).
- **After running pytest**: `git status data/nfl.db` — API tests write predictions into the real DB. `git restore data/nfl.db` before committing.
- **vitest only from `frontend/`** — from repo root it silently skips jsdom/setup and "passes".
- **Theme classes**: check `frontend/src/index.css` tokens before writing Tailwind classes — `bg-surface` doesn't exist, `bg-surface-800` does. Invalid classes fail silently.

## Session end (Pflicht — never skip)

1. Full verification: backend pytest (~16 s) + `cd frontend && npm run build && npm test`.
2. Docs sync: any DoD status change → GUIDEBOOK §3 checkboxes + pillar score + §7 snapshot; test-count changes → GUIDEBOOK + CLAUDE.md + SKILL.md + README (all four, they drift independently).
3. **Never `git commit` or `git push` — committing is Normen's job** (his explicit instruction, 2026-07-17). Leave changes in the working tree, report what changed, optionally suggest a commit message.
4. Write Wissensdatenbank session file (`/wissensdatenbank-capture`) — German prose, template applies, also for pure planning sessions.
5. New durable lesson learned? → append to /lessons-learned skill table + update auto-memory.
