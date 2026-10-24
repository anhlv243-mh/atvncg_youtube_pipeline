"""Bước EXTRACT — đọc danh sách anh tài (CSV) và gọi YouTube Data API v3.

Các endpoint dùng: search, channels, playlistItems, videos, commentThreads.
API key gửi qua header X-Goog-Api-Key (không nằm trên URL) để log lỗi không làm lộ key.
"""

import logging

import pandas as pd
import requests

from .config import API_URL, YOUTUBE_API_KEY

logger = logging.getLogger(__name__)

BATCH_SIZE = 50  # channels/videos nhận tối đa 50 id mỗi lần gọi


def extract_csv(path: str) -> pd.DataFrame:
    """Đọc CSV thành DataFrame, mọi cột là chuỗi để giữ nguyên channel_id."""
    return pd.read_csv(path, dtype=str)


def call_api(endpoint: str, params: dict) -> dict:
    """Gọi 1 endpoint, trả về JSON. Lỗi HTTP (4xx/5xx) thì raise."""
    headers = {"X-Goog-Api-Key": YOUTUBE_API_KEY, "Accept": "application/json"}
    response = requests.get(f"{API_URL}/{endpoint}", headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def search_channels(keyword: str, limit: int = 3) -> list[dict]:
    """Tìm kênh theo từ khoá, trả về tối đa `limit` kết quả đầu.

    Bỏ kênh "- Topic" (kênh YouTube Music tự sinh, không có video).
    search.list tốn 100 unit quota mỗi lần gọi, không phụ thuộc số kết quả.
    """
    params = {"part": "snippet", "q": keyword, "type": "channel", "maxResults": 10, "regionCode": "VN"}
    items = call_api("search", params).get("items", [])
    items = [item for item in items if not item["snippet"]["title"].endswith(" - Topic")]
    return items[:limit]


def get_channels(channel_ids: list[str]) -> list[dict]:
    """Lấy thông tin kênh (snippet, statistics, contentDetails) theo lô 50 id."""
    channels: list[dict] = []
    for i in range(0, len(channel_ids), BATCH_SIZE):
        params = {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(channel_ids[i : i + BATCH_SIZE]),
            "maxResults": BATCH_SIZE,
        }
        channels.extend(call_api("channels", params).get("items", []))
    logger.info("Đã lấy %d/%d kênh", len(channels), len(channel_ids))
    return channels


def get_video_ids(playlist_id: str) -> list[str]:
    """Lặp qua mọi trang của playlist uploads (50 video/trang), gom video_id."""
    video_ids: list[str] = []
    page_token = None
    while True:
        params = {"part": "contentDetails", "playlistId": playlist_id, "maxResults": 50, "pageToken": page_token}
        try:
            payload = call_api("playlistItems", params)
        except requests.exceptions.HTTPError as http_err:
            if http_err.response.status_code != 404:
                raise
            logger.warning("Bỏ qua playlist %s: không tồn tại (kênh chưa có video)", playlist_id)
            break
        video_ids.extend(item["contentDetails"]["videoId"] for item in payload["items"])
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    return video_ids


def get_videos(video_ids: list[str]) -> list[dict]:
    """Lấy chi tiết video (snippet, statistics, contentDetails) theo lô 50 id."""
    videos: list[dict] = []
    for i in range(0, len(video_ids), BATCH_SIZE):
        params = {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(video_ids[i : i + BATCH_SIZE]),
            "maxResults": BATCH_SIZE,
        }
        videos.extend(call_api("videos", params).get("items", []))
    return videos


def get_comments(video_id: str, max_comments: int) -> list[dict]:
    """Lấy tối đa max_comments comment gốc của 1 video, sắp theo độ nổi bật (relevance).

    Video tắt comment (403 commentsDisabled) thì bỏ qua; lỗi khác (vd hết quota) thì raise.
    """
    comments: list[dict] = []
    page_token = None
    while len(comments) < max_comments:
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": min(100, max_comments - len(comments)),
            "order": "relevance",
            "textFormat": "plainText",
            "pageToken": page_token,
        }
        try:
            payload = call_api("commentThreads", params)
        except requests.exceptions.HTTPError as http_err:
            if "commentsDisabled" not in http_err.response.text:
                raise
            logger.warning("Bỏ qua video %s: đã tắt comment", video_id)
            break
        comments.extend(payload["items"])
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    logger.info("Video %s: lấy được %d comment", video_id, len(comments))
    return comments
