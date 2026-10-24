"""Cấu hình chung: đọc .env, endpoint API, đường dẫn file và logging."""

import logging
import os

from dotenv import load_dotenv

# Đọc file .env (nếu có) vào biến môi trường — key KHÔNG viết thẳng trong code
load_dotenv()

API_URL = "https://www.googleapis.com/youtube/v3"
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
BQ_DATASET = os.getenv("BQ_DATASET", "atvncg_youtube")

ARTISTS_PATH = "config/artists.csv"
RAW_DIR = "data/raw"
PROCESSED_DIR = "data/processed"

TOP_N = 10
MAX_COMMENTS = 200


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
