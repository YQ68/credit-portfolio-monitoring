"""Chạy một file SQL và in kết quả của từng câu lệnh.

Cách dùng:
    python scripts/query.py sql/explore/01_profile.sql
    python scripts/query.py sql/explore/01_profile.sql --max-rows 100

Các câu lệnh trong file phân tách bằng dấu ; ở cuối dòng.
Dòng comment ngay trước code của mỗi câu lệnh được in làm tiêu đề.
"""
import argparse
import re
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "warehouse.duckdb"


def is_comment_or_blank(line):
    stripped = line.strip()
    return not stripped or stripped.startswith("--")


def split_statements(sql):
    chunks = re.split(r";[ \t]*(?:\r?\n|$)", sql)
    return [c.strip() for c in chunks if not all(is_comment_or_blank(l) for l in c.splitlines())]


def statement_title(statement):
    title = None
    for line in statement.splitlines():
        if not is_comment_or_blank(line):
            break
        if line.strip():
            title = line.strip()
    return title or statement.splitlines()[0]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run a SQL file against the DuckDB warehouse.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--max-rows", type=int, default=40)
    args = parser.parse_args()

    con = duckdb.connect(str(args.db), read_only=True)
    for statement in split_statements(args.file.read_text(encoding="utf-8")):
        print(f"\n{statement_title(statement)}")
        relation = con.sql(statement)
        if relation is not None:
            relation.show(max_rows=args.max_rows)
    con.close()


if __name__ == "__main__":
    main()
