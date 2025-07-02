import queue
import threading
from flask import Flask, request, jsonify, render_template, Response
from config import secret_key
from models.GameModel import GameModel, game_Model

from models.GameResponse import UserError, NotFoundError, GameResponse
from routes.admin_route import admin_bp

app = Flask(__name__)
app.secret_key = secret_key

app.register_blueprint(admin_bp)


@app.route('/')
def index():
    return render_template("index.html", games=game_Model.games, leaderboards=game_Model.get_games())

def map_result_to_response(response: GameResponse):
    resp = response.toJSON()
    match response:
        case UserError():
            return resp, 400
        case NotFoundError():
            return resp, 404
        case _:
            return resp, 200

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data.get("name")
    color = data.get("color")
    pin = data.get("pin")

    if not name or not color or not pin:
        return jsonify({"error": "Naam, kleur en PIN zijn verplicht"}), 400

    response = game_Model.register_user(pin, name, color)
    return map_result_to_response(response)


@app.route('/api/move', methods=['POST'])
def move():
    data = request.get_json()
    token = data.get("token")
    direction = data.get("direction")
    pin = data.get("pin")

    if not token or not direction or not pin:
        return jsonify({"error": "Token, direction en PIN zijn verplicht"}), 400

    return map_result_to_response(game_Model.movePlayer(pin,token,direction))

@app.route('/api/state/<pin>')
def get_state(pin):
    return map_result_to_response(game_Model.get_game_state(pin))


@app.route('/stream/<pin>')
def stream(pin):
    func, queu = game_Model.stream_from_pin(pin)
    return Response(func(queu), mimetype="text/event-stream")


if __name__ == '__main__':
    threading.Thread(target=game_Model.game_loop, daemon=True).start()
    app.run(debug=True, port=8080, threaded=True)