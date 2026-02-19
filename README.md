# SportPulse

Sports stats toolkit for working with box scores, team schedules, and ELO rating trends. Includes a command-line interface and a lightweight JSON API.

## Features

- **Box scores** — parse and summarize game results with per-team totals
- **Schedules** — build and filter team calendars by date range
- **ELO trends** — track rating changes across a season with configurable K-factor
- **Ratings leaderboard** — replay a season file and rank every team by current ELO
- **League standings** — rank every team by win/loss record and point differential
- **Matchups** — project today's slate with odds-lite win probabilities, spreads, moneylines, and scoring totals
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

# League ELO leaderboard from the sample season
sportpulse ratings --file examples/season.json

# Same leaderboard in a terminal-friendly table
sportpulse ratings --file examples/season.json --output table

# League win/loss standings from the sample season
sportpulse standings --file examples/season.json

# Same standings in a terminal-friendly table
sportpulse standings --file examples/season.json --output table

# Standings for a date window (only teams that played in the range appear)
sportpulse standings --file examples/season.json \
  --start-date 2026-01-11 --end-date 2026-01-31

# Filtered record for games in a date range (ELO still uses the full file)
sportpulse season-report --team Lakers --file examples/season.json \
  --start-date 2026-01-11 --end-date 2026-01-31

# Today's slate with odds-lite projections (ELO win %, spread, moneylines, O/U totals)
sportpulse matchups --file examples/matchups.json --history examples/season.json \
  --date 2026-01-16

# Zero-flag today board when sportpulse.json is present (auto-discovers examples/)
sportpulse today --date 2026-01-16

# Same slate in a terminal-friendly table
sportpulse matchups --file examples/matchups.json --history examples/season.json \
  --date 2026-01-16 --format table

# Quick look at today's slate (table output; auto-rolls to the next day when empty)
sportpulse today --file examples/matchups.json --history examples/season.json \
  --date 2026-01-15

# Force the exact requested day even when it has no games
sportpulse today --file examples/matchups.json --history examples/season.json \
  --date 2026-01-15 --no-next

# Filter to one team's upcoming matchup
sportpulse today --file examples/matchups.json --history examples/season.json \
  --date 2026-01-16 --team Lakers

# Start the JSON API on port 8080
sportpulse serve --port 8080
```

### Configuration

`sportpulse today` and `sportpulse matchups` can run without `--file` when a config file is present. The CLI walks up from the current directory looking for `sportpulse.json` or `.sportpulse.json`:

```json
{
  "matchups_file": "examples/matchups.json",
  "history_file": "examples/season.json",
  "k_factor": 20,
  "home_advantage": 65,
  "points_per_100_elo": 4,
  "home_court_points": 2.5
}
```

`points_per_100_elo` controls how ELO gaps translate to point spreads. `home_court_points` adjusts projected scoring totals for the home team.

The `today` and `matchups` commands include an odds-lite `summary` block (JSON) and a one-line slate digest (table) with favorite counts, average projected total, and notable matchups.

Paths are resolved relative to the config file. Environment variables override config values:

- `SPORTPULSE_MATCHUPS_FILE`
- `SPORTPULSE_HISTORY_FILE`

When no config exists, the CLI falls back to `examples/` in the repo root (editable installs).

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

The `examples/` directory ships a short four-game sample season spanning five teams (Lakers, Celtics, Warriors, Knicks, and Heat). Import it as JSON or CSV to try season reports, ELO leaderboards, and league standings.

| Date | Matchup | Score |
|------|---------|-------|
| 2026-01-10 | Lakers vs Celtics | 112–108 |
| 2026-01-12 | Warriors @ Lakers | 99–102 |
| 2026-01-14 | Lakers vs Knicks | 105–101 |
| 2026-01-16 | Heat @ Lakers | 110–110 (tie) |

Lakers finish **3–0–1** (+11 point differential); every other team appears once in the file.

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

League standings from the same file (Lakers lead on win percentage and point differential):

```bash
sportpulse standings --file examples/season.json --output table
```

Example output:

```
League standings — 4 game(s)

 RK TEAM               W-L-T    PCT   DIFF    AVG
-------------------------------------------------
  1 Lakers             3-0-1  0.750    +11   +2.8
  2 Heat               0-0-1  0.000     +0   +0.0
  3 Warriors           0-1-0  0.000     -3   -3.0
  4 Celtics            0-1-0  0.000     -4   -4.0
  5 Knicks             0-1-0  0.000     -4   -4.0
```

The same workflow in Python:

```python
from datetime import date

from sportpulse.elo import EloCalculator
from sportpulse.models import EloRating
from sportpulse.parsers import load_box_scores
from sportpulse.schedule import Schedule
from sportpulse.standings import build_standings_report

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

standings = build_standings_report(scores)
print(standings["standings"][0]["team"])  # "Lakers"
```

Both the CLI and library examples above read from `examples/season.json` (or the equivalent CSV).

### JSON API

When the API server is running (`sportpulse serve --port 8080`), the sample season is available over HTTP:

```bash
curl "http://127.0.0.1:8080/standings?file=examples/season.json"
curl "http://127.0.0.1:8080/ratings?file=examples/season.json"
```

Optional query parameters for `/standings`: `start_date`, `end_date`, and `tie_breaker` (`win_pct`, `point_diff`, or `team_name`).

## Caching

SportPulse keeps parsed schedule files and derived reports in an in-process cache keyed by file modification time. Repeated CLI or API calls against unchanged data skip disk I/O, JSON parsing, and ELO replay.

- **File loaders** — `load_box_scores`, `load_matchups`, and `load_team_schedule` cache parsed file contents.
- **Report loaders** — `load_matchups_report` and `load_season_report` (in `sportpulse.schedule_cache`) cache fully built matchups and season reports.

Caches invalidate automatically when a source file's mtime or size changes. Call `clear_schedule_report_cache()` (or the module-specific `clear_*_cache()` helpers) in tests or long-running processes when you need a fresh read.

## Development

```bash
pytest
```

## License

MIT
