from flask import Flask, render_template, request, Blueprint
from flask_cors import CORS
from utils import send_annotation_metric
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import json
import os


with open(".env", "r") as file:
    common_vars = json.load(file)


app_name = common_vars["app"]
app = Flask(__name__)
app.config["APPLICATION_ROOT"] = f"/{app_name}"
CORS(app)
env = Environment(loader=FileSystemLoader("templates"))

health_flag = True


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

    template = env.get_template("login.html")

    return template.render(username=username, **common_vars)


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, use_reloader=False)
