from flask import Flask

def create_app():
    app = Flask(__name__)

    # 설정 불러오기 (config.py)
    app.config.from_object("config")

    # 라우트 등록
    from .routes import bp as routes_bp
    app.register_blueprint(routes_bp)

    return app


