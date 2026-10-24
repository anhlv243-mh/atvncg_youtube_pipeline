"""Bước TRANSFORM — bóc JSON lồng nhau thành list[dict] phẳng, dựng DataFrame rồi làm sạch.

Làm sạch chung cho mọi bảng:
  - Bỏ dòng trùng theo khoá chính.
  - Bỏ khoảng trắng thừa ở cột chữ.
  - Số (API trả về dạng chuỗi) → Int64; thời gian ISO 8601 → datetime UTC.
  - Thêm cột loaded_at để biết dữ liệu nạp lúc nào.
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def to_int(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Ép cột sang Int64 (kiểu số nguyên cho phép rỗng, vd video ẩn số like)."""
    for col in columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    return df


def to_datetime(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        df[col] = pd.to_datetime(df[col], format="ISO8601", utc=True)
    return df


def transform_artists(df: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn hoá danh sách anh tài; CHỈ giữ anh tài có kênh YouTube (đã có channel_id)."""
    df = df.drop_duplicates(subset="artist_name").copy()
    for col in ["artist_name", "keyword", "channel_id"]:
        df[col] = df[col].str.strip()

    has_channel = df["channel_id"].fillna("") != ""
    if not has_channel.all():
        skipped = df.loc[~has_channel, "artist_name"]
        logger.warning("Bỏ qua %d anh tài chưa có channel_id: %s", len(skipped), ", ".join(skipped))
    df = df[has_channel].copy()
    df["loaded_at"] = pd.Timestamp.now(tz="UTC")
    return df


def transform_channels(items: list[dict]) -> pd.DataFrame:
    """1 dòng / kênh."""
    rows = []
    for item in items:
        snippet = item["snippet"]
        stats = item.get("statistics", {})
        rows.append(
            {
                "channel_id": item["id"],
                "channel_title": snippet["title"],
                "custom_url": snippet.get("customUrl"),
                "country": snippet.get("country"),
                "published_at": snippet["publishedAt"],
                "subscriber_count": stats.get("subscriberCount"),
                "view_count": stats.get("viewCount"),
                "video_count": stats.get("videoCount"),
                "uploads_playlist_id": item["contentDetails"]["relatedPlaylists"]["uploads"],
            }
        )
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).drop_duplicates(subset="channel_id")
    df["channel_title"] = df["channel_title"].str.strip()
    df = to_datetime(df, ["published_at"])
    df = to_int(df, ["subscriber_count", "view_count", "video_count"])
    df["loaded_at"] = pd.Timestamp.now(tz="UTC")
    return df


def transform_videos(items: list[dict]) -> pd.DataFrame:
    """1 dòng / video. duration dạng ISO 8601 (vd PT3M45S) → duration_seconds."""
    rows = []
    for item in items:
        snippet = item["snippet"]
        stats = item.get("statistics", {})
        content = item.get("contentDetails", {})
        rows.append(
            {
                "video_id": item["id"],
                "channel_id": snippet["channelId"],
                "channel_title": snippet["channelTitle"],
                "title": snippet["title"],
                "description": snippet.get("description"),
                "published_at": snippet["publishedAt"],
                "category_id": snippet.get("categoryId"),
                "tags": ", ".join(snippet.get("tags", [])),
                "live_status": snippet.get("liveBroadcastContent"),
                "duration": content.get("duration"),
                "definition": content.get("definition"),
                "view_count": stats.get("viewCount"),
                "like_count": stats.get("likeCount"),
                "comment_count": stats.get("commentCount"),
            }
        )
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).drop_duplicates(subset="video_id")
    df["title"] = df["title"].str.strip()
    df["duration_seconds"] = (
        pd.to_timedelta(df["duration"], errors="coerce").dt.total_seconds().astype("Int64")
    )
    df = to_datetime(df, ["published_at"])
    df = to_int(df, ["view_count", "like_count", "comment_count"])
    df["loaded_at"] = pd.Timestamp.now(tz="UTC")
    return df


def pick_top_videos(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """Top n video nhiều view nhất trên tất cả các kênh."""
    return df.sort_values("view_count", ascending=False).head(n)


def transform_comments(items: list[dict]) -> pd.DataFrame:
    """1 dòng / comment gốc (top-level), bỏ comment rỗng."""
    rows = []
    for item in items:
        thread = item["snippet"]
        comment = thread["topLevelComment"]["snippet"]
        rows.append(
            {
                "comment_id": thread["topLevelComment"]["id"],
                "video_id": thread["videoId"],
                "channel_id": thread.get("channelId"),
                "author_name": comment.get("authorDisplayName"),
                "author_channel_id": comment.get("authorChannelId", {}).get("value"),
                "text": comment.get("textDisplay"),
                "like_count": comment.get("likeCount"),
                "reply_count": thread.get("totalReplyCount"),
                "published_at": comment["publishedAt"],
                "updated_at": comment.get("updatedAt"),
            }
        )
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).drop_duplicates(subset="comment_id")
    df["text"] = df["text"].str.strip()
    df = df[df["text"].notna() & (df["text"] != "")].copy()
    df = to_datetime(df, ["published_at", "updated_at"])
    df = to_int(df, ["like_count", "reply_count"])
    df["loaded_at"] = pd.Timestamp.now(tz="UTC")
    return df
