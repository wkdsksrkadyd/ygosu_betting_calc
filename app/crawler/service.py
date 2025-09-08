import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from app.database import get_connection

def parse_list_page(page: int, slug: str):
    url = f"https://ygosu.com/board/{slug}/?s_wato=Y&page={page}"
    res = requests.get(url, timeout=10)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    posts = []
    for row in soup.select("table.bd_list tbody tr"):
        if "notice" in row.get("class", []):
            continue
        a = row.select_one("td.tit a[href]")
        cat = row.select_one("span.cat")
        if not a or not cat:
            continue
        if "종료" not in cat.get_text(strip=True):
            continue
        m = re.search(r"/(\d+)", a["href"])
        if m:
            posts.append(m.group(1))
    return posts


def parse_post(post_id: str, slug: str):
    url = f"https://ygosu.com/board/{slug}/{post_id}"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"[에러] 게시물 요청 실패 → slug={slug}, post_id={post_id}, error={e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")

    # ✅ 마감 시각 및 종료 상태 체크
    bet_info_div = soup.select_one("div.ub_bet_start")
    if not bet_info_div:
        print(f"[스킵] 마감 정보 없음 → slug={slug}, post_id={post_id}")
        return []

    if "종료됨" not in bet_info_div.get_text():
        print(f"[스킵] 진행 중인 베팅 → slug={slug}, post_id={post_id}")
        return []

    # ✅ 마감 시각 추출
    participated_at = None
    match = re.search(
        r"마감 시각:\s*([\d]{4})년\s*([\d]{2})월\s*([\d]{2})일.*?([\d]{2}):([\d]{2}):([\d]{2})",
        bet_info_div.get_text()
    )
    if match:
        year, month, day, hour, minute, second = map(int, match.groups())
        try:
            participated_at = datetime(year, month, day, hour, minute, second)
        except ValueError as e:
            print(f"[오류] 마감 시각 파싱 실패 → slug={slug}, post_id={post_id}, error={e}")
            return []
    else:
        print(f"[오류] 마감 시각 형식 불일치 → slug={slug}, post_id={post_id}")
        return []

    # ✅ 참여자 정보 파싱
    records = []
    for bet_side, item in enumerate(soup.select("div.wato_view div.item")):
        for row in item.select("div.apply_list tbody tr"):
            cols = row.find_all("td")
            if len(cols) < 4:
                print(f"[스킵] 참여자 row 칼럼 수 부족 → slug={slug}, post_id={post_id}")
                continue

            nickname = cols[0].get_text(strip=True)
            try:
                bet = int(cols[1].get_text(strip=True).replace(",", ""))
                payout = int(cols[2].get_text(strip=True).replace(",", ""))
            except ValueError:
                print(f"[스킵] 숫자 파싱 실패 → slug={slug}, post_id={post_id}, nickname={nickname}")
                continue

            records.append({
                "post_id": int(post_id),
                "slug": slug,
                "bet_side": bet_side,
                "nickname": nickname,
                "bet_amount": bet,
                "payout_amount": payout,
                "participated_at": participated_at
            })

    if not records:
        print(f"[스킵] 참여자 없음 → slug={slug}, post_id={post_id}")

    return records


def get_or_create_user(cur, nickname, cache=None):
    if cache is not None and nickname in cache:
        return cache[nickname]

    cur.execute("INSERT INTO users (nickname) VALUES (%s) ON CONFLICT (nickname) DO NOTHING;", (nickname,))
    cur.execute("SELECT id FROM users WHERE nickname = %s", (nickname,))
    user_id = cur.fetchone()[0]

    if cache is not None:
        cache[nickname] = user_id

    return user_id


def get_or_create_board(cur, slug, cache=None):
    if cache is not None and slug in cache:
        return cache[slug]

    cur.execute("INSERT INTO boards (slug, name) VALUES (%s, %s) ON CONFLICT (slug) DO NOTHING;", (slug, slug))
    cur.execute("SELECT id FROM boards WHERE slug = %s", (slug,))
    board_id = cur.fetchone()[0]

    if cache is not None:
        cache[slug] = board_id

    return board_id


