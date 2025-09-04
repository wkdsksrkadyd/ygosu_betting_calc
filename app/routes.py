from flask import Blueprint, render_template, jsonify, request, current_app
from app.database import get_connection
import subprocess
import threading
import os
from datetime import date, timedelta

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


# ✅ 일간 통계 API
@bp.route("/api/daily_stats", methods=["GET"])
def daily_stats():
    nickname = request.args.get("nickname")
    start_date = request.args.get("startDate")
    end_date = request.args.get("endDate")

    if not nickname:
        return jsonify({"error": "nickname required"}), 400

    # 기본값: 최근 30일
    if not start_date or not end_date:
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
    else:
        # 문자열을 date로 변환
        start_date = date.fromisoformat(start_date)
        end_date = date.fromisoformat(end_date)

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


# ✅ 월간 통계 API
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
            query += " AND stat_month BETWEEN %s AND (%s::date + interval '1 month - 1 day')"
            params.extend([start_month + "-01", end_month + "-01"])
        else:
            query += " ORDER BY stat_month DESC LIMIT 12"

        cur.execute(query, tuple(params))
        stats = cur.fetchall()

        results[nick] = []
        for r in stats:
            stat_month, total_bets, total_amount, total_profit, wins = r
            win_rate = round((wins / total_bets * 100), 2) if total_bets > 0 else 0.0
            results[nick].append({
               "stat_month": stat_month.strftime("%Y-%m"),
                "total_bets": total_bets,
                "total_amount": total_amount,
                "total_profit": total_profit,
                "wins": wins,
                "win_rate": win_rate
            })

    cur.close()
    conn.close()
    return jsonify(results)

# ✅ 일간 랭킹 API (배팅액 기준)
@bp.route("/api/daily_ranking", methods=["GET"])
def daily_ranking():
    stat_date = request.args.get("statDate")  # YYYY-MM-DD
    limit = int(request.args.get("limit", 50))  # 기본 상위 50명

    if not stat_date:
        return jsonify({"error": "statDate required"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT u.nickname, d.total_bets, d.total_amount, d.total_profit, d.wins
        FROM daily_betting_stats d
        JOIN users u ON d.user_id = u.id
        WHERE d.stat_date = %s
        ORDER BY d.total_amount DESC   -- ✅ 배팅액 순위
        LIMIT %s
    """, (stat_date, limit))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    results = []
    for nickname, total_bets, total_amount, total_profit, wins in rows:
        win_rate = round((wins / total_bets * 100), 2) if total_bets > 0 else 0.0
        results.append({
            "nickname": nickname,
            "total_bets": total_bets,
            "total_amount": total_amount,
            "total_profit": total_profit,
            "wins": wins,
            "win_rate": win_rate
        })

    return jsonify(results)


# ✅ 월간 랭킹 API (배팅액 기준)
@bp.route("/api/monthly_ranking", methods=["GET"])
def monthly_ranking():
    stat_month = request.args.get("statMonth")  # YYYY-MM
    limit = int(request.args.get("limit", 50))

    if not stat_month:
        return jsonify({"error": "statMonth required"}), 400

    stat_month = stat_month + "-01"

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT u.nickname, m.total_bets, m.total_amount, m.total_profit, m.wins
        FROM monthly_betting_stats m
        JOIN users u ON m.user_id = u.id
        WHERE m.stat_month = %s
        ORDER BY m.total_amount DESC   -- ✅ 배팅액 순위
        LIMIT %s
    """, (stat_month, limit))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    results = []
    for nickname, total_bets, total_amount, total_profit, wins in rows:
        win_rate = round((wins / total_bets * 100), 2) if total_bets > 0 else 0.0
        results.append({
            "nickname": nickname,
            "total_bets": total_bets,
            "total_amount": total_amount,
            "total_profit": total_profit,
            "wins": wins,
            "win_rate": win_rate
        })

    return jsonify(results)

