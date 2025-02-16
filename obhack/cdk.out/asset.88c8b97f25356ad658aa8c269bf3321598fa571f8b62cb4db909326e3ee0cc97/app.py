from flask import Flask, render_template, request, Blueprint
from flask_cors import CORS
from utils import send_annotation_metric, CommonMiddleware
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import json
import os
from flask_sqlalchemy import SQLAlchemy
import pymysql
from unicodedata import normalize

pymysql.install_as_MySQLdb()

with open(".env", "r") as file:
    common_vars = json.load(file)

DB_PASSWORD = os.getenv("MYSQL_PASSWORD", "A+a8th+++ms")

app_name = common_vars["app"]
app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
app.config["APPLICATION_ROOT"] = f"/{app_name}"
CORS(app)
env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=True,
)

health_flag = True

app.wsgi_app = CommonMiddleware(app.wsgi_app)

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://root:{DB_PASSWORD}@localhost/test?charset=utf8mb4"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "connect_args": {
        "charset": "utf8mb4",
        "use_unicode": True,
        "init_command": "SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci",
    },
}
db = SQLAlchemy(app)


class User(db.Model):
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(
        db.String(80, collation="utf8mb4_unicode_ci"), unique=False, nullable=False
    )


@app.route("/")
def main():
    template = env.get_template("home.html")
    return template.render(**common_vars)


@app.route("/health")
def health():
    if health_flag:
        return {"status": "ok"}
    else:
        raise Exception("Unhealthy. Login as health to toggle.")


@app.route("/login")
def login():
    global health_flag

    # Get username and password from request
    username = request.args.get("username", "None")
    password = request.args.get("password", "None")

    send_annotation_metric(app_name, username, 1)

    if username.lower() == "health":
        health_flag = not health_flag

    # Raise exception for admin user
    if username.lower() == "admin":
        raise Exception("Admin login not allowed")

    try:

        normalized_username = normalize("NFKC", username)
        user = User(username=normalized_username)
        db.session.add(user)
        db.session.commit()
        message = f"User {username} added successfully!"
    except Exception as e:
        db.session.rollback()
        message = f"Error adding user: {str(e)}"

    print(message)

    template = env.get_template("login.html")

    return template.render(username=username, message=message, **common_vars)


@app.route("/users")
def get_users():
    users = User.query.all()
    return "\n".join([f"{user.username}: {user.email}" for user in users])


# Create tables
def init_db():
    print("Initializing DB")
    with app.app_context():
        db.create_all()
        print("Database tables created successfully")


if __name__ == "__main__":
    print("Initializing App")
    # Initialize database tables
    init_db()
    app.run(host="0.0.0.0", debug=True, use_reloader=False)
else:
    print("Initializing App Externally")
    # Initialize database tables
    init_db()
