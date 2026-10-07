# -*- coding: utf-8 -*-
"""Kiểm câu chữ của dashboard HTML và báo cáo Power BI có khớp nhau và khớp số liệu.

Ba lớp kiểm, exit khác 0 nếu có bất kỳ lỗi nào:

1. Mọi con số trong câu chữ của scripts/headlines.py truy được về
   data/export/findings.json: script tự đọc lại findings.json, tự tính lại từng
   biểu thức nguồn gốc (đường dẫn khóa, hoặc cộng, trừ, chia giữa các khóa), định
   dạng lại kiểu Việt Nam và so với chuỗi trong câu. Sau khi gỡ các con số đã truy
   được và các nhãn có chữ số (B1 1-30, MOB 12, 30+, SK_DPD...), câu không được
   còn chữ số nào: còn tức là có số gõ tay không rõ nguồn.
2. dashboard/index.html: tên trang, dek, LƯU Ý và tập tiêu đề visual của từng
   trang bằng đúng đầu ra headlines.py; ghi chú dành riêng cho HTML có mặt.
3. PBIR trong powerbi/CreditPortfolio.Report: tên trang (tab), tên trang lớn và
   dek trong masthead, LƯU Ý và tập tiêu đề visual của từng trang bằng đúng đầu
   ra headlines.py.

Chạy: python scripts/check_headlines_sync.py
"""
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import headlines  # noqa: E402

FINDINGS = ROOT / "data" / "export" / "findings.json"
HTML_PATH = ROOT / "dashboard" / "index.html"
PAGES_DIR = ROOT / "powerbi" / "CreditPortfolio.Report" / "definition" / "pages"

# Nhãn có chữ số nhưng không phải con số cần truy nguồn. Gỡ trước khi tìm số lạ.
LABELS = [
    r"B[0-4] (?:Current|1-30|31-60|61-90|90\+)", r"\bB[0-4]\b",
    r"MOB \d+", r"MOB n", r"\b\d+\+", r"t\+1", r"SK_DPD(?:_DEF)?", r"AP\+",
    r"khoảng tin cậy 95%", r"FPD30", r"Cận (?:dưới|trên) 95%",
    # Tên đợt mở hợp đồng (tháng tương đối), là nhãn định nghĩa chứ không phải số liệu.
    r"-\d+ đến -\d+", r"-\d+ trở về (?:trước|sau)", r"(?:nhóm|đợt mở) \d+ tháng",
]


# ---------------------------------------------------------------------------
# Lớp 1: tính lại số từ findings.json, độc lập với code định dạng của headlines
# ---------------------------------------------------------------------------

def resolve(data, path):
    """Bản cài lại độc lập của bộ chọn đường dẫn (không gọi headlines.resolve)."""
    parts, buf, depth = [], "", 0
    for ch in path:
        depth += ch == "["
        depth -= ch == "]"
        if ch == "." and depth == 0:
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    parts.append(buf)
    cur = data
    for part in parts:
        m = re.fullmatch(r"([^\[]+)(?:\[(.+)\])?", part)
        key, sel = m.group(1), m.group(2)
        cur = cur[int(key)] if isinstance(cur, list) else cur[key]
        if sel:
            cond = dict(kv.split("=", 1) for kv in sel.split(","))
            hits = [x for x in cur if all(str(x.get(k)) == v for k, v in cond.items())]
            if len(hits) != 1:
                raise KeyError("%s: bộ chọn %s khớp %d phần tử" % (path, sel, len(hits)))
            cur = hits[0]
    return cur


def evaluate(data, expr):
    if "path" in expr:
        return resolve(data, expr["path"])
    a, b = evaluate(data, expr["a"]), evaluate(data, expr["b"])
    return {"+": a + b, "-": a - b, "/": a / b}[expr["op"]]


def vn(x, d):
    s = f"{x:,.{d}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def fmt(kind, d, v):
    if kind == "int":
        return f"{int(round(v)):,}".replace(",", ".")
    if kind == "num":
        return vn(v, d)
    if kind == "pct":
        return vn(v * 100, d) + "%"
    if kind == "pctci":
        return vn(v * 100, d)
    if kind == "bil":
        return vn(v / 1e9, d)
    raise ValueError(kind)


def check_numbers(data, where, item, errors):
    text = item["text"]
    rest = text
    for pat in LABELS:
        rest = re.sub(pat, " ", rest)
    for n in item["numbers"]:
        try:
            value = evaluate(data, n["expr"])
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{where}: không truy được nguồn {n['expr']}: {exc}")
            continue
        want = fmt(n["kind"], n["decimals"], value)
        if want != n["text"]:
            errors.append(f"{where}: số {n['text']!r} lệch findings.json (tính lại ra {want!r})")
        # Gỡ đúng một lần xuất hiện, như một token số trọn vẹn (không ăn vào số khác).
        token = r"(?<![\d,.])" + re.escape(n["text"]) + r"(?![\d])"
        rest, hit = re.subn(token, " ", rest, count=1)
        if not hit:
            errors.append(f"{where}: số {n['text']!r} không có trong câu")
    stray = re.findall(r"\d[\d.,]*", rest)
    if stray:
        errors.append(f"{where}: có số không rõ nguồn {stray} trong câu: {text}")


# ---------------------------------------------------------------------------
# Lớp 2: đọc câu chữ từ dashboard/index.html
# ---------------------------------------------------------------------------

