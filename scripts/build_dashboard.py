"""Dựng dashboard HTML tĩnh 4 trang từ các bảng mart trong warehouse.

Cách dùng:
    .venv/Scripts/python.exe scripts/build_dashboard.py

Đọc data/warehouse.duckdb ở chế độ CHỈ ĐỌC (read_only=True), không ghi gì vào kho.
Sinh ra hai đầu ra:
    - dashboard/index.html
        Dashboard tĩnh 4 trang, đồng bộ với bản Power BI (powerbi/, sinh bằng
        scripts/build_pbip_report.py): cùng 4 trang, cùng tên trang, cùng dòng
        kết luận, cùng tiêu đề visual và cùng ghi chú LƯU Ý. Mọi biểu đồ được vẽ
        sẵn thành SVG từ Python, số liệu tổng hợp được nhúng thêm dưới dạng JSON
        (thẻ <script type="application/json" id="dashboard-data">). Mở thẳng file
        bằng trình duyệt là xem được, không cần server. Hỗ trợ mở thẳng từng trang
        bằng hash: index.html#page-1 đến #page-4.
    - data/export/*.csv
        Xuất nguyên 5 mart: mart.funnel_by_channel, mart.fpd_by_segment, mart.vintage,
        mart.roll_rate, mart.portfolio_snapshot để bản PBIP trong powerbi/ đọc. Các file
        CSV này được commit (.gitignore có ngoại lệ riêng cho data/export/*.csv).
        Bảng độ nhạy mart.roll_rate_no_threshold KHÔNG được xuất.

CÂU CHỮ: mọi tên trang, dek, tiêu đề visual có số và ghi chú LƯU Ý lấy từ
scripts/headlines.py, vốn sinh từ data/export/findings.json (nguồn sự thật duy
nhất, do scripts/compute_findings.py viết). File này không gõ cứng chuỗi có số
nào. Kiểm đồng bộ: python scripts/check_headlines_sync.py.

Định nghĩa quá hạn chính là SK_DPD_DEF (DPD có ngưỡng trọng yếu, bỏ qua khoản nợ
giá trị thấp). SK_DPD (không áp ngưỡng) chỉ xuất hiện ở phần độ nhạy, cột hậu tố
_no_threshold.

Chạy lại nhiều lần cho cùng kết quả: truy vấn xác định, một luồng, không sinh số
ngẫu nhiên.

Tông thiết kế "Editorial Newsroom", trùng hằng số màu trong
scripts/build_pbip_report.py: nền kem, chữ mực, MỘT màu nhấn mustard tô đúng đối
tượng mà câu kết luận của visual nói tới, phần còn lại xám.

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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import headlines  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "warehouse.duckdb"
DASHBOARD_DIR = ROOT / "dashboard"
EXPORT_DIR = ROOT / "data" / "export"

MART_TABLES_TO_EXPORT = [
    "mart.funnel_by_channel",
    "mart.fpd_by_segment",
    "mart.vintage",
    "mart.roll_rate",
    "mart.portfolio_snapshot",
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

# Đối tượng được tô mustard ở từng trang, đúng đối tượng mà câu kết luận nói tới.
# Trùng lựa chọn trong scripts/build_pbip_report.py.
HL_P1_BUCKET = "B1 1-30"                       # đuôi quá hạn chủ yếu là B1
HL_P1_CHANNEL = "Credit and cash offices"      # tỷ lệ 30+ hiện tại cao nhất
HL_P2_CHANNELS = {"Contact center", "Stone"}   # hai kênh trên kỳ vọng sau chuẩn hoá
HL_P3_CHANNEL = "Contact center"               # cao nhất ở mọi MOB
HL_P3_PRODUCT = "Revolving loans"              # sản phẩm rủi ro nhất
HL_P3_COHORT = -96                             # đợt mở cũ nhất, câu kết luận nói tới
HL_P4_FROM = "B1 1-30"                         # nhóm còn cửa sổ thu hồi

OTHER_CHANNEL = "Khác"  # nhóm kênh gộp, mẫu số nhỏ
SMALL_N = 1000  # ngưỡng diễn giải của project (findings.json meta.min_n_to_interpret)
FEW_K = 5       # tử số dưới ngưỡng này: đẩy xuống cuối bảng SMR, quá ít ca
THIN_K = 10     # tử số dưới ngưỡng này: tỷ số không kết luận được (theo A1, mục 9)


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
# Hai thẻ tỷ lệ tính trên CÙNG một tập: hợp đồng có dư nợ proxy (cột *_exposure_known).
SQL_P1_TOTAL = """
select
    sum(n_loans)                                              as n_open,
    sum(n_30_plus)                                            as n_30plus,
    sum(n_loans_exposure_known)                               as n_exp_known,
    sum(n_30_plus_exposure_known)                             as n_30plus_exp_known,
    sum(n_30_plus_exposure_known) * 1.0 / sum(n_loans_exposure_known) as rate_30plus_same_set,
    sum(exposure)                                             as exposure_total,
    sum(exposure_30_plus)                                     as exposure_30plus,
    sum(exposure_30_plus) / sum(exposure)                     as exposure_rate_30plus
