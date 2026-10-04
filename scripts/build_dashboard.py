"""Dựng dashboard HTML tĩnh 4 trang từ các bảng mart trong warehouse.

Cách dùng:
    .venv/Scripts/python.exe scripts/build_dashboard.py

Đọc data/warehouse.duckdb ở chế độ CHỈ ĐỌC (read_only=True), không ghi gì vào kho.
Sinh ra hai đầu ra:
    - dashboard/index.html
        Dashboard tĩnh 4 trang, đồng bộ với bản Power BI (powerbi/, sinh bằng
        scripts/build_pbip_report.py): cùng 4 trang, cùng tên trang, cùng dòng
        kết luận, cùng lựa chọn biểu đồ và cùng ghi chú LƯU Ý. Mọi biểu đồ được vẽ
        sẵn thành SVG từ Python, số liệu tổng hợp được nhúng thêm dưới dạng JSON
        (thẻ <script type="application/json" id="dashboard-data">). Mở thẳng file
        bằng trình duyệt là xem được, không cần server. Hỗ trợ mở thẳng từng trang
        bằng hash: index.html#page-1 đến #page-4.
    - data/export/*.csv
        Xuất nguyên 4 mart: mart.funnel_by_channel, mart.fpd_by_segment, mart.vintage,
        mart.roll_rate để bản PBIP trong powerbi/ đọc. Các file CSV này được commit
        (.gitignore có ngoại lệ riêng cho data/export/*.csv). File thứ 5,
        mart_portfolio_snapshot.csv, do scripts/export_snapshot.py xuất.

Chạy lại nhiều lần cho cùng kết quả: mọi con số lấy trực tiếp từ mart bằng truy
vấn xác định (deterministic), không sinh số ngẫu nhiên, không ghi cứng con số nào
trong tiêu đề.

Trục rủi ro theo kênh dùng ever 30+ tại MOB 12 (mart.vintage), KHÔNG dùng FPD30:
FPD30 có thiên lệch sống sót (xem docs/metric_dictionary.md mục M11 và
docs/methodology.md).

Tông thiết kế "Editorial Newsroom", trùng hằng số màu trong
scripts/build_pbip_report.py: nền kem, chữ mực, MỘT màu nhấn mustard tô đúng một
đối tượng mỗi biểu đồ, phần còn lại xám.

FONT: tuyệt đối không đưa Georgia vào font stack. Georgia thiếu 19 ký tự tiếng
Việt (ấ ầ ẩ ẫ ậ ế ề ể ễ ệ ố ồ ổ ỗ ộ ơ ư ớ ứ) nên "gấp" hiện thành "gâ´p". Tiêu đề dùng
Source Serif 4 (Google Fonts, có subset vietnamese), dự phòng Cambria rồi Times
New Roman, cả hai đều đủ 19 ký tự trên khi mở file không có mạng.
"""
import html
import json
import math
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "warehouse.duckdb"
DASHBOARD_DIR = ROOT / "dashboard"
EXPORT_DIR = ROOT / "data" / "export"

MART_TABLES_TO_EXPORT = [
    "mart.funnel_by_channel",
    "mart.fpd_by_segment",
    "mart.vintage",
    "mart.roll_rate",
]

UNKNOWN = "(không rõ)"

# Thứ tự trạng thái chuẩn cho ma trận roll rate (trang 4).
FROM_STATES = ["B0 Current", "B1 1-30", "B2 31-60", "B3 61-90", "B4 90+"]
TO_STATES = [
    "B0 Current", "B1 1-30", "B2 31-60", "B3 61-90", "B4 90+",
    "Closed", "Other", "Missing",
]
TO_STATE_VN = {"Closed": "tất toán", "Other": "khác", "Missing": "thiếu dữ liệu"}

PRODUCTS = ["Cash loans", "Consumer loans", "Revolving loans"]  # thứ tự ô như Power BI
PRODUCT_LABEL_VN = {
    "Consumer loans": "Vay tiêu dùng trả góp",
    "Cash loans": "Vay tiền mặt",
    "Revolving loans": "Thẻ quay vòng",
}

# Đối tượng được tô mustard (chữ ký highlight-and-grey). Trùng lựa chọn trong
# scripts/build_pbip_report.py.
HIGHLIGHT_CHANNEL = "Stone"
HIGHLIGHT_PRODUCT = "Consumer loans"
HIGHLIGHT_CURE_FROM = "B1 1-30"

# Các cặp so sánh mà dòng kết luận trang 2 nêu (xem docs/methodology.md):
#   - khoảng cách thô: kênh xấu nhất so với Credit and cash offices, gộp mọi sản phẩm
#   - trong vay tiêu dùng trả góp: Stone so với Regional / Local (Credit and cash
#     offices gần như không bán sản phẩm này)
#   - trong vay tiền mặt: Country-wide so với Credit and cash offices
RAW_PAIR = ("Stone", "Credit and cash offices")
WITHIN_PAIRS = {
    "Consumer loans": ("Stone", "Regional / Local"),
    "Cash loans": ("Country-wide", "Credit and cash offices"),
}

SMALL_N = 1000  # mẫu số MOB 12 dưới ngưỡng này thì gắn dấu * khi diễn giải

NUM_WORDS = {2: "hai", 3: "ba", 4: "bốn", 5: "năm", 6: "sáu", 7: "bảy",
             8: "tám", 9: "chín", 10: "mười"}


# ---------------------------------------------------------------------------
# Định dạng số kiểu Việt Nam: chấm ngăn nghìn, phẩy thập phân.
# ---------------------------------------------------------------------------

def esc(value):
    return html.escape(str(value), quote=True)


def fmt_int(n):
    if n is None:
        return "n/a"
    return f"{int(n):,}".replace(",", ".")


def fmt_num(x, decimals=1):
    if x is None:
        return "n/a"
    s = f"{x:,.{decimals}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_pct(x, decimals=2):
    if x is None:
        return "n/a"
    return fmt_num(x * 100, decimals) + "%"


def fmt_billion(raw, decimals=2):
    """Đơn vị thô của Kaggle (không phải VND) đổi sang 'tỷ đơn vị'."""
    if raw is None:
        return "n/a"
    return fmt_num(raw / 1e9, decimals)


def times_word(x):
    """Số lần làm tròn ra chữ (ba, bảy...) cho câu kết luận, giống Power BI."""
    n = round(x)
    return NUM_WORDS.get(n, str(n))


# ---------------------------------------------------------------------------
# Đọc dữ liệu
# ---------------------------------------------------------------------------

def rows(con, sql):
    rel = con.sql(sql)
    cols = rel.columns
    return [dict(zip(cols, r)) for r in rel.fetchall()]


def one(con, sql):
    r = rows(con, sql)
    return r[0] if r else {}


SQL_FOOTER_BASE = """
-- Nền chung của danh mục, dùng ở phần "Về dữ liệu" để nêu quy mô.
select
    (select count(*) from core.dim_loan)          as n_loans_total,
    (select count(*) from core.fct_loan_month)     as n_loan_months
"""

# ---- Trang 1: ảnh chụp tháng quan sát gần nhất (mart.portfolio_snapshot, cùng
# nguồn với trang 1 Power BI). Mã chỉ tiêu M02 (DPD bucket), M06 (30+ coincident).
SQL_P1_TOTAL = """
select
    sum(n_loans)                                as n_open,
    sum(n_30_plus)                              as n_30plus,
    sum(n_30_plus) * 1.0 / sum(n_loans)         as rate_30plus,
    sum(exposure)                               as exposure_total,
    sum(exposure_30_plus)                       as exposure_30plus,
    sum(exposure_30_plus) / sum(exposure)       as exposure_rate_30plus
from mart.portfolio_snapshot
"""

SQL_P1_BUCKETS = """
select dpd_bucket, dpd_bucket_order, sum(n_loans) as n_loans, sum(exposure) as exposure
from mart.portfolio_snapshot
group by dpd_bucket, dpd_bucket_order
order by dpd_bucket_order
"""

SQL_P1_BY_CHANNEL = """
-- Xếp hạng kênh: lọc bỏ '(không rõ)' như Power BI (nhóm không biết được phân khúc).
select channel_type, sum(n_loans) as n_open, sum(n_30_plus) as n_30plus,
       sum(n_30_plus) * 1.0 / sum(n_loans) as rate_30plus
from mart.portfolio_snapshot
where channel_type <> '(không rõ)'
group by channel_type
order by rate_30plus desc, channel_type
"""

SQL_P1_BY_PRODUCT = """
-- Bảng theo sản phẩm: GIỮ '(không rõ)' như bảng Power BI, tổng vẫn đủ danh mục.
select contract_type, sum(n_loans) as n_open, sum(n_30_plus) as n_30plus,
       sum(n_30_plus) * 1.0 / sum(n_loans) as rate_30plus
from mart.portfolio_snapshot
group by contract_type
order by rate_30plus desc, contract_type
"""

# ---- Trang 2: kênh bán. Trục rủi ro: ever 30+ tại MOB 12 (M08). Trục duyệt: M12.
SQL_P2_CHANNEL_PRODUCT_MOB12 = """
select channel_type, contract_type,
       sum(n_loans) as n_mob12, sum(n_ever_30_plus) as n_ever30,
       sum(n_ever_30_plus) * 1.0 / sum(n_loans) as rate
from mart.vintage
where mob = 12 and contract_type <> '(không rõ)' and channel_type <> '(không rõ)'
group by channel_type, contract_type
"""

SQL_P2_FUNNEL = """
select channel_type,
       sum(n_applications)                         as n_applications,
       sum(n_decided)                              as n_decided,
       sum(n_offered)                              as n_offered,
       sum(n_approved)                             as n_approved,
       sum(n_offered) * 1.0 / sum(n_decided)       as approval_rate,
       sum(n_approved) * 1.0 / sum(n_offered)      as take_up_rate
from mart.funnel_by_channel
where channel_type <> '(không rõ)'
group by channel_type
order by n_applications desc
"""

SQL_P2_FPD_BLIND = """
-- Vùng mù FPD: hồ sơ được duyệt nhưng không có dòng trả góp nào (M11).
select sum(n_approved_no_installment) as n_blind from mart.fpd_by_segment
"""

