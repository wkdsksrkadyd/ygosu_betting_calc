from flask import Blueprint, render_template, jsonify

bp = Blueprint("routes", __name__)

@bp.route("/")
def index():
    return render_template("index.html")
