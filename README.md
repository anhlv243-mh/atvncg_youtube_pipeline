# ATVNCG 2026 YouTube Data Pipeline

Pipeline ETL lấy dữ liệu YouTube của **34 anh tài – Anh Trai Vượt Ngàn Chông Gai 2026** (những ai có kênh YouTube):

```
YouTube Data API v3 → Python (extract) → pandas (transform) → BigQuery (load) → GitHub
```

## Dữ liệu đầu ra (BigQuery dataset `atvncg_youtube`)

| Bảng | Grain | Nội dung chính |
|---|---|---|
| `artists` | 1 dòng / anh tài **có kênh YouTube** | `artist_name`, `channel_id` — nối anh tài với kênh |
| `channels` | 1 dòng / kênh | tên kênh, subscriber, tổng view, số video, playlist uploads |
| `videos` | 1 dòng / video | toàn bộ video của các kênh: title, published_at, duration_seconds, view/like/comment |
| `comments` | 1 dòng / comment | tối đa 200 comment gốc của **top 10 video nhiều view nhất** (tính trên tất cả kênh) |

- Thỏ và Thơm (Da LAB) dùng chung kênh **Da LAB** → kênh chỉ lấy 1 lần; muốn biết video của ai thì `JOIN artists USING (channel_id)`.
- Mọi bảng load kiểu **full load** (`WRITE_TRUNCATE`): mỗi lần chạy lấy lại số view mới nhất, chạy lại không bị nhân đôi dữ liệu.

## Cấu trúc project

```
atvncg_youtube_pipeline/
├── config/
│   └── artists.csv     # danh sách anh tài: artist_name, keyword (từ khoá tìm kênh), channel_id
├── etl/
│   ├── __init__.py
│   ├── config.py       # đọc .env, endpoint API, đường dẫn, TOP_N/MAX_COMMENTS, logging
│   ├── extract.py      # gọi YouTube API: search, channels, playlistItems, videos, commentThreads
│   ├── transform.py    # JSON lồng nhau → DataFrame, làm sạch, ép kiểu
│   ├── storage.py      # lưu JSON thô / CSV đã xử lý
│   └── load.py         # load DataFrame → BigQuery
├── data/               # (gitignore) raw/*.json, processed/*.csv
├── main.py             # CLI: run() điều phối extract → transform → load
├── test_connect.py     # kiểm tra kết nối BigQuery
├── requirements.txt
├── .env.example        # mẫu biến môi trường (KHÔNG chứa key thật)
└── .gitignore
```

## Kiến thức áp dụng theo lộ trình

| Lesson | Áp dụng vào project |
|---|---|
| 1. Linux & command line | `mkdir`, `touch`, heredoc + redirection để dựng thư mục, tạo `artists.csv` |
| 2. Python & Project Structure | `.venv`, `requirements.txt`, package `etl/` + `__init__.py`, `.gitignore` |
| 3. API & JSON → DataFrame | `requests.get` + headers/params, phân trang `nextPageToken`, bóc JSON → `list[dict]` → `pd.DataFrame` |
| 4. Thiết kế Project / Step Pipeline | `main.py` chia bước, `argparse`, `logging`, lỗi HTTP thì log warning và chạy tiếp |
| 5. ETL / ELT trên Cloud | `extract()/transform()/load()`, `load_table_from_dataframe`, `WRITE_TRUNCATE`, `test_connect.py` |

Riêng `.env` + `python-dotenv` (học ở buổi sau) được dùng thêm để giữ key ngoài source code.

## Cài đặt

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # rồi điền giá trị thật vào .env
```

### 1. YouTube API key
1. Vào [Google Cloud Console](https://console.cloud.google.com/) → chọn project.
2. **APIs & Services → Library** → tìm **YouTube Data API v3** → **Enable**.
3. **APIs & Services → Credentials → Create credentials → API key**.
4. Dán key vào `YOUTUBE_API_KEY` trong `.env`.

### 2. BigQuery
1. Tạo service account (quyền **BigQuery Data Editor** + **BigQuery Job User**), tải key JSON về, đặt tên `key.json` ở thư mục gốc project
   (hoặc chạy `gcloud auth application-default login` và để trống `GOOGLE_APPLICATION_CREDENTIALS`).
2. Điền `GCP_PROJECT_ID` trong `.env`.
3. Tạo dataset `atvncg_youtube` trên [BigQuery Studio](https://console.cloud.google.com/bigquery).
4. Kiểm tra kết nối: `python test_connect.py` → in ra `ok = 1` là đạt.

## Chạy

```bash
# Bước chuẩn bị: tìm channel_id cho anh tài CHƯA có channel_id (theo cột keyword)
python main.py --find-channels
# → mở data/processed/channel_candidates.csv: mỗi anh tài có tối đa 3 ứng viên (đã bỏ kênh "- Topic"),
#   mở channel_url kiểm tra tay, chép channel_id đúng vào config/artists.csv.
#   Kênh sai hết → sửa keyword (vd thêm "official") rồi chạy lại; chỉ dòng còn trống mới bị tìm lại.

# Chạy pipeline
python main.py                                   # top 10 video, tối đa 200 comment/video
python main.py --top-n 5 --max-comments 100      # đổi tham số
python main.py --skip-load                       # chỉ lưu file trong data/, không load BigQuery
```

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `--find-channels` | — | Chỉ tìm kênh gợi ý (top 3) cho anh tài chưa có `channel_id`, không chạy pipeline |
| `--top-n` | 10 | Số video nhiều view nhất cần lấy comment |
| `--max-comments` | 200 | Số comment tối đa mỗi video |
| `--skip-load` | — | Bỏ qua bước load BigQuery |
| `--log-level` | INFO | DEBUG / INFO / WARNING / ERROR |

## Quota YouTube API (10.000 unit/ngày)

| Lệnh | Ước tính |
|---|---|
| `--find-channels` | 100 unit / từ khoá (search.list), chỉ tính các anh tài chưa có `channel_id` |
| `python main.py` | channels 1 unit + (số video / 50) × 2 unit + 10 video × 2 unit comment → thường < 500 unit |

## Bảo mật

- Key chỉ nằm trong `.env` và `key.json` — cả hai đã có trong `.gitignore`, **không commit lên GitHub**.
- API key gửi qua header `X-Goog-Api-Key` thay vì trên URL, nên log lỗi không làm lộ key.
- Trước khi push, kiểm tra: `git status` không được có `.env` hay `key.json`.
