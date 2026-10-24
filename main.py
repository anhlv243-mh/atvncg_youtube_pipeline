"""CLI: pipeline YouTube → transform → BigQuery cho các anh tài Anh Trai Vượt Ngàn Chông Gai 2026.

Ví dụ:
    python main.py --find-channels               # chạy 1 lần: gợi ý channel_id cho config/artists.csv
    python main.py                               # top 10 video, tối đa 200 comment/video
    python main.py --top-n 5 --max-comments 100 --skip-load
"""

import argparse
import logging

import pandas as pd

from etl.config import (
    ARTISTS_PATH,
    BQ_DATASET,
    GCP_PROJECT_ID,
    MAX_COMMENTS,
    PROCESSED_DIR,
    RAW_DIR,
    TOP_N,
    YOUTUBE_API_KEY,
    setup_logging,
)
from etl.extract import extract_csv, get_channels, get_comments, get_video_ids, get_videos, search_channels
from etl.load import load
from etl.storage import export_csv, save_json
from etl.transform import (
    pick_top_videos,
    transform_artists,
    transform_channels,
    transform_comments,
    transform_videos,
)

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pipeline YouTube các anh tài ATVNCG 2026")
    parser.add_argument(
        "--find-channels", action="store_true", help="Chỉ tìm channel_id gợi ý cho config/artists.csv"
    )
    parser.add_argument(
        "--top-n", type=int, default=TOP_N, help=f"Số video nhiều view nhất cần lấy comment (mặc định: {TOP_N})"
    )
    parser.add_argument(
        "--max-comments", type=int, default=MAX_COMMENTS, help=f"Số comment tối đa mỗi video (mặc định: {MAX_COMMENTS})"
    )
    parser.add_argument(
        "--skip-load", action="store_true", help="Không nạp lên BigQuery, chỉ lưu file trong data/"
    )
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    return parser.parse_args()


def find_channels(artists: pd.DataFrame) -> pd.DataFrame:
    """Tìm kênh cho anh tài CHƯA có channel_id: top 3 ứng viên / keyword, kèm tên kênh + subscriber để chọn tay."""
    todo = artists[artists["channel_id"].isna()]
    logger.info("Cần tìm kênh cho %d/%d anh tài", len(todo), len(artists))
    if todo.empty:
        return todo

    rows = []
    for keyword in todo["keyword"].unique():
        results = search_channels(keyword)
        for rank, result in enumerate(results, start=1):
            rows.append({"keyword": keyword, "rank": rank, "channel_id": result["id"]["channelId"]})
        logger.info("Tìm '%s' → %d ứng viên", keyword, len(results))
    candidates = pd.DataFrame(rows, columns=["keyword", "rank", "channel_id"])

    channels = transform_channels(get_channels(candidates["channel_id"].unique().tolist()))
    if not channels.empty:
        info_cols = ["channel_id", "channel_title", "custom_url", "subscriber_count", "video_count"]
        candidates = candidates.merge(channels[info_cols], on="channel_id", how="left")
    candidates["channel_url"] = "https://www.youtube.com/channel/" + candidates["channel_id"]
    result = todo[["artist_name", "keyword"]].merge(candidates, on="keyword", how="left")
    result["rank"] = result["rank"].astype("Int64")  # merge có dòng rỗng làm rank thành float
    return result


def run(top_n: int, max_comments: int, skip_load: bool) -> None:
    # Bước 1: danh sách anh tài → các kênh cần lấy (Da LAB chỉ lấy 1 lần dù có 2 anh tài)
    artists = transform_artists(extract_csv(ARTISTS_PATH))
    channel_ids = artists["channel_id"].dropna().unique().tolist()
    if not channel_ids:
        logger.error("Chưa có channel_id trong %s — chạy `python main.py --find-channels` trước", ARTISTS_PATH)
        return
    logger.info("Bước 1: %d anh tài, %d kênh", len(artists), len(channel_ids))

    # Bước 2: thông tin kênh
    channel_items = get_channels(channel_ids)
    save_json(channel_items, f"{RAW_DIR}/channels.json")

    # Bước 3: toàn bộ video của từng kênh (playlist uploads → chi tiết video)
    video_items = []
    for channel in channel_items:
        video_ids = get_video_ids(channel["contentDetails"]["relatedPlaylists"]["uploads"])
        video_items.extend(get_videos(video_ids))
        logger.info("Bước 3: kênh %s có %d video", channel["snippet"]["title"], len(video_ids))
    save_json(video_items, f"{RAW_DIR}/videos.json")

    videos = transform_videos(video_items)
    if videos.empty:
        logger.error("Không lấy được video nào, dừng pipeline")
        return

    # Bước 4: comment của top N video nhiều view nhất trên tất cả các kênh
    top_videos = pick_top_videos(videos, top_n)
    comment_items = []
    for _, video in top_videos.iterrows():
        logger.info("Bước 4: %s — %s (%s view)", video["channel_title"], video["title"], video["view_count"])
        comment_items.extend(get_comments(video["video_id"], max_comments))
    save_json(comment_items, f"{RAW_DIR}/comments.json")

    # Bước 5: transform xong → lưu CSV
    tables = {
        "artists": artists,
        "channels": transform_channels(channel_items),
        "videos": videos,
        "comments": transform_comments(comment_items),
    }
    for name, df in tables.items():
        export_csv(df, f"{PROCESSED_DIR}/{name}.csv")
        logger.info("Bước 5: lưu %d dòng vào %s/%s.csv", len(df), PROCESSED_DIR, name)

    # Bước 6: load lên BigQuery (bảng rỗng thì bỏ qua để không xoá mất dữ liệu cũ)
    if skip_load:
        logger.info("Bước 6: bỏ qua load BigQuery (--skip-load)")
        return
    for name, df in tables.items():
        if df.empty:
            logger.warning("Bước 6: bảng %s rỗng, không load", name)
            continue
        load(df, f"{GCP_PROJECT_ID}.{BQ_DATASET}.{name}")


def main() -> None:
    args = parse_args()
    setup_logging(args.log_level)

    if not YOUTUBE_API_KEY:
        logger.error("Chưa có YOUTUBE_API_KEY — copy .env.example thành .env rồi điền key")
        return
    if not GCP_PROJECT_ID and not (args.find_channels or args.skip_load):
        logger.error("Chưa có GCP_PROJECT_ID trong .env (hoặc chạy với --skip-load)")
        return

    if args.find_channels:
        candidates = find_channels(extract_csv(ARTISTS_PATH))
        if candidates.empty:
            logger.info("Mọi anh tài trong %s đã có channel_id, không cần tìm", ARTISTS_PATH)
            return
        export_csv(candidates, f"{PROCESSED_DIR}/channel_candidates.csv")
        logger.info("Đã lưu gợi ý vào %s/channel_candidates.csv — kiểm tra rồi chép channel_id vào %s",
                    PROCESSED_DIR, ARTISTS_PATH)
        return

    run(args.top_n, args.max_comments, args.skip_load)


if __name__ == "__main__":
    main()
