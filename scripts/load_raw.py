"""Nạp các file CSV của Home Credit vào schema raw của DuckDB.

Cách dùng:
    python scripts/load_raw.py
    python scripts/load_raw.py --raw-dir D:/data/home-credit --db data/warehouse.duckdb
"""
import argparse
import sys
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = ROOT / "data" / "raw"
DEFAULT_DB = ROOT / "data" / "warehouse.duckdb"

# Tên bảng trong schema raw -> tên file CSV gốc
RAW_FILES = {
    "application_train": "application_train.csv",
    "previous_application": "previous_application.csv",
    "pos_cash_balance": "POS_CASH_balance.csv",
    "credit_card_balance": "credit_card_balance.csv",
    "installments_payments": "installments_payments.csv",
}


def lowercase_column_names(con, table):
    """SK_ID_PREV -> sk_id_prev. Chỉ đổi tên cột, không đổi dữ liệu."""
    for (column,) in con.execute(f"select column_name from (describe {table})").fetchall():
        if column != column.lower():
            con.execute(f'alter table {table} rename column "{column}" to "{column.lower()}"')


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Load Home Credit CSV files into DuckDB.")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    missing = [name for name in RAW_FILES.values() if not (args.raw_dir / name).exists()]
    if missing:
        sys.exit(f"Missing in {args.raw_dir}: {', '.join(missing)}. Run scripts/download_data.py first.")

    args.db.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(args.db))
    con.execute("create schema if not exists raw")

    print(f"Loading CSV into {args.db}")
    for table, filename in RAW_FILES.items():
        start = time.perf_counter()
        path = (args.raw_dir / filename).resolve().as_posix().replace("'", "''")
        # sample_size = -1: đọc toàn bộ file khi suy luận kiểu dữ liệu, tránh đoán sai
        # kiểu của những cột chỉ có giá trị ở cuối file.
        con.execute(f"""
            create or replace table raw.{table} as
            select * from read_csv('{path}', header = true, sample_size = -1)
        """)
        lowercase_column_names(con, f"raw.{table}")
        n_rows = con.execute(f"select count(*) from raw.{table}").fetchone()[0]
        print(f"  raw.{table:<24} {n_rows:>12,} rows  ({time.perf_counter() - start:.0f}s)")

    con.close()


if __name__ == "__main__":
    main()