def update_daily_stats(cur):
    cur.execute("""
        WITH per_post_all AS (
            SELECT
                CASE
                    WHEN EXTRACT(HOUR FROM deadline_date) < 5
                    THEN (deadline_date - INTERVAL '1 day')::DATE
                    ELSE deadline_date::DATE
                END AS d,
                user_id,
                board_id,
                SUM(profit) AS net_profit
            FROM betting_stats
            GROUP BY d, user_id, board_id
        ),
        per_post_single AS (
            SELECT
                CASE
                    WHEN EXTRACT(HOUR FROM deadline_date) < 5
                    THEN (deadline_date - INTERVAL '1 day')::DATE
                    ELSE deadline_date::DATE
                END AS d,
                user_id,
                board_id,
                post_id,
                MAX(bet_amount) AS amount_one_side,
                CASE WHEN SUM(profit) > 0 THEN 1 ELSE 0 END AS post_win
            FROM betting_stats
            GROUP BY d, user_id, board_id, post_id
            HAVING COUNT(DISTINCT bet_side) = 1
        ),
        per_day AS (
            SELECT
                a.d AS stat_date,
                a.user_id,
                a.board_id,
                COUNT(s.post_id) AS total_bets,
                COALESCE(SUM(s.amount_one_side), 0) AS total_amount,
                a.net_profit AS total_profit,
                COALESCE(SUM(s.post_win), 0) AS wins
            FROM per_post_all a
            LEFT JOIN per_post_single s
            ON a.d = s.d AND a.user_id = s.user_id AND a.board_id = s.board_id
            GROUP BY a.d, a.user_id, a.board_id, a.net_profit
        )
        INSERT INTO daily_betting_stats (stat_date, user_id, board_id, total_bets, total_amount, total_profit, wins, created_at)
        SELECT stat_date, user_id, board_id, total_bets, total_amount, total_profit, wins, NOW()
        FROM per_day
        ON CONFLICT (stat_date, user_id, board_id)
        DO UPDATE SET
            total_bets   = EXCLUDED.total_bets,
            total_amount = EXCLUDED.total_amount,
            total_profit = EXCLUDED.total_profit,
            wins         = EXCLUDED.wins,
            created_at   = NOW();
    """)


def update_monthly_stats(cur):
    cur.execute("""
        WITH per_post_all AS (
            SELECT
                CASE
                    WHEN EXTRACT(HOUR FROM deadline_date) < 5
                    THEN DATE_TRUNC('month', deadline_date - INTERVAL '1 day')::DATE
                    ELSE DATE_TRUNC('month', deadline_date)::DATE
                END AS m,
                user_id,
                board_id,
                SUM(profit) AS net_profit
            FROM betting_stats
            GROUP BY m, user_id, board_id
        ),
        per_post_single AS (
            SELECT
                CASE
                    WHEN EXTRACT(HOUR FROM deadline_date) < 5
                    THEN DATE_TRUNC('month', deadline_date - INTERVAL '1 day')::DATE
                    ELSE DATE_TRUNC('month', deadline_date)::DATE
                END AS m,
                user_id,
                board_id,
                post_id,
                MAX(bet_amount) AS amount_one_side,
                CASE WHEN SUM(profit) > 0 THEN 1 ELSE 0 END AS post_win
            FROM betting_stats
            GROUP BY m, user_id, board_id, post_id
            HAVING COUNT(DISTINCT bet_side) = 1
        ),
        per_month AS (
            SELECT
                a.m AS stat_month,
                a.user_id,
                a.board_id,
                COUNT(s.post_id) AS total_bets,
                COALESCE(SUM(s.amount_one_side), 0) AS total_amount,
                a.net_profit AS total_profit,
                COALESCE(SUM(s.post_win), 0) AS wins
            FROM per_post_all a
            LEFT JOIN per_post_single s
            ON a.m = s.m AND a.user_id = s.user_id AND a.board_id = s.board_id
            GROUP BY a.m, a.user_id, a.board_id, a.net_profit
        )
        INSERT INTO monthly_betting_stats (stat_month, user_id, board_id, total_bets, total_amount, total_profit, wins, created_at)
        SELECT stat_month, user_id, board_id, total_bets, total_amount, total_profit, wins, NOW()
        FROM per_month
        ON CONFLICT (stat_month, user_id, board_id)
        DO UPDATE SET
            total_bets   = EXCLUDED.total_bets,
            total_amount = EXCLUDED.total_amount,
            total_profit = EXCLUDED.total_profit,
            wins         = EXCLUDED.wins,
            created_at   = NOW();
    """)


# app/crawler/service.py → insert_records 교체
def insert_records(posts_records):
    conn = get_connection()
    cur = conn.cursor()

    user_cache = {}
    board_cache = {}

    for post_id, records in posts_records.items():
        if not records:
            continue

        # 게시판별 중복 체크: (board_id, post_id)
        first_slug = records[0]["slug"]
        board_id_for_check = get_or_create_board(cur, first_slug, board_cache)
        cur.execute(
            "SELECT 1 FROM betting_stats WHERE board_id = %s AND post_id = %s LIMIT 1;",
            (board_id_for_check, post_id),
        )
        if cur.fetchone():
            continue

        for r in records:
            user_id = get_or_create_user(cur, r["nickname"], user_cache)
            board_id = get_or_create_board(cur, r["slug"], board_cache)

            cur.execute("""
                INSERT INTO betting_stats 
                (post_id, deadline_date, user_id, board_id, bet_side, bet_amount, payout_amount, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (user_id, board_id, post_id, bet_side) DO NOTHING;
            """, (
                r["post_id"], r["participated_at"], user_id, board_id,
                r["bet_side"], r["bet_amount"], r["payout_amount"]
            ))

    update_daily_stats(cur)
    update_monthly_stats(cur)

    conn.commit()
    cur.close()
    conn.close()
