# -*- coding: utf-8 -*-
"""Bắt xung đột tên trong semantic model TMDL trước khi mở Power BI Desktop.

Ba quy tắc mà powerbi-report-author validate và MCP ConnectFolder KHÔNG bắt được,
chỉ lộ ra khi Desktop dựng database Analysis Services thật:

  1. measure trùng tên với cột trong CÙNG bảng (không phân biệt hoa thường)
  2. measure trùng tên với tên một BẢNG bất kỳ trong model
  3. measure trùng tên measure khác ở bất kỳ bảng nào (measure là namespace toàn model)

Chạy: python scripts/check_model_names.py <đường-dẫn-thư-mục-.SemanticModel>
Ví dụ: python scripts/check_model_names.py powerbi/CreditPortfolio.SemanticModel
"""
import glob
import os
import re
import sys
from collections import defaultdict


def parse(path):
    """Trả về (tên_bảng, [measure], [cột]) từ một file .tmdl."""
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    m = re.search(r"^table\s+'([^']+)'|^table\s+(\S+)", src, re.M)
    table = (m.group(1) or m.group(2)) if m else os.path.basename(path)[:-5]
    measures = re.findall(r"^\tmeasure\s+'([^']+)'|^\tmeasure\s+(\S+?)\s*=", src, re.M)
    measures = [a or b for a, b in measures]
    columns = re.findall(r"^\tcolumn\s+'([^']+)'|^\tcolumn\s+(\S+)", src, re.M)
    columns = [a or b for a, b in columns]
    return table, measures, columns


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    files = sorted(glob.glob(os.path.join(root, "definition", "tables", "*.tmdl")))
    if not files:
        files = sorted(glob.glob(os.path.join(root, "tables", "*.tmdl")))
    if not files:
        print("Không tìm thấy file bảng nào trong", root)
        return 2

    tables, all_measures = {}, defaultdict(list)
    for f in files:
        table, measures, columns = parse(f)
        tables[table] = (measures, columns, f)
        for x in measures:
            all_measures[x.casefold()].append((table, x))

    table_fold = {t.casefold(): t for t in tables}
    problems = []

    for table, (measures, columns, f) in sorted(tables.items()):
        col_fold = {c.casefold(): c for c in columns}
        for x in measures:
            key = x.casefold()
            if key in col_fold:
                problems.append(
                    "[1] bảng '%s': measure '%s' trùng cột '%s' (không phân biệt hoa thường), file %s"
                    % (table, x, col_fold[key], os.path.basename(f)))
            if key in table_fold:
                problems.append(
                    "[2] measure '%s' (bảng '%s') trùng tên bảng '%s'"
                    % (x, table, table_fold[key]))

    for key, hits in sorted(all_measures.items()):
        if len(hits) > 1:
            problems.append("[3] measure '%s' bị khai báo %d lần: %s"
                            % (hits[0][1], len(hits), ", ".join(t for t, _ in hits)))

    n_m = sum(len(v[0]) for v in tables.values())
    n_c = sum(len(v[1]) for v in tables.values())
    print("Đã kiểm %d bảng, %d measure, %d cột." % (len(tables), n_m, n_c))
    if problems:
        print("\nCÓ %d XUNG ĐỘT:" % len(problems))
        for p in problems:
            print("  " + p)
        return 1
    print("Không có xung đột tên.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
