import os
import time
from app.crawler.service import parse_list_page, parse_post, insert_records

def _get_slugs():
    raw = os.getenv("SLUGS", "pan_setkacup")
    return [s.strip() for s in raw.split(",") if s.strip()]

def main():
    start_time = time.time()

    for slug in _get_slugs():
        print(f"[INFO] 게시판 시작: {slug}")
        for page in range(1, 9):
            print(f"크롤링 중: 게시판 페이지 {page}")
            post_ids = parse_list_page(page, slug)

            posts_records = {}
            for pid in post_ids:
                recs = parse_post(pid, slug)
                if recs:
                    posts_records[pid] = recs
                print(f"[{slug} #{pid}] 파싱된 레코드 수: {len(recs)}")
                time.sleep(0.2)

            if posts_records:
                insert_records(posts_records)

            time.sleep(0.8)
        print(f"[OK] 게시판 완료: {slug}")

    elapsed = time.time() - start_time
    print(f"크롤링 및 DB 저장 완료 (총 소요: {elapsed:.2f}초)")

if __name__ == "__main__":
    main()
