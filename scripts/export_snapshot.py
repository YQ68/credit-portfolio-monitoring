# -*- coding: utf-8 -*-
"""Build mart.portfolio_snapshot và xuất CSV cho trang 1 của báo cáo Power BI.

Trang 1 của dashboard/index.html đọc thẳng core.fct_loan_month chứ không qua mart,
nên bốn file CSV do build_dashboard.py xuất ra không đủ để dựng lại trang đó.
Script này lấp chỗ trống.

Chạy: .venv/Scripts/python.exe scripts/export_snapshot.py
"""
import sys
from pathlib import Path

import duckdb

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SQL = ROOT / "sql" / "mart" / "mart_portfolio_snapshot.sql"
OUT = ROOT / "data" / "export" / "mart_portfolio_snapshot.csv"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(ROOT / "data" / "warehouse.duckdb"))
    try:
        con.execute(SQL.read_text(encoding="utf-8"))
        con.execute(
            "copy (select * from mart.portfolio_snapshot) to ? (header, delimiter ',')",
            [str(OUT)],
        )
        rows = con.execute(
            "select dpd_bucket, sum(n_loans) as n from mart.portfolio_snapshot "
            "group by 1 order by 1"
        ).fetchall()
    finally:
        con.close()

    total = sum(n for _, n in rows)
    print(f"Đã ghi {OUT.relative_to(ROOT)}")
    for bucket, n in rows:
        print(f"  {bucket:<12} {n:>8,} {100 * n / total:>6.2f}%")
    print(f"  {'TỔNG':<12} {total:>8,}")
    print("\nĐối chiếu: B0 Current phải ra 98,65% như trang 1 của dashboard/index.html.")


if __name__ == "__main__":
    main()
