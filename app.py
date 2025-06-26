import json
import queue
import threading
import time
import uuid
import random

from flask import Flask, request, jsonify, render_template, Response, redirect, url_for, session
from config import secret_key
from models.GameModel import lock, games, game_queues, TICK_INTERVAL
from routes.admin_route import admin_bp

app = Flask(__name__)
app.secret_key = secret_key


app.register_blueprint(admin_bp)

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
        print(games)
        if pin not in games:
            return jsonify({"error": "Ongeldige PIN"}), 404

        # Check of naam al bestaat in deze game
        if any(p["name"] == name for p in games[pin]["players"].values()):
            return jsonify({"error": "Naam is al in gebruik in deze game"}), 400

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
def get_state(pin):
    with lock:
        game = games.get(pin)
        if not game:
            return jsonify({"error": "Game niet gevonden"}), 404

        visible_players = [
            {
                "name": p["name"],
                "color": p["color"],
                "x": p["x"],
                "y": p["y"]
            }
            for p in game["players"].values()
        ]

        return jsonify({
            "players": {p["name"]: p for p in visible_players},
            "goal": game["goal"],
            "winner": game["winner"],
            "scores": game.get("scores", {}),
            "blocked": game.get("blocked", []),
            "grid_size": game.get("grid_size", 20)
        })

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


# ----------------------- START -----------------------

if __name__ == '__main__':
    threading.Thread(target=game_loop, daemon=True).start()
    app.run(debug=True, port=8080, threaded=True)