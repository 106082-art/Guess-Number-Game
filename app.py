import random
import os
from flask import Flask, render_template, request, jsonify, session

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "guess-number-secret")

BEST_SCORE_DIR = "scores"
os.makedirs(BEST_SCORE_DIR, exist_ok=True)

def load_best(max_range):
    path = os.path.join(BEST_SCORE_DIR, f"best_{max_range}.txt")
    if os.path.exists(path):
        content = open(path).read().strip()
        return int(content) if content else None
    return None

def save_best(max_range, score):
    path = os.path.join(BEST_SCORE_DIR, f"best_{max_range}.txt")
    with open(path, "w") as f:
        f.write(str(score))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/start", methods=["POST"])
def start():
    data = request.json
    mode = data.get("mode")  # "casual" or "competitive"
    min_val = int(data.get("min", 1))
    max_val = int(data.get("max", 100))

    if min_val >= max_val:
        return jsonify({"error": "Max must be greater than Min"}), 400

    session["num"] = random.randint(min_val, max_val)
    session["min"] = min_val
    session["max"] = max_val
    session["count"] = 0
    session["mode"] = mode
    session["difficulty"] = max_val if mode == "competitive" else 0

    return jsonify({"ok": True, "min": min_val, "max": max_val})

@app.route("/api/guess", methods=["POST"])
def guess():
    data = request.json
    try:
        a = int(data.get("guess"))
    except (TypeError, ValueError):
        return jsonify({"error": "Enter a valid number"}), 400

    num = session.get("num")
    cur_min = session.get("min")
    cur_max = session.get("max")
    count = session.get("count", 0)
    difficulty = session.get("difficulty", 0)

    if num is None:
        return jsonify({"error": "No game in progress"}), 400

    if a < cur_min or a > cur_max:
        return jsonify({"error": f"Out of range! Guess between {cur_min} and {cur_max}"}), 400

    count += 1
    session["count"] = count

    if a == num:
        # Check best score
        best = load_best(difficulty) if difficulty else None
        new_record = False
        if difficulty and (best is None or count < best):
            save_best(difficulty, count)
            new_record = True
            best = count
        return jsonify({
            "result": "win",
            "count": count,
            "new_record": new_record,
            "best": best,
        })

    if a > num:
        session["max"] = a
        hint = "Too high! Go lower."
    else:
        session["min"] = a
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
