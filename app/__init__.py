from flask import Flask
from .routes import bp as routes_bp
from config import Config

def create_app():
    app = Flask(__name__)

    # 설정 불러오기 (config.py)
    app.config.from_object(Config)
    # print("[DEBUG] CRAWLER_SECRET_KEY =", app.config.get("CRAWLER_SECRET_KEY"))


    # 라우트 등록
    app.register_blueprint(routes_bp)

    return app


