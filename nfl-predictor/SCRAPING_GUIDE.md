# How to Scrape NFL Data from Pro Football Reference

## The Problem

Pro Football Reference (PFR) uses Cloudflare bot protection. Automated HTTP requests
(via `requests`, `curl`, or `cloudscraper`) get a **403 Forbidden** response.
The scraper handles this gracefully, but you need to manually download the HTML
when PFR blocks you.

## Step-by-Step: Manual Download + Import

### 1. Open the season schedule page

Go to this URL in your browser (replace `YYYY` with the season year):

```
https://www.pro-football-reference.com/years/YYYY/games.htm
```

For example, for the 2025 season:
```
https://www.pro-football-reference.com/years/2025/games.htm
```

### 2. Save the page as HTML

- **Mac**: Cmd+S → select "Web Page, HTML Only" → save to Downloads
- **Windows**: Ctrl+S → select "Web Page, HTML Only" → save to Downloads
- **Important**: Use "HTML Only", NOT "Web Page, Complete" (we don't need images/CSS)

The file will typically be saved as `games.htm`.

### 3. Run the import command

```bash
cd nfl-predictor
python -m src.cli.main --from-file ~/Downloads/games.htm --start 2025
```

The `--start` flag tells the parser which season year the file belongs to.

### 4. Verify the import

```bash
# Check how many games were loaded
python -m src.cli.main "Bills record in 2025"

# Or via the API
curl http://localhost:8000/api/teams/BUF/season/2025
```

## Importing Multiple Seasons

If you need to backfill several seasons, repeat for each year:

```bash
# Download each page manually, rename to avoid collisions
# games_2023.htm, games_2024.htm, games_2025.htm

python -m src.cli.main --from-file ~/Downloads/games_2023.htm --start 2023
python -m src.cli.main --from-file ~/Downloads/games_2024.htm --start 2024
python -m src.cli.main --from-file ~/Downloads/games_2025.htm --start 2025
```

## Trying Automated Scraping First

The scraper will always try automated scraping first, with cloudscraper as a fallback.
Sometimes PFR loosens their protection temporarily. Try this before downloading manually:

```bash
python -m src.cli.main --scrape --start 2025 --end 2025
```

If it works, great — no manual download needed.

## What Gets Imported

Each season page contains:
- All regular season games (weeks 1-18)
- All playoff games (Wild Card, Divisional, Conference, Super Bowl)
- Scores, home/away, overtime status

After import, `team_season_stats` is automatically recalculated for the imported season.

## Troubleshooting

**"No games found in file"**
- Make sure you saved as "HTML Only", not a PDF or text file
- Open the file in a text editor — it should contain `<table id="games">`

**Duplicate games skipped**
- This is normal. If you re-import the same season, existing games are skipped.
  The output shows "X inserted, Y skipped".

**Season stats look wrong after import**
- Stats are recalculated automatically. If needed, force recalculation:
  ```python
  from src.database.db import get_database
  db = get_database()
  db.calculate_team_season_stats(2025)
  ```