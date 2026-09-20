# -*- coding: utf-8 -*-
"""Bat xung dot ten trong semantic model TMDL truoc khi mo Power BI Desktop.

Ba quy tac ma powerbi-report-author validate va MCP ConnectFolder KHONG bat duoc,
chi lo ra khi Desktop dung database Analysis Services that:

  1. measure trung ten voi cot trong CUNG bang (khong phan biet hoa thuong)
  2. measure trung ten voi ten mot BANG bat ky trong model
  3. measure trung ten measure khac o bat ky bang nao (measure la namespace toan model)

Chay: python check_names.py <duong-dan-thu-muc-.SemanticModel>
"""
import glob
import os
import re
import sys
from collections import defaultdict


def parse(path):
    """Tra ve (ten_bang, [measure], [cot]) tu mot file .tmdl."""
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
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    files = sorted(glob.glob(os.path.join(root, "definition", "tables", "*.tmdl")))
    if not files:
        files = sorted(glob.glob(os.path.join(root, "tables", "*.tmdl")))
    if not files:
        print("Khong tim thay file bang nao trong", root)
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
                    "[1] bang '%s': measure '%s' trung cot '%s' (khong phan biet hoa thuong) -- %s"
                    % (table, x, col_fold[key], os.path.basename(f)))
            if key in table_fold:
                problems.append(
                    "[2] measure '%s' (bang '%s') trung ten bang '%s'"
                    % (x, table, table_fold[key]))

    for key, hits in sorted(all_measures.items()):
        if len(hits) > 1:
            problems.append("[3] measure '%s' bi khai bao %d lan: %s"
                            % (hits[0][1], len(hits), ", ".join(t for t, _ in hits)))

    n_m = sum(len(v[0]) for v in tables.values())
    n_c = sum(len(v[1]) for v in tables.values())
    print("Da kiem %d bang, %d measure, %d cot." % (len(tables), n_m, n_c))
    if problems:
        print("\nCO %d XUNG DOT:" % len(problems))
        for p in problems:
            print("  " + p)
        return 1
    print("Khong co xung dot ten.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
