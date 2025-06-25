from flask import Flask, jsonify, request, render_template, Response
import threading
import uuid
import time
import random
import queue
import json

app = Flask(__name__)

GRID_SIZE = 20
TICK_INTERVAL = 1  # seconden

game_state = {
    "players": {},  # token -> {"name", "color", "x", "y", "last_move"}
    "goal": {"x": random.randint(0, GRID_SIZE - 1), "y": random.randint(0, GRID_SIZE - 1)},
    "winner": None
}

client_queues = []
lock = threading.Lock()

@app.route('/')
def index():
    return render_template('index.html')

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

@app.route('/api/state')
def state():
    with lock:
        return jsonify({
            "players": game_state["players"],
            "goal": game_state["goal"],
            "winner": game_state["winner"]
        })

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

if __name__ == '__main__':
    threading.Thread(target=game_loop, daemon=True).start()
    app.run(debug=True, port=8080, threaded=True)
