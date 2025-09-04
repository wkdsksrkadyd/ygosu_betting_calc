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
    users = cur.fetchall()
    if not users:
        cur.close(); conn.close()
        return jsonify({"error": "user not found"}), 404

    # 기간 처리: 월 문자열을 날짜 범위로
    # (끝월은 다음달 1일 미만으로 범위를 잡아 안전하게 처리)
    from datetime import date
    def month_start(ym):
        y, m = [int(x) for x in ym.split("-")]
        return date(y, m, 1)
    def month_after(ym):
        y, m = [int(x) for x in ym.split("-")]
        if m == 12:
            return date(y+1, 1, 1)
        return date(y, m+1, 1)

    results = {}
    for user_id, nick in users:
        params = [user_id]
        time_filter_sql = ""
        if start_month and end_month:
            s = month_start(start_month)
            e = month_after(end_month)
            time_filter_sql = "AND participated_at >= %s AND participated_at < %s"
            params.extend([s, e])

        cur.execute(f"""
            WITH per_post AS (
              SELECT
                DATE_TRUNC('month', participated_at)::date AS m,
                post_id,
                user_id,
                board_id,
                SUM(profit) AS net_profit,           -- ✅ 양방 적용
                MAX(bet_amount) AS amount_one_side   -- ✅ 양방 미적용(대표 1건)
              FROM betting_stats
              WHERE user_id = %s
              {time_filter_sql}
              GROUP BY DATE_TRUNC('month', participated_at), post_id, user_id, board_id
            ),
            per_month AS (
              SELECT
                m,
                user_id,
                board_id,
                COUNT(*) AS total_bets,                              -- 게시물 수
                SUM(amount_one_side) AS total_amount,               -- 대표 금액 합
                SUM(net_profit) AS total_profit,                    -- 순수익(양방 합산)
                SUM(CASE WHEN net_profit > 0 THEN 1 ELSE 0 END) AS wins
              FROM per_post
              GROUP BY m, user_id, board_id
            )
            SELECT m AS stat_month, total_bets, total_amount, total_profit, wins
            FROM per_month
            ORDER BY m DESC
            {"" if (start_month and end_month) else "LIMIT 12"}
        """, tuple(params))

        rows = cur.fetchall()
        result_rows = []
        for stat_month, total_bets, total_amount, total_profit, wins in rows:
            win_rate = round((wins / total_bets * 100), 2) if total_bets else 0.0
            result_rows.append({
                "stat_month": stat_month.strftime("%Y-%m"),
                "total_bets": int(total_bets),
                "total_amount": int(total_amount or 0),
                "total_profit": int(total_profit or 0),  # 순수익(양방 적용)
                "wins": int(wins),
                "win_rate": win_rate,
            })
        results[nick] = result_rows

    cur.close()
    conn.close()
    return jsonify(results)
