"""Đọc/ghi dữ liệu ra file JSON (dữ liệu thô) và CSV (dữ liệu đã xử lý)."""

import json
import os

import pandas as pd


def save_json(data, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def export_csv(df: pd.DataFrame, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
