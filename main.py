import os

import psycopg2
from flask import jsonify, request
from flask_cors import CORS

from app import app

CORS(app, resources={r"/*": {"origins": "*"}})


class DatabaseNotConfigured(RuntimeError):
    """Raised when DATABASE_URL has not been supplied by the hosting environment."""


def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise DatabaseNotConfigured("DATABASE_URL is not configured")
    # libpq's default "prefer" mode uses TLS when the server supports it,
    # while still allowing local PostgreSQL instances without TLS.
    return psycopg2.connect(database_url)


def initialize_database():
    """Create the leaderboard table and query index when the server starts."""
    try:
        connection = get_db_connection()
    except DatabaseNotConfigured as exc:
        app.logger.warning("%s; leaderboard database setup was skipped.", exc)
        return False

    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS leaderboard (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(80) NOT NULL,
                        score INTEGER NOT NULL,
                        level INTEGER NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS leaderboard_level_score_idx
                    ON leaderboard (level, score ASC, created_at ASC, id ASC)
                    """
                )
        app.logger.info("Leaderboard table is ready.")
        return True
    finally:
        connection.close()


def database_error_response(error):
    if isinstance(error, DatabaseNotConfigured):
        app.logger.warning("%s", error)
        message = "Leaderboard database is not configured"
    else:
        app.logger.exception("Leaderboard database request failed")
        message = "Leaderboard database is unavailable"
    return jsonify({"error": message}), 503


@app.route("/ping", methods=["GET"])
def ping():
    return "Server is running", 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/api/score", methods=["POST"])
def submit_score():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    name = data.get("name")
    score = data.get("score")
    level = data.get("level")

    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "name must be a non-empty string"}), 400
    name = name.strip()
    if len(name) > 80:
        return jsonify({"error": "name must be 80 characters or fewer"}), 400
    if type(score) is not int or score < 0:
        return jsonify({"error": "score must be a non-negative integer"}), 400
    if type(level) is not int or level < 1:
        return jsonify({"error": "level must be a positive integer"}), 400

    try:
        connection = get_db_connection()
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO leaderboard (name, score, level)
                        VALUES (%s, %s, %s)
                        RETURNING id, created_at
                        """,
                        (name, score, level),
                    )
                    record_id, created_at = cursor.fetchone()
            return jsonify(
                {
                    "id": record_id,
                    "name": name,
                    "score": score,
                    "level": level,
                    "created_at": created_at.isoformat(),
                }
            ), 201
        finally:
            connection.close()
    except (DatabaseNotConfigured, psycopg2.Error) as exc:
        return database_error_response(exc)


@app.route("/api/leaderboard", methods=["GET"])
def get_leaderboard():
    level_value = request.args.get("level")
    try:
        level = int(level_value)
        if level < 1:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "level must be a positive integer"}), 400

    try:
        connection = get_db_connection()
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id, name, score, level, created_at
                        FROM leaderboard
                        WHERE level = %s
                        ORDER BY score ASC, created_at ASC, id ASC
                        LIMIT 10
                        """,
                        (level,),
                    )
                    records = cursor.fetchall()
            return jsonify(
                [
                    {
                        "id": record_id,
                        "name": name,
                        "score": score,
                        "level": record_level,
                        "created_at": created_at.isoformat(),
                    }
                    for record_id, name, score, record_level, created_at in records
                ]
            )
        finally:
            connection.close()
    except (DatabaseNotConfigured, psycopg2.Error) as exc:
        return database_error_response(exc)


# Initialize the table during application startup when the host has supplied
# DATABASE_URL. Without it, the game still runs and leaderboard routes return 503.
initialize_database()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