from mart.portfolio_snapshot
"""

SQL_P1_BUCKETS = """
select dpd_bucket, dpd_bucket_order, sum(n_loans) as n_loans, sum(exposure) as exposure
from mart.portfolio_snapshot
group by dpd_bucket, dpd_bucket_order
order by dpd_bucket_order
"""

SQL_P1_BY_CHANNEL = """
-- Xếp hạng kênh: lọc bỏ '(không rõ)' như Power BI (nhóm không biết được kênh).
-- Mẫu số là mọi hợp đồng mở, đúng như snapshot.by_channel trong findings.json.
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
# SMR và tỷ số duyệt chuẩn hoá lấy thẳng từ findings.json (nguồn sự thật).
SQL_P2_CHANNEL_PRODUCT_MOB12 = """
select channel_type, contract_type,
       sum(n_loans) as n_mob12, sum(n_ever_30_plus) as n_ever30,
       sum(n_ever_30_plus) * 1.0 / sum(n_loans) as rate
from mart.vintage
where mob = 12 and contract_type <> '(không rõ)' and channel_type <> '(không rõ)'
group by channel_type, contract_type
"""

SQL_P2_FUNNEL = """
select channel_type, sum(n_applications) as n_applications
from mart.funnel_by_channel
where channel_type <> '(không rõ)'
group by channel_type
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
        "p3_channel_mob": rows(con, SQL_P3_CHANNEL_MOB),
        "p3_product_mob": rows(con, SQL_P3_PRODUCT_MOB),
        "p4_roll": rows(con, SQL_P4_ROLL),
    }


def export_marts_to_csv(con):
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    for table in MART_TABLES_TO_EXPORT:
        file_name = table.replace(".", "_") + ".csv"
        out_path = EXPORT_DIR / file_name
        # COPY chỉ ghi file ngoài, không đụng gì vào warehouse.duckdb (vẫn đang
        # mở ở chế độ read_only).
        # order by all: thứ tự dòng cố định giữa các lần chạy, diff CSV trên git mới có nghĩa.
        con.sql(f"copy (select * from {table} order by all) to '{out_path.as_posix()}' (header, delimiter ',')")
        print(f"  export  {out_path.relative_to(ROOT)}")


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
# Trang 2: SMR theo kênh, chấm và khoảng tin cậy 95%, vạch tham chiếu tại 1
# =============================================================================

def smr_chart(items, desc, W=560, label_w=150, value_w=118, row_h=30, x_max=4.0, label_px=12.5):
    """items: dict {label, smr, lo, hi, cls, value_txt, tip, faint}. Trục tuyến tính
    từ 0 đến x_max; vạch đứt tại SMR = 1 (đúng bằng mức kỳ vọng của sản phẩm)."""
    track_x, track_w = label_w, W - label_w - value_w
    top = 6
    H = len(items) * row_h + top + 24

    def sx(v):
        return track_x + min(v, x_max) / x_max * track_w

    out = [svg_open(W, H, desc)]
    for t in [0, 1, 2, 3, 4]:
        if t <= x_max:
            out.append(f'<text x="{sx(t):.1f}" y="{H - 6}" class="t-axis" text-anchor="middle">'
                       f'{fmt_num(t, 0)}</text>')
    out.append(f'<line x1="{sx(1):.1f}" x2="{sx(1):.1f}" y1="{top - 2}" y2="{H - 20}" '
               'class="s-base" stroke-dasharray="3 3" />')
    for i, it in enumerate(items):
        y = top + i * row_h
        cy = y + row_h / 2
        tcls = "t-label t-strong" if it["cls"] == "accent" else "t-label"
        out.append(f'<text x="{label_w - 10}" y="{cy:.1f}" class="{tcls}" text-anchor="end" '
                   f'dominant-baseline="central" style="font-size:{label_px}px">{esc(it["label"])}</text>')
        line_cls = "s-accent" if it["cls"] == "accent" else "s-greyl"
        dot_cls = "f-accent" if it["cls"] == "accent" else "f-grey"
        out.append(f'<line x1="{sx(it["lo"]):.1f}" x2="{sx(it["hi"]):.1f}" y1="{cy:.1f}" y2="{cy:.1f}" '
                   f'class="{line_cls}" stroke-width="3" stroke-linecap="round" />')
        if it.get("ref") is not None:
            # Vòng rỗng: SMR khi chỉ chuẩn hoá theo sản phẩm, để thấy dịch chuyển.
            out.append(f'<circle cx="{sx(it["ref"]):.1f}" cy="{cy:.1f}" r="4.5" fill="none" '
                       'class="s-ink" stroke-width="1.4" />')
        out.append(f'<circle cx="{sx(it["smr"]):.1f}" cy="{cy:.1f}" r="5.5" class="{dot_cls}" />')
        vcls = "t-muted" if it.get("faint") else "t-value"
        out.append(f'<text x="{W - value_w + 8}" y="{cy:.1f}" class="{vcls}" '
                   f'dominant-baseline="central">{esc(it["value_txt"])}</text>')
        if it.get("tip"):
            out.append(f'<rect class="hit" x="0" y="{y}" width="{W}" height="{row_h}" '
                       f'tabindex="0" data-tip="{it["tip"]}" />')
    out.append("</svg>")
    return "".join(out)


# =============================================================================
# Biểu đồ đường (trang 3): dùng cho cả ô nhỏ trellis lẫn biểu đồ theo sản phẩm
# =============================================================================

def line_chart(series, desc, y_ticks, x_max, W, H, left=44, right=14, top=10, bottom=28,
               x_ticks=(0, 12, 24, 36), end_labels=False, x_title=None):
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
                    lines.append(f"{s['name']}: {fmt_pct(r['rate'], 3)} "
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
    return (f'<section class="viz {cls}"><h3 class="viz-title">{esc(title)}</h3>'
            f"{body}{n}</section>")


def kpi(label, value, context):
    return (f'<div class="kpi"><div class="kpi-label">{esc(label)}</div>'
            f'<div class="kpi-value">{value}</div><div class="kpi-ctx">{esc(context)}</div></div>')


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


def page_shell(n, H, body):
    """Khung trang: tên trang, dek, kẻ mực, nội dung, kẻ chân, LƯU Ý. Mọi câu lấy từ headlines."""
    return (
        f'<section class="page" id="sec-{n}" data-hash="page-{n}" role="tabpanel" aria-labelledby="tab-{n}">'
        f'<header class="masthead"><h2 class="page-title">{esc(H["title"])}</h2>'
        f'<p class="dek">{esc(H["dek"])}</p></header>'
        f'<div class="rule-ink" role="presentation"></div>'
        f"{body}"
        f'<div class="rule-grey" role="presentation"></div>'
        f'<p class="caveat"><span class="caveat-tag">LƯU Ý</span>{esc(H["caveat"])}</p>'
        "</section>"
    )


def interval(lo, hi, d, pct=True):
    """'[0,137; 0,203]': cùng quy ước với headlines.py."""
    if pct:
        return f"[{fmt_num(lo * 100, d)}; {fmt_num(hi * 100, d)}]"
    return f"[{fmt_num(lo, d)}; {fmt_num(hi, d)}]"


def by(items, key):
    return {x[key]: x for x in items}


# =============================================================================
# Trang 1. Tổng quan danh mục
# =============================================================================

def page1(data, F, H):
    t = data["p1_total"]
    n_open = t["n_open"]
    buckets = data["p1_buckets"]
    N = H["notes"]

    kpis = "".join([
        kpi("HỢP ĐỒNG ĐANG MỞ", fmt_int(n_open), N["kpi_open"]),
        kpi("TỶ LỆ 30+ THEO HỢP ĐỒNG", fmt_pct(t["rate_30plus_same_set"], 3), N["kpi_rate"]),
        kpi("DƯ NỢ PROXY ĐANG MỞ", fmt_billion(t["exposure_total"], 1) + " tỷ",
            "Đơn vị thô của dữ liệu Kaggle, không phải VND"),
        kpi("TỶ LỆ 30+ THEO DƯ NỢ", fmt_pct(t["exposure_rate_30plus"], 3), N["kpi_exposure_rate"]),
    ])

    # Xếp hạng kênh: Credit and cash offices mustard (đối tượng của câu kết luận), còn lại xám.
    snap_ch = by(F["snapshot"]["by_channel"], "channel_type")
    ch_items = []
    for r in data["p1_by_channel"]:
        c = r["channel_type"]
        ci = snap_ch[c]["primary"]["ci95"]
        ch_items.append({
            "label": c, "value": r["rate_30plus"],
            "cls": "f-accent" if c == HL_P1_CHANNEL else "f-grey",
            "value_txt": fmt_pct(r["rate_30plus"], 3),
            "tip": tip(c, f"Tỷ lệ 30+ hiện tại: {fmt_pct(r['rate_30plus'], 3)} {interval(*ci, 3)}",
                       f"{fmt_int(r['n_30plus'])} trên {fmt_int(r['n_open'])} hợp đồng đang mở"),
        })
    ch_desc = ("Biểu đồ thanh tỷ lệ quá hạn 30+ hiện tại theo kênh bán, sắp giảm dần. "
               + "; ".join(f"{it['label']} {it['value_txt']}" for it in ch_items)
               + f". {HL_P1_CHANNEL} được tô màu nhấn.")
    channel_viz = viz(H["visuals"]["rate_by_channel"], responsive(
        hbar_chart(ch_items, ch_desc, W=640, label_w=170, row_h=36, bar_h=22),
        hbar_chart(ch_items, ch_desc, W=360, label_w=140, value_w=58, row_h=32, bar_h=18, label_px=12)),
        note="Khoảng tin cậy 95% của từng kênh hiện khi rê chuột. Các kênh ngoài Credit and cash "
             "offices có tử số rất nhỏ, chênh lệch giữa chúng không có ý nghĩa.")

    # Biểu đồ chủ đạo: cơ cấu nhóm quá hạn. Thanh 100% để thấy đuôi mỏng cỡ nào,
    # rồi phóng to riêng phần đuôi B1 đến B4. B1 1-30 mustard: câu kết luận nói về nó.
    tail = [b for b in buckets if b["dpd_bucket"] != "B0 Current"]
    tail_items = [{
        "label": b["dpd_bucket"], "value": b["n_loans"],
        "cls": "f-accent" if b["dpd_bucket"] == HL_P1_BUCKET else "f-grey",
        "value_txt": fmt_int(b["n_loans"]),
        "tip": tip(b["dpd_bucket"], f"{fmt_int(b['n_loans'])} hợp đồng ({fmt_pct(b['n_loans'] / n_open, 3)} danh mục)",
                   f"Dư nợ proxy: {fmt_billion(b['exposure'], 3)} tỷ"),
    } for b in tail]
    n_tail = sum(b["n_loans"] for b in tail)
    b0_share = buckets[0]["n_loans"] / n_open
    bucket_desc = ("Cơ cấu danh mục theo nhóm quá hạn: "
                   + ", ".join(f"{b['dpd_bucket']} {fmt_int(b['n_loans'])} hợp đồng" for b in buckets)
                   + f". Nhóm {HL_P1_BUCKET} được tô màu nhấn.")
    hero_body = (
        share_bar(b0_share, f"Thanh tỷ trọng: B0 Current chiếm {fmt_pct(b0_share, 2)} hợp đồng đang mở.")
        + f'<p class="viz-sub">Phóng to phần đuôi B1 đến B4 ({fmt_int(n_tail)} hợp đồng quá hạn), '
        "trục là số hợp đồng:</p>"
        + hbar_chart(tail_items, bucket_desc, W=360, label_w=70, value_w=52, row_h=34, bar_h=20)
    )
    hero_viz = viz(H["visuals"]["bucket_mix"], hero_body)

    prod_rows = []
    for r in data["p1_by_product"]:
        name = PRODUCT_LABEL_VN.get(r["contract_type"], r["contract_type"])
        prod_rows.append([esc(name), fmt_int(r["n_open"]), fmt_int(r["n_30plus"]), fmt_pct(r["rate_30plus"], 3)])
    product_viz = viz(H["visuals"]["product_table"], table(
        ["Sản phẩm", "Số hợp đồng mở", "Số hợp đồng 30+", "Tỷ lệ 30+ hiện tại"], prod_rows,
        total=["Tổng", fmt_int(n_open), fmt_int(t["n_30plus"]), fmt_pct(t["n_30plus"] / n_open, 3)]))

    body = (
        '<div class="grid-p1">'
        f'<div class="col-main"><div class="kpi-row">{kpis}</div>{channel_viz}</div>'
        f'<div class="col-side">{hero_viz}{product_viz}</div>'
        "</div>"
    )
    return page_shell(1, H, body)


# =============================================================================
# Trang 2. Kênh bán và rủi ro
# =============================================================================

def page2(data, F, H):
    cp = {(r["channel_type"], r["contract_type"]): r for r in data["p2_channel_product_mob12"]}
    smr_rows = [r for r in F["channel_comparison"]["mob12"]["smr_by_channel"]
                if r["channel_type"] != UNKNOWN]
    smr_rows.sort(key=lambda r: -r["primary"]["smr"])
    # Trellis bỏ kênh Khác: mẫu số dưới ngưỡng ở hai trong ba sản phẩm, một ca lẻ
    # của nó kéo giãn thang chung. Khác vẫn có mặt ở biểu đồ SMR và bảng duyệt.
    channels = [r["channel_type"] for r in smr_rows if r["channel_type"] != OTHER_CHANNEL]
    x_max = nice_ticks(max(r["rate"] for (c, _), r in cp.items() if c in channels), 4)[-1]

    # Trellis: mỗi ô một sản phẩm, cùng thang. Màu nhấn: Contact center và Stone,
    # hai kênh mà câu kết luận của trang nói là trên kỳ vọng.
    panels = []
    for p in PRODUCTS:
        items = []
        for c in channels:
            r = cp.get((c, p))
            if r is None:
                items.append({"label": c, "value": None, "note": "không bán"})
                continue
            small = r["n_mob12"] < SMALL_N
            items.append({
                "label": c, "value": r["rate"],
                "cls": "f-accent" if c in HL_P2_CHANNELS else "f-grey",
                "value_txt": fmt_pct(r["rate"], 3) + ("*" if small else ""),
                "tip": tip(f"{c} · {PRODUCT_LABEL_VN[p]}",
                           f"Từng 30+ tại MOB 12: {fmt_pct(r['rate'], 3)}",
                           f"{fmt_int(r['n_ever30'])} trên {fmt_int(r['n_mob12'])} hợp đồng",
                           f"* mẫu số dưới {fmt_int(SMALL_N)} hợp đồng, không diễn giải" if small else None),
            })
        desc = (f"Ô {PRODUCT_LABEL_VN[p]}: tỷ lệ từng 30+ tại MOB 12 theo kênh, cùng thang với hai ô kia. "
                + "; ".join(f"{it['label']} {it['value_txt']}" for it in items if it["value"] is not None))
        panels.append(
            f'<figure class="panel"><figcaption>{esc(PRODUCT_LABEL_VN[p])}'
            f'<span class="en">{esc(p)}</span></figcaption>'
            + hbar_chart(items, desc, W=360, label_w=150, value_w=66, row_h=30, bar_h=16,
                         x_max=x_max, label_px=12)
            + "</figure>"
        )
    trellis_viz = viz(
        H["visuals"]["mix_trellis"],
        f'<p class="viz-sub">Từng quá hạn 30+ tại MOB 12, mỗi ô một loại sản phẩm, thang chung từ 0 đến '
        f'{pct_tick_label(x_max)}; kênh {OTHER_CHANNEL} bị bỏ vì mẫu số nhỏ. {esc(H["notes"]["trellis_sub"])}</p>'
        f'<div class="trellis-3">{"".join(panels)}</div>',
        note=f"* mẫu số tại MOB 12 dưới {fmt_int(SMALL_N)} hợp đồng, không diễn giải.",
        cls="viz-wide")

    # SMR theo kênh: chấm đặc là SMR sản phẩm × đợt mở 12 tháng kèm khoảng tin cậy,
    # vòng rỗng là SMR chỉ chuẩn hoá theo sản phẩm. Kênh có tử số dưới 10 ghi mờ.
    smr_sc = F["origination_cohort"]["mob12"]["smr_by_channel"]
    sx_rows = sorted((r for r in smr_sc["product_x_cut12"]["primary"] if r["channel_type"] != UNKNOWN),
                     key=lambda r: (r["observed"] < FEW_K, -r["smr"]))
    sp_by = by(smr_sc["product_only"]["primary"], "channel_type")
    s_items = []
    for pr in sx_rows:
        c = pr["channel_type"]
        ref = sp_by[c]["smr"]
        thin = pr["observed"] < THIN_K
        s_items.append({
            "label": c, "smr": pr["smr"], "lo": pr["ci95"][0], "hi": pr["ci95"][1], "ref": ref,
            "cls": "accent" if c in HL_P2_CHANNELS else "grey", "faint": thin,
            "value_txt": f"{fmt_num(pr['smr'], 2)} {interval(*pr['ci95'], 2, pct=False)}",
            "tip": tip(c, f"SMR sản phẩm × đợt mở {fmt_num(pr['smr'], 2)} {interval(*pr['ci95'], 2, pct=False)}",
                       f"SMR chỉ sản phẩm {fmt_num(ref, 2)}",
                       f"Quan sát {fmt_int(pr['observed'])} ca, kỳ vọng {fmt_num(pr['expected'], 1)} ca",
                       f"Tử số dưới {THIN_K}: không kết luận" if thin else None),
        })
    s_desc = ("SMR từng 30+ tại MOB 12 theo kênh, chuẩn hoá theo sản phẩm × đợt mở, kèm khoảng tin cậy 95%: "
              + "; ".join(f"{it['label']} {it['value_txt']} (chỉ sản phẩm {fmt_num(it['ref'], 2)})"
                          for it in s_items))
    smr_viz = viz(H["visuals"]["smr"], responsive(
        smr_chart(s_items, s_desc, W=560),
        smr_chart(s_items, s_desc, W=360, label_w=118, value_w=96, label_px=11)),
        note="Chấm đặc: SMR chuẩn hoá theo sản phẩm × đợt mở 12 tháng, gạch ngang là khoảng tin cậy 95%. "
             "Vòng rỗng: SMR chỉ chuẩn hoá theo sản phẩm. Vạch đứt là SMR bằng một, đúng mức kỳ vọng. "
             f"Chữ mờ: tử số dưới {THIN_K} ca, không kết luận.")

    # Bảng duyệt: thô, chuẩn hoá theo sản phẩm, take-up chỉ cho vay tiêu dùng.
    std = by(F["approval"]["channel_standardized"], "channel_type")
    tk = by(F["approval"]["take_up_consumer_by_channel"], "channel_type")
    apps = by(data["p2_funnel"], "channel_type")
    a_rows = []
    for c in sorted(std, key=lambda c: -apps[c]["n_applications"]):
        tu = (tk.get(c) or {}).get("take_up_rate") or {}
        tu_txt = fmt_pct(tu["rate"], 1) if tu.get("rate") is not None and tu.get("enough_n") else "không bán"
        if tu.get("rate") is not None and not tu.get("enough_n"):
            tu_txt = fmt_pct(tu["rate"], 1) + "*"
        a_rows.append([esc(c), fmt_int(apps[c]["n_applications"]), fmt_pct(std[c]["crude"]["rate"], 1),
                       fmt_num(std[c]["standardized_ratio"], 2), tu_txt])
    appr_viz = viz(H["visuals"]["approval"], table(
        ["Kênh", "Số hồ sơ", "Tỷ lệ duyệt thô", "Duyệt so với kỳ vọng", "Take-up vay tiêu dùng"], a_rows),
        note="Duyệt so với kỳ vọng = số được duyệt / số kỳ vọng nếu kênh có tỷ lệ duyệt của từng sản phẩm. "
             f"* mẫu số dưới {fmt_int(SMALL_N)} hồ sơ.")

    body = f'{trellis_viz}<div class="grid-2">{smr_viz}{appr_viz}</div>'
    return page_shell(2, H, body)


# =============================================================================
# Trang 3. Vintage theo MOB
# =============================================================================

def page3(data, F, H):
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
                "cls": "s-accent" if c == HL_P3_CHANNEL else "s-ink"}
        r12 = next(r for r in by_ch[c] if r["mob"] == 12)
        desc = (f"Đường vintage của kênh {c}, MOB 0 đến {x_max}, cùng thang với các ô khác. "
                f"Tại MOB 12: {fmt_pct(r12['rate'], 3)}. Các đường mờ phía sau là sáu kênh còn lại.")
        cls = " is-accent" if c == HL_P3_CHANNEL else ""
        cells.append(
            f'<figure class="panel{cls}"><figcaption>{esc(c)}'
            f'<span class="en">MOB 12: {fmt_pct(r12["rate"], 3)}</span></figcaption>'
            + line_chart(ghost + [main], desc, y_ticks, x_max, W=280, H=150, left=46, bottom=24)
            + "</figure>"
        )
    trellis_viz = viz(
        H["visuals"]["trellis"],
        f'<p class="viz-sub">Tỷ lệ từng quá hạn 30+ theo MOB 0 đến {x_max}, mọi sản phẩm. Đường mờ phía sau '
        "mỗi ô là sáu kênh còn lại, để so vị trí mà không cần chuyển mắt.</p>"
        f'<div class="trellis-7">{"".join(cells)}</div>',
        cls="viz-wide")

    prod_cls = {"Revolving loans": ("s-accent", "t-accent"), "Cash loans": ("s-stone", "t-label"),
                "Consumer loans": ("s-greyl", "t-label")}
    order = ["Consumer loans", "Cash loans", "Revolving loans"]  # mustard vẽ sau cùng, nằm trên
    series = [{"name": PRODUCT_LABEL_VN[p], "rows": by_p[p], "cls": prod_cls[p][0],
               "tcls": prod_cls[p][1], "width": 2.6 if p == HL_P3_PRODUCT else 2, "tip": True}
              for p in order]
    p_ticks = nice_ticks(max(r["rate"] for r in data["p3_product_mob"]), 4)
    prod_desc = ("Ba đường vintage theo loại sản phẩm. "
                 + ", ".join(f"{PRODUCT_LABEL_VN[p]} {fmt_pct(next(r for r in by_p[p] if r['mob'] == 12)['rate'], 3)} "
                             "tại MOB 12" for p in PRODUCTS)
                 + ". Thẻ quay vòng được tô màu nhấn.")
    prod_viz = viz(H["visuals"]["by_product"], responsive(
        line_chart(series, prod_desc, p_ticks, x_max, W=600, H=300, left=52, right=150, bottom=42,
                   end_labels=True, x_title="MOB, số tháng kể từ khi mở hợp đồng"),
        line_chart(series, prod_desc, p_ticks, x_max, W=360, H=260, left=44, right=124, bottom=40,
                   end_labels=True, x_title="MOB, số tháng kể từ khi mở")))

    # Bảng độ nhạy: tỷ số so với vay tiền mặt tại MOB 12 theo bốn cách đo.
    ratio = F["origination_cohort"]["mob12"]["product_ratio_vs_cash"]
    ways = [("primary", "crude", "Định nghĩa chính"), ("primary", "mh_cut12", "Kiểm soát đợt mở"),
            ("due_only", "crude", "Định nghĩa giữa"), ("no_threshold", "crude", "Không áp ngưỡng")]
    s_rows = []
    for tag, key, label in ways:
        row = [esc(label)]
        for p in ["Revolving loans", "Consumer loans"]:
            x = ratio[p][tag][key]
            row.append(f"{fmt_num(x['ratio'], 2)} {interval(*x['ci95'], 2, pct=False)}")
        s_rows.append(row)
    sens_viz = viz(H["visuals"]["sensitivity"], table(
        ["Cách đo", "Thẻ quay vòng / vay tiền mặt", "Vay tiêu dùng / vay tiền mặt"], s_rows),
        note="Tỷ số tỷ lệ từng 30+ tại MOB 12, kèm khoảng tin cậy 95%. Định nghĩa chính dùng SK_DPD_DEF; "
             "kiểm soát đợt mở gộp Mantel-Haenszel qua đợt 12 tháng; định nghĩa giữa là SK_DPD 30+ ở tháng "
             "còn kỳ phải trả; không áp ngưỡng là SK_DPD.")

    # Vintage theo đợt mở: mỗi đợt một đường, chỉ MOB mà cả đợt đã đủ tuổi.
    cohorts = [c for c in F["origination_cohort"]["curve_by_cohort_labeled_products"]["cohorts"]
               if len(c["points"]) > 1]
    c_series = []
    for c in sorted(cohorts, key=lambda c: c["origination_cohort_start"] == HL_P3_COHORT):
        hl = c["origination_cohort_start"] == HL_P3_COHORT
        c_series.append({
            "name": c["origination_cohort"],
            "rows": [{"mob": pt["mob"], "rate": pt["rate"], "n_loans": pt["n"], "n_ever30": pt["k"]}
                     for pt in c["points"]],
            "cls": "s-accent" if hl else "s-greyl", "tcls": "t-accent" if hl else "t-axis",
            "width": 2.6 if hl else 1.6, "tip": True, "end": c["points"][-1]["mob"]})
    c_max = max(pt["mob"] for c in cohorts for pt in c["points"])
    # Nhãn cuối đường chỉ cho đợt chạy hết trục; đợt ngắn hơn ghi tên trong chú thích
    # (nhãn giữa biểu đồ đè lên trục và các đường khác).
    short = [s_ for s_ in c_series if s_["end"] < c_max]
    for s_ in short:
        s_["label"] = False
    c_ticks = nice_ticks(max(pt["rate"] for c in cohorts for pt in c["points"]), 4)
    c_desc = ("Đường vintage theo đợt mở 12 tháng, sản phẩm có nhãn, chỉ vẽ MOB mà cả đợt đã đủ tuổi. "
              + "; ".join(f"đợt {c['origination_cohort']} tới MOB {c['points'][-1]['mob']}: "
                          f"{fmt_pct(c['points'][-1]['rate'], 3)}" for c in cohorts)
              + ". Đợt cũ nhất được tô màu nhấn.")
    cohort_viz = viz(H["visuals"]["cohort"], responsive(
        line_chart(c_series, c_desc, c_ticks, c_max, W=1000, H=320, left=52, right=120, bottom=42,
                   end_labels=True, x_title="MOB, số tháng kể từ khi mở hợp đồng"),
        line_chart(c_series, c_desc, c_ticks, c_max, W=360, H=280, left=44, right=96, bottom=40,
                   end_labels=True, x_title="MOB, số tháng kể từ khi mở")),
        note="Mỗi đường một đợt mở 12 tháng (tháng tương đối so với ngày nộp hồ sơ hiện tại). "
             + " ".join(f"Đợt {s_['name']} dừng ở MOB {s_['end']}." for s_ in sorted(short, key=lambda x: -x["end"]))
             + " Đợt -12 đến -1 chưa đủ tuổi tới MOB 1 nên không vẽ. Thẻ quay vòng, vay tiền mặt và vay "
             "tiêu dùng gộp chung; cơ cấu sản phẩm đổi theo đợt.",
        cls="viz-wide")

    body = f'{cohort_viz}{trellis_viz}<div class="grid-2">{prod_viz}{sens_viz}</div>'
    return page_shell(3, H, body)


# =============================================================================
# Trang 4. Chuyển nhóm và thu hồi
# =============================================================================

def page4(data, F, H):
    grid, base = build_roll_grid(data["p4_roll"])
    cure = {fs: grid[(fs, "B0 Current")]["rate"] for fs in FROM_STATES}
    total_n = sum(base[fs]["n"] for fs in FROM_STATES)
    rc = by(F["roll_cure"]["primary"]["all"], "from_state")

    # Ma trận: nền ô xám đậm dần theo tỷ lệ (thang một màu), riêng ô B1 sang B0 tô mustard.
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
            accent = fs == HL_P4_FROM and ts == "B0 Current"
            alpha = 0 if accent else min(c["rate"], 1) * 0.34
            style = "" if accent else f' style="--a:{alpha:.3f}"'
            cls = "num cell accent" if accent else "num cell"
            t = tip(f"{fs} sang {ts}", f"Tỷ lệ: {fmt_pct(c['rate'], 3)}",
                    f"{fmt_int(c['n'])} trên {fmt_int(base[fs]['n'])} lượt hợp đồng-tháng")
            tds.append(f'<td class="{cls}"{style} tabindex="0" data-tip="{t}">{fmt_pct(c["rate"], 1)}</td>')
        tds.append(f'<td class="num total">{fmt_pct(1, 1)}</td>')
        body_rows.append("<tr>" + "".join(tds) + "</tr>")
    tot_cells = ['<th scope="row">Tổng</th>']
    for ts in TO_STATES:
        n = sum(grid[(fs, ts)]["n"] for fs in FROM_STATES)
        tot_cells.append(f'<td class="num total">{fmt_pct(n / total_n, 1)}</td>')
    tot_cells.append(f'<td class="num total">{fmt_pct(1, 1)}</td>')
    matrix_html = (
        '<div class="table-wrap"><table class="matrix" aria-describedby="matrix-desc">'
        f'<thead><tr>{"".join(head)}</tr></thead><tbody>{"".join(body_rows)}</tbody>'
        f'<tfoot><tr>{"".join(tot_cells)}</tr></tfoot></table></div>'
        '<p class="viz-sub" id="matrix-desc">Dòng là nhóm tháng t, cột là nhóm tháng t+1, mỗi dòng cộng lại '
        "100%. Ô càng đậm tỷ lệ càng cao; ô màu nhấn là B1 quay về B0. Ô trống: không có quan sát nào.</p>"
    )
    matrix_viz = viz(H["visuals"]["matrix"], matrix_html, cls="viz-wide")

    # Cure: bỏ B0 (B0 về B0 không phải cure). B3 dưới ngưỡng mẫu nên tô xám nhạt.
    cure_from = [fs for fs in FROM_STATES if fs != "B0 Current"]
    items = []
    for fs in cure_from:
        ok = rc[fs]["enough_n"]
        ci = rc[fs]["cure_to_b0"]["ci95"]
        items.append({
            "label": fs, "value": cure[fs],
            "cls": "f-accent" if fs == HL_P4_FROM else ("f-grey" if ok else "f-greyl"),
            "value_txt": fmt_pct(cure[fs], 1) + ("" if ok else "*"),
            "tip": tip(fs, f"Cure rate: {fmt_pct(cure[fs], 1)} {interval(*ci, 1)}",
                       f"{fmt_int(grid[(fs, 'B0 Current')]['n'])} quay về B0 trên {fmt_int(base[fs]['n'])} lượt",
                       None if ok else f"* dưới {fmt_int(SMALL_N)} lượt, không diễn giải"),
        })
    cure_desc = ("Biểu đồ thanh cure rate theo nhóm quá hạn xuất phát, đã bỏ B0 Current. "
                 + ", ".join(f"{it['label']} {it['value_txt']}" for it in items) + ". B1 1-30 được tô màu nhấn.")
    cure_viz = viz(H["visuals"]["cure"], responsive(
        hbar_chart(items, cure_desc, W=520, label_w=84, value_w=64, row_h=40, bar_h=24),
        hbar_chart(items, cure_desc, W=360, label_w=74, value_w=56, row_h=36, bar_h=20)),
        note="Cure rate: tỷ lệ lượt ở nhóm xuất phát tháng t quay về B0 Current tháng t+1. "
             f"* dưới {fmt_int(SMALL_N)} lượt, không diễn giải.")

    s_rows = []
    for fs in FROM_STATES:
        c_txt = "" if fs == "B0 Current" else fmt_pct(cure[fs], 1)
        s_rows.append([esc(fs), fmt_int(base[fs]["n"]), c_txt, fmt_billion(base[fs]["exposure"], 1)])
    od = [fs for fs in FROM_STATES if fs != "B0 Current"]
    tot_cure = sum(grid[(fs, "B0 Current")]["n"] for fs in od) / sum(base[fs]["n"] for fs in od)
    tot_exp = sum(base[fs]["exposure"] for fs in FROM_STATES)
    scale_viz = viz(H["visuals"]["roll_tbl"], table(
        ["Nhóm xuất phát", "Số lượt hợp đồng-tháng", "Cure rate", "Dư nợ cộng dồn qua tháng (tỷ)"], s_rows,
        total=["Tổng", fmt_int(total_n), fmt_pct(tot_cure, 1), fmt_billion(tot_exp, 1)]),
        note="Cure của dòng tổng tính trên B1 đến B4. Dư nợ cộng dồn: một hợp đồng nằm ở B0 nhiều tháng "
             "được cộng mỗi tháng một lần, không phải dư nợ tại một thời điểm.")

    body = f'{matrix_viz}<div class="grid-2">{cure_viz}{scale_viz}</div>'
    return page_shell(4, H, body)


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
        ("SK_DPD_DEF", "DPD có ngưỡng trọng yếu: bỏ qua khoản nợ giá trị thấp. Định nghĩa quá hạn chính của dashboard."),
        ("SK_DPD", "DPD không áp ngưỡng trọng yếu, đếm cả khoản dư lẻ sau kỳ trả cuối. Chỉ dùng làm độ nhạy."),
        ("Nhóm B0 đến B4", "B0 Current = 0 ngày, B1 = 1-30, B2 = 31-60, B3 = 61-90, B4 = trên 90 ngày quá hạn."),
        ("30+", "Quá hạn trên 30 ngày, tức từ nhóm B2 trở lên."),
        ("Coincident", "Đo tại đúng một thời điểm (ảnh chụp), khác với vintage theo tuổi hợp đồng."),
        ("Dư nợ proxy", "Ước lượng số tiền còn phải thu của hợp đồng trong tháng, không phải số kế toán chính thức."),
        ("MOB", "Month on book, số tháng kể từ khi mở hợp đồng (MOB 0 là tháng mở)."),
        ("Vintage", "Theo dõi một nhóm hợp đồng theo tuổi hợp đồng (MOB) thay vì theo tháng lịch."),
        ("Từng 30+ tại MOB 12", "Tỷ lệ hợp đồng TỪNG quá hạn trên 30 ngày tính đến MOB 12 (ever 30+@MOB12)."),
        ("Khoảng tin cậy 95%", "Viết trong ngoặc vuông sau con số. Hai nhóm chỉ thật sự khác nhau khi khoảng của tỷ số không chứa 1."),
        ("SMR", "Standardized ratio: số ca quan sát chia số ca kỳ vọng nếu kênh có tỷ lệ của từng sản phẩm. Trên 1 là xấu hơn mức sản phẩm của chính nó."),
        ("Chuẩn hoá theo sản phẩm", "So kênh sau khi bỏ ảnh hưởng của việc mỗi kênh bán tỷ trọng sản phẩm khác nhau."),
        ("Tỷ lệ duyệt", "Hồ sơ được duyệt (kể cả khách không dùng) trên hồ sơ đã có quyết định."),
        ("Take-up", "Trong hồ sơ được duyệt, tỷ lệ khách thật sự nhận khoản vay. Chỉ có nghĩa ở vay tiêu dùng."),
        ("FPD30", "First payment default 30: kỳ trả đầu tiên chưa trả đủ sau 30 ngày. Quá ít ca để làm trục rủi ro."),
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
    findings = headlines.load_findings()
    H = headlines.texts(headlines.build(findings))
    pages = [page1(data, findings, H[1]), page2(data, findings, H[2]),
             page3(data, findings, H[3]), page4(data, findings, H[4])]
    tab_html = "".join(
        f'<button class="tab" type="button" role="tab" id="tab-{i}" aria-controls="sec-{i}" data-hash="page-{i}" '
        f'aria-selected="{"true" if i == 1 else "false"}">{esc(H[i]["tab"])}</button>'
        for i in range(1, 5))

    payload = {
        "ghi_chu": ("Số liệu tổng hợp từ data/warehouse.duckdb (chỉ đọc), sinh bởi scripts/build_dashboard.py. "
                    "Câu chữ lấy từ scripts/headlines.py, sinh từ data/export/findings.json."),
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
  {''.join(pages)}
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
    lines = []
    for n in range(1, 5):
        lines += [H[n]["title"], H[n]["dek"]] + list(H[n]["visuals"].values())
    return html_out, lines


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
    html_out, heads = build_html(data)
    for bad in (chr(0x2014), chr(0x2013), "Georgia"):  # em dash, en dash, font thiếu dấu
        if bad in html_out:
            sys.exit(f"Lỗi: HTML chứa ký tự hoặc font cấm: {bad!r}")
    out_path = DASHBOARD_DIR / "index.html"
    out_path.write_text(html_out, encoding="utf-8", newline="\n")
    print(f"  ok  {out_path.relative_to(ROOT)}  ({len(html_out):,} ký tự)")

    print("\nTiêu đề kết luận (đối chiếu với bản Power BI):")
    for h in heads:
        print("  " + h)


if __name__ == "__main__":
    main()
