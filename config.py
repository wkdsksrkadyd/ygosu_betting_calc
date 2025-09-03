import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    CRAWLER_SECRET_KEY = os.getenv("CRAWLER_SECRET_KEY", "default_secret")