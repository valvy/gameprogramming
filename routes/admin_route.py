import random
import bcrypt
from flask import Blueprint, redirect, url_for, session, request, render_template

from config import ADMIN_PASSWORD_HASH
from models.GameModel import lock, games, game_queues

admin_bp = Blueprint('admin', __name__)

def generate_unique_pin():
    while True:
        pin = str(random.randint(1000, 9999))
        if pin not in games:
            return pin

@admin_bp.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get("logged_in"):
        return redirect(url_for("admin.login"))

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


@admin_bp.route('/login', methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        pw_input = request.form.get("password", "").encode("utf-8")
        hash_bytes = ADMIN_PASSWORD_HASH.encode("utf-8")
        if bcrypt.checkpw(pw_input, hash_bytes):
            session['logged_in'] = True
            return redirect(url_for('admin.admin'))
        else:
            error = "Ongeldig wachtwoord"
    return render_template("login.html", error=error)

@admin_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("login"))