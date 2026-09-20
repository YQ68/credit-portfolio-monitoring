"""Build các bảng stg, core (và mart khi có) rồi chạy data test.

Cách dùng:
    python scripts/build.py               # build tất cả và chạy test
    python scripts/build.py --tests-only  # chỉ chạy test

Test là file .sql trong sql/tests/, trả về các dòng vi phạm (0 dòng = đạt).
Dòng đầu file ghi mức độ: "-- severity: error" (dừng pipeline) hoặc "-- severity: warn".
"""
import argparse
import sys
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
DEFAULT_DB = ROOT / "data" / "warehouse.duckdb"

# Thứ tự build: file sau phụ thuộc file trước. Thêm mart mới vào cuối danh sách.
MODELS = [
    "00_setup.sql",
    "stg/stg_application.sql",
    "stg/stg_previous_application.sql",
    "stg/stg_pos_cash_balance.sql",
    "stg/stg_credit_card_balance.sql",
    "stg/stg_installments_payments.sql",
    "core/int_loan_month.sql",
    "core/dim_loan.sql",
    "core/fct_loan_month.sql",
    "mart/mart_funnel_by_channel.sql",
    "mart/mart_fpd_by_segment.sql",
    "mart/mart_vintage.sql",
    "mart/mart_roll_rate.sql",
]


def run_models(con):
    print("Building models")
    for rel_path in MODELS:
        start = time.perf_counter()
        con.execute((SQL_DIR / rel_path).read_text(encoding="utf-8"))
        print(f"  ok    {rel_path}  ({time.perf_counter() - start:.1f}s)")


def read_severity(sql):
    for line in sql.splitlines():
        if line.strip().lower().startswith("-- severity:"):
            return line.split(":", 1)[1].strip().lower()
    return "error"


def run_tests(con):
    print("Running tests")
    n_failed = 0
    for path in sorted((SQL_DIR / "tests").glob("*.sql")):
        sql = path.read_text(encoding="utf-8").strip().rstrip(";")
        severity = read_severity(sql)
        n_rows = con.execute(f"select count(*) from (\n{sql}\n)").fetchone()[0]
        if n_rows == 0:
            print(f"  pass  {path.stem}")
            continue

        label = "FAIL" if severity == "error" else "WARN"
        print(f"  {label}  {path.stem}: {n_rows:,} rows")
        con.sql(f"select * from (\n{sql}\n) limit 5").show()
        if severity == "error":
            n_failed += 1
    return n_failed


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build SQL models and run data tests.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--tests-only", action="store_true")
    args = parser.parse_args()

    if not args.db.exists():
        sys.exit(f"{args.db} not found. Run scripts/load_raw.py first.")

    con = duckdb.connect(str(args.db))
    if not args.tests_only:
        run_models(con)
    n_failed = run_tests(con)
    con.close()

    if n_failed:
        sys.exit(f"{n_failed} error test(s) failed.")
    print("All error tests passed.")


if __name__ == "__main__":
    main()