# ---- Trang 3: vintage theo MOB (M08).
SQL_P3_CHANNEL_MOB = """
select channel_type, mob,
       sum(n_loans) as n_loans, sum(n_observed_full) as n_observed_full,
       sum(n_ever_30_plus) as n_ever30,
       sum(n_ever_30_plus) * 1.0 / sum(n_loans) as rate
from mart.vintage
where channel_type <> '(không rõ)'
group by channel_type, mob
order by channel_type, mob
"""

SQL_P3_PRODUCT_MOB = """
select contract_type, mob,
       sum(n_loans) as n_loans, sum(n_observed_full) as n_observed_full,
       sum(n_ever_30_plus) as n_ever30,
       sum(n_ever_30_plus) * 1.0 / sum(n_loans) as rate
from mart.vintage
where contract_type <> '(không rõ)'
group by contract_type, mob
order by contract_type, mob
"""

SQL_P3_UNKNOWN_MOB12 = """
-- Tỷ lệ của nhóm '(không rõ)' tại MOB 12, nêu trong ghi chú LƯU Ý trang 3.
select sum(n_loans) as n_mob12, sum(n_ever_30_plus) * 1.0 / sum(n_loans) as rate
from mart.vintage
where mob = 12 and channel_type = '(không rõ)'
"""

# ---- Trang 4: roll rate (M09) và cure rate (M10), toàn danh mục.
SQL_P4_ROLL = """
-- Mẫu số mỗi dòng = tổng n_loans của nhóm xuất phát cộng qua MỌI nhóm đến (tính
-- ở Python). KHÔNG cộng cột n_from: cột đó là window sum lặp lại trên mỗi dòng.
select from_state, to_state, sum(n_loans) as n_loans, sum(exposure_from) as exposure_from
from mart.roll_rate
group by from_state, to_state
"""


def fetch_data(con):
    """Đọc toàn bộ dữ liệu cần cho 4 trang từ warehouse (chỉ đọc)."""
    return {
        "footer_base": one(con, SQL_FOOTER_BASE),
        "p1_total": one(con, SQL_P1_TOTAL),
        "p1_buckets": rows(con, SQL_P1_BUCKETS),
        "p1_by_channel": rows(con, SQL_P1_BY_CHANNEL),
        "p1_by_product": rows(con, SQL_P1_BY_PRODUCT),
        "p2_channel_product_mob12": rows(con, SQL_P2_CHANNEL_PRODUCT_MOB12),
        "p2_funnel": rows(con, SQL_P2_FUNNEL),
        "p2_fpd_blind": one(con, SQL_P2_FPD_BLIND),
        "p3_channel_mob": rows(con, SQL_P3_CHANNEL_MOB),
        "p3_product_mob": rows(con, SQL_P3_PRODUCT_MOB),
        "p3_unknown_mob12": one(con, SQL_P3_UNKNOWN_MOB12),
        "p4_roll": rows(con, SQL_P4_ROLL),
    }


def export_marts_to_csv(con):
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    for table in MART_TABLES_TO_EXPORT:
        file_name = table.replace(".", "_") + ".csv"
        out_path = EXPORT_DIR / file_name
        # COPY chỉ ghi file ngoài, không đụng gì vào warehouse.duckdb (vẫn đang
        # mở ở chế độ read_only).
        con.sql(f"copy (select * from {table}) to '{out_path.as_posix()}' (header, delimiter ',')")
        print(f"  export  {out_path.relative_to(ROOT)}")


# ---------------------------------------------------------------------------
# Tính các chỉ số dẫn xuất dùng trong tiêu đề kết luận
# ---------------------------------------------------------------------------

def derive(data):
    d = {}
    t = data["p1_total"]
    buckets = {b["dpd_bucket"]: b for b in data["p1_buckets"]}
    d["b0_share"] = buckets["B0 Current"]["n_loans"] / t["n_open"]
    d["b4_vs_b2b3"] = buckets["B4 90+"]["n_loans"] / (
        buckets["B2 31-60"]["n_loans"] + buckets["B3 61-90"]["n_loans"])
    ch = {r["channel_type"]: r for r in data["p1_by_channel"]}
    d["p1_top"] = data["p1_by_channel"][0]
    d["p1_cco"] = ch["Credit and cash offices"]

    # Rủi ro MOB 12 theo kênh (mọi sản phẩm) và theo kênh x sản phẩm.
    mob12_ch = {r["channel_type"]: r for r in data["p3_channel_mob"] if r["mob"] == 12}
    d["mob12_channel"] = mob12_ch
    cp = {(r["channel_type"], r["contract_type"]): r for r in data["p2_channel_product_mob12"]}
    d["mob12_cp"] = cp
    d["raw_ratio"] = mob12_ch[RAW_PAIR[0]]["rate"] / mob12_ch[RAW_PAIR[1]]["rate"]
    d["within_ratio"] = {
        p: cp[(a, p)]["rate"] / cp[(b, p)]["rate"] for p, (a, b) in WITHIN_PAIRS.items()
    }
    fun = {r["channel_type"]: r for r in data["p2_funnel"]}
    d["funnel"] = fun

    mob12_p = {r["contract_type"]: r for r in data["p3_product_mob"] if r["mob"] == 12}
    d["mob12_product"] = mob12_p
    d["consumer_vs_cash"] = mob12_p["Consumer loans"]["rate"] / mob12_p["Cash loans"]["rate"]

    grid, base = build_roll_grid(data["p4_roll"])
    d["roll_grid"], d["roll_base"] = grid, base
    d["cure"] = {fs: grid[(fs, "B0 Current")]["rate"] for fs in FROM_STATES}
    return d


def build_roll_grid(raw_rows):
    """Ghép kết quả roll rate với lưới trạng thái đầy đủ. Ô không có quan sát nào
    (ví dụ B1 sang B4) có n_loans = 0 và được hiện trống như ma trận Power BI."""
    by_key = {(r["from_state"], r["to_state"]): r for r in raw_rows}
    base = {}
    for fs in FROM_STATES:
        base[fs] = {
            "n": sum((by_key.get((fs, ts)) or {}).get("n_loans", 0) for ts in TO_STATES),
            "exposure": sum((by_key.get((fs, ts)) or {}).get("exposure_from") or 0 for ts in TO_STATES),
        }
    grid = {}
    for fs in FROM_STATES:
        for ts in TO_STATES:
            n = (by_key.get((fs, ts)) or {}).get("n_loans", 0)
            grid[(fs, ts)] = {"n": n, "rate": n / base[fs]["n"] if base[fs]["n"] else 0.0,
                              "observed": (fs, ts) in by_key}
    return grid, base


# =============================================================================
# SVG: tiện ích chung. Màu đi qua class CSS (f-ink, f-grey, f-accent...) để một
# bản SVG duy nhất tự đổi theo chế độ sáng/tối.
# =============================================================================

def tip(*lines):
    return esc("\n".join(str(x) for x in lines if x is not None))


def svg_open(w, h, desc, cls=""):
    return (f'<svg class="chart {cls}" viewBox="0 0 {w} {h}" role="img" '
            f'aria-label="{esc(desc)}" xmlns="http://www.w3.org/2000/svg">')


def text_w(s, px=12):
    """Ước lượng bề rộng chữ (sans) để đặt nhãn không đè nhau."""
    return len(str(s)) * px * 0.56


def nice_step(rough):
    if rough <= 0:
        return 1.0
    exp = math.floor(math.log10(rough))
    base = rough / 10 ** exp
    nice = 1 if base <= 1 else 2 if base <= 2 else 2.5 if base <= 2.5 else 5 if base <= 5 else 10
    return nice * 10 ** exp


def nice_ticks(max_val, count=4):
    step = nice_step(max_val / count)
    n = max(1, math.ceil(max_val / step - 1e-9))
    return [round(i * step, 12) for i in range(n + 1)]


def pct_tick_label(v):
    """Nhãn trục phần trăm gọn: 0%, 0,5%, 1%, 1,25%."""
    s = f"{v * 100:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",") + "%"


def hbar_chart(items, desc, W=560, label_w=150, value_w=78, row_h=32, bar_h=18,
               x_max=None, label_px=12.5):
    """Thanh ngang. items: dict {label, value, cls, value_txt, tip, note}.
    value None nghĩa là không có dữ liệu (ví dụ kênh không bán sản phẩm đó)."""
    vals = [it["value"] for it in items if it["value"] is not None]
    x_max = x_max or (max(vals) if vals else 1) or 1
    track_x, track_w = label_w, W - label_w - value_w
    H = len(items) * row_h + 6
    out = [svg_open(W, H, desc)]
    for i, it in enumerate(items):
        y = 3 + i * row_h
        cy = y + row_h / 2
        out.append(f'<text x="{label_w - 10}" y="{cy:.1f}" class="t-label" text-anchor="end" '
                   f'dominant-baseline="central" style="font-size:{label_px}px">{esc(it["label"])}</text>')
        if it["value"] is None:
            out.append(f'<text x="{track_x + 8}" y="{cy:.1f}" class="t-muted" '
                       f'dominant-baseline="central">{esc(it.get("note") or "không có")}</text>')
        else:
            w = max(track_w * it["value"] / x_max, 0)
            out.append(f'<rect x="{track_x}" y="{cy - bar_h / 2:.1f}" width="{w:.1f}" '
                       f'height="{bar_h}" class="{it["cls"]}" />')
            out.append(f'<text x="{track_x + w + 6:.1f}" y="{cy:.1f}" class="t-value" '
                       f'dominant-baseline="central">{esc(it["value_txt"])}</text>')
        if it.get("tip"):
            out.append(f'<rect class="hit" x="0" y="{y}" width="{W}" height="{row_h}" '
                       f'tabindex="0" data-tip="{it["tip"]}" />')
    out.append(f'<line x1="{track_x}" y1="2" x2="{track_x}" y2="{H - 2}" class="s-rule" />')
    out.append("</svg>")
    return "".join(out)


def share_bar(b0_share, desc, W=360):
    """Một thanh 100%: B0 xám nhạt, phần đuôi B1 đến B4 mực."""
    H = 46
    w0 = W * b0_share
    out = [svg_open(W, H, desc)]
    out.append(f'<rect x="0" y="4" width="{w0:.1f}" height="16" class="f-greyl" />')
    out.append(f'<rect x="{w0:.1f}" y="4" width="{W - w0:.1f}" height="16" class="f-ink" />')
    out.append(f'<text x="0" y="38" class="t-label">B0 Current {fmt_pct(b0_share, 2)}</text>')
    out.append(f'<text x="{W}" y="38" class="t-label" text-anchor="end">'
               f'B1 đến B4: {fmt_pct(1 - b0_share, 2)}</text>')
    out.append("</svg>")
    return "".join(out)


