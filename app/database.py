import psycopg2
import os
from dotenv import load_dotenv
from pathlib import Path


# .env 파일 불러오기
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# 로컬용
# DB_CONFIG = {
#     "dbname": "ygosu",
#     "user": "postgres",
#     "password": "P@ssw0rd",
#     "host": "localhost",
#     "port": 5432,
# }

# .env 실무
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", 5432)),  # 문자열이므로 int로 변환 필요
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)
