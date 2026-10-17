import random
import os
from flask import Flask, render_template, request, jsonify, session

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "guess-number-secret")

BEST_SCORE_DIR = "scores"
os.makedirs(BEST_SCORE_DIR, exist_ok=True)
CHEAT_CODE = "112358132134558914423337761098715972584418167651094617711"
SUPPORTED_LEVELS = {100, 1000, 10000}
MAX_GAME_NUMBER = 2_147_483_647


def parse_integer(value):
    if type(value) is int:
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None

def load_best(max_range):
    path = os.path.join(BEST_SCORE_DIR, f"best_{max_range}.txt")
    try:
        with open(path, "r") as f:
            content = f.read().strip()
    except FileNotFoundError:
        return None
    except OSError:
        app.logger.exception("Could not read the saved best score for range %s", max_range)
        return None
    if not content:
        return None
    try:
        return int(content)
    except ValueError:
        app.logger.warning("Ignoring an invalid saved best score for range %s", max_range)
        return None

def save_best(max_range, score):
    path = os.path.join(BEST_SCORE_DIR, f"best_{max_range}.txt")
    with open(path, "w") as f:
        f.write(str(score))

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
        return jsonify({"error": f"Numbers must be between 0 and {MAX_GAME_NUMBER}"}), 400

    if min_val >= max_val:
        return jsonify({"error": "Max must be greater than Min"}), 400
    if mode == "competitive" and (min_val != 1 or max_val not in SUPPORTED_LEVELS):
        return jsonify({
            "error": "Competitive levels must be 100, 1000, or 10000 with a minimum of 1"
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

    # Check the exact string before converting it or updating the attempt count.
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
        return jsonify({"error": f"Out of range! Guess between {cur_min} and {cur_max}"}), 400

    count += 1
    session["count"] = count

    if a == num:
        # Check best score
        best = load_best(difficulty) if difficulty else None
        new_record = False
        if difficulty and (best is None or count < best):
            try:
                save_best(difficulty, count)
                new_record = True
                best = count
            except OSError:
                app.logger.exception(
                    "Could not persist the local best score for range %s",
                    difficulty,
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
    for level in [100, 1000, 10000]:
        scores[level] = load_best(level)
    return jsonify(scores)

@app.route("/api/clear_scores", methods=["POST"])
def clear_scores():
    for level in [100, 1000, 10000]:
        path = os.path.join(BEST_SCORE_DIR, f"best_{level}.txt")
        if os.path.exists(path):
            os.remove(path)
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
