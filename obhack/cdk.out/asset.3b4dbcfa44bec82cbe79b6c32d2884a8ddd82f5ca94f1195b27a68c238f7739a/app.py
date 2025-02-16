# from aws_xray_sdk.core import xray_recorder
# from aws_xray_sdk.ext.flask.middleware import XRayMiddleware
from flask import Flask, render_template, request, Blueprint
from flask_cors import CORS
from utils import send_annotation_metric
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import json
import os

# from werkzeug.middleware.dispatcher import DispatcherMiddleware

with open(".env", "r") as file:
    common_vars = json.load(file)


app_name = common_vars["app"]
app = Flask(__name__)
app.config["APPLICATION_ROOT"] = f"/{app_name}"
CORS(app)
# xray_recorder.configure(service=app_name)
# XRayMiddleware(app, xray_recorder)
env = Environment(loader=FileSystemLoader("templates"))


@app.route("/")
def main():
    template = env.get_template("home.html")
    return template.render(**common_vars)


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/login")
def login():
    # segment = xray_recorder.current_segment()

    # Get username and password from request
    username = request.args.get("username")
    password = request.args.get("password")

    # Add annotations (used for filtering)
    # segment.put_annotation("request_type", "Login API")
    # segment.put_annotation("username", username)
    # send_annotation_metric(app_name, username, 1)

    # Add metadata (used for debugging)
    # segment.put_metadata("processing_time", 150, "performance")

    # Raise exception for admin user
    if username.lower() == "admin":
        raise Exception("Admin login not allowed")

    template = env.get_template("login.html")

    return template.render(username=username, **common_vars)


# app.wsgi_app = DispatcherMiddleware(simple, {f"/{app_name}": app.wsgi_app})

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, use_reloader=False)
