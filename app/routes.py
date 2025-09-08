from flask import Blueprint, render_template, jsonify, request, current_app, abort
from app.database import get_connection
import subprocess
import threading
from datetime import date, timedelta

bp = Blueprint("routes", __name__)

# ---------------------------------------------------------------------
# 기본 페이지
# ---------------------------------------------------------------------
@bp.route("/")
def index():
    return render_template("index.html")

@bp.route("/ranking")
def ranking():
    return render_template("ranking.html")

@bp.route("/healthz")
def healthz():
    return jsonify(status="ok"), 200

# ---------------------------------------------------------------------
# 폴더/파일 구조 전용 페이지
#   예) /pan_setkacup/pan_setkacup.html  → templates/pan_setkacup/pan_setkacup.html
#       /star/star.html                  → templates/star/star.html
# ---------------------------------------------------------------------
FOLDER_TO_BOARD_SLUG = {
    "pan_setkacup": "pan_setkacup",
    "pan_ccy": "pan_ccy",
    "starbbs": "starbbs",
}

@bp.route("/<folder>/<page>")
def board_page(folder, page):
    board_slug = FOLDER_TO_BOARD_SLUG.get(folder)
    if not board_slug:
        abort(404)
    # 폴더 내 임의의 page 지원 (예: /pan_setkacup/ranking.html)
    return render_template(f"{folder}/{page}.html",
                           board_slug=board_slug,
                           folder_name=folder,
                           page_name=page)

# ---------------------------------------------------------------------
# 크롤러 트리거
# ---------------------------------------------------------------------
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
            print(result.stdout)
        except subprocess.CalledProcessError as e:
            print("[ERROR] Crawler 실패:", e.stderr)

    threading.Thread(target=background_job, daemon=True).start()
    return jsonify({"status": "started"}), 202

# ---------------------------------------------------------------------
# API: 일간 통계 (boardSlug 미지정 시 전체 게시판 합산)
# ---------------------------------------------------------------------
@bp.route("/api/daily_stats", methods=["GET"])
def daily_stats():
    nickname   = request.args.get("nickname")
    start_date = request.args.get("startDate")
    end_date   = request.args.get("endDate")
    board_slug = request.args.get("boardSlug")  # 선택

    if not nickname:
        return jsonify({"error": "nickname required"}), 400

    if not start_date or not end_date:
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
    else:
        start_date = date.fromisoformat(start_date)
        end_date   = date.fromisoformat(end_date)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, nickname FROM users WHERE nickname = %s", (nickname,))
    rows = cur.fetchall()
    if not rows:
        cur.close(); conn.close()
        return jsonify({"error": "user not found"}), 404

    results = {}
    for user_id, nick in rows:
        if board_slug:
            cur.execute("""
                SELECT d.stat_date, d.total_bets, d.total_amount, d.total_profit, d.wins
                FROM daily_betting_stats d
                JOIN boards b ON d.board_id = b.id
                WHERE d.user_id = %s
                  AND b.slug = %s
                  AND d.stat_date BETWEEN %s AND %s
                ORDER BY d.stat_date DESC
            """, (user_id, board_slug, start_date, end_date))
        else:
            cur.execute("""
                SELECT d.stat_date,
                       SUM(d.total_bets)   AS total_bets,
                       SUM(d.total_amount) AS total_amount,
                       SUM(d.total_profit) AS total_profit,
                       SUM(d.wins)         AS wins
                FROM daily_betting_stats d
                WHERE d.user_id = %s
                  AND d.stat_date BETWEEN %s AND %s
                GROUP BY d.stat_date
                ORDER BY d.stat_date DESC
            """, (user_id, start_date, end_date))

        stats = cur.fetchall()
        results[nick] = []
        for stat_date_v, total_bets, total_amount, total_profit, wins in stats:
            win_rate = round((wins / total_bets * 100), 2) if total_bets else 0.0
            results[nick].append({
                "stat_date": str(stat_date_v),
                "total_bets": total_bets,
                "total_amount": total_amount,
                "total_profit": total_profit,
                "wins": wins,
                "win_rate": win_rate
            })

    cur.close(); conn.close()
    return jsonify(results)

