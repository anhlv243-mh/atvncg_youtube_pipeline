"""test_connect.py — kiểm tra môi trường đã kết nối BigQuery chưa.

Chạy được và in ra ok = 1 nghĩa là môi trường sẵn sàng.
"""
import os

from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()  # nạp GOOGLE_APPLICATION_CREDENTIALS, GCP_PROJECT_ID từ .env

# Client tự đọc biến môi trường GOOGLE_APPLICATION_CREDENTIALS
client = bigquery.Client(project=os.getenv("GCP_PROJECT_ID"))

df = client.query("SELECT 1 AS ok").to_dataframe()
print(df)
