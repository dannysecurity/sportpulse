# SportPulse

Sports stats toolkit for working with box scores, team schedules, and ELO rating trends. Includes a command-line interface and a lightweight JSON API.

## Features

- **Box scores** — parse and summarize game results with per-team totals
- **Schedules** — build and filter team calendars by date range
- **ELO trends** — track rating changes across a season with configurable K-factor
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
sportpulse import-boxscores --file data/season.json

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

for box in load_box_scores("data/season.csv"):
    print(box.summary())

calc = EloCalculator(k_factor=20)
updated = calc.update(1580, 1620, home_score=112, away_score=108)
print(updated)  # (1589.2, 1610.8)
```

## Development

```bash
pytest
```

## License

MIT
