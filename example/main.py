import gridlib

name = "student" + gridlib.random_string()
color = "yellow"
pin = input("Voer de PIN van de game in (4 cijfers): ").strip()
gridlib.register(name,"yellow", pin)

print("Gebruik 'up', 'down', 'left', 'right', of 'exit'")
while True:
    for p in gridlib.get_other_players():
        print(f"👤 {p['name']} ({p['color']}) op positie ({p['x']}, {p['y']})")

    cmd = input("Beweeg: ").strip().lower()
    if cmd in {"up", "down", "left", "right"}:
        if not gridlib.is_blocked(cmd):
            gridlib.move(cmd)
        else:
            print("je kan niet die kant op!")
    elif cmd == "exit":
        break
    else:
        print("❌ Ongeldige input.")
