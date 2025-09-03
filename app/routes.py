from flask import Blueprint, render_template, jsonify, request, current_app, Response
import subprocess
import threading
import os

SECRET_KEY = os.getenv("CRAWLER_SECRET_KEY", "default_secret")

bp = Blueprint("routes", __name__)

@bp.route("/")
def index():
    return render_template("index.html")

@bp.route("/healthz")
def healthz():
    return jsonify(status="ok"), 200

@bp.route("/run-crawler", methods=["POST"])
def run_crawler():
    token = request.headers.get("X-API-KEY")
    if token != current_app.config["CRAWLER_SECRET_KEY"]:
        return jsonify({"error": "unauthorized"}), 403

    def background_job():
        try:
            result = subprocess.run(
                ["python", "-m", "app.crawler.cli"],
                capture_output=True,
                text=True,
                check=True
            )
            print("[OK] Crawler finished:", result.stdout)
        except subprocess.CalledProcessError as e:
            print("[ERROR] Crawler failed:", e.stderr)

    threading.Thread(target=background_job, daemon=True).start()

    return jsonify({"status": "started"}), 202

