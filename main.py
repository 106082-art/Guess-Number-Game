import math
import os

import psycopg2
from flask import jsonify, request
from flask_cors import CORS

from app import app

CORS(app, resources={r"/*": {"origins": "*"}})
SUPPORTED_LEVELS = {100, 1000, 10000}


class DatabaseNotConfigured(RuntimeError):
    """Raised when DATABASE_URL has not been supplied by the hosting environment."""


def get_db_connection():
    # Replit reserves DATABASE_URL for its own database. Allow a Neon-specific
    # secret to override it in Replit while keeping DATABASE_URL for other hosts.
    database_url = os.environ.get("NEON_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        raise DatabaseNotConfigured("No PostgreSQL connection URL is configured")
    # libpq's default "prefer" mode uses TLS when the server supports it,
    # while still allowing local PostgreSQL instances without TLS.
    return psycopg2.connect(database_url)


def initialize_database():
    """Create or upgrade the leaderboard table without deleting existing rows."""
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
                        username VARCHAR(80) NOT NULL,
                        level INTEGER NOT NULL,
                        attempts INTEGER NOT NULL,
                        time_taken DOUBLE PRECISION,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    ALTER TABLE leaderboard
                    ADD COLUMN IF NOT EXISTS username VARCHAR(80)
                    """
                )
                cursor.execute(
                    """
                    ALTER TABLE leaderboard
                    ADD COLUMN IF NOT EXISTS attempts INTEGER
                    """
                )
                cursor.execute(
                    """
                    ALTER TABLE leaderboard
                    ADD COLUMN IF NOT EXISTS time_taken DOUBLE PRECISION
                    """
                )
                cursor.execute(
                    """
                    ALTER TABLE leaderboard
                    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    """
                )
                cursor.execute(
                    "UPDATE leaderboard SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
                )
                cursor.execute(
                    """
                    ALTER TABLE leaderboard
                    ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP
                    """
                )
                cursor.execute(
                    """
                    ALTER TABLE leaderboard
                    ALTER COLUMN created_at SET NOT NULL
                    """
                )
                cursor.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'leaderboard'
                    """
                )
                columns = {row[0] for row in cursor.fetchall()}

                # Migrate the older name/score schema in place, retaining rows.
                if "name" in columns:
                    cursor.execute(
                        """
                        UPDATE leaderboard
                        SET username = name
                        WHERE username IS NULL OR BTRIM(username) = ''
                        """
                    )
                if "score" in columns:
                    cursor.execute(
                        """
                        UPDATE leaderboard
                        SET attempts = score
                        WHERE attempts IS NULL
                        """
                    )
                cursor.execute(
                    """
                    UPDATE leaderboard
                    SET username = 'Guest'
                    WHERE username IS NULL OR BTRIM(username) = ''
                    """
                )
                cursor.execute(
                    "UPDATE leaderboard SET attempts = 0 WHERE attempts IS NULL"
                )
                cursor.execute(
                    """
                    ALTER TABLE leaderboard
                    ALTER COLUMN username SET NOT NULL
                    """
                )
                cursor.execute(
                    """
                    ALTER TABLE leaderboard
                    ALTER COLUMN attempts SET NOT NULL
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS leaderboard_level_attempts_time_idx
                    ON leaderboard (
                        level,
                        attempts ASC,
                        time_taken ASC NULLS LAST,
                        created_at ASC,
                        id ASC
                    )
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

    username = data.get("username")
    attempts = data.get("attempts")
    level = data.get("level")
    time_taken = data.get("time_taken")

    if not isinstance(username, str) or not username.strip():
        return jsonify({"error": "username must be a non-empty string"}), 400
    username = username.strip()
    if len(username) > 80:
        return jsonify({"error": "username must be 80 characters or fewer"}), 400
    if type(attempts) is not int or not 1 <= attempts <= 2_147_483_647:
        return jsonify({"error": "attempts must be a positive integer"}), 400
    if type(level) is not int or level not in SUPPORTED_LEVELS:
        return jsonify({"error": "level must be 100, 1000, or 10000"}), 400
    if (
        isinstance(time_taken, bool)
        or not isinstance(time_taken, (int, float))
    ):
        return jsonify({"error": "time_taken must be a non-negative number"}), 400
    try:
        time_taken = float(time_taken)
    except OverflowError:
        return jsonify({"error": "time_taken must be a finite number"}), 400
    if not math.isfinite(time_taken) or time_taken < 0:
        return jsonify({"error": "time_taken must be a finite non-negative number"}), 400

    try:
        connection = get_db_connection()
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO leaderboard (username, level, attempts, time_taken)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id, created_at
                        """,
                        (username, level, attempts, time_taken),
                    )
                    record_id, created_at = cursor.fetchone()
            return jsonify(
                {
                    "id": record_id,
                    "username": username,
                    "level": level,
                    "attempts": attempts,
                    "time_taken": time_taken,
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
        if level not in SUPPORTED_LEVELS:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "level must be 100, 1000, or 10000"}), 400

    try:
        connection = get_db_connection()
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id, username, level, attempts, time_taken, created_at
                        FROM leaderboard
                        WHERE level = %s
                        ORDER BY
                            attempts ASC,
                            time_taken ASC NULLS LAST,
                            created_at ASC,
                            id ASC
                        LIMIT 10
                        """,
                        (level,),
                    )
                    records = cursor.fetchall()
            return jsonify(
                [
                    {
                        "id": record_id,
                        "username": username,
                        "level": record_level,
                        "attempts": attempts,
                        "time_taken": time_taken,
                        "created_at": created_at.isoformat(),
                    }
                    for (
                        record_id,
                        username,
                        record_level,
                        attempts,
                        time_taken,
                        created_at,
                    ) in records
                ]
            )
        finally:
            connection.close()
    except (DatabaseNotConfigured, psycopg2.Error) as exc:
        return database_error_response(exc)


# Initialize the table during application startup when a PostgreSQL URL is set.
# Without one, the game still runs and leaderboard routes return 503.
initialize_database()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
