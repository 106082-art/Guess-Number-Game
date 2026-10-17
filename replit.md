# Guess Number Game

A Flask web game with a PostgreSQL-backed leaderboard API.

## Run

Install dependencies and start the server:
```bash
pip install -r requirements.txt
python main.py
```

The existing game UI and its routes are served alongside the leaderboard API.

## Leaderboard API

- `POST /api/score` — save a winning score for level `100`, `1000`, or `10000`
- `GET /api/leaderboard?level=100` — return the top ten for the selected level, ordered by fewest attempts and then fastest time. Supported levels: `100`, `1000`, `10000`.
- `GET /api/best_scores` — return the local best attempt count for each supported level
- `GET /ping` — health check (`Server is running`)

The server creates or upgrades the `leaderboard` table on startup. It reads
`NEON_DATABASE_URL` first when present (to override Replit's reserved
`DATABASE_URL` in this workspace), then falls back to `DATABASE_URL`. On Neon,
configure the appropriate variable with the Neon PostgreSQL connection string.
If neither is available, the game still starts, but leaderboard requests return
HTTP 503.

## Stack

- Python 3.12
- Flask, Flask-CORS, psycopg2-binary, Gunicorn
