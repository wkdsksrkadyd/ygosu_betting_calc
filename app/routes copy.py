from flask import Blueprint, render_template, jsonify, request, current_app, Response
from app.database import get_connection
import subprocess
import threading
import os

SECRET_KEY = os.getenv("CRAWLER_SECRET_KEY", "default_secret")

bp = Blueprint("routes", __name__)

@bp.route("/")
def index():
    return render_template("index.html")

@bp.route("/rankings")
def rankings():
    return render_template("rankings.html")

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
            print("[INFO] Crawler 시작")
            result = subprocess.run(
                ["python", "-m", "app.crawler.cli"],
                capture_output=True,
                text=True,
                check=True
            )
            print("[OK] Crawler 완료")
            print(result.stdout)   # 크롤링 결과 로그
        except subprocess.CalledProcessError as e:
            print("[ERROR] Crawler 실패:", e.stderr)

    threading.Thread(target=background_job, daemon=True).start()

    return jsonify({"status": "started"}), 202

@bp.route("/api/daily_stats", methods=["GET"])
def daily_stats():
    nickname = request.args.get("nickname")
    start_date = request.args.get("startDate")
    end_date = request.args.get("endDate")

    if not nickname:
        return jsonify({"error": "nickname required"}), 400
    if not start_date or not end_date:
        return jsonify({"error": "startDate and endDate required"}), 400

    conn = get_connection()
    cur = conn.cursor()

    # 정확히 일치하는 닉네임만 검색
    cur.execute("SELECT id, nickname FROM users WHERE nickname = %s", (nickname,))
    rows = cur.fetchall()

    if not rows:
        cur.close()
        conn.close()
        return jsonify({"error": "user not found"}), 404

    results = {}
    for user_id, nick in rows:
        cur.execute("""
            SELECT stat_date, total_bets, total_amount, total_profit, wins
            FROM daily_betting_stats
            WHERE user_id = %s
              AND stat_date BETWEEN %s AND %s
            ORDER BY stat_date DESC
        """, (user_id, start_date, end_date))
        stats = cur.fetchall()

        results[nick] = []
        for r in stats:
            stat_date, total_bets, total_amount, total_profit, wins = r
            # ✅ 승률 계산 (0으로 나누는 경우 방지)
            win_rate = round((wins / total_bets * 100), 2) if total_bets > 0 else 0.0
            results[nick].append({
                "stat_date": str(stat_date),
                "total_bets": total_bets,
                "total_amount": total_amount,
                "total_profit": total_profit,
                "wins": wins,
                "win_rate": win_rate
            })

    cur.close()
    conn.close()
    return jsonify(results)

@bp.route("/api/monthly_stats", methods=["GET"])
def monthly_stats():
    nickname = request.args.get("nickname")
    start_month = request.args.get("startMonth")  # YYYY-MM
    end_month = request.args.get("endMonth")      # YYYY-MM

    if not nickname:
        return jsonify({"error": "nickname required"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, nickname FROM users WHERE nickname = %s", (nickname,))
    rows = cur.fetchall()
    if not rows:
        cur.close()
        conn.close()
        return jsonify({"error": "user not found"}), 404

    results = {}
    for user_id, nick in rows:
        query = """
            SELECT stat_month, total_bets, total_amount, total_profit, wins
            FROM monthly_betting_stats
            WHERE user_id = %s
        """
        params = [user_id]

        # ✅ 기간 필터링
        if start_month and end_month:
            query += " AND stat_month BETWEEN %s AND %s"
            params.extend([start_month + "-01", end_month + "-31"])  
            # stat_month가 DATE 형식이라고 가정, 월 첫째날~마지막날로 확장
        query += " ORDER BY stat_month DESC"

        # 기본적으로 최근 12개월 제한 (필터 없을 때만)
        if not (start_month and end_month):
            query += " LIMIT 12"

        cur.execute(query, tuple(params))
        stats = cur.fetchall()

        results[nick] = []
        for r in stats:
            stat_month, total_bets, total_amount, total_profit, wins = r
            win_rate = round((wins / total_bets * 100), 2) if total_bets > 0 else 0.0
            results[nick].append({
                "stat_month": str(stat_month),
                "total_bets": total_bets,
                "total_amount": total_amount,
                "total_profit": total_profit,
                "wins": wins,
                "win_rate": win_rate
            })

    cur.close()
    conn.close()
    return jsonify(results)