# =============================================================================
# Trang 2: scatter tỷ lệ duyệt x ever 30+ MOB 12, nhãn không đè bong bóng
# =============================================================================

def place_labels(points, bounds, px=12):
    """Đặt nhãn cạnh bong bóng, thử lần lượt nhiều vị trí, chọn vị trí đầu tiên
    không đè lên nhãn khác hay bong bóng khác và nằm trong khung vẽ."""
    x0, y0, x1, y1 = bounds
    placed = []
    circles = [(p["cx"], p["cy"], p["r"]) for p in points]

    def box_for(p, cand):
        w, h = text_w(p["label"], px), px + 2
        dx, dy, anchor = cand
        tx, ty = p["cx"] + dx, p["cy"] + dy
        bx = tx if anchor == "start" else tx - w if anchor == "end" else tx - w / 2
        return (bx, ty - h + 3, bx + w, ty + 3), tx, ty, anchor

    def hits_circle(box, own):
        bx0, by0, bx1, by1 = box
        for c in circles:
            if c == own:
                continue
            nx, ny = min(max(c[0], bx0), bx1), min(max(c[1], by0), by1)
            if (nx - c[0]) ** 2 + (ny - c[1]) ** 2 < (c[2] + 1) ** 2:
                return True
        return False

    def overlaps(a, b):
        return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])

    for p in sorted(points, key=lambda q: q["priority"]):
        r = p["r"]
        cands = [(r + 5, 4, "start"), (-r - 5, 4, "end"), (0, -r - 5, "middle"),
                 (0, r + 14, "middle"), (r * 0.7 + 4, -r * 0.7 - 2, "start"),
                 (-r * 0.7 - 4, -r * 0.7 - 2, "end"), (r * 0.7 + 4, r * 0.7 + 12, "start"),
                 (-r * 0.7 - 4, r * 0.7 + 12, "end")]
        chosen = None
        for cand in cands:
            box, tx, ty, anchor = box_for(p, cand)
            inside = box[0] >= x0 and box[2] <= x1 and box[1] >= y0 and box[3] <= y1
            if not inside or hits_circle(box, (p["cx"], p["cy"], p["r"])):
                continue
            if any(overlaps(box, b) for b in placed):
                continue
            chosen = (box, tx, ty, anchor)
            break
        if chosen is None:
            chosen = box_for(p, cands[0])
        placed.append(chosen[0])
        p["lx"], p["ly"], p["anchor"] = chosen[1], chosen[2], chosen[3]
    return points


def scatter_chart(channels, fun, mob12, desc, W=540, H=330, r_max=22):
    left, right, top, bottom = 56, 16, 16, 46
    pw, ph = W - left - right, H - top - bottom
    xs = [fun[c]["approval_rate"] for c in channels]
    ys = [mob12[c]["rate"] for c in channels]
    x_lo = math.floor(min(xs) * 10 - 0.5) / 10
    x_hi = min(1.0, math.ceil(max(xs) * 10 + 0.3) / 10)
    y_ticks = nice_ticks(max(ys) * 1.12, 4)
    y_max = y_ticks[-1]
    n_max = max(fun[c]["n_applications"] for c in channels)

    def sx(v):
        return left + (v - x_lo) / (x_hi - x_lo) * pw

    def sy(v):
        return top + ph - v / y_max * ph

    out = [svg_open(W, H, desc)]
    for t in y_ticks:
        out.append(f'<line x1="{left}" x2="{W - right}" y1="{sy(t):.1f}" y2="{sy(t):.1f}" class="s-grid" />')
        out.append(f'<text x="{left - 8}" y="{sy(t):.1f}" class="t-axis" text-anchor="end" '
                   f'dominant-baseline="central">{pct_tick_label(t)}</text>')
    xt = x_lo
    while xt <= x_hi + 1e-9:
        out.append(f'<text x="{sx(xt):.1f}" y="{H - bottom + 18}" class="t-axis" '
                   f'text-anchor="middle">{round(xt * 100)}%</text>')
        xt = round(xt + 0.1, 10)
    out.append(f'<line x1="{left}" x2="{W - right}" y1="{top + ph}" y2="{top + ph}" class="s-base" />')
    out.append(f'<text x="{left + pw / 2:.1f}" y="{H - 6}" class="t-axis" text-anchor="middle">'
               "Tỷ lệ duyệt</text>")
    out.append(f'<text transform="translate(14 {top + ph / 2:.1f}) rotate(-90)" class="t-axis" '
               'text-anchor="middle">Từng 30+ tại MOB 12</text>')

    pts = []
    for c in channels:
        r = 4 + math.sqrt(fun[c]["n_applications"] / n_max) * r_max
        pts.append({"c": c, "label": c, "cx": sx(fun[c]["approval_rate"]),
                    "cy": sy(mob12[c]["rate"]), "r": r,
                    "priority": 0 if c == HIGHLIGHT_CHANNEL else 1 + (-fun[c]["n_applications"]) / 1e9})
    place_labels(pts, (left + 2, top, W - right, top + ph - 2))
    # Vẽ bong bóng lớn trước để bong bóng nhỏ nằm trên.
    for p in sorted(pts, key=lambda q: -q["r"]):
        cls = "f-accent" if p["c"] == HIGHLIGHT_CHANNEL else "f-grey"
        out.append(f'<circle cx="{p["cx"]:.1f}" cy="{p["cy"]:.1f}" r="{p["r"]:.1f}" class="{cls} bubble" />')
    for p in pts:
        c = p["c"]
        bold = " t-strong" if c == HIGHLIGHT_CHANNEL else ""
        out.append(f'<text x="{p["lx"]:.1f}" y="{p["ly"]:.1f}" class="t-label{bold}" '
                   f'text-anchor="{p["anchor"]}">{esc(c)}</text>')
        t = tip(c, f"Tỷ lệ duyệt: {fmt_pct(fun[c]['approval_rate'], 1)}",
                f"Từng 30+ tại MOB 12: {fmt_pct(mob12[c]['rate'], 2)} "
                f"({fmt_int(mob12[c]['n_ever30'])} trên {fmt_int(mob12[c]['n_loans'])} hợp đồng)",
                f"Số hồ sơ: {fmt_int(fun[c]['n_applications'])}")
        out.append(f'<circle class="hit" cx="{p["cx"]:.1f}" cy="{p["cy"]:.1f}" '
                   f'r="{max(p["r"], 12):.1f}" tabindex="0" data-tip="{t}" />')
    out.append("</svg>")
    return "".join(out)


# =============================================================================
# Biểu đồ đường (trang 3): dùng cho cả ô nhỏ trellis lẫn biểu đồ theo sản phẩm
# =============================================================================

def line_chart(series, desc, y_ticks, x_max, W, H, left=44, right=14, top=10, bottom=28,
               x_ticks=(0, 12, 24, 36), end_labels=False, x_title=None, compact=False):
    """series: list dict {name, rows:[{mob, rate, n_loans, n_ever30}], cls, width,
    label (bool), tip (bool)}. Vẽ theo thứ tự danh sách: phần tử sau nằm trên."""
    pw, ph = W - left - right, H - top - bottom
    y_max = y_ticks[-1]

    def sx(m):
        return left + m / x_max * pw

    def sy(v):
        return top + ph - min(v, y_max) / y_max * ph

    out = [svg_open(W, H, desc)]
    for t in y_ticks:
        out.append(f'<line x1="{left}" x2="{W - right}" y1="{sy(t):.1f}" y2="{sy(t):.1f}" class="s-grid" />')
        out.append(f'<text x="{left - 6}" y="{sy(t):.1f}" class="t-axis" text-anchor="end" '
                   f'dominant-baseline="central">{pct_tick_label(t)}</text>')
    for m in x_ticks:
        if m <= x_max:
            out.append(f'<text x="{sx(m):.1f}" y="{top + ph + 16}" class="t-axis" '
                       f'text-anchor="middle">{m}</text>')
    out.append(f'<line x1="{left}" x2="{W - right}" y1="{top + ph}" y2="{top + ph}" class="s-base" />')
    if x_title:
        out.append(f'<text x="{left + pw / 2:.1f}" y="{H - 4}" class="t-axis" '
                   f'text-anchor="middle">{esc(x_title)}</text>')

    labels = []
    for s in series:
        pts = " ".join(f"{sx(r['mob']):.1f},{sy(r['rate']):.1f}" for r in s["rows"])
        out.append(f'<polyline points="{pts}" fill="none" class="{s["cls"]}" '
                   f'stroke-width="{s.get("width", 2)}" stroke-linejoin="round" stroke-linecap="round" />')
        if end_labels and s.get("label", True):
            last = s["rows"][-1]
            labels.append({"y": sy(last["rate"]), "x": sx(last["mob"]) + 8, "name": s["name"],
                           "tcls": s.get("tcls", "t-label")})
    if labels:
        labels.sort(key=lambda l: l["y"])
        for i in range(1, len(labels)):
            labels[i]["y"] = max(labels[i]["y"], labels[i - 1]["y"] + 15)
        for lab in labels:
            out.append(f'<text x="{lab["x"]:.1f}" y="{lab["y"]:.1f}" class="{lab["tcls"]}" '
                       f'dominant-baseline="central">{esc(lab["name"])}</text>')

    # Dải hover dọc theo từng MOB, gộp số của các chuỗi có cờ tip.
    tip_series = [s for s in series if s.get("tip")]
    if tip_series:
        band = pw / x_max
        for m in range(0, x_max + 1):
            lines = [f"MOB {m}"]
            for s in tip_series:
                r = next((r for r in s["rows"] if r["mob"] == m), None)
                if r:
                    lines.append(f"{s['name']}: {fmt_pct(r['rate'], 2)} "
                                 f"({fmt_int(r['n_ever30'])} trên {fmt_int(r['n_loans'])})")
            x = max(left, sx(m) - band / 2)
            w = min(band, W - right - x)
            out.append(f'<rect class="hit" x="{x:.1f}" y="{top}" width="{w:.1f}" height="{ph}" '
                       f'tabindex="-1" data-tip="{tip(*lines)}" />')
    out.append("</svg>")
    return "".join(out)


