import requests
import time

# 🎮 Invullen door student
GAME_ID = "ABC"       # <-- Verkregen van docent
NAME = "Alice"        # <-- Eigen naam
COLOR = "#ff0000"     # <-- Kleur op het grid (hex)

# 🌐 Serveradres (pas aan als je het op een andere host draait)
BASE_URL = "http://localhost:5000"

# 1. Aanmelden bij game
print(f"🔗 Meldt aan bij game {GAME_ID}...")
res = requests.post(f"{BASE_URL}/game/{GAME_ID}/join", json={
    "name": NAME,
    "color": COLOR
})
if res.status_code != 200:
    print("❌ Kan niet aanmelden bij game.")
    print(res.json())
    exit()

token = res.json()["token"]
print(f"✅ Aangemeld! Token: {token}")

# Functie om state op te halen
def get_state():
    res = requests.post(f"{BASE_URL}/game/{GAME_ID}/state", json={
        "token": token
    })
    if res.status_code == 200:
        return res.json()
    else:
        print("❌ Fout bij ophalen van game state:", res.text)
        return None

# Functie om richting te bepalen
def richting_naar(speler_pos, doel_pos):
    sx, sy = speler_pos
    dx, dy = doel_pos
    if dx > sx:
        return "right"
    elif dx < sx:
        return "left"
    elif dy > sy:
        return "down"
    elif dy < sy:
        return "up"
    else:
        return "none"

# 2. Game loop
while True:
    state = get_state()
    if not state:
        break

    speler = state["players"][token]
    speler_pos = speler["pos"]
    goal_pos = state["goal"]

    if speler_pos == goal_pos:
        print("🎉 Je hebt het doel bereikt!")
        break

    direction = richting_naar(speler_pos, goal_pos)
    print(f"➡️  Beweeg {direction}")

    # 3. Stuur move
    requests.post(f"{BASE_URL}/game/{GAME_ID}/move", json={
        "token": token,
        "direction": direction
    })

    time.sleep(1)
