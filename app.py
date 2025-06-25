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

# ====================
# Configuratie
# ====================

GRID_SIZE = 20
TICK_INTERVAL = 1  # seconden

# Omgevingsvariabele voor bcrypt hash van admin wachtwoord
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH")

if not ADMIN_PASSWORD_HASH:
    print("❌ FOUT: ADMIN_PASSWORD_HASH is niet ingesteld als omgevingsvariabele.")
    print("Gebruik bijvoorbeeld:")
    print("   python -c \"import bcrypt; print(bcrypt.hashpw(b'geheim', bcrypt.gensalt()).decode())\"")
    print("en stel deze in via:")
    print("   export ADMIN_PASSWORD_HASH='...'  (Linux/macOS)")
    print("   set ADMIN_PASSWORD_HASH=...       (Windows)")
    sys.exit(1)

# ====================
# Game State
# ====================

game_state = {
    "players": {},
    "goal": {"x": random.randint(0, GRID_SIZE - 1), "y": random.randint(0, GRID_SIZE - 1)},
    "winner": None
}

client_queues = []
lock = threading.Lock()

# ====================
# Routes: Frontend
# ====================

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/admin')
def admin():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return "<h1>Welkom, admin!</h1><p><a href='/logout'>Uitloggen</a></p>"

@app.route('/login', methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        password = request.form.get("password", "").encode("utf-8")
        hash_from_env = ADMIN_PASSWORD_HASH.encode("utf-8")

        if bcrypt.checkpw(password, hash_from_env):
            session["logged_in"] = True
            return redirect(url_for("admin"))
        else:
            error = "Ongeldig wachtwoord"

    return render_template("login.html", error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("login"))

# ====================
# Routes: API voor studenten
# ====================

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data.get("name")
    color = data.get("color")

    if not name or not color:
        return jsonify({"error": "Naam en kleur verplicht"}), 400

    token = str(uuid.uuid4())
    with lock:
        game_state["players"][token] = {
            "name": name,
            "color": color,
            "x": random.randint(0, GRID_SIZE - 1),
            "y": random.randint(0, GRID_SIZE - 1),
            "last_move": None
        }
    return jsonify({"token": token})

@app.route('/api/move', methods=['POST'])
def move():
    data = request.get_json()
    token = data.get("token")
    direction = data.get("direction")

    if token not in game_state["players"]:
        return jsonify({"error": "Ongeldige sessie"}), 403

    if direction not in {"up", "down", "left", "right"}:
        return jsonify({"error": "Ongeldige richting"}), 400

    with lock:
        game_state["players"][token]["last_move"] = direction

    return jsonify({"status": "Beweging geregistreerd"})

@app.route('/api/state')
def state():
    with lock:
        return jsonify({
            "players": game_state["players"],
            "goal": game_state["goal"],
            "winner": game_state["winner"]
        })

# ====================
# Server-Sent Events (SSE)
# ====================

@app.route('/stream')
def stream():
    def event_stream(q):
        try:
            while True:
                data = q.get()
                yield f"data: {data}\n\n"
        except GeneratorExit:
            with lock:
                if q in client_queues:
                    client_queues.remove(q)

    q = queue.Queue()
    with lock:
        client_queues.append(q)
    return Response(event_stream(q), mimetype="text/event-stream")

# ====================
# Game Logic
# ====================

def game_loop():
    while True:
        time.sleep(TICK_INTERVAL)
        with lock:
            if game_state["winner"]:
                continue

            for token, player in game_state["players"].items():
                move = player.get("last_move")
                if not move:
                    continue

                dx, dy = 0, 0
                if move == "up": dy = -1
                elif move == "down": dy = 1
                elif move == "left": dx = -1
                elif move == "right": dx = 1

                new_x = max(0, min(GRID_SIZE - 1, player["x"] + dx))
                new_y = max(0, min(GRID_SIZE - 1, player["y"] + dy))

                player["x"], player["y"] = new_x, new_y
                player["last_move"] = None

                if new_x == game_state["goal"]["x"] and new_y == game_state["goal"]["y"]:
                    game_state["winner"] = player["name"]
                    print(f"🏁 WINNAAR: {player['name']}")

        # Verzenden van game state naar frontend
        state_json = json.dumps({
            "players": game_state["players"],
            "goal": game_state["goal"],
            "winner": game_state["winner"]
        })

        for q in client_queues[:]:
            try:
                q.put_nowait(state_json)
            except queue.Full:
                pass

# ====================
# Start de app
# ====================

if __name__ == '__main__':
    threading.Thread(target=game_loop, daemon=True).start()
    app.run(debug=True, port=8080, threaded=True)
