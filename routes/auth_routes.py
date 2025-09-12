from flask import Blueprint, render_template, request, redirect, url_for, session
from models import db
from models.user_model import User
from werkzeug.security import generate_password_hash, check_password_hash

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["role"] = user.role
            if user.role == "faculty":
                return redirect(url_for("faculty.dashboard"))
            else:
                return redirect(url_for("student.dashboard"))
        else:
            return "Invalid credentials", 401
    return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
