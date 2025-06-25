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
    return render_template("index.html", games=games)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    message = None
    if request.method == 'POST':
        grid_size = int(request.form.get("grid_size", 50))
        pin = generate_unique_pin()
        with lock:
            games[pin] = {
                "grid_size": grid_size,
                "players": {},
                "goal": {"x": random.randint(0, grid_size-1), "y": random.randint(0, grid_size-1)},
                "winner": None
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

    with lock:
        if pin not in games:
            return jsonify({"error": "Ongeldige PIN"}), 404

        token = str(uuid.uuid4())
        games[pin]["players"][token] = {
            "name": name,
            "color": color,
            "x": random.randint(0, games[pin]["grid_size"]-1),
            "y": random.randint(0, games[pin]["grid_size"]-1),
            "last_move": None
        }
    return jsonify({"token": token})

@app.route('/api/move', methods=['POST'])
def move():
    data = request.get_json()
    token = data.get("token")
    direction = data.get("direction")
    pin = data.get("pin")

    with lock:
        if pin not in games or token not in games[pin]["players"]:
            return jsonify({"error": "Ongeldige sessie of PIN"}), 403
        if direction not in {"up", "down", "left", "right"}:
            return jsonify({"error": "Ongeldige richting"}), 400

        games[pin]["players"][token]["last_move"] = direction

    return jsonify({"status": "Beweging geregistreerd"})

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
                if game["winner"]:
                    continue
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
                    player["x"], player["y"] = new_x, new_y
                    player["last_move"] = None

                    if new_x == game["goal"]["x"] and new_y == game["goal"]["y"]:
                        game["winner"] = player["name"]

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