class DashParser(HTMLParser):
    """Gom tên trang, dek, tiêu đề visual, LƯU Ý theo từng section.page."""

    WANT = {("h2", "page-title"): "title", ("p", "dek"): "dek",
            ("h3", "viz-title"): "viz", ("p", "caveat"): "caveat"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pages, self.cur, self.cap, self.buf, self.depth = {}, None, None, "", 0
        self.page_text = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        if tag == "section" and "page" in cls:
            self.cur = int(a["data-hash"].split("-")[1])
            self.pages[self.cur] = {"title": None, "dek": None, "viz": [], "caveat": None}
            self.page_text[self.cur] = ""
        if self.cap is None:
            for (t, c), role in self.WANT.items():
                if tag == t and c in cls:
                    self.cap, self.buf, self.depth = role, "", 0
                    return
        elif self.cap and tag == "span":
            self.depth += 1

    def handle_endtag(self, tag):
        if self.cap and tag in ("h2", "h3", "p") and self.cur is not None:
            text = self.buf.strip()
            if self.cap == "caveat":
                text = re.sub(r"^LƯU Ý\s*", "", text)
            if self.cap == "viz":
                self.pages[self.cur]["viz"].append(text)
            else:
                self.pages[self.cur][self.cap] = text
            self.cap = None
        if tag == "main":
            self.cur = None

    def handle_data(self, d):
        if self.cap:
            self.buf += d
        if self.cur is not None:
            self.page_text[self.cur] += d


# ---------------------------------------------------------------------------
# Lớp 3: đọc câu chữ từ PBIR
# ---------------------------------------------------------------------------

def unq(lit_value):
    """Gỡ dạng chuỗi PBIR 'abc' (nháy đơn nhân đôi) về chuỗi thường."""
    v = lit_value["expr"]["Literal"]["Value"]
    return v[1:-1].replace("''", "'")


def read_pbir():
    out = {}
    for pdir in sorted(p for p in PAGES_DIR.iterdir() if p.is_dir()):
        page = json.loads((pdir / "page.json").read_text(encoding="utf-8"))
        rec = {"tab": page["displayName"], "title": None, "dek": None, "caveat": None, "viz": []}
        for vfile in sorted((pdir / "visuals").glob("*/visual.json")):
            v = json.loads(vfile.read_text(encoding="utf-8"))["visual"]
            if v["visualType"] == "textbox":
                paras = v["objects"]["general"][0]["properties"]["paragraphs"]
                runs = [r["value"] for p in paras for r in p["textRuns"]]
                alt = unq(v["visualContainerObjects"]["general"][0]["properties"]["altText"])
                if alt.startswith("Tên trang"):
                    rec["title"], rec["dek"] = runs[0], runs[1]
                elif alt.startswith("Ghi chú cảnh báo"):
                    rec["caveat"] = runs[1]
                continue
            t = (v.get("visualContainerObjects") or {}).get("title")
            if t and "text" in t[0]["properties"]:
                rec["viz"].append(unq(t[0]["properties"]["text"]))
        out[rec["tab"]] = rec
    return out


def compare(where, got, want, errors):
    if got != want:
        errors.append(f"{where}: lệch\n      có:   {got!r}\n      cần:  {want!r}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    data = json.loads(FINDINGS.read_text(encoding="utf-8"))
    pages = headlines.build(data)
    errors = []

    n_texts = n_nums = 0
    for p in pages:
        items = [("title", p["title"]), ("dek", p["dek"]), ("caveat", p["caveat"])]
        items += [("visual " + k, v) for k, v in p["visuals"].items()]
        items += [("ghi chú " + k, v) for k, v in p["notes"].items()]
        for name, item in items:
            n_texts += 1
            n_nums += len(item["numbers"])
            check_numbers(data, f"trang {p['n']} {name}", item, errors)
            for bad in (chr(0x2014), chr(0x2013)):
                if bad in item["text"]:
                    errors.append(f"trang {p['n']} {name}: có em dash hoặc en dash")
    print(f"[1] findings.json: {n_texts} câu, {n_nums} con số đã tính lại")

    want = headlines.texts(pages)

    # HTML
    parser = DashParser()
    parser.feed(HTML_PATH.read_text(encoding="utf-8"))
    for n, w in want.items():
        got = parser.pages.get(n)
        if got is None:
            errors.append(f"HTML: thiếu trang {n}")
            continue
        compare(f"HTML trang {n} tên trang", got["title"], w["title"], errors)
        compare(f"HTML trang {n} dek", got["dek"], w["dek"], errors)
        compare(f"HTML trang {n} LƯU Ý", got["caveat"], w["caveat"], errors)
        compare(f"HTML trang {n} tiêu đề visual", sorted(got["viz"]), sorted(w["visuals"].values()), errors)
        for k, note in w["notes"].items():
            if note not in parser.page_text[n]:
                errors.append(f"HTML trang {n}: thiếu ghi chú {k}: {note}")
    print(f"[2] HTML: đã so {len(parser.pages)} trang")

    # PBIR
    pbir = read_pbir()
    for n, w in want.items():
        got = pbir.get(w["tab"])
        if got is None:
            errors.append(f"PBIR: thiếu trang {w['tab']!r}")
            continue
        compare(f"PBIR {w['tab']} tên trang", got["title"], w["title"], errors)
        compare(f"PBIR {w['tab']} dek", got["dek"], w["dek"], errors)
        compare(f"PBIR {w['tab']} LƯU Ý", got["caveat"], w["caveat"], errors)
        compare(f"PBIR {w['tab']} tiêu đề visual", sorted(got["viz"]), sorted(w["visuals"].values()), errors)
    print(f"[3] PBIR: đã so {len(pbir)} trang")

    if errors:
        print(f"\nCÓ {len(errors)} LỖI:")
        for e in errors:
            print("  - " + e)
        return 1
    print("\nĐồng bộ: HTML, PBIR và findings.json khớp nhau.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
