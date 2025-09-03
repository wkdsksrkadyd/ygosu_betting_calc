import time
from app.crawler.service import parse_list_page, parse_post, insert_records

def main():
    start_time = time.time()  # ✅ 시작 시각 기록

    for page in range(1, 9):  # 원하는 페이지 범위 조정 가능
        # print(f"크롤링 중: 게시판 페이지 {page}")
        post_ids = parse_list_page(page)
        for pid in post_ids:
            # print(f" → 게시물 {pid} 크롤링 중...")
            recs = parse_post(pid)
            if recs:
                insert_records(recs)
            time.sleep(0.2)
        time.sleep(0.8)
        

    end_time = time.time()  # ✅ 종료 시각 기록
    elapsed = end_time - start_time
    print(f"크롤링 및 DB 저장 완료 (소요 시간: {elapsed:.2f}초)")

if __name__ == "__main__":
    main()
