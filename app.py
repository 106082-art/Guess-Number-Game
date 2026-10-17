
import os
import math
import random
import threading
from contextlib import contextmanager

import psycopg2 as psycopg
from psycopg2.extras import RealDictCursor as dict_row
from flask import Flask, render_template, request, jsonify, session

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SESSION_SECRET", "guess-number-secret-change-this"
)

CHEAT_CODE = "112358132134558914423337761098715972584418167651094617711"
SUPPORTED_LEVELS = {100, 1000, 10000}
MAX_GAME_NUMBER = 2_147_483_647
MAX_USERNAME_LENGTH = 80

_schema_lock = threading.Lock()
_schema_ready = False


@contextmanager
def db_connection():
    """Connect to Neon and ensure the required tables exist."""
    global _schema_ready

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    conn = psycopg.connect(
        database_url,
        connect_timeout=10,
        row_factory=dict_row,
    )

    try:
        if not _schema_ready:
            with _schema_lock:
                if not _schema_ready:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS best_scores (
                            level INTEGER PRIMARY KEY,
                            attempts INTEGER NOT NULL
                                CHECK (attempts > 0)
                        )
                    """)

                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS leaderboard (
                            id BIGSERIAL PRIMARY KEY,
                            level INTEGER NOT NULL,
                            username VARCHAR(80) NOT NULL,
                            attempts INTEGER NOT NULL
                                CHECK (attempts > 0),
                            time_taken DOUBLE PRECISION NOT NULL
                                CHECK (
                                    time_taken >= 0
                                    AND time_taken <= 86400
                                ),
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                    """)

                    conn.execute("""
                        CREATE INDEX IF NOT EXISTS leaderboard_ranking_idx
                        ON leaderboard (
                            level,
                            attempts,
                            time_taken,
                            created_at,
                            id
                        )
                    """)

                    conn.commit()
                    _schema_ready = True

        yield conn
        conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def parse_integer(value):
    if type(value) is int:
        return value

    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None

    return None


def load_best(level):
    try:
        with db_connection() as conn:
            row = conn.execute(
                "SELECT attempts FROM best_scores WHERE level = %s",
                (level,),
            ).fetchone()

            return row["attempts"] if row else None

    except Exception:
        app.logger.exception("Could not load best score for level %s", level)
        return None


def save_best(level, attempts):
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO best_scores (level, attempts)
            VALUES (%s, %s)
            ON CONFLICT (level)
            DO UPDATE SET attempts =
                LEAST(best_scores.attempts, EXCLUDED.attempts)
            """,
            (level, attempts),
        )


def get_leaderboard(level):
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT username, attempts, time_taken, created_at
            FROM leaderboard
            WHERE level = %s
            ORDER BY attempts ASC, time_taken ASC, created_at ASC, id ASC
            LIMIT 10
            """,
            (level,),
        ).fetchall()

    return [
        {
            "username": row["username"],
            "attempts": row["attempts"],
            "time_taken": row["time_taken"],
            "created_at": row["created_at"].isoformat(),
        }
        for row in rows
    ]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    return "", 204


@app.route("/api/start", methods=["POST"])
def start():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    mode = data.get("mode")
    if mode not in {"casual", "competitive"}:
        return jsonify({"error": "mode must be casual or competitive"}), 400

    min_val = parse_integer(data.get("min", 1))
    max_val = parse_integer(data.get("max", data.get("level", 100)))

    if min_val is None or max_val is None:
        return jsonify({"error": "Min and Max must be whole numbers"}), 400

    if min_val < 0 or max_val > MAX_GAME_NUMBER:
        return jsonify({
            "error": f"Numbers must be between 0 and {MAX_GAME_NUMBER}"
        }), 400

    if min_val >= max_val:
        return jsonify({"error": "Max must be greater than Min"}), 400

    if mode == "competitive" and (
        min_val != 1 or max_val not in SUPPORTED_LEVELS
    ):
        return jsonify({
            "error": "Competitive levels must be 100, 1000, or 10000 "
                     "with a minimum of 1"
        }), 400

    session["num"] = random.randint(min_val, max_val)
    session["min"] = min_val
    session["max"] = max_val
    session["count"] = 0
    session["mode"] = mode
    session["difficulty"] = max_val if mode == "competitive" else 0

    return jsonify({"ok": True, "min": min_val, "max": max_val})