# ---------------------------------------------------------------------
# API: 월간 통계 (boardSlug 미지정 시 전체 게시판 합산)
# ---------------------------------------------------------------------
@bp.route("/api/monthly_stats", methods=["GET"])
def monthly_stats():
    nickname    = request.args.get("nickname")
    start_month = request.args.get("startMonth")  # YYYY-MM
    end_month   = request.args.get("endMonth")    # YYYY-MM
    board_slug  = request.args.get("boardSlug")   # 선택

    if not nickname:
        return jsonify({"error": "nickname required"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, nickname FROM users WHERE nickname = %s", (nickname,))
    rows = cur.fetchall()
    if not rows:
        cur.close(); conn.close()
        return jsonify({"error": "user not found"}), 404

    results = {}
    for user_id, nick in rows:
        params = [user_id]
        if board_slug:
            base = """
                SELECT m.stat_month, m.total_bets, m.total_amount, m.total_profit, m.wins
                FROM monthly_betting_stats m
                JOIN boards b ON m.board_id = b.id
                WHERE m.user_id = %s
                  AND b.slug = %s
            """
            params.append(board_slug)
        else:
            base = """
                SELECT m.stat_month,
                       SUM(m.total_bets)   AS total_bets,
                       SUM(m.total_amount) AS total_amount,
                       SUM(m.total_profit) AS total_profit,
                       SUM(m.wins)         AS wins
                FROM monthly_betting_stats m
                WHERE m.user_id = %s
            """

        if start_month and end_month:
            base += " AND m.stat_month BETWEEN %s AND (%s::date + interval '1 month - 1 day')"
            params.extend([start_month + "-01", end_month + "-01"])

        if board_slug:
            base += " ORDER BY m.stat_month DESC"
        else:
            base += " GROUP BY m.stat_month ORDER BY m.stat_month DESC"

        if not (start_month and end_month):
            base += " LIMIT 12"

        cur.execute(base, tuple(params))
        stats = cur.fetchall()

        results[nick] = []
        for stat_month_v, total_bets, total_amount, total_profit, wins in stats:
            win_rate = round((wins / total_bets * 100), 2) if total_bets else 0.0
            results[nick].append({
                "stat_month": stat_month_v.strftime("%Y-%m"),
                "total_bets": total_bets,
                "total_amount": total_amount,
                "total_profit": total_profit,
                "wins": wins,
                "win_rate": win_rate
            })

    cur.close(); conn.close()
    return jsonify(results)

# ---------------------------------------------------------------------
# API: 일간 랭킹 (boardSlug 미지정 시 전체 게시판 합산)
# ---------------------------------------------------------------------
@bp.route("/api/daily_ranking", methods=["GET"])
def daily_ranking():
    stat_date  = request.args.get("statDate")  # YYYY-MM-DD
    limit      = int(request.args.get("limit", 50))
    board_slug = request.args.get("boardSlug")  # 선택

    if not stat_date:
        return jsonify({"error": "statDate required"}), 400

    conn = get_connection()
    cur = conn.cursor()

    if board_slug:
        cur.execute("""
            SELECT u.nickname, d.total_bets, d.total_amount, d.total_profit, d.wins
            FROM daily_betting_stats d
            JOIN users  u ON d.user_id = u.id
            JOIN boards b ON d.board_id = b.id
            WHERE d.stat_date = %s
              AND b.slug = %s
            ORDER BY d.total_amount DESC
            LIMIT %s
        """, (stat_date, board_slug, limit))
    else:
        cur.execute("""
            SELECT u.nickname,
                   SUM(d.total_bets)   AS total_bets,
                   SUM(d.total_amount) AS total_amount,
                   SUM(d.total_profit) AS total_profit,
                   SUM(d.wins)         AS wins
            FROM daily_betting_stats d
            JOIN users u ON d.user_id = u.id
            WHERE d.stat_date = %s
            GROUP BY u.nickname
            ORDER BY SUM(d.total_amount) DESC
            LIMIT %s
        """, (stat_date, limit))

    rows = cur.fetchall()
    cur.close(); conn.close()

    results = []
    for nickname, total_bets, total_amount, total_profit, wins in rows:
        win_rate = round((wins / total_bets * 100), 2) if total_bets else 0.0
        results.append({
            "nickname": nickname,
            "total_bets": total_bets,
            "total_amount": total_amount,
            "total_profit": total_profit,
            "wins": wins,
            "win_rate": win_rate
        })
    return jsonify(results)

# ---------------------------------------------------------------------
# API: 월간 랭킹 (boardSlug 미지정 시 전체 게시판 합산)
# ---------------------------------------------------------------------
@bp.route("/api/monthly_ranking", methods=["GET"])
def monthly_ranking():
    stat_month = request.args.get("statMonth")  # YYYY-MM
    limit      = int(request.args.get("limit", 50))
    board_slug = request.args.get("boardSlug")  # 선택

    if not stat_month:
        return jsonify({"error": "statMonth required"}), 400

    stat_month = stat_month + "-01"

    conn = get_connection()
    cur = conn.cursor()

    if board_slug:
        cur.execute("""
            SELECT u.nickname, m.total_bets, m.total_amount, m.total_profit, m.wins
            FROM monthly_betting_stats m
            JOIN users  u ON m.user_id = u.id
            JOIN boards b ON m.board_id = b.id
            WHERE m.stat_month = %s
              AND b.slug = %s
            ORDER BY m.total_amount DESC
            LIMIT %s
        """, (stat_month, board_slug, limit))
    else:
        cur.execute("""
            SELECT u.nickname,
                   SUM(m.total_bets)   AS total_bets,
                   SUM(m.total_amount) AS total_amount,
                   SUM(m.total_profit) AS total_profit,
                   SUM(m.wins)         AS wins
            FROM monthly_betting_stats m
            JOIN users u ON m.user_id = u.id
            WHERE m.stat_month = %s
            GROUP BY u.nickname
            ORDER BY SUM(m.total_amount) DESC
            LIMIT %s
        """, (stat_month, limit))

    rows = cur.fetchall()
    cur.close(); conn.close()

    results = []
    for nickname, total_bets, total_amount, total_profit, wins in rows:
        win_rate = round((wins / total_bets * 100), 2) if total_bets else 0.0
        results.append({
            "nickname": nickname,
            "total_bets": total_bets,
            "total_amount": total_amount,
            "total_profit": total_profit,
            "wins": wins,
            "win_rate": win_rate
        })
    return jsonify(results)
