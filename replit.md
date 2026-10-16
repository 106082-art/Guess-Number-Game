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

- `POST /api/score` — save `{ "name": "Ada", "score": 10, "level": 100 }`
- `GET /api/leaderboard?level=100` — return the top ten scores, lowest first
- `GET /ping` — health check (`Server is running`)

The server creates the `leaderboard` table and its query index on startup when
`DATABASE_URL` is set. The variable should be supplied by the hosting platform;
on Render, configure it with the Render PostgreSQL connection string. If it is
missing, the game still starts, but leaderboard requests return HTTP 503.

## Stack

- Python 3.12
- Flask, Flask-CORS, psycopg2-binary, Gunicorn
