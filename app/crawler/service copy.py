import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from app.database import get_connection
import os

SLUG = os.getenv("SLUG", "pan_setkacup")
BASE_LIST_URL = f"https://ygosu.com/board/{SLUG}/?s_wato=Y&page={{}}"
BASE_POST_URL = f"https://ygosu.com/board/{SLUG}/{{}}"


def parse_list_page(page):
    url = BASE_LIST_URL.format(page)
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


def parse_post(post_id, slug=SLUG):
    url = BASE_POST_URL.format(post_id)
    res = requests.get(url, timeout=10)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    records = []
    for bet_side, item in enumerate(soup.select("div.wato_view div.item")):
        for row in item.select("div.apply_list tbody tr"):
            cols = row.find_all("td")
            if len(cols) < 4:
                continue

            nickname = cols[0].get_text(strip=True)
            bet = int(cols[1].get_text(strip=True).replace(",", ""))
            payout = int(cols[2].get_text(strip=True).replace(",", ""))

            # ✅ 참여 시각 파싱
            participated_at = None
            time_txt = cols[3].get_text(strip=True)
            m = re.match(r"(\d{2})일 (\d{2}):(\d{2}):(\d{2})", time_txt)
            if m:
                day = int(m.group(1))
                hour, minute, second = map(int, m.groups()[1:])
                today = datetime.now()
                participated_at = datetime(today.year, today.month, day, hour, minute, second)

            records.append({
                "post_id": int(post_id),
                "slug": slug,
                "bet_side": bet_side,
                "nickname": nickname,
                "bet_amount": bet,
                "payout_amount": payout,
                "participated_at": participated_at
            })
    return records


def get_or_create_user(cur, nickname):
    cur.execute("INSERT INTO users (nickname) VALUES (%s) ON CONFLICT (nickname) DO NOTHING;", (nickname,))
    cur.execute("SELECT id FROM users WHERE nickname = %s", (nickname,))
    return cur.fetchone()[0]


def get_or_create_board(cur, slug):
    cur.execute("INSERT INTO boards (slug, name) VALUES (%s, %s) ON CONFLICT (slug) DO NOTHING;", (slug, slug))
    cur.execute("SELECT id FROM boards WHERE slug = %s", (slug,))
    return cur.fetchone()[0]


def update_daily_stats(cur):
    cur.execute("""
        INSERT INTO daily_betting_stats (stat_date, user_id, board_id, total_bets, total_amount, total_profit, wins, created_at)
        SELECT DATE(participated_at), user_id, board_id,
               COUNT(*), SUM(bet_amount), SUM(profit),
               SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END), NOW()
        FROM betting_stats
        GROUP BY DATE(participated_at), user_id, board_id
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
        INSERT INTO monthly_betting_stats (stat_month, user_id, board_id, total_bets, total_amount, total_profit, wins, created_at)
        SELECT DATE_TRUNC('month', participated_at)::DATE, user_id, board_id,
               COUNT(*), SUM(bet_amount), SUM(profit),
               SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END), NOW()
        FROM betting_stats
        GROUP BY DATE_TRUNC('month', participated_at), user_id, board_id
        ON CONFLICT (stat_month, user_id, board_id)
        DO UPDATE SET
            total_bets   = EXCLUDED.total_bets,
            total_amount = EXCLUDED.total_amount,
            total_profit = EXCLUDED.total_profit,
            wins         = EXCLUDED.wins,
            created_at   = NOW();
    """)


def insert_records(posts_records):
    conn = get_connection()
    cur = conn.cursor()

    # ✅ 유저 & 보드 캐시 초기화
    user_cache = {}
    board_cache = {}

    cur.execute("SELECT id, nickname FROM users;")
    for uid, nickname in cur.fetchall():
        user_cache[nickname] = uid

    cur.execute("SELECT id, slug FROM boards;")
    for bid, slug in cur.fetchall():
        board_cache[slug] = bid

    for post_id, records in posts_records.items():
        cur.execute("SELECT 1 FROM betting_stats WHERE post_id = %s LIMIT 1;", (post_id,))
        if cur.fetchone():
            continue

        for r in records:
            nickname = r["nickname"]
            slug = r["slug"]

            if nickname not in user_cache:
                cur.execute("INSERT INTO users (nickname) VALUES (%s) ON CONFLICT (nickname) DO NOTHING;", (nickname,))
                cur.execute("SELECT id FROM users WHERE nickname = %s", (nickname,))
                user_id = cur.fetchone()[0]
                user_cache[nickname] = user_id
            else:
                user_id = user_cache[nickname]

            if slug not in board_cache:
                cur.execute("INSERT INTO boards (slug, name) VALUES (%s, %s) ON CONFLICT (slug) DO NOTHING;", (slug, slug))
                cur.execute("SELECT id FROM boards WHERE slug = %s", (slug,))
                board_id = cur.fetchone()[0]
                board_cache[slug] = board_id
            else:
                board_id = board_cache[slug]

            cur.execute("""
                INSERT INTO betting_stats 
                (post_id, participated_at, user_id, board_id, bet_side, bet_amount, payout_amount, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (user_id, post_id, bet_side) DO NOTHING;
            """, (
                r["post_id"], r["participated_at"], user_id, board_id,
                r["bet_side"], r["bet_amount"], r["payout_amount"]
            ))

    update_daily_stats(cur)
    update_monthly_stats(cur)

    conn.commit()
    cur.close()
    conn.close()
