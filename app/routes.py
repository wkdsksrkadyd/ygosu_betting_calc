from flask import Blueprint, render_template, jsonify, request, current_app, Response
import subprocess
import os
import json

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
    
    # 디버그 출력
    # print("[DEBUG] token =", token)

    if token != current_app.config["CRAWLER_SECRET_KEY"]:
        return jsonify({"error": "unauthorized"}), 403

    try:
        result = subprocess.run(
            ["python", "-m", "app.crawler.cli"],
            capture_output=True,
            text=True,
            check=True
        )
        return Response(
            json.dumps({"status": "ok", "output": result.stdout}, ensure_ascii=False),
            content_type="application/json; charset=utf-8"
        )
    except subprocess.CalledProcessError as e:
        return Response(
            json.dumps({"status": "error", "error": e.stderr}, ensure_ascii=False),
            content_type="application/json; charset=utf-8",
            status=500
        )
