from flask import Flask, request, jsonify, render_template, Response, redirect, url_for, session
import bcrypt
import os
import threading
import time
import uuid
import random
import queue
import json
import sys

app = Flask(__name__)
app.secret_key = os.urandom(24)

ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH")
if not ADMIN_PASSWORD_HASH:
    print("\n❌ FOUT: ADMIN_PASSWORD_HASH is niet ingesteld als omgevingsvariabele.")
    print("Gebruik bijvoorbeeld:")
    print("  python -c \"import bcrypt; print(bcrypt.hashpw(b'geheim', bcrypt.gensalt()).decode())\"")
    print("en stel deze in via:")
    print("  export ADMIN_PASSWORD_HASH='...' (Linux/macOS)")
    print("  set ADMIN_PASSWORD_HASH=...       (Windows)")
    sys.exit(1)

TICK_INTERVAL = 1
games = {}  # pin -> game_state
game_queues = {}  # pin -> [queue.Queue()]
lock = threading.Lock()

# ----------------------- FRONTEND -----------------------


@app.route('/')
def index():
    leaderboard_data = {}
    with lock:
        for pin, game in games.items():
            leaderboard = []
            for token, score in game.get("scores", {}).items():
                player = game["players"].get(token)
                if player:
                    leaderboard.append({
                        "name": player["name"],
                        "score": score
                    })
            leaderboard.sort(key=lambda x: x["score"], reverse=True)
            leaderboard_data[pin] = leaderboard

    return render_template("index.html", games=games, leaderboards=leaderboard_data)
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    message = None
    if request.method == 'POST':
        grid_size = int(request.form.get("grid_size", 20))
        pin = generate_unique_pin()
        blocked_tiles = [
            {"x": random.randint(0, grid_size - 1), "y": random.randint(0, grid_size - 1)}
            for _ in range(grid_size // 2)
        ]
        # Kies een doel dat niet geblokkeerd is
        while True:
            goal = {"x": random.randint(0, grid_size - 1), "y": random.randint(0, grid_size - 1)}
            if goal not in blocked_tiles:
                break

        with lock:
            games[pin] = {
                "grid_size": grid_size,
                "players": {},
                "goal": goal,
                "winner": None,
                "blocked": blocked_tiles,
                "scores": {}  # token -> score
            }
            game_queues[pin] = []
        message = f"Nieuwe game aangemaakt met PIN: {pin} (grid {grid_size}x{grid_size})"

    return render_template("admin.html", games=games, message=message)

@app.route('/login', methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        pw_input = request.form.get("password", "").encode("utf-8")
        hash_bytes = ADMIN_PASSWORD_HASH.encode("utf-8")
        if bcrypt.checkpw(pw_input, hash_bytes):
            session['logged_in'] = True
            return redirect(url_for('admin'))
        else:
            error = "Ongeldig wachtwoord"
    return render_template("login.html", error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("login"))

# ----------------------- API -----------------------

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data.get("name")
    color = data.get("color")
    pin = data.get("pin")

    if not name or not color or not pin:
        return jsonify({"error": "Naam, kleur en PIN zijn verplicht"}), 400

    disallowed_colors = {"black", "yellow"}
    all_used_colors = set(disallowed_colors)

    with lock:
        if pin not in games:
            return jsonify({"error": "Ongeldige PIN"}), 404

        used_colors = {p["color"] for p in games[pin]["players"].values()}
        all_used_colors.update(used_colors)

        original_color = color
        available_colors = [
            c for c in ["red", "blue", "green", "orange", "purple", "pink", "cyan", "lime", "brown", "magenta", "teal"]
            if c not in all_used_colors
        ]

        if color in all_used_colors:
            if available_colors:
                color = random.choice(available_colors)
            else:
                return jsonify({"error": "Geen kleuren meer beschikbaar"}), 400

        token = str(uuid.uuid4())
        games[pin]["players"][token] = {
            "name": name,
            "color": color,
            "x": random.randint(0, games[pin]["grid_size"]-1),
            "y": random.randint(0, games[pin]["grid_size"]-1),
            "last_move": None
        }
        games[pin]["scores"][token] = 0

    response = {"token": token, "color": color}
    if color != original_color:
        response["notice"] = f"Kleur '{original_color}' was niet beschikbaar. Je hebt nu '{color}' gekregen."

    return jsonify(response)
@app.route('/api/move', methods=['POST'])
def move():
    data = request.get_json()
    token = data.get("token")
    direction = data.get("direction")
    pin = data.get("pin")

    if not token or not direction or not pin:
        return jsonify({"error": "Token, direction en PIN zijn verplicht"}), 400

    with lock:
        game = games.get(pin)
        if not game:
            return jsonify({"error": "Game niet gevonden"}), 404

        player = game["players"].get(token)
        if not player:
            return jsonify({"error": "Speler niet gevonden"}), 404

        dx, dy = 0, 0
        if direction == "up":
            dy = -1
        elif direction == "down":
            dy = 1
        elif direction == "left":
            dx = -1
        elif direction == "right":
            dx = 1
        else:
            return jsonify({"error": "Ongeldige richting"}), 400

        new_x = max(0, min(game["grid_size"] - 1, player["x"] + dx))
        new_y = max(0, min(game["grid_size"] - 1, player["y"] + dy))

        if {"x": new_x, "y": new_y} in game.get("blocked", []):
            return jsonify({"notice": "Je botste tegen een muur. Beweging ongeldig."}), 200

        player["last_move"] = direction

    return jsonify({"status": "OK"})

@app.route('/api/state/<pin>')
def state(pin):
    with lock:
        if pin not in games:
            return jsonify({"error": "PIN niet gevonden"}), 404
        return jsonify(games[pin])

@app.route('/stream/<pin>')
def stream(pin):
    def event_stream(q):
        try:
            while True:
                data = q.get()
                yield f"data: {data}\n\n"
        except GeneratorExit:
            with lock:
                game_queues[pin].remove(q)

    q = queue.Queue()
    with lock:
        if pin not in game_queues:
            return "PIN niet gevonden", 404
        game_queues[pin].append(q)

    return Response(event_stream(q), mimetype="text/event-stream")

# ----------------------- GAME LOGICA -----------------------

def game_loop():
    while True:
        time.sleep(TICK_INTERVAL)
        with lock:
            for pin, game in games.items():
                for token, player in game["players"].items():
                    move = player.get("last_move")
                    if not move:
                        continue
                    dx, dy = 0, 0
                    if move == "up": dy = -1
                    elif move == "down": dy = 1
                    elif move == "left": dx = -1
                    elif move == "right": dx = 1

                    new_x = max(0, min(game["grid_size"]-1, player["x"] + dx))
                    new_y = max(0, min(game["grid_size"]-1, player["y"] + dy))

                    if {"x": new_x, "y": new_y} in game.get("blocked", []):
                        player["last_move"] = None
                        continue

                    player["x"], player["y"] = new_x, new_y
                    player["last_move"] = None

                    if new_x == game["goal"]["x"] and new_y == game["goal"]["y"]:
                        game["scores"][token] += 1000
                        while True:
                            new_goal = {
                                "x": random.randint(0, game["grid_size"]-1),
                                "y": random.randint(0, game["grid_size"]-1)
                            }
                            if new_goal not in game.get("blocked", []):
                                game["goal"] = new_goal
                                break

                state_json = json.dumps(game)
                for q in game_queues[pin]:
                    try:
                        q.put_nowait(state_json)
                    except queue.Full:
                        pass

def generate_unique_pin():
    while True:
        pin = str(random.randint(1000, 9999))
        if pin not in games:
            return pin

# ----------------------- START -----------------------

if __name__ == '__main__':
    threading.Thread(target=game_loop, daemon=True).start()
    app.run(debug=True, port=8080, threaded=True)