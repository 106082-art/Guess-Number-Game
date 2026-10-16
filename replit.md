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

- `POST /api/score` — save `{ "username": "Ada", "level": 100, "attempts": 10, "time_taken": 12.4 }`
- `GET /api/leaderboard?level=100` — return the top ten scores by fewest attempts, then fastest time
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