@app.route("/api/guess", methods=["POST"])
def guess():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    submitted_guess = data.get("guess")
    num = session.get("num")

    if num is None:
        return jsonify({"error": "No game in progress"}), 400

    if str(submitted_guess).strip() == CHEAT_CODE:
        return jsonify({
            "result": "cheat",
            "answer": num,
            "count": session.get("count", 0),
        })

    a = parse_integer(submitted_guess)
    if a is None:
        return jsonify({"error": "Enter a valid number"}), 400

    cur_min = session.get("min")
    cur_max = session.get("max")
    count = session.get("count", 0)
    difficulty = session.get("difficulty", 0)

    if a < cur_min or a > cur_max:
        return jsonify({
            "error": f"Out of range! Guess between {cur_min} and {cur_max}"
        }), 400

    count += 1
    session["count"] = count

    if a == num:
        best = load_best(difficulty) if difficulty else None
        new_record = False

        if difficulty and (best is None or count < best):
            try:
                save_best(difficulty, count)
                new_record = True
                best = min(best, count) if best is not None else count
            except Exception:
                app.logger.exception(
                    "Could not save best score for level %s", difficulty
                )

        return jsonify({
            "result": "win",
            "count": count,
            "new_record": new_record,
            "best": best,
        })

    if a > num:
        session["max"] = a - 1
        hint = "Too high! Go lower."
    else:
        session["min"] = a + 1
        hint = "Too low! Go higher."

    return jsonify({
        "result": "wrong",
        "hint": hint,
        "min": session["min"],
        "max": session["max"],
        "count": count,
    })


@app.route("/api/best_scores", methods=["GET"])
def best_scores():
    scores = {}

    for level in sorted(SUPPORTED_LEVELS):
        scores[level] = load_best(level)

    return jsonify(scores)


@app.route("/api/leaderboard", methods=["GET"])
def leaderboard():
    level = parse_integer(request.args.get("level", "100"))

    if level not in SUPPORTED_LEVELS:
        return jsonify({"error": "Invalid leaderboard level"}), 400

    try:
        # The frontend expects an array, not a dictionary.
        return jsonify(get_leaderboard(level))
    except Exception:
        app.logger.exception("Could not load leaderboard")
        return jsonify({"error": "Leaderboard is temporarily unavailable"}), 503


@app.route("/api/score", methods=["POST"])
def submit_score():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    username = data.get("username")
    level = parse_integer(data.get("level"))
    attempts = parse_integer(data.get("attempts"))

    if not isinstance(username, str):
        return jsonify({"error": "Username is required"}), 400

    username = username.strip()

    if not username or len(username) > MAX_USERNAME_LENGTH:
        return jsonify({
            "error": f"Username must be 1-{MAX_USERNAME_LENGTH} characters"
        }), 400

    if level not in SUPPORTED_LEVELS:
        return jsonify({"error": "Invalid level"}), 400

    if attempts is None or attempts < 1:
        return jsonify({"error": "Attempts must be a positive integer"}), 400

    raw_time = data.get("time_taken")

    try:
        time_taken = float(raw_time)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid game time"}), 400

    if not math.isfinite(time_taken) or not 0 <= time_taken <= 86400:
        return jsonify({"error": "Invalid game time"}), 400

    try:
        with db_connection() as conn:
            # Serialize submissions for the same level while ranking/pruning.
            conn.execute(
                "SELECT pg_advisory_xact_lock(%s)",
                (level,),
            )

            inserted = conn.execute(
                """
                INSERT INTO leaderboard (
                    level, username, attempts, time_taken
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (level, username, attempts, time_taken),
            ).fetchone()

            new_id = inserted["id"]

            ranked = conn.execute(
                """
                SELECT id,
                       ROW_NUMBER() OVER (
                           ORDER BY attempts ASC,
                                    time_taken ASC,
                                    created_at ASC,
                                    id ASC
                       ) AS rank
                FROM leaderboard
                WHERE level = %s
                ORDER BY attempts ASC, time_taken ASC, created_at ASC, id ASC
                """,
                (level,),
            ).fetchall()

            rank = next(
                (row["rank"] for row in ranked if row["id"] == new_id),
                None,
            )

            conn.execute(
                """
                DELETE FROM leaderboard
                WHERE level = %s
                  AND id NOT IN (
                      SELECT id
                      FROM leaderboard
                      WHERE level = %s
                      ORDER BY attempts ASC,
                               time_taken ASC,
                               created_at ASC,
                               id ASC
                      LIMIT 10
                  )
                """,
                (level, level),
            )

        return jsonify({
            "ok": True,
            "qualified": rank is not None and rank <= 10,
            "rank": rank if rank is not None and rank <= 10 else None,
        }), 201

    except Exception:
        app.logger.exception("Could not save leaderboard score")
        return jsonify({"error": "Could not save score right now"}), 503


@app.route("/api/clear_scores", methods=["POST"])
def clear_scores():
    try:
        with db_connection() as conn:
            conn.execute("DELETE FROM best_scores")
            conn.execute("DELETE FROM leaderboard")

        return jsonify({"ok": True})

    except Exception:
        app.logger.exception("Could not clear scores")
        return jsonify({"error": "Could not clear scores"}), 503


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)

