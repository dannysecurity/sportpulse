# SportPulse

Sports stats toolkit for working with box scores, team schedules, and ELO rating trends. Includes a command-line interface and a lightweight JSON API.

## Features

- **Box scores** — parse and summarize game results with per-team totals
- **Schedules** — build and filter team calendars by date range
- **ELO trends** — track rating changes across a season with configurable K-factor
- **Matchups** — project today's slate with odds-lite win probabilities, spreads, and moneylines
- **CLI** — inspect data from the terminal
- **JSON API** — serve stats over HTTP for integrations

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## CLI Usage

```bash
# Summarize a box score
sportpulse boxscore --home "Lakers" --away "Celtics" --home-score 112 --away-score 108

# Show ELO trend after a result
sportpulse elo --team-a "Lakers" --rating-a 1580 --team-b "Celtics" --rating-b 1620 --score-a 112 --score-b 108

# Import historical box scores from JSON or CSV
sportpulse import-boxscores --file examples/season.json

# Team record and ELO trend from the sample season
sportpulse season-report --team Lakers --file examples/season.json

# Filtered record for games in a date range (ELO still uses the full file)
sportpulse season-report --team Lakers --file examples/season.json \
  --start-date 2026-01-11 --end-date 2026-01-31

# Today's slate with odds-lite projections (ELO win %, spread, moneylines)
sportpulse matchups --file examples/matchups.json --history examples/season.json \
  --date 2026-01-16

# Same slate in a terminal-friendly table
sportpulse matchups --file examples/matchups.json --history examples/season.json \
  --date 2026-01-16 --format table

# Start the JSON API on port 8080
sportpulse serve --port 8080
```

## Library Usage

```python
from sportpulse.boxscore import BoxScore
from sportpulse.elo import EloCalculator
from sportpulse.parsers import load_box_scores

game = BoxScore(home="Lakers", away="Celtics", home_score=112, away_score=108)
print(game.winner())  # "Lakers"

for box in load_box_scores("examples/season.csv"):
    print(box.summary())

calc = EloCalculator(k_factor=20)
updated = calc.update(1580, 1620, home_score=112, away_score=108)
print(updated)  # (1589.2, 1610.8)
```

## Sample season data

The `examples/` directory ships a short Lakers sample season you can import as JSON or CSV.

**JSON** (`examples/season.json`) — schedule wrapper with optional dates:

```json
{
  "team": "Lakers",
  "games": [
    {
      "home": "Lakers",
      "away": "Celtics",
      "home_score": 112,
      "away_score": 108,
      "played_on": "2026-01-10"
    },
    {
      "home": "Warriors",
      "away": "Lakers",
      "home_score": 99,
      "away_score": 102,
      "played_on": "2026-01-12"
    }
  ]
}
```

**CSV** (`examples/season.csv`) — one game per row with a header:

```csv
home,away,home_score,away_score,played_on
Lakers,Celtics,112,108,2026-01-10
Warriors,Lakers,99,102,2026-01-12
```

Load the sample season and compute a team record plus ELO trend:

```bash
sportpulse season-report --team Lakers --file examples/season.json
```

Example output (truncated):

```json
{
  "team": "Lakers",
  "games_played": 4,
  "record": {"wins": 3, "losses": 0, "ties": 1},
  "elo_rating": 1560.5,
  "elo_trend": [
    {"played_on": "2026-01-10", "rating": 1500.0},
    {"played_on": "2026-01-12", "rating": 1523.2}
  ]
}
```

Filter the record to a date window while still replaying every game for ELO:

```bash
sportpulse season-report --team Lakers --file examples/season.json \
  --start-date 2026-01-11 --end-date 2026-01-31
```

The same workflow in Python:
from datetime import date

from sportpulse.elo import EloCalculator
from sportpulse.models import EloRating
from sportpulse.parsers import load_box_scores
from sportpulse.schedule import Schedule

scores = load_box_scores("examples/season.json")
schedule = Schedule(team="Lakers")
for box in scores:
    schedule.add(box.to_result())

print(schedule.record())  # {"wins": 3, "losses": 0, "ties": 1}
print(
    schedule.record_in_range(date(2026, 1, 11), date(2026, 1, 31))
)  # {"wins": 2, "losses": 0, "ties": 1}

calc = EloCalculator()
ratings: dict[str, EloRating] = {}
for box in scores:
    calc.apply_result(
        ratings,
        box.home,
        box.away,
        box.home_score,
        box.away_score,
        box.played_on,
    )
print(calc.trend(ratings["Lakers"]))
```

Both the CLI and library examples above read from `examples/season.json` (or the equivalent CSV).

## Development

```bash
pytest
```

## License

MIT
