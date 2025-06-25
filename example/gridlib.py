import random
import string
import requests
BASE_URL = "http://localhost:8080"  # Pas aan indien nodig
token = None
player_name = None
game_pin = None


def set_uri(uri):
    global BASE_URL
    BASE_URL = uri


def random_string():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

def register(name, color, pin):
    global token, game_pin, player_name
    game_pin = pin
    player_name = name

    response = requests.post(f"{BASE_URL}/api/register", json={
        "name": name,
        "color": color,
        "pin": pin
    })

    if response.status_code != 200:
        print("❌ Fout bij registratie:", response.json())
        exit(1)

    data = response.json()
    token = data["token"]
    assigned_color = data.get("color", color)
    print(f"✅ Geregistreerd als {name}, kleur: {assigned_color}")

    if "notice" in data:
        print(f"⚠️  Opmerking: {data['notice']}")


def move(direction):
    response = requests.post(f"{BASE_URL}/api/move", json={
        "token": token,
        "direction": direction,
        "pin": game_pin
    })

    if response.status_code != 200:
        print("❌ Beweegfout:", response.json())
    else:
        data = response.json()
        if "notice" in data:
            print(f"⚠️  Opmerking: {data['notice']}")
        else:
            print(f"➡️ Beweeg {direction}")


def get_state(pin=None):
    pin = pin or game_pin
    response = requests.get(f"{BASE_URL}/api/state/{pin}")
    if response.status_code != 200:
        print("❌ Fout bij ophalen spelstatus:", response.json())
        exit(1)
    return response.json()


def is_blocked(direction):
    state = get_state()
    player = state["players"].get(player_name)
    blocked = state.get("blocked", [])
    size = state.get("grid_size", 20)

    if not player:
        print("⚠️ Speler niet gevonden in state")
        return True

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
        raise ValueError("Ongeldige richting")

    new_x = max(0, min(size - 1, player["x"] + dx))
    new_y = max(0, min(size - 1, player["y"] + dy))

    return {"x": new_x, "y": new_y} in blocked


def get_other_players():
    state = get_state()
    all_players = state.get("players", {})
    return [
        {
            "name": name,
            "color": p["color"],
            "x": p["x"],
            "y": p["y"]
        }
        for name, p in all_players.items()
        if name != player_name
    ]
