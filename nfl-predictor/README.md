# NFL Game Prediction System

A Python-based NFL game prediction system that uses historical data to calculate win probabilities for matchups.

## Features

- **Historical Data**: 35 years of NFL game data (1990-2024) scraped from Pro Football Reference
- **Win Probability Predictions**: Calculate win percentages based on multiple weighted factors
- **Natural Language Queries**: Ask questions in plain English
- **Factor System**: Framework for adding custom game factors (injuries, weather, etc.)
- **Comprehensive Stats**: Team records, head-to-head history, playoff performance

## Installation

```bash
# Clone or navigate to the project
cd nfl-predictor

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

### 1. Initialize the Database

```bash
python -m src.cli.main --init-db
```

### 2. Scrape Historical Data

This will take some time due to rate limiting (respecting the source website):

```bash
# Scrape all seasons (1990-2024) - takes several hours
python -m src.cli.main --scrape

# Or scrape specific years
python -m src.cli.main --scrape --start 2020 --end 2024
```

### 3. Make Predictions

```bash
# Single query
python -m src.cli.main "Predict Chiefs vs Eagles"

# Interactive mode
python -m src.cli.main --interactive
```

## Usage Examples

### Predictions

```bash
python -m src.cli.main "Predict Chiefs vs Eagles"
python -m src.cli.main "Who wins: Cowboys at Giants?"
python -m src.cli.main "49ers vs Seahawks"
```

Example output:
```
San Francisco 49ers @ Seattle Seahawks
Prediction: Seahawks 52% | 49ers 48%
Confidence: High
Key Factors:
├─ SEA: 9-5 record, +42 point diff
├─ SF: 10-4 record, +89 point diff
├─ Recent form: SEA 3-2 last 5, SF 4-1 last 5
├─ SEA home: 5-2
├─ Head-to-head (last 10): SEA 5-5
└─ Home field advantage: +3.2% to Seahawks
[No custom game factors applied - add factors for refined predictions]
```

### Historical Queries

```bash
# Head-to-head history
python -m src.cli.main "Head to head Patriots vs Dolphins"

# Recent games
python -m src.cli.main "Last 10 games for the Bills"

# Season record
python -m src.cli.main "Bills record in 2023"

# Playoff history
python -m src.cli.main "Playoff history for the Lions"

# Team info
python -m src.cli.main "Tell me about the Chiefs"
```

### Interactive Mode

```bash
python -m src.cli.main -i
```

Then type queries at the prompt:
```
NFL> Predict Ravens vs Bengals
NFL> h2h Chiefs and Raiders
NFL> Last 5 games for Cowboys
NFL> exit
```

## Prediction Methodology

### Core Metrics

The prediction engine considers:

1. **Overall Win/Loss Record** (30% weight)
   - Weighted by recency (exponential decay)
   - Current season weighted 3x vs previous seasons

2. **Offensive/Defensive Strength** (25% weight)
   - Points scored vs league average
   - Points allowed vs league average

3. **Recent Form** (20% weight)
   - Last 5 games performance
   - Recent point differential

4. **Home/Away Splits** (15% weight)
   - Home team's home record
   - Away team's road record

5. **Head-to-Head Record** (10% weight)
   - Last 10 matchups between teams

6. **Home Field Advantage**
   - ~3.2% added to home team probability

### Confidence Levels

- **High**: 20+ games of data for both teams
- **Medium**: 8-19 games of data
- **Low**: Less than 8 games of data

## Game Factors (Advanced)

The system supports custom factors for more refined predictions:

### Adding Factors

```bash
# Add a factor via CLI
python -m src.cli.main --add-factor GAME_ID TEAM_ID FACTOR_TYPE IMPACT --factor-desc "Description"

# Example: Team has key injuries (-3 impact)
python -m src.cli.main --add-factor 1234 5 injury_impact -3 --factor-desc "Starting QB out"
```

### Available Factor Types

| Factor Type | Description |
|-------------|-------------|
| `better_defense` | Team has defensive advantage |
| `bad_defense` | Team has defensive weakness |
| `better_offense` | Team has offensive advantage |
| `bad_offense` | Team has offensive weakness |
| `better_qb` | Team has quarterback advantage |
| `qb_struggles` | Quarterback is struggling |
| `turnover_prone` | Team turns the ball over frequently |
| `turnover_forcing` | Team forces turnovers |
| `injury_impact` | Key injuries affecting performance |
| `weather_impact` | Weather conditions favor/hurt team |
| `coaching_advantage` | Coaching staff has edge |
| `motivation_factor` | Extra motivation (revenge, playoffs) |
| `custom` | Custom factor with description |

### Impact Rating Scale

- **-5**: Very negative impact
- **-3**: Moderate negative impact
- **-1**: Slight negative impact
- **0**: Neutral
- **+1**: Slight positive impact
- **+3**: Moderate positive impact
- **+5**: Very positive impact

### Bulk Import Factors

```bash
python -m src.cli.main --import-factors factors.csv
```

CSV format:
```csv
game_id,team_id,factor_type,description,impact_rating
1234,5,injury_impact,Starting QB out,-3
1234,8,motivation_factor,Playoff implications,2
```

## Project Structure

```
nfl-predictor/
├── src/
│   ├── database/
│   │   ├── schema.sql      # Database schema
│   │   ├── db.py           # Connection handling
│   │   └── models.py       # Data classes
│   ├── scraper/
│   │   ├── pfr_scraper.py  # Pro Football Reference scraper
│   │   └── team_mappings.py # Team name changes/relocations
│   ├── prediction/
│   │   ├── engine.py       # Core prediction logic
│   │   ├── metrics.py      # Stat calculations
│   │   └── factors.py      # Factor adjustments
│   ├── cli/
│   │   └── main.py         # Query interface
│   └── utils/
│       └── helpers.py      # Utility functions
├── data/
│   └── nfl.db              # SQLite database
├── tests/
├── requirements.txt
└── README.md
```

## Database Schema

### Teams Table
- All 32 current NFL teams
- Historical franchise information (relocations, name changes)

### Games Table
- Regular season and playoff games
- Scores, venues, attendance
- Support for overtime games

### Game Factors Table
- Custom factors affecting predictions
- Impact ratings (-5 to +5)
- Factor type categorization

### Team Season Stats Table
- Aggregated season statistics
- Win/loss records, point differentials
- Home/away splits

## Technical Details

- **Python**: 3.10+
- **Database**: SQLite (no external database required)
- **Scraping**: BeautifulSoup4 with rate limiting (4s between requests)
- **Data Source**: Pro Football Reference

## Handling Team Relocations

The system correctly handles:
- St. Louis/Los Angeles Rams
- San Diego/Los Angeles Chargers
- Oakland/Las Vegas Raiders
- Houston Oilers/Tennessee Titans
- Washington name changes
- Baltimore Colts/Indianapolis Colts
- And other historical changes

## Resumable Scraping

If scraping is interrupted, it will resume from where it left off:

```bash
# Check progress
python -m src.scraper.pfr_scraper --progress

# Resume scraping (automatically skips completed seasons)
python -m src.cli.main --scrape
```

## License

MIT License
