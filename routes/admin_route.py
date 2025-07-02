import random
import bcrypt
from flask import Blueprint, redirect, url_for, session, request, render_template

from config import ADMIN_PASSWORD_HASH
from models.GameModel import game_Model

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get("logged_in"):
        return redirect(url_for("admin.login"))

    message = None
    if request.method == 'POST':

        grid_size = int(request.form.get("grid_size", 20))
        pin = game_Model.create_game(grid_size)
        message = f"Nieuwe game aangemaakt met PIN: {pin} (grid {grid_size}x{grid_size})"

    return render_template("admin.html", games=game_Model.games, message=message)


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