# =============================================================================
# Khối HTML dùng chung
# =============================================================================

def responsive(wide_svg, narrow_svg):
    """Hai bản cùng một biểu đồ: bản rộng cho màn hình lớn, bản hẹp (viewBox
    khoảng 360) cho điện thoại để chữ trong SVG không bị thu nhỏ quá mức. CSS chọn
    bản hiển thị; bản ẩn dùng display:none nên trình đọc màn hình cũng bỏ qua."""
    return f'<div class="only-wide">{wide_svg}</div><div class="only-narrow">{narrow_svg}</div>'


def viz(title, body, note=None, cls=""):
    n = f'<p class="viz-note">{note}</p>' if note else ""
    return (f'<section class="viz {cls}"><h3 class="viz-title">{title}</h3>'
            f"{body}{n}</section>")


def kpi(label, value, context):
    return (f'<div class="kpi"><div class="kpi-label">{esc(label)}</div>'
            f'<div class="kpi-value">{value}</div><div class="kpi-ctx">{context}</div></div>')


def table(headers, body_rows, total=None, num_from=1, cls=""):
    """Bảng chỉ kẻ ngang. Cột từ num_from trở đi canh phải, chữ số tabular."""
    def cell(tag, i, v):
        c = ' class="num"' if i >= num_from else ""
        return f"<{tag}{c}>{v}</{tag}>"
    th = "".join(cell("th", i, h) for i, h in enumerate(headers))
    tb = "".join("<tr>" + "".join(cell("td", i, v) for i, v in enumerate(r)) + "</tr>" for r in body_rows)
    tf = ("<tfoot><tr>" + "".join(cell("td", i, v) for i, v in enumerate(total)) + "</tr></tfoot>"
          if total else "")
    return (f'<div class="table-wrap {cls}"><table><thead><tr>{th}</tr></thead>'
            f"<tbody>{tb}</tbody>{tf}</table></div>")


def page_shell(n, title, dek, body, caveat):
    return (
        f'<section class="page" id="sec-{n}" data-hash="page-{n}" role="tabpanel" aria-labelledby="tab-{n}">'
        f'<header class="masthead"><h2 class="page-title">{esc(title)}</h2>'
        f'<p class="dek">{esc(dek)}</p></header>'
        f'<div class="rule-ink" role="presentation"></div>'
        f"{body}"
        f'<div class="rule-grey" role="presentation"></div>'
        f'<p class="caveat"><span class="caveat-tag">LƯU Ý</span>{caveat}</p>'
        "</section>"
    )


# =============================================================================
# Trang 1. Tổng quan danh mục
# =============================================================================

def page1(data, d):
    t = data["p1_total"]
    n_open = t["n_open"]
    buckets = data["p1_buckets"]
    bmap = {b["dpd_bucket"]: b for b in buckets}
    top, cco = d["p1_top"], d["p1_cco"]

    kpis = "".join([
        kpi("HỢP ĐỒNG ĐANG MỞ", fmt_int(n_open), "Tại tháng quan sát gần nhất của từng hợp đồng"),
        kpi("TỶ LỆ 30+ THEO HỢP ĐỒNG", fmt_pct(t["rate_30plus"], 2),
            f"{fmt_int(t['n_30plus'])} trên {fmt_int(n_open)} hợp đồng đang mở"),
        kpi("DƯ NỢ PROXY ĐANG MỞ", fmt_billion(t["exposure_total"], 1) + " tỷ",
            "Đơn vị thô của dữ liệu Kaggle, không phải VND"),
        kpi("TỶ LỆ 30+ THEO DƯ NỢ", fmt_pct(t["exposure_rate_30plus"], 2),
            f"{fmt_billion(t['exposure_30plus'], 2)} trên {fmt_billion(t['exposure_total'], 1)} tỷ dư nợ proxy"),
    ])

    # Biểu đồ xếp hạng kênh: Stone mustard, còn lại xám. Đã lọc '(không rõ)'.
    ch_items = [{
        "label": r["channel_type"], "value": r["rate_30plus"],
        "cls": "f-accent" if r["channel_type"] == HIGHLIGHT_CHANNEL else "f-grey",
        "value_txt": fmt_pct(r["rate_30plus"], 2),
        "tip": tip(r["channel_type"], f"Tỷ lệ 30+ hiện tại: {fmt_pct(r['rate_30plus'], 3)}",
                   f"{fmt_int(r['n_30plus'])} trên {fmt_int(r['n_open'])} hợp đồng đang mở"),
    } for r in data["p1_by_channel"]]
    ch_desc = ("Biểu đồ thanh tỷ lệ quá hạn 30+ hiện tại theo kênh bán, sắp giảm dần. "
               + "; ".join(f"{r['channel_type']} {fmt_pct(r['rate_30plus'], 2)}" for r in data["p1_by_channel"])
               + f". {HIGHLIGHT_CHANNEL} được tô màu nhấn.")
    ch_title = (f"{top['channel_type']} dẫn đầu tỷ lệ 30+ hiện tại, {fmt_pct(top['rate_30plus'], 2)} "
                f"so với {fmt_pct(cco['rate_30plus'], 2)} của Credit and cash offices")
    channel_viz = viz(esc(ch_title), responsive(
        hbar_chart(ch_items, ch_desc, W=640, label_w=170, row_h=36, bar_h=22),
        hbar_chart(ch_items, ch_desc, W=360, label_w=140, value_w=52, row_h=32, bar_h=18, label_px=12)))

    # Biểu đồ chủ đạo: cơ cấu nhóm quá hạn. Thanh 100% để thấy đuôi mỏng cỡ nào,
    # rồi phóng to riêng phần đuôi B1 đến B4 (Power BI không làm được vì B0 ép mọi
    # thanh khác về gần 0). B4 90+ mustard.
    tail = [b for b in buckets if b["dpd_bucket"] != "B0 Current"]
    tail_items = [{
        "label": b["dpd_bucket"], "value": b["n_loans"],
        "cls": "f-accent" if b["dpd_bucket"] == "B4 90+" else "f-grey",
        "value_txt": fmt_int(b["n_loans"]),
        "tip": tip(b["dpd_bucket"], f"{fmt_int(b['n_loans'])} hợp đồng ({fmt_pct(b['n_loans'] / n_open, 3)} danh mục)",
                   f"Dư nợ proxy: {fmt_billion(b['exposure'], 3)} tỷ"),
    } for b in tail]
    n_tail = sum(b["n_loans"] for b in tail)
    bucket_desc = ("Cơ cấu danh mục theo nhóm quá hạn: "
                   + ", ".join(f"{b['dpd_bucket']} {fmt_int(b['n_loans'])} hợp đồng" for b in buckets)
                   + ". Nhóm B4 90+ được tô màu nhấn.")
    hero_title = f"B4 90+ đông gấp {times_word(d['b4_vs_b2b3'])} lần B2 và B3 gộp"
    hero_body = (
        share_bar(d["b0_share"], f"Thanh tỷ trọng: B0 Current chiếm {fmt_pct(d['b0_share'], 2)} hợp đồng đang mở.")
        + f'<p class="viz-sub">Phóng to phần đuôi B1 đến B4 ({fmt_int(n_tail)} hợp đồng quá hạn), '
        "trục là số hợp đồng:</p>"
        + hbar_chart(tail_items, bucket_desc, W=360, label_w=70, value_w=52, row_h=34, bar_h=20)
    )
    hero_viz = viz(esc(hero_title), hero_body)

    prod_rows = []
    for r in data["p1_by_product"]:
        name = PRODUCT_LABEL_VN.get(r["contract_type"], r["contract_type"])
        prod_rows.append([esc(name), fmt_int(r["n_open"]), fmt_pct(r["rate_30plus"], 2)])
    product_viz = viz("Tỷ lệ 30+ theo loại sản phẩm", table(
        ["Sản phẩm", "Số hợp đồng mở", "Tỷ lệ 30+ hiện tại"], prod_rows,
        total=["Tổng", fmt_int(n_open), fmt_pct(t["rate_30plus"], 2)]))

    body = (
        '<div class="grid-p1">'
        f'<div class="col-main"><div class="kpi-row">{kpis}</div>{channel_viz}</div>'
        f'<div class="col-side">{hero_viz}{product_viz}</div>'
        "</div>"
    )
    dek = (f"{fmt_pct(d['b0_share'], 2)} danh mục vẫn sạch, nhưng đuôi B4 90+ đông gấp "
           f"{times_word(d['b4_vs_b2b3'])} lần B2 và B3 cộng lại")
    caveat = ("Ảnh chụp tại tháng quan sát gần nhất của từng hợp đồng. Tỷ lệ 30+ ở đây là coincident, "
              "đo tại một thời điểm, khác với tỷ lệ vintage theo tuổi hợp đồng ở trang 3. Biểu đồ xếp hạng "
              "kênh đã lọc bỏ nhóm (không rõ) vì nhóm đó không biết được phân khúc; bốn thẻ KPI vẫn tính "
              "đủ danh mục.")
    return page_shell(1, "Tổng quan danh mục", dek, body, caveat), [dek, ch_title, hero_title]


# =============================================================================
# Trang 2. Kênh bán và rủi ro
# =============================================================================

def page2(data, d):
    mob12 = d["mob12_channel"]
    cp = d["mob12_cp"]
    fun = d["funnel"]
    channels = sorted(mob12, key=lambda c: -mob12[c]["rate"])
    x_max = nice_ticks(max(r["rate"] for r in cp.values()), 4)[-1]

    panels = []
    for p in PRODUCTS:
        items = []
        # Màu nhấn của mỗi ô chỉ vào đúng kênh mà chú thích của ô đó nói tới.
        # Tô cứng Stone ở mọi ô sẽ sai ở ô vay tiền mặt: ở đó Stone thấp nhất
        # (0,06%), còn câu chuyện là Country-wide gấp 4,4 lần.
        focus = WITHIN_PAIRS[p][0] if p in WITHIN_PAIRS else HIGHLIGHT_CHANNEL
        for c in channels:
            r = cp.get((c, p))
            if r is None:
                items.append({"label": c, "value": None, "note": "không bán"})
                continue
            small = r["n_mob12"] < SMALL_N
            items.append({
                "label": c, "value": r["rate"],
                "cls": "f-accent" if c == focus else "f-grey",
                "value_txt": fmt_pct(r["rate"], 2) + ("*" if small else ""),
                "tip": tip(f"{c} · {PRODUCT_LABEL_VN[p]}",
                           f"Từng 30+ tại MOB 12: {fmt_pct(r['rate'], 3)}",
                           f"{fmt_int(r['n_ever30'])} trên {fmt_int(r['n_mob12'])} hợp đồng",
                           "* mẫu số dưới 1.000 hợp đồng, thận trọng" if small else None),
            })
        desc = (f"Ô {PRODUCT_LABEL_VN[p]}: tỷ lệ từng 30+ tại MOB 12 theo kênh, cùng thang với hai ô kia. "
                + "; ".join(f"{it['label']} {it['value_txt']}" for it in items if it["value"] is not None))
        note = ""
        if p in WITHIN_PAIRS:
            a, b = WITHIN_PAIRS[p]
            note = (f'<p class="panel-note">{esc(a)} gấp <strong>{fmt_num(d["within_ratio"][p], 1)} lần</strong> '
                    f"{esc(b)}</p>")
        panels.append(
            f'<figure class="panel"><figcaption>{esc(PRODUCT_LABEL_VN[p])}'
            f'<span class="en">{esc(p)}</span></figcaption>'
            + hbar_chart(items, desc, W=360, label_w=150, value_w=62, row_h=30, bar_h=16,
                         x_max=x_max, label_px=12)
            + note + "</figure>"
        )
    trellis_title = "Cùng một sản phẩm, cùng một thang: khoảng cách co lại"
    trellis_viz = viz(
        trellis_title,
        f'<p class="viz-sub">Từng quá hạn 30+ tại MOB 12, mỗi ô một loại sản phẩm, thang trục giá trị '
        f"chung từ 0 đến {pct_tick_label(x_max)}. Gộp mọi sản phẩm thì {RAW_PAIR[0]} gấp "
        f"{fmt_num(d['raw_ratio'], 1)} lần {RAW_PAIR[1]}.</p>"
        f'<div class="trellis-3">{"".join(panels)}</div>',
        note="* mẫu số tại MOB 12 dưới 1.000 hợp đồng, thận trọng khi diễn giải.",
        cls="viz-wide")

    st = HIGHLIGHT_CHANNEL
    cco = "Credit and cash offices"
    sc_title = (f"Duyệt rộng, rủi ro cao: {st} duyệt {fmt_pct(fun[st]['approval_rate'], 1)}, "
                f"xấu nhất {fmt_pct(mob12[st]['rate'], 2)}")
    sc_desc = ("Biểu đồ phân tán, trục ngang tỷ lệ duyệt, trục dọc tỷ lệ từng quá hạn 30+ tại MOB 12, "
               "kích thước bong bóng theo số hồ sơ. "
               + "; ".join(f"{c}: duyệt {fmt_pct(fun[c]['approval_rate'], 1)}, rủi ro {fmt_pct(mob12[c]['rate'], 2)}"
                           for c in channels)
               + f". {st} được tô màu nhấn.")
    scatter_viz = viz(esc(sc_title), responsive(
        scatter_chart(channels, fun, mob12, sc_desc),
        scatter_chart(channels, fun, mob12, sc_desc, W=360, H=300, r_max=15)),
                      note=f"Kích thước bong bóng theo số hồ sơ. {cco} duyệt "
                           f"{fmt_pct(fun[cco]['approval_rate'], 1)} và chỉ {fmt_pct(mob12[cco]['rate'], 2)}.")

    f_rows = [[esc(r["channel_type"]), fmt_int(r["n_applications"]), fmt_pct(r["approval_rate"], 1),
               fmt_pct(r["take_up_rate"], 1)] for r in data["p2_funnel"]]
    tot = {k: sum(r[k] for r in data["p2_funnel"]) for k in ("n_applications", "n_decided", "n_offered", "n_approved")}
    funnel_viz = viz("Phễu duyệt theo kênh, kèm tỷ lệ khách nhận khoản vay", table(
        ["Kênh", "Số hồ sơ", "Tỷ lệ duyệt", "Tỷ lệ nhận vay"], f_rows,
        total=["Tổng", fmt_int(tot["n_applications"]), fmt_pct(tot["n_offered"] / tot["n_decided"], 1),
               fmt_pct(tot["n_approved"] / tot["n_offered"], 1)]))

    body = (f"{trellis_viz}"
            f'<div class="grid-2">{scatter_viz}{funnel_viz}</div>')
    wc, wcash = d["within_ratio"]["Consumer loans"], d["within_ratio"]["Cash loans"]
    dek = (f"Khoảng cách thô {fmt_num(d['raw_ratio'], 1)} lần giữa các kênh co lại còn "
           f"{fmt_num(wc, 1)} và {fmt_num(wcash, 1)} lần khi so trong cùng sản phẩm")
    caveat = (f"Khoảng cách thô {fmt_num(d['raw_ratio'], 1)} lần giữa {RAW_PAIR[0]} và {RAW_PAIR[1]} phần lớn "
              f"là nhiễu cơ cấu sản phẩm; so trong cùng sản phẩm chỉ còn {fmt_num(wc, 1)} lần (vay tiêu dùng "
              f"trả góp) và {fmt_num(wcash, 1)} lần (vay tiền mặt). FPD30 không dùng làm trục rủi ro vì thiên "
              f"lệch sống sót, vùng mù {fmt_int(data['p2_fpd_blind']['n_blind'])} hồ sơ. Ba visual đã lọc bỏ "
              "nhóm (không rõ).")
    return page_shell(2, "Kênh bán và rủi ro", dek, body, caveat), [dek, trellis_title, sc_title]


# =============================================================================
# Trang 3. Vintage theo MOB
# =============================================================================

def page3(data, d):
    by_ch = {}
    for r in data["p3_channel_mob"]:
        by_ch.setdefault(r["channel_type"], []).append(r)
    by_p = {}
    for r in data["p3_product_mob"]:
        by_p.setdefault(r["contract_type"], []).append(r)
    x_max = max(r["mob"] for r in data["p3_channel_mob"])
    channels = sorted(by_ch)  # thứ tự chữ cái như trellis Power BI
    y_ticks = nice_ticks(max(r["rate"] for r in data["p3_channel_mob"]), 4)

    cells = []
    for c in channels:
        ghost = [{"name": o, "rows": by_ch[o], "cls": "s-ghost", "width": 1.2}
                 for o in channels if o != c]
        main = {"name": c, "rows": by_ch[c], "width": 2.4, "tip": True,
                "cls": "s-accent" if c == HIGHLIGHT_CHANNEL else "s-ink"}
        r12 = d["mob12_channel"][c]
        desc = (f"Đường vintage của kênh {c}, MOB 0 đến {x_max}, cùng thang với các ô khác. "
                f"Tại MOB 12: {fmt_pct(r12['rate'], 2)}; tại MOB {x_max}: {fmt_pct(by_ch[c][-1]['rate'], 2)}. "
                "Các đường mờ phía sau là sáu kênh còn lại.")
        cls = " is-accent" if c == HIGHLIGHT_CHANNEL else ""
        cells.append(
            f'<figure class="panel{cls}"><figcaption>{esc(c)}'
            f'<span class="en">MOB 12: {fmt_pct(r12["rate"], 2)}</span></figcaption>'
            + line_chart(ghost + [main], desc, y_ticks, x_max, W=280, H=150, left=40, bottom=24)
            + "</figure>"
        )
    trellis_title = "Bảy kênh trên cùng một thang: Stone và Country-wide dựng dốc sớm nhất"
    trellis_viz = viz(
        esc(trellis_title),
        f'<p class="viz-sub">Tỷ lệ từng quá hạn 30+ theo MOB 0 đến {x_max}, mọi sản phẩm. Đường mờ phía sau '
        "mỗi ô là sáu kênh còn lại, để so vị trí mà không cần chuyển mắt.</p>"
        f'<div class="trellis-7">{"".join(cells)}</div>',
        cls="viz-wide")

    prod_cls = {"Consumer loans": ("s-accent", "t-accent"), "Revolving loans": ("s-stone", "t-label"),
                "Cash loans": ("s-greyl", "t-label")}
    order = ["Cash loans", "Revolving loans", "Consumer loans"]  # mustard vẽ sau cùng, nằm trên
    series = [{"name": PRODUCT_LABEL_VN[p], "rows": by_p[p], "cls": prod_cls[p][0],
               "tcls": prod_cls[p][1], "width": 2.6 if p == HIGHLIGHT_PRODUCT else 2, "tip": True}
              for p in order]
    p_ticks = nice_ticks(max(r["rate"] for r in data["p3_product_mob"]), 4)
    m12p = d["mob12_product"]
    prod_title = (f"Vay tiêu dùng trả góp xấu gấp {times_word(d['consumer_vs_cash'])} lần vay tiền mặt tại MOB 12")
    prod_desc = ("Ba đường vintage theo loại sản phẩm. "
                 + ", ".join(f"{PRODUCT_LABEL_VN[p]} {fmt_pct(m12p[p]['rate'], 2)} tại MOB 12" for p in PRODUCTS)
                 + ". Vay tiêu dùng trả góp được tô màu nhấn.")
    prod_viz = viz(esc(prod_title), responsive(
        line_chart(series, prod_desc, p_ticks, x_max, W=600, H=300, left=48, right=150, bottom=42,
                   end_labels=True, x_title="MOB, số tháng kể từ khi mở hợp đồng"),
        line_chart(series, prod_desc, p_ticks, x_max, W=360, H=260, left=38, right=128, bottom=40,
                   end_labels=True, x_title="MOB, số tháng kể từ khi mở")),
        note="Tại MOB 12: " + ", ".join(f"{PRODUCT_LABEL_VN[p].lower()} {fmt_pct(m12p[p]['rate'], 2)}"
                                       for p in PRODUCTS) + ".")

    rank = sorted(d["mob12_channel"].values(), key=lambda r: -r["rate"])
    rank_rows = [[esc(r["channel_type"]), fmt_pct(r["rate"], 2), fmt_int(r["n_loans"])] for r in rank]
    n_tot = sum(r["n_loans"] for r in rank)
    e_tot = sum(r["n_ever30"] for r in rank)
    rank_viz = viz("Xếp hạng kênh tại MOB 12, kèm mẫu số ghim cùng ngữ cảnh", table(
        ["Kênh", "Từng 30+ tại MOB 12", "Mẫu số tại MOB 12"], rank_rows,
        total=["Tổng (trừ nhóm không rõ)", fmt_pct(e_tot / n_tot, 2), fmt_int(n_tot)]))

    body = f'{trellis_viz}<div class="grid-2">{prod_viz}{rank_viz}</div>'
    dek = (f"So cùng tuổi hợp đồng: vay tiêu dùng trả góp xấu gấp {times_word(d['consumer_vs_cash'])} lần "
           "vay tiền mặt tại MOB 12")
    caveat = ("Mẫu số vintage đã loại hợp đồng có cờ is_partial_history. Đuôi MOB cao duỗi dần vì số hợp đồng "
              "quan sát đủ giảm đi, không phải vì rủi ro dừng lại, nên đọc kèm cột mẫu số tại MOB 12. "
              "Ba visual đã lọc bỏ nhóm (không rõ), nhóm có tỷ lệ "
              f"{fmt_pct(data['p3_unknown_mob12']['rate'], 2)} và sẽ kéo lệch thang trục dùng chung.")
    return page_shell(3, "Vintage theo MOB", dek, body, caveat), [dek, trellis_title, prod_title]


# =============================================================================
# Trang 4. Chuyển nhóm và thu hồi
# =============================================================================

def page4(data, d):
    grid, base = d["roll_grid"], d["roll_base"]
    cure = d["cure"]
    total_n = sum(base[fs]["n"] for fs in FROM_STATES)

    # Ma trận: nền ô xám đậm dần theo tỷ lệ (thang một màu), riêng ô B1 sang B0
    # (cure của nhóm đáng can thiệp nhất) tô mustard.
    head = ['<th scope="col">Nhóm xuất phát</th>'] + [
        f'<th scope="col" class="num">{esc(ts)}'
        + (f'<span class="en">{TO_STATE_VN[ts]}</span>' if ts in TO_STATE_VN else "") + "</th>"
        for ts in TO_STATES] + ['<th scope="col" class="num">Tổng</th>']
    body_rows = []
    for fs in FROM_STATES:
        tds = [f'<th scope="row">{esc(fs)}</th>']
        for ts in TO_STATES:
            c = grid[(fs, ts)]
            if not c["observed"]:
                tds.append('<td class="num empty" title="Không có quan sát nào"></td>')
                continue
            accent = fs == HIGHLIGHT_CURE_FROM and ts == "B0 Current"
            alpha = 0 if accent else min(c["rate"], 1) * 0.34
            style = "" if accent else f' style="--a:{alpha:.3f}"'
            cls = "num cell accent" if accent else "num cell"
            t = tip(f"{fs} sang {ts}", f"Tỷ lệ: {fmt_pct(c['rate'], 2)}",
                    f"{fmt_int(c['n'])} trên {fmt_int(base[fs]['n'])} lượt hợp đồng-tháng")
            tds.append(f'<td class="{cls}"{style} tabindex="0" data-tip="{t}">{fmt_pct(c["rate"], 1)}</td>')
        tds.append(f'<td class="num total">{fmt_pct(1, 1)}</td>')
        body_rows.append("<tr>" + "".join(tds) + "</tr>")
    tot_cells = ['<th scope="row">Tổng</th>']
    for ts in TO_STATES:
        n = sum(grid[(fs, ts)]["n"] for fs in FROM_STATES)
        tot_cells.append(f'<td class="num total">{fmt_pct(n / total_n, 1)}</td>')
    tot_cells.append(f'<td class="num total">{fmt_pct(1, 1)}</td>')
    b1 = HIGHLIGHT_CURE_FROM
    matrix_html = (
        '<div class="table-wrap"><table class="matrix" aria-describedby="matrix-desc">'
        f'<thead><tr>{"".join(head)}</tr></thead><tbody>{"".join(body_rows)}</tbody>'
        f'<tfoot><tr>{"".join(tot_cells)}</tr></tfoot></table></div>'
        f'<p class="viz-sub" id="matrix-desc">Mỗi dòng cộng lại 100%. Ô càng đậm tỷ lệ càng cao; ô màu nhấn: '
        f"{fmt_pct(grid[(b1, 'B0 Current')]['rate'], 1)} hợp đồng {b1} quay về B0 Current, "
        f"{fmt_pct(grid[(b1, b1)]['rate'], 1)} ở lại {b1}. Ô trống: không có quan sát nào.</p>"
    )
    matrix_viz = viz("Từ nhóm quá hạn tháng t (dòng) sang nhóm tháng t+1 (cột)", matrix_html, cls="viz-wide")

    cure_from = [fs for fs in FROM_STATES if fs != "B0 Current"]  # B0 về B0 không phải cure
    items = [{
        "label": fs, "value": cure[fs],
        "cls": "f-accent" if fs == HIGHLIGHT_CURE_FROM else "f-grey",
        "value_txt": fmt_pct(cure[fs], 1),
        "tip": tip(fs, f"Cure rate: {fmt_pct(cure[fs], 2)}",
                   f"{fmt_int(grid[(fs, 'B0 Current')]['n'])} quay về B0 trên {fmt_int(base[fs]['n'])} lượt"),
    } for fs in cure_from]
    b3 = "B3 61-90"
    cure_title = (f"Cửa sổ thu hồi đóng nhanh: {fmt_pct(cure[b1], 1)} ở B1 còn {fmt_pct(cure[b3], 1)} ở B3")
    cure_desc = ("Biểu đồ thanh cure rate theo nhóm quá hạn xuất phát, đã bỏ B0 Current. "
                 + ", ".join(f"{fs} {fmt_pct(cure[fs], 1)}" for fs in cure_from) + ". B1 1-30 được tô màu nhấn.")
    cure_viz = viz(esc(cure_title), responsive(
        hbar_chart(items, cure_desc, W=520, label_w=84, value_w=64, row_h=40, bar_h=24),
        hbar_chart(items, cure_desc, W=360, label_w=74, value_w=56, row_h=36, bar_h=20)),
                   note="Cure rate: tỷ lệ hợp đồng ở nhóm xuất phát tháng t quay về B0 Current tháng t+1.")

    s_rows = [[esc(fs), fmt_int(base[fs]["n"]), fmt_pct(cure[fs], 1), fmt_billion(base[fs]["exposure"], 1)]
              for fs in FROM_STATES]
    tot_cure = sum(grid[(fs, "B0 Current")]["n"] for fs in FROM_STATES) / total_n
    tot_exp = sum(base[fs]["exposure"] for fs in FROM_STATES)
    scale_viz = viz("Mẫu số từng nhóm xuất phát, đặt cạnh cure rate", table(
        ["Nhóm xuất phát", "Số lượt hợp đồng-tháng", "Cure rate", "Dư nợ xuất phát (tỷ)"], s_rows,
        total=["Tổng", fmt_int(total_n), fmt_pct(tot_cure, 1), fmt_billion(tot_exp, 1)]),
        note=f"Cure {fmt_pct(cure[b3], 1)} của B3 chỉ dựa trên {fmt_int(base[b3]['n'])} lượt, khác hẳn "
             f"{fmt_int(base[b1]['n'])} lượt của B1. Dòng B0 Current giữ lại để thấy mẫu số thật.")

    body = f'{matrix_viz}<div class="grid-2">{cure_viz}{scale_viz}</div>'
    dek = (f"Cửa sổ thu hồi đóng lại sau B1: cure rate rơi từ {fmt_pct(cure[b1], 1)} xuống "
           f"{fmt_pct(cure[b3], 1)} chỉ sau hai nhóm")
    caveat = (f"Cure rate rơi từ {fmt_pct(cure[b1], 1)} ở B1 xuống {fmt_pct(cure[b3], 1)} ở B3, nên can thiệp "
              "thu hồi phải dồn vào B1. Biểu đồ cure đã lọc bỏ dòng B0 Current vì B0 về B0 không phải là cure. "
              "Mẫu số là tổng lượt hợp đồng-tháng của nhóm xuất phát cộng qua mọi nhóm đến, KHÔNG cộng cột "
              "n_from vì n_from là window sum lặp lại trên mỗi dòng bucket đến.")
    return page_shell(4, "Chuyển nhóm và thu hồi", dek, body, caveat), [dek, cure_title]


# =============================================================================
# Phần chung: về dữ liệu, thuật ngữ
# =============================================================================

def about_html(fb):
    return (
        '<section class="about"><h2 class="about-title">Về dữ liệu</h2>'
        f"<p>Dữ liệu Home Credit Default Risk (Kaggle): {fmt_int(fb['n_loans_total'])} hợp đồng có lịch sử "
        f"tháng, {fmt_int(fb['n_loan_months'])} dòng hợp đồng-tháng. Thời gian là <strong>tháng tương đối</strong> "
        "(mốc <code>-96</code> đến <code>-1</code>), không quy đổi được sang tháng lịch thật. Danh mục chỉ gồm "
        "khoản vay <strong>trước đây</strong> của khách có hồ sơ mới trong dữ liệu. Đơn vị tiền là đơn vị thô "
        "của Kaggle, không phải VND. Đây là project portfolio luyện tập, không phải số liệu thật của tổ chức nào.</p>"
        "<p>Bản Power BI cùng nội dung nằm trong thư mục <code>powerbi/</code>; bản đó có thêm bộ lọc kênh và "
        "sản phẩm. Định nghĩa chỉ tiêu: <code>docs/metric_dictionary.md</code>. Các quyết định phân tích: "
        "<code>docs/methodology.md</code>.</p>"
        "</section>"
    )


def glossary_html():
    terms = [
        ("DPD", "Days past due, số ngày quá hạn tính đến kỳ quan sát."),
        ("Nhóm B0 đến B4", "B0 Current = 0 ngày, B1 = 1-30, B2 = 31-60, B3 = 61-90, B4 = trên 90 ngày quá hạn."),
        ("30+", "Quá hạn trên 30 ngày, tức từ nhóm B2 trở lên."),
        ("Coincident", "Đo tại đúng một thời điểm (ảnh chụp), khác với vintage theo tuổi hợp đồng."),
        ("Dư nợ proxy", "Ước lượng số tiền còn phải thu của hợp đồng trong tháng, không phải số kế toán chính thức."),
        ("MOB", "Month on book, số tháng kể từ khi mở hợp đồng (MOB 0 là tháng mở)."),
        ("Vintage", "Theo dõi một nhóm hợp đồng theo tuổi hợp đồng (MOB) thay vì theo tháng lịch."),
        ("Từng 30+ tại MOB 12", "Tỷ lệ hợp đồng TỪNG quá hạn trên 30 ngày tính đến MOB 12 (ever 30+@MOB12)."),
        ("Tỷ lệ duyệt", "Hồ sơ được duyệt (kể cả khách không dùng) trên hồ sơ đã có quyết định."),
        ("Tỷ lệ nhận vay", "Take-up rate: trong hồ sơ được duyệt, tỷ lệ khách thật sự nhận khoản vay."),
        ("FPD30", "First payment default 30: kỳ trả đầu tiên chưa trả đủ sau 30 ngày. Có thiên lệch sống sót trong dữ liệu này."),
        ("Nhiễu cơ cấu sản phẩm", "Confounding: các kênh bán tỷ trọng sản phẩm khác nhau, mà sản phẩm vốn đã rủi ro khác nhau, nên so kênh gộp mọi sản phẩm bị lệch."),
        ("Roll rate", "Tỷ lệ hợp đồng chuyển từ nhóm quá hạn này sang nhóm khác ở tháng kế tiếp."),
        ("Cure rate", "Tỷ lệ hợp đồng đang quá hạn quay về B0 Current ngay tháng sau."),
        ("Closed, Other, Missing", "Tháng sau đã tất toán; trạng thái khác; không có dòng dữ liệu tháng sau."),
        ("Nhóm (không rõ)", "Hợp đồng không khớp được hồ sơ gốc nên không biết kênh hay sản phẩm."),
    ]
    items = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in terms)
    return ('<details class="glossary"><summary>Giải thích thuật ngữ</summary>'
            f'<dl>{items}</dl></details>')


# =============================================================================
# CSS. Hằng số màu trùng scripts/build_pbip_report.py (CREAM, INK, STONE, GREY,
# GREY_L, RULE, MUSTARD). Thêm --accent-text: mustard #D4A30A chỉ đạt 2,2:1 trên
# nền kem, không đủ WCAG AA cho chữ nhỏ, nên chữ màu nhấn dùng bản sẫm #8A6A00
# (4,7:1). Thanh và đường vẫn dùng đúng #D4A30A.
# =============================================================================

CSS_BLOCK = """
:root {
  color-scheme: light;
  --bg: #FAF7F0; --bg-2: #F0EADC;
  --ink: #0F172A; --stone: #5C5349; --grey: #938A7F; --grey-l: #C2B9AC; --rule: #E3DACB;
  --accent: #D4A30A; --accent-text: #8A6A00;
  --ghost: #DCD4C6; --cell: 92, 83, 73;
  --serif: "Source Serif 4", Cambria, "Times New Roman", serif;
  --sans: "Segoe UI", Roboto, "Noto Sans", Arial, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --bg: #1C1915; --bg-2: #26221C;
    --ink: #F3EDE1; --stone: #B8AE9F; --grey: #8C8378; --grey-l: #5E574E; --rule: #3A342C;
    --accent: #D4A30A; --accent-text: #E0B53A;
    --ghost: #3A342C; --cell: 243, 237, 225;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #1C1915; --bg-2: #26221C;
  --ink: #F3EDE1; --stone: #B8AE9F; --grey: #8C8378; --grey-l: #5E574E; --rule: #3A342C;
  --accent: #D4A30A; --accent-text: #E0B53A;
  --ghost: #3A342C; --cell: 243, 237, 225;
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--bg); color: var(--ink);
  font-family: var(--sans); font-size: 15px; line-height: 1.5;
  -webkit-text-size-adjust: 100%;
}
code { font-family: Consolas, "Cascadia Mono", monospace; font-size: 0.9em; background: var(--bg-2);
  padding: 0.05em 0.3em; border-radius: 3px; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }

.wrap { max-width: 1240px; margin: 0 auto; padding: 22px 32px 48px; }

/* Dải nhận diện dùng chung: kicker trái, điều hướng phải */
.topbar { display: flex; align-items: center; gap: 12px 16px; }
.kicker { margin: 0 auto 0 0; color: var(--accent-text); font-weight: 700; font-size: 0.78rem; letter-spacing: 0.06em; }
.tabs { display: flex; gap: 4px; overflow-x: auto; scrollbar-width: none; min-width: 0; flex: 0 1 auto; }
.theme { flex: 0 0 auto; }
.only-narrow { display: none; }
.tabs::-webkit-scrollbar { display: none; }
.tab {
  appearance: none; border: 0; background: none; cursor: pointer; white-space: nowrap;
  font: inherit; font-size: 0.92rem; color: var(--stone);
  padding: 8px 14px 9px; border-bottom: 3px solid transparent;
}
.tab:hover { color: var(--ink); }
.tab[aria-selected="true"] { color: var(--ink); font-weight: 600; border-bottom-color: var(--accent); }
.tab:focus-visible, .theme:focus-visible, .hit:focus-visible, td[tabindex]:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.theme {
  appearance: none; background: none; border: 1px solid var(--rule); color: var(--stone);
  font: inherit; font-size: 0.8rem; padding: 4px 10px; border-radius: 3px; cursor: pointer; white-space: nowrap;
}
.theme:hover { color: var(--ink); border-color: var(--grey); }

/* Masthead mỗi trang */
.masthead { margin: 18px 0 18px; }
.page-title { font-family: var(--serif); font-weight: 700; font-size: 2.7rem; line-height: 1.12;
  margin: 0 0 6px; letter-spacing: -0.01em; }
.dek { margin: 0; color: var(--stone); font-size: 1.08rem; max-width: 92ch; }
.rule-ink { height: 2px; background: var(--ink); margin-bottom: 26px; }
.rule-grey { height: 2px; background: var(--ink); margin-top: 34px; }
.caveat { color: var(--stone); font-size: 0.85rem; margin: 12px 0 0; max-width: 150ch; }
.caveat-tag { color: var(--accent-text); font-weight: 700; letter-spacing: 0.04em; margin-right: 10px; }

/* Lưới nội dung */
.grid-p1 { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); gap: 28px 48px; }
.grid-2 { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 28px 48px; }
.col-main, .col-side { min-width: 0; display: flex; flex-direction: column; gap: 28px; }
.viz { min-width: 0; }
.viz-wide { margin-bottom: 32px; }
.viz-title { font-family: var(--serif); font-weight: 600; font-size: 1.32rem; line-height: 1.3; margin: 0 0 10px; }
.viz-sub { color: var(--stone); font-size: 0.86rem; margin: 0 0 12px; }
.viz-note { color: var(--stone); font-size: 0.8rem; margin: 8px 0 0; }

/* KPI: kẻ mực mảnh trên đỉnh mỗi thẻ */
.kpi-row { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 20px; }
.kpi { border-top: 2px solid var(--ink); padding-top: 8px; min-width: 0; }
.kpi-label { color: var(--stone); font-size: 0.72rem; font-weight: 600; letter-spacing: 0.04em; }
.kpi-value { font-size: 2.15rem; font-weight: 600; line-height: 1.15; margin: 6px 0 4px;
  font-variant-numeric: tabular-nums; white-space: nowrap; }
.kpi-ctx { color: var(--stone); font-size: 0.78rem; line-height: 1.35; }

/* SVG */
.chart { display: block; width: 100%; height: auto; overflow: visible; }
.chart text { font-family: var(--sans); }
.t-label { fill: var(--stone); font-size: 12.5px; }
.t-strong { fill: var(--ink); font-weight: 700; }
.t-accent { fill: var(--accent-text); font-size: 12.5px; font-weight: 700; }
.t-value { fill: var(--ink); font-size: 12.5px; font-weight: 600; font-variant-numeric: tabular-nums; }
.t-muted { fill: var(--grey); font-size: 11.5px; font-style: italic; }
.t-axis { fill: var(--stone); font-size: 11px; }
.f-ink { fill: var(--ink); } .f-grey { fill: var(--grey); } .f-greyl { fill: var(--grey-l); }
.f-accent { fill: var(--accent); }
.bubble { fill-opacity: 0.9; stroke: var(--bg); stroke-width: 1.5; }
.s-ink { stroke: var(--ink); } .s-stone { stroke: var(--stone); } .s-greyl { stroke: var(--grey-l); }
.s-accent { stroke: var(--accent); } .s-ghost { stroke: var(--ghost); }
.s-grid { stroke: var(--rule); stroke-width: 1; }
.s-base { stroke: var(--grey-l); stroke-width: 1; }
.s-rule { stroke: var(--grey-l); stroke-width: 1; }
.hit { fill: transparent; cursor: default; }

/* Small multiples */
.trellis-3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px 36px; }
.trellis-7 { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 18px 32px; }
.panel { margin: 0; min-width: 0; }
.panel figcaption { font-weight: 600; font-size: 0.92rem; border-top: 1px solid var(--rule); padding-top: 6px; margin-bottom: 4px; }
.panel.is-accent figcaption { border-top: 2px solid var(--accent); }
.panel .en, th .en { display: block; font-weight: 400; color: var(--stone); font-size: 0.76rem; }
.panel-note { margin: 4px 0 0; font-size: 0.82rem; color: var(--stone); }
.panel-note strong { color: var(--ink); }

/* Bảng: chỉ kẻ ngang */
.table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; max-width: 100%; }
table { border-collapse: collapse; width: 100%; font-size: 0.88rem; font-variant-numeric: tabular-nums; }
th, td { padding: 6px 10px; text-align: left; border-bottom: 1px solid var(--rule); white-space: nowrap; }
th:first-child, td:first-child { padding-left: 0; }
thead th { font-weight: 600; font-size: 0.82rem; vertical-align: bottom; border-bottom: 1px solid var(--grey-l);
  white-space: normal; min-width: 4.5em; }
.matrix thead th { white-space: nowrap; }
tbody th { font-weight: 600; }
.num { text-align: right; }
tfoot td, tfoot th { font-weight: 700; border-bottom: 0; border-top: 1px solid var(--grey-l); }
.matrix td.cell { background: rgba(var(--cell), var(--a, 0)); }
.matrix td.accent { background: var(--accent); color: #0F172A; font-weight: 700; }
.matrix td.total { color: var(--stone); }
.matrix tfoot td.total { color: var(--ink); }
.matrix th.num, .matrix td.num { padding-left: 14px; }
.matrix th:first-child { position: sticky; left: 0; background: var(--bg); z-index: 1; padding-right: 12px; }

/* Phần chung cuối trang */
.about { margin-top: 44px; border-top: 1px solid var(--rule); padding-top: 18px; color: var(--stone); font-size: 0.88rem; }
.about p { max-width: 110ch; }
.about-title { font-family: var(--serif); color: var(--ink); font-size: 1.15rem; margin: 0 0 6px; }
.about p { margin: 0 0 8px; }
.glossary { margin-top: 14px; border-top: 1px solid var(--rule); padding-top: 12px; font-size: 0.88rem; }
.glossary summary { cursor: pointer; font-weight: 600; }
.glossary dl { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 6px 18px; margin: 12px 0 0; }
.glossary dt { font-weight: 600; }
.glossary dd { margin: 0; color: var(--stone); }
.foot { margin-top: 22px; color: var(--stone); font-size: 0.78rem; }

#tooltip {
  position: fixed; z-index: 50; pointer-events: none; max-width: 300px; white-space: pre-line;
  background: var(--ink); color: var(--bg); font-size: 0.8rem; line-height: 1.4;
  padding: 7px 10px; border-radius: 3px; opacity: 0; left: 0; top: 0;
  transform: translate(-1000px, -1000px); transition: opacity 0.08s;
}
#tooltip.on { opacity: 1; }

@media (max-width: 1080px) {
  .grid-p1 { grid-template-columns: minmax(0, 1fr); }
  .col-side { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 28px 40px; }
  .trellis-7 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 820px) {
  .wrap { padding: 14px 16px 36px; }
  .grid-2, .col-side { grid-template-columns: minmax(0, 1fr); }
  .kpi-row { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px 16px; }
  .trellis-3 { grid-template-columns: minmax(0, 1fr); }
  .trellis-7 { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 16px; }
  .page-title { font-size: 2rem; }
  .dek { font-size: 1rem; }
  .viz-title { font-size: 1.18rem; }
  .kpi-value { font-size: 1.7rem; }
  .topbar { flex-wrap: wrap; gap: 8px 12px; }
  .tabs { order: 3; flex: 1 1 100%; }
  .kicker { font-size: 0.68rem; letter-spacing: 0.03em; }
  .theme { padding: 3px 8px; }
  .tab { padding: 8px 8px 9px; font-size: 0.86rem; }
  .glossary dl { grid-template-columns: minmax(0, 1fr); }
  .glossary dd { margin-bottom: 6px; }
}
@media (max-width: 560px) {
  .only-wide { display: none; }
  .only-narrow { display: block; }
  .trellis-7 { grid-template-columns: minmax(0, 1fr); }
  .kpi-value { font-size: 1.5rem; }
  .page-title { font-size: 1.8rem; }
}
"""

# =============================================================================
# JS: chuyển trang theo hash (#page-1 đến #page-4), tooltip, nút sáng/tối.
# Không dùng thư viện ngoài để file mở được khi không có mạng.
# =============================================================================

JS_BLOCK = """
(function () {
  "use strict";
  var tabs = [].slice.call(document.querySelectorAll(".tab"));
  var pages = [].slice.call(document.querySelectorAll(".page"));

  // Hash #page-1 đến #page-4 chọn trang; id của section là sec-N (khác hash) để
  // trình duyệt không tự cuộn xuống giữa trang khi mở link có hash.
  function show(h, push) {
    var ok = pages.some(function (p) { return p.getAttribute("data-hash") === h; });
    if (!ok) h = "page-1";
    pages.forEach(function (p) { p.hidden = p.getAttribute("data-hash") !== h; });
    tabs.forEach(function (t) {
      var on = t.getAttribute("data-hash") === h;
      t.setAttribute("aria-selected", String(on));
      t.tabIndex = on ? 0 : -1;
    });
    if (push && history.replaceState) history.replaceState(null, "", "#" + h);
  }
  tabs.forEach(function (t, i) {
    t.addEventListener("click", function () { show(t.getAttribute("data-hash"), true); window.scrollTo(0, 0); });
    t.addEventListener("keydown", function (e) {
      var k = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (!k) return;
      var n = tabs[(i + k + tabs.length) % tabs.length];
      n.focus(); n.click();
    });
  });
  window.addEventListener("hashchange", function () { show(location.hash.slice(1), false); });
  show(location.hash.slice(1) || "page-1", false);
  window.scrollTo(0, 0);

  var root = document.documentElement, btn = document.getElementById("theme");
  function applyTheme(m) {
    if (m) root.setAttribute("data-theme", m); else root.removeAttribute("data-theme");
    var dark = m === "dark" || (!m && window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches);
    btn.textContent = dark ? "Nền sáng" : "Nền tối";
  }
  var saved = null;
  try { saved = localStorage.getItem("cpm-theme"); } catch (e) {}
  applyTheme(saved);
  btn.addEventListener("click", function () {
    var dark = btn.textContent === "Nền sáng";
    var next = dark ? "light" : "dark";
    applyTheme(next);
    try { localStorage.setItem("cpm-theme", next); } catch (e) {}
  });

  var tip = document.getElementById("tooltip"), cur = null;
  function place(x, y) {
    var w = tip.offsetWidth, h = tip.offsetHeight;
    var tx = Math.max(8, Math.min(x + 14, innerWidth - w - 8));
    var ty = Math.max(8, Math.min(y + 14, innerHeight - h - 8));
    tip.style.transform = "translate(" + tx + "px," + ty + "px)";
  }
  function on(el, x, y) { cur = el; tip.textContent = el.getAttribute("data-tip"); tip.classList.add("on"); place(x, y); }
  function off() { cur = null; tip.classList.remove("on"); }
  document.addEventListener("pointermove", function (e) {
    var el = e.target.closest && e.target.closest("[data-tip]");
    if (el) { if (el !== cur) on(el, e.clientX, e.clientY); else place(e.clientX, e.clientY); }
    else if (cur) off();
  });
  document.addEventListener("focusin", function (e) {
    var el = e.target.closest && e.target.closest("[data-tip]");
    if (el) { var r = el.getBoundingClientRect(); on(el, r.left + r.width / 2, r.top); }
  });
  document.addEventListener("focusout", off);
})();
"""


def build_html(data):
    d = derive(data)
    p1, h1 = page1(data, d)
    p2, h2 = page2(data, d)
    p3, h3 = page3(data, d)
    p4, h4 = page4(data, d)
    tabs = [("1. Tổng quan"), ("2. Kênh bán"), ("3. Vintage"), ("4. Thu hồi")]
    tab_html = "".join(
        f'<button class="tab" type="button" role="tab" id="tab-{i}" aria-controls="sec-{i}" data-hash="page-{i}" '
        f'aria-selected="{"true" if i == 1 else "false"}">{esc(label)}</button>'
        for i, label in enumerate(tabs, start=1))

    payload = {
        "ghi_chu": "Số liệu tổng hợp từ data/warehouse.duckdb (chỉ đọc), sinh bởi scripts/build_dashboard.py",
        **{k: v for k, v in data.items() if k != "p4_roll"},
        "p4_roll": data["p4_roll"],
    }
    json_blob = json.dumps(payload, ensure_ascii=False, indent=1, default=float).replace("</", "<\\/")

    fonts = ("https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,600;8..60,700"
             "&subset=vietnamese&display=swap")
    html_out = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Giám sát danh mục cho vay</title>
<meta name="description" content="Dashboard giám sát danh mục cho vay tiêu dùng, dữ liệu Home Credit Default Risk (Kaggle).">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{fonts}">
<style>{CSS_BLOCK}</style>
</head>
<body>
<div class="wrap">
  <h1 class="sr-only">Dashboard giám sát danh mục cho vay tiêu dùng</h1>
  <div class="topbar">
    <p class="kicker">GIÁM SÁT DANH MỤC CHO VAY TIÊU DÙNG</p>
    <nav class="tabs" role="tablist" aria-label="Bốn trang của dashboard">{tab_html}</nav>
    <button class="theme" id="theme" type="button" aria-label="Đổi nền sáng hoặc tối">Nền tối</button>
  </div>
  <main>
  {p1}{p2}{p3}{p4}
  </main>
  {about_html(data["footer_base"])}
  {glossary_html()}
  <p class="foot">Sinh tự động bằng <code>scripts/build_dashboard.py</code> từ <code>data/warehouse.duckdb</code>
  (chỉ đọc). Số liệu tổng hợp nhúng trong thẻ <code>&lt;script id="dashboard-data"&gt;</code> để kiểm chứng lại.</p>
</div>
<div id="tooltip" role="status" aria-live="polite"></div>
<script type="application/json" id="dashboard-data">
{json_blob}
</script>
<script>{JS_BLOCK}</script>
</body>
</html>
"""
    return html_out, h1 + h2 + h3 + h4


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if not DB_PATH.exists():
        sys.exit(f"{DB_PATH} not found. Chạy scripts/build.py trước.")

    con = duckdb.connect(str(DB_PATH), read_only=True)
    # 1 thread: sum() trên số thực có thể lệch vài chữ số cuối tùy thứ tự cộng
    # song song. Ép 1 thread để chạy lại nhiều lần cho đúng 1 kết quả (và để CSV
    # xuất ra giống hệt từng byte).
    con.execute("PRAGMA threads=1")
    print("Đọc dữ liệu từ warehouse (read_only)")
    data = fetch_data(con)

    print("Xuất CSV cho Power BI")
    export_marts_to_csv(con)
    con.close()

    print("Dựng HTML")
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    html_out, headlines = build_html(data)
    for bad in (chr(0x2014), chr(0x2013), "Georgia"):  # em dash, en dash, font thiếu dấu
        if bad in html_out:
            sys.exit(f"Lỗi: HTML chứa ký tự hoặc font cấm: {bad!r}")
    out_path = DASHBOARD_DIR / "index.html"
    out_path.write_text(html_out, encoding="utf-8", newline="\n")
    print(f"  ok  {out_path.relative_to(ROOT)}  ({len(html_out):,} ký tự)")

    print("\nTiêu đề kết luận (đối chiếu với bản Power BI):")
    for h in headlines:
        print("  " + h)


if __name__ == "__main__":
    main()
