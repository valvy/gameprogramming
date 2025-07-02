import json
import queue
import threading
import random
import time
import uuid
from models.GameResponse import UserError, NotFoundError, SuccessResponse

class GameModel:
    TICK_INTERVAL = 0.1
    def __init__(self):
        self.__games = {}  # pin -> game_state
        self.__game_queues = {}  # pin -> [queue.Queue()]
        self.__lock = threading.Lock()


    @property
    def games(self):
        return self.__games

    def __generate_unique_pin(self):
        while (pin := str(random.randint(1000, 9999))) in self.__games:
            continue
        return pin

    def create_game(self, grid_size):
        pin = self.__generate_unique_pin()
        blocked_tiles = [
            {"x": random.randint(0, grid_size - 1), "y": random.randint(0, grid_size - 1)}
            for _ in range(grid_size // 2)
        ]
        # Kies een doel dat niet geblokkeerd is
        while True:
            goal = {"x": random.randint(0, grid_size - 1), "y": random.randint(0, grid_size - 1)}
            if goal not in blocked_tiles:
                break

        with self.__lock:
            self.__games[pin] = {
                "grid_size": grid_size,
                "players": {},
                "goal": goal,
                "winner": None,
                "blocked": blocked_tiles,
                "scores": {}  # token -> score
            }
            self.__game_queues[pin] = []
        return pin




    def register_user(self,pin, name, color):
        disallowed_colors = {"black", "yellow"}
        all_used_colors = set(disallowed_colors)

        with self.__lock:
            if pin not in self.__games:
                return NotFoundError("pin not found")

            # Check of naam al bestaat in deze game
            if any(p["name"] == name for p in self.__games[pin]["players"].values()):
                return UserError("Name already exists")

            used_colors = {p["color"] for p in self.__games[pin]["players"].values()}
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
                    return UserError("Game is full")

            token = str(uuid.uuid4())
            self.__games[pin]["players"][token] = {
                "name": name,
                "color": color,
                "x": random.randint(0, self.__games[pin]["grid_size"]-1),
                "y": random.randint(0, self.__games[pin]["grid_size"]-1),
                "last_move": None
            }
            self.__games[pin]["scores"][token] = 0

        response = {"token": token, "color": color}
        notice = ""
        if color != original_color:
            notice = f"Kleur '{original_color}' was niet beschikbaar. Je hebt nu '{color}' gekregen."

        return SuccessResponse(response, notice=notice)

    def movePlayer(self, pin, token, direction):
        with self.__lock:
            game = self.__games.get(pin)
            if not game:
                return NotFoundError("Game niet gevonden")

            player = game["players"].get(token)
            if not player:
                return NotFoundError("Speler niet gevonden")

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
                return UserError("Ongeldige richting")

            new_x = max(0, min(game["grid_size"] - 1, player["x"] + dx))
            new_y = max(0, min(game["grid_size"] - 1, player["y"] + dy))

            if {"x": new_x, "y": new_y} in game.get("blocked", []):
                return UserError("Je botste tegen een muur. Beweging ongeldig.")

            player["last_move"] = direction

            return SuccessResponse("ok")


    def get_games(self):
        leaderboard_data = {}
        with self.__lock:
            for pin, game in self.__games.items():
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
        return leaderboard_data


    def get_game_state(self, pin):
        with self.__lock:
            game = self.__games.get(pin)
            if not game:
                return NotFoundError("Game niet gevonden")

            visible_players = [
                {
                    "name": p["name"],
                    "color": p["color"],
                    "x": p["x"],
                    "y": p["y"]
                }
                for p in game["players"].values()
            ]

            return SuccessResponse({
                "players": {p["name"]: p for p in visible_players},
                "goal": game["goal"],
                "winner": game["winner"],
                "scores": game.get("scores", {}),
                "blocked": game.get("blocked", []),
                "grid_size": game.get("grid_size", 20)
            })

    def game_loop(self):
        while True:
            time.sleep(GameModel.TICK_INTERVAL)
            with self.__lock:
                for pin, game in self.__games.items():
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
                    for q in self.__game_queues[pin]:
                        try:
                            q.put_nowait(state_json)
                        except queue.Full:
                            pass

    def stream_from_pin(self, pin):
        def event_stream(q):
            try:
                while True:
                    data = q.get()
                    yield f"data: {data}\n\n"
            except GeneratorExit:
                with self.__lock:
                    self.__game_queues[pin].remove(q)

        q = queue.Queue()
        with self.__lock:
            if pin not in self.__game_queues:
                return "PIN niet gevonden", 404
            self.__game_queues[pin].append(q)
        return event_stream, q

game_Model = GameModel()