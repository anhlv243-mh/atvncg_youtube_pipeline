"""Bước LOAD — nạp DataFrame lên BigQuery.

table_id gồm 3 phần: "project.dataset.table" (dataset phải tạo sẵn trên BigQuery Studio).
Client tự đọc biến môi trường GOOGLE_APPLICATION_CREDENTIALS (đã nạp từ .env).
"""

import logging

from google.cloud import bigquery

from .config import GCP_PROJECT_ID

logger = logging.getLogger(__name__)


def load(df, table_id: str, write_disposition: str = "WRITE_TRUNCATE") -> None:
    """Nạp DataFrame lên một bảng BigQuery.

    Mặc định WRITE_TRUNCATE (full load): mỗi lần chạy lấy lại toàn bộ video với số view mới nhất,
    nếu dùng WRITE_APPEND thì chạy lại sẽ nhân đôi dữ liệu.
    """
    client = bigquery.Client(project=GCP_PROJECT_ID)
    job_config = bigquery.LoadJobConfig(write_disposition=write_disposition)
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()  # chặn tới khi job nạp xong
    logger.info("Đã nạp %d dòng vào %s (%s)", len(df), table_id, write_disposition)
