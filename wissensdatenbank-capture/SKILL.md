---
name: wissensdatenbank-capture
description: >
  Captures the current session as a structured Markdown file in the Wissensdatenbank.
  Use at the end of every session with code changes, or when user says "capture session",
  "wissensdatenbank", "session loggen", "save session", "dokumentiere session".
  Writes to /Users/normenkitzmann/Wissensdatenbank/AI_Sessions/Claude_Code/{Projekt}/
  Also updates memory/decisions.md if architecture decisions were made.
---

# Wissensdatenbank Capture

Capture current session as structured Markdown. Write directly via Write tool.

## Target Path

```
/Users/normenkitzmann/Wissensdatenbank/AI_Sessions/Claude_Code/{PROJEKT}/YYYY-MM-DD_{Kurztitel}.md
```

**Projekt-Ordner mapping:**

| Projekt | Ordner |
|---------|--------|
| NFL prediction app (FastAPI/React/SQLite) | `NFLpredictiveAI` |
| Unity Siedler-Clone | `Siedler-Clone` |
| Azure / PowerShell / Beruf | `Arbeit-IT-Cloud` |
| Raspberry Pi / Flask / Dashboard | `Raspberry-Pi-Restaurant` |

## Steps

1. **Determine**: project folder from active repo, date from today, short title from main work done
2. **Write** session file using template below
3. **If** architecture decisions made → append entry to `memory/decisions.md`
4. **Confirm** to user: path written + any decisions.md update

## Session File Template

```markdown
---
type: claude-code-session
date: YYYY-MM-DD
thema: "Kurzer Titel"
projekt: "Projektname"
repo: "github.com/n0kitz/NFL"
branch: "main"
tags: [claude-code, python, fastapi, react]
status: abgeschlossen
---

# 🛠️ Thema

> **Projekt:** Name | **Datum:** YYYY-MM-DD | **Repo:** link

## Ziel
Was sollte in dieser Session erreicht werden?

## Betroffene Dateien
| Datei | Aktion | Beschreibung |
|-------|--------|--------------|
| `path/to/file` | erstellt/geändert/gelöscht | Was wurde gemacht |

## Änderungen
Kurze Beschreibung der wichtigsten Änderungen.

## Probleme & Lösungen
| Problem | Lösung |
|---------|--------|
| Problem | Lösung |

## Learnings
- Erkenntnis 1
- Erkenntnis 2

## Nächste Schritte
- [ ] Todo 1
- [ ] Todo 2
```

## Rules

- Always write the file — do not just show the content
- Short title: max 4 words, kebab-case-friendly (e.g. `Phase1-Config-Fixes`)
- If no code changed (pure planning/research): still capture with `status: planung`
- German prose, English code/paths/technical terms
- decisions.md entry format: `### [YYYY-MM-DD] Decision: <title>` with Why + Impact lines
