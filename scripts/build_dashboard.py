"""Dựng dashboard tĩnh (gói việc G4) từ các bảng mart trong warehouse.

Cách dùng:
    .venv/Scripts/python.exe scripts/build_dashboard.py

Đọc data/warehouse.duckdb ở chế độ CHỈ ĐỌC (read_only=True), không ghi gì vào kho.
Sinh ra hai đầu ra:
    - dashboard/index.html
        Dashboard tĩnh 4 trang. Số liệu đã tổng hợp được nhúng vào HTML dưới
        dạng JSON (thẻ <script type="application/json" id="dashboard-data">), mọi
        chart còn lại được vẽ sẵn thành SVG từ Python. Mở bằng trình duyệt là xem
        được, không cần chạy server. Không đọc file ngoài khi mở.
    - data/export/*.csv
        Xuất nguyên mart.funnel_by_channel, mart.fpd_by_segment, mart.vintage,
        mart.roll_rate để dựng lại dashboard bằng Power BI (xem dashboard/README.md).
        Thư mục data/export/ nằm trong .gitignore (kế thừa từ quy tắc "data/").

Chạy lại nhiều lần cho cùng kết quả: mọi con số lấy trực tiếp từ mart bằng truy
vấn xác định (deterministic), không sinh số ngẫu nhiên.

Trục rủi ro của trang 2 dùng ever 30+ tại MOB 12 (mart.vintage), KHÔNG dùng FPD30:
FPD30 đo được chỉ 0,011% vì vùng mù dữ liệu (xem docs/metric_dictionary.md mục M11
và ghi chú trên trang 2 của dashboard).
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

# Trang 3, biểu đồ 2 (kênh trong CÙNG một sản phẩm, xem VERIFIED_NUMBERS.md mục
# BỔ SUNG): lọc theo đúng 1 sản phẩm để tránh nhiễu do cơ cấu sản phẩm (phát
# hiện của người review). Vay tiêu dùng trả góp là sản phẩm có 3 kênh cùng bán
# đáng kể (Stone, Country-wide, Regional / Local); Credit and cash offices gần
# như không bán sản phẩm này (0%) nên không thể đưa vào đây.
VINTAGE_WITHIN_PRODUCT = "Consumer loans"
VINTAGE_CHART_CHANNELS = ["Stone", "Country-wide", "Regional / Local"]

# Thứ tự trạng thái chuẩn cho ma trận roll rate (trang 4), dùng để ghép lưới đầy đủ.
FROM_STATES = ["B0 Current", "B1 1-30", "B2 31-60", "B3 61-90", "B4 90+"]
TO_STATES = [
    "B0 Current", "B1 1-30", "B2 31-60", "B3 61-90", "B4 90+",
    "Closed", "Other", "Missing",
]
BUCKET_LABELS = {
    "B0 Current": "B0 · Hiện tại (0 ngày)",
    "B1 1-30": "B1 · Quá hạn 1-30 ngày",
    "B2 31-60": "B2 · Quá hạn 31-60 ngày",
    "B3 61-90": "B3 · Quá hạn 61-90 ngày",
    "B4 90+": "B4 · Quá hạn trên 90 ngày",
}

# Tên kênh rút gọn để đặt vừa nhãn trực tiếp trên bubble/điểm.
CHANNEL_SHORT = {
    "Stone": "Stone",
    "Country-wide": "Country-wide",
    "Contact center": "Contact center",
    "Regional / Local": "Regional/Local",
    "AP+ (Cash loan)": "AP+",
    "Credit and cash offices": "Credit&cash",
    "Khác": "Khác",
}

# Gán màu categorical (slot 0/1/2 của palette) theo TỪNG sản phẩm, dùng nhất
# quán giữa biểu đồ phân tán trang 2 và biểu đồ đường trang 3 để người đọc nối
# được màu với sản phẩm xuyên suốt dashboard.
PRODUCT_COLOR_SLOT = {"Consumer loans": 0, "Cash loans": 1, "Revolving loans": 2}

TO_STATE_LABELS = {
    "B0 Current": "B0", "B1 1-30": "B1", "B2 31-60": "B2", "B3 61-90": "B3",
    "B4 90+": "B4", "Closed": "Đã tất toán", "Other": "Khác", "Missing": "Thiếu dữ liệu",
}


# ---------------------------------------------------------------------------
# Bảng màu (theo skill dataviz). Đã validate bằng
# dataviz/scripts/validate_palette.js trước khi dùng (xem báo cáo cuối).
#   - 3 màu categorical (kênh ở trang 3): 3 slot đầu của bảng màu mặc định, đã
#     được palette.md xác nhận là pass cả hai chế độ ở mode all-pairs.
#   - Ordinal 5 bước (bucket B0..B4 ở trang 1 và 4): riêng bộ màu dark KHÔNG
#     dùng lại bộ light vì bước tối nhất (#104281) không đủ tương phản trên nền
#     tối (1.76:1 < 2:1) -> phải chọn riêng một dải 5 bước khác cho dark
#     (200..600) đã validate riêng, xem báo cáo cuối.
#   - Sequential liên tục (heatmap trang 4): nội suy tuyến tính giữa các bước có
#     sẵn trong palette.md, riêng dark dùng lại đúng 5 bước đã validate ordinal.
# ---------------------------------------------------------------------------

SEQ_STEPS_LIGHT = [
    (100, "#cde2fb"), (150, "#b7d3f6"), (200, "#9ec5f4"), (250, "#86b6ef"),
    (300, "#6da7ec"), (350, "#5598e7"), (400, "#3987e5"), (450, "#2a78d6"),
    (500, "#256abf"), (550, "#1c5cab"), (600, "#184f95"), (650, "#104281"),
    (700, "#0d366b"),
]
SEQ_ANCHORS_LIGHT = [((s - 100) / 600, h) for s, h in SEQ_STEPS_LIGHT]

SEQ_STEPS_DARK = [
    (200, "#9ec5f4"), (300, "#6da7ec"), (400, "#3987e5"), (500, "#256abf"),
    (600, "#184f95"),
]
SEQ_ANCHORS_DARK = [((s - 200) / 400, h) for s, h in SEQ_STEPS_DARK]

PALETTES = {
    "light": dict(
        mode="light",
        surface="#fcfcfb", page="#f9f9f7",
        text_primary="#0b0b0b", text_secondary="#52514e", text_muted="#898781",
        gridline="#e1e0d9", baseline="#c3c2b7", border="rgba(11,11,11,0.10)",
        series=["#2a78d6", "#eb6834", "#1baf7a"],
        ordinal=["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"],
        seq_anchors=SEQ_ANCHORS_LIGHT,
        warn="#eda100", warn_soft="#fdf1dc",
    ),
    "dark": dict(
        mode="dark",
        surface="#1a1a19", page="#0d0d0d",
        text_primary="#ffffff", text_secondary="#c3c2b7", text_muted="#898781",
        gridline="#2c2c2a", baseline="#383835", border="rgba(255,255,255,0.10)",
        series=["#3987e5", "#d95926", "#199e70"],
        ordinal=["#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95"],
        seq_anchors=SEQ_ANCHORS_DARK,
        warn="#c98500", warn_soft="#2a2210",
    ),
}


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c))) for c in rgb)


def interp_color(anchors, t):
    """Nội suy tuyến tính màu theo t trong [0,1] qua danh sách anchor (pos, hex)."""
    t = max(0.0, min(1.0, t))
    if t <= anchors[0][0]:
        return anchors[0][1]
    if t >= anchors[-1][0]:
        return anchors[-1][1]
    for (p0, c0), (p1, c1) in zip(anchors, anchors[1:]):
        if p0 <= t <= p1:
            local_t = (t - p0) / (p1 - p0) if p1 > p0 else 0
            rgb0, rgb1 = hex_to_rgb(c0), hex_to_rgb(c1)
            rgb = tuple(rgb0[i] + (rgb1[i] - rgb0[i]) * local_t for i in range(3))
            return rgb_to_hex(rgb)
    return anchors[-1][1]


def ink_for_fill(hexcolor, palette):
    """Chọn chữ trắng hay chữ tối trên một ô màu, theo độ sáng của fill."""
    r, g, b = hex_to_rgb(hexcolor)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#ffffff" if luminance < 0.55 else "#0b0b0b"


# ---------------------------------------------------------------------------
# Tiện ích định dạng số kiểu Việt Nam: chấm ngăn nghìn, phẩy thập phân.
# ---------------------------------------------------------------------------

def esc(value):
    return html.escape(str(value), quote=True)


def fmt_int(n):
    if n is None:
        return "n/a"
    return f"{n:,}".replace(",", ".")


def fmt_pct(x, decimals=3):
    if x is None:
        return "n/a"
    s = f"{x * 100:.{decimals}f}"
    return s.replace(".", ",") + "%"


def fmt_ratio(x, decimals=2):
    if x is None:
        return "n/a"
    s = f"{x:.{decimals}f}"
    return s.replace(".", ",")


def fmt_billion(raw):
    """Đổi đơn vị thô (Kaggle, không phải VND) sang 'tỷ đơn vị', 2 chữ số thập phân."""
    if raw is None:
        return "n/a"
    return fmt_ratio(raw / 1e9, 2)


# ---------------------------------------------------------------------------
# Tiện ích đọc dữ liệu
# ---------------------------------------------------------------------------

def rows(con, sql):
    """Chạy 1 câu SQL, trả về list[dict] (tên cột lấy từ relation.columns)."""
    rel = con.sql(sql)
    cols = rel.columns
    return [dict(zip(cols, r)) for r in rel.fetchall()]


def one(con, sql):
    r = rows(con, sql)
    return r[0] if r else {}


# ---------------------------------------------------------------------------
# Các câu SQL dùng cho dashboard. Comment tiếng Việt theo quy ước sql/ hiện có.
# ---------------------------------------------------------------------------

SQL_FOOTER_BASE = """
-- Nền chung của danh mục, dùng ở chân trang để nêu quy mô dữ liệu.
select
    (select count(*) from core.dim_loan)          as n_loans_total,
    (select count(*) from core.fct_loan_month)     as n_loan_months
"""

SQL_PAGE1_BUCKETS = """
-- Trang 1: cơ cấu nhóm quá hạn (M02 DPD bucket) của hợp đồng đang mở, tại tháng
-- gần nhất trong dữ liệu (months_balance = -1, KHÔNG phải tháng lịch).
-- Nguồn: core.fct_loan_month. Mã chỉ tiêu: M02, M06 (tỷ lệ 30+ coincident).
select
    dpd_bucket,
    dpd_bucket_order,
    count(*)             as n_loans,
    sum(exposure_proxy)  as exposure
from core.fct_loan_month
where is_open and months_balance = -1
group by dpd_bucket, dpd_bucket_order
order by dpd_bucket_order
"""

SQL_PAGE1_SUMMARY = """
-- Trang 1: KPI tổng hợp tại tháng gần nhất. "30+" là DPD lớn hơn 30 (từ B2 trở
-- lên, theo quy ước M02 trong docs/metric_dictionary.md).
select
    count(*)                                                        as n_open,
    count(*) filter (where dpd_bucket_order >= 2)                   as n_30plus,
    count(*) filter (where dpd_bucket_order >= 2) * 1.0 / count(*)  as rate_30plus_count,
    sum(exposure_proxy)                                             as exposure_total,
    sum(exposure_proxy) filter (where dpd_bucket_order >= 2)        as exposure_30plus,
    sum(exposure_proxy) filter (where dpd_bucket_order >= 2)
        / sum(exposure_proxy)                                       as rate_30plus_exposure
from core.fct_loan_month
where is_open and months_balance = -1
"""

# ---------------------------------------------------------------------------
# Trang 2 (BẢN SỬA SAU KHI REVIEW PHÁT HIỆN NHIỄU DO CƠ CẤU SẢN PHẨM):
# so sánh rủi ro giữa các kênh gộp mọi sản phẩm bị NHIỄU (confounding, yếu tố
# gây nhiễu) vì các kênh bán tỷ trọng sản phẩm rất khác nhau, và bản thân từng
# sản phẩm đã có mức rủi ro rất khác nhau (xem SQL_PAGE2_PRODUCT_AVG_RISK bên
# dưới). Vì vậy MỌI truy vấn so sánh kênh ở trang 2 đều group theo cả
# channel_type LẪN contract_type (sản phẩm: 'Consumer loans' = vay tiêu dùng
# trả góp, 'Cash loans' = vay tiền mặt, 'Revolving loans' = thẻ quay vòng),
# không còn truy vấn nào gộp tất cả sản phẩm làm một điểm / kênh nữa.
# ---------------------------------------------------------------------------

PRODUCTS = ["Consumer loans", "Cash loans", "Revolving loans"]
PRODUCT_LABEL_VN = {
    "Consumer loans": "Vay tiêu dùng trả góp",
    "Cash loans": "Vay tiền mặt",
    "Revolving loans": "Thẻ quay vòng",
}

SQL_PAGE2_CHANNEL_PRODUCT_RISK = """
-- Trang 2: rủi ro (ever 30+ tại MOB 12, M08) theo từng cặp kênh x sản phẩm.
-- Đây là trục dọc của 3 khung nhỏ (small multiples) trang 2, mỗi khung 1 sản phẩm.
-- Loại kênh '(không rõ)' và sản phẩm '(không rõ)': không có dữ liệu approval
-- rate tương ứng trong mart.funnel_by_channel để ghép cặp.
select
    channel_type,
    contract_type,
    sum(n_loans)                              as n_mob12,
    sum(n_ever_30_plus)                       as n_ever30,
    sum(n_ever_30_plus) * 1.0 / sum(n_loans)  as risk_rate
from mart.vintage
where mob = 12
  and channel_type <> '(không rõ)'
  and contract_type <> '(không rõ)'
group by channel_type, contract_type
"""

SQL_PAGE2_CHANNEL_PRODUCT_APPROVAL = """
-- Trang 2: approval rate (M12) theo từng cặp kênh x sản phẩm. Trục ngang của 3
-- khung nhỏ trang 2. Ghép với SQL_PAGE2_CHANNEL_PRODUCT_RISK theo (channel_type,
-- contract_type) ở tầng Python.
select
    channel_type,
    contract_type,
    sum(n_decided)                                          as n_decided,
    sum(n_approved + n_unused_offer)                        as n_offered,
    sum(n_approved + n_unused_offer) * 1.0 / sum(n_decided) as approval_rate
from mart.funnel_by_channel
where contract_type <> 'Unknown'
group by channel_type, contract_type
"""

SQL_PAGE2_PRODUCT_AVG_RISK = """
-- Trang 2: rủi ro trung bình CỦA TỪNG SẢN PHẨM, gộp mọi kênh. Dùng làm đường
-- tham chiếu trong từng khung nhỏ (thay vì trung bình toàn danh mục gộp sản
-- phẩm, vốn chính là nguồn gây nhiễu mà review đã chỉ ra).
select
    contract_type,
    sum(n_loans)                              as n_mob12,
    sum(n_ever_30_plus)                       as n_ever30,
    sum(n_ever_30_plus) * 1.0 / sum(n_loans)  as risk_rate
from mart.vintage
where mob = 12 and contract_type <> '(không rõ)'
group by contract_type
order by contract_type
"""

SQL_PAGE2_PRODUCT_AVG_APPROVAL = """
-- Trang 2: approval rate trung bình CỦA TỪNG SẢN PHẨM, gộp mọi kênh.
select
    contract_type,
    sum(n_decided)                                          as n_decided,
    sum(n_approved + n_unused_offer) * 1.0 / sum(n_decided) as approval_rate
from mart.funnel_by_channel
where contract_type <> 'Unknown'
group by contract_type
order by contract_type
"""

SQL_PAGE2_FPD_NOTE = """
-- Trang 2 (ở ghi chú nhỏ): FPD30 (first payment default 30, kỳ trả đầu tiên
-- chưa trả đủ sau 30 ngày kể từ ngày đến hạn) toàn danh mục. CHỈ để minh họa
-- giới hạn dữ liệu, KHÔNG dùng để xếp hạng kênh (docs/metric_dictionary.md M11).
-- Mẫu số của tỷ lệ "vùng mù" (n_approved_no_installment) là TỔNG HỒ SƠ APPROVED
-- toàn danh mục (không phải n_loans, vì n_loans đã bị lọc theo days_due <= -30 -
-- một điều kiện khác). Dùng đúng filter dedup (is_last_appl_per_contract,
-- is_last_appl_in_day) giống hệt các mart khác để ra đúng 7,52% như comment
-- trong sql/mart/mart_fpd_by_segment.sql.
select
    (select sum(n_loans) from mart.fpd_by_segment)                    as n_loans,
    (select sum(n_fpd30) from mart.fpd_by_segment)                    as n_fpd30,
    (select sum(n_fpd30) * 1.0 / sum(n_loans) from mart.fpd_by_segment) as fpd30_rate,
    (select sum(n_approved_no_installment) from mart.fpd_by_segment)  as n_approved_no_installment,
    (select count(*) from stg.previous_application
     where application_status = 'Approved'
       and is_last_appl_per_contract and is_last_appl_in_day)         as n_approved_total
"""

# ---------------------------------------------------------------------------
# Trang 3 (BẢN SỬA SAU KHI REVIEW): biểu đồ đường CHÍNH giờ là so sánh theo SẢN
# PHẨM (khác biệt lớn nhất trong dữ liệu, không bị nhiễu vì đây đúng là trục
# phân nhóm). Biểu đồ đường THỨ HAI vẫn trả lời "kênh nào xấu đi nhanh hơn" nhưng
# CHỈ trong MỘT sản phẩm (vay tiêu dùng trả góp, nơi cả 3 kênh Stone /
# Country-wide / Regional-Local đều bán đáng kể, xem BỔ SUNG trong
# VERIFIED_NUMBERS.md), để không còn gộp lẫn sản phẩm như bản cũ.
# ---------------------------------------------------------------------------

SQL_PAGE3_VINTAGE_BY_PRODUCT = """
-- Trang 3, biểu đồ 1 (chính): đường cong vintage ever 30+@MOBn (M08) theo SẢN
-- PHẨM, gộp mọi kênh, MOB 0 đến 24. Đây là trục phân nhóm không bị nhiễu bởi
-- cơ cấu kênh, vì mọi điểm trên 1 đường đều cùng một sản phẩm.
select
    contract_type,
    mob,
    sum(n_loans)                              as n_loans,
    sum(n_observed_full)                      as n_observed_full,
    sum(n_ever_30_plus)                       as n_ever30,
    sum(n_ever_30_plus) * 1.0 / sum(n_loans)  as rate
from mart.vintage
where mob between 0 and 24
  and contract_type in ({products})
group by contract_type, mob
order by contract_type, mob
"""

SQL_PAGE3_VINTAGE_PORTFOLIO = """
-- Trang 3: đường trung bình toàn danh mục (không tách kênh, không tách sản
-- phẩm) để làm đường tham chiếu trên biểu đồ 1.
select
    mob,
    sum(n_loans)                              as n_loans,
    sum(n_observed_full)                      as n_observed_full,
    sum(n_ever_30_plus)                       as n_ever30,
    sum(n_ever_30_plus) * 1.0 / sum(n_loans)  as rate
from mart.vintage
where mob between 0 and 24
group by mob
order by mob
"""

SQL_PAGE3_VINTAGE_CHANNEL_IN_PRODUCT = """
-- Trang 3, biểu đồ 2: đường cong vintage theo KÊNH nhưng CHỈ trong MỘT sản phẩm
-- (mặc định: vay tiêu dùng trả góp, xem biến VINTAGE_WITHIN_PRODUCT) để tránh
-- nhiễu vừa bị review chỉ ra ở biểu đồ kênh gộp sản phẩm cũ. Chỉ lấy các
-- kênh có khối lượng đáng kể trong đúng sản phẩm này.
select
    channel_type,
    mob,
    sum(n_loans)                              as n_loans,
    sum(n_observed_full)                      as n_observed_full,
    sum(n_ever_30_plus)                       as n_ever30,
    sum(n_ever_30_plus) * 1.0 / sum(n_loans)  as rate
from mart.vintage
where mob between 0 and 24
  and contract_type = '{product}'
  and channel_type in ({channels})
group by channel_type, mob
order by channel_type, mob
"""

SQL_PAGE4_ROLLRATE = """
-- Trang 4: ma trận roll rate toàn danh mục (M09), gộp qua source / contract_type
-- / channel_type. Kết quả sẽ được ghép với lưới trạng thái đầy đủ trong Python vì
-- mart.roll_rate không có dòng cho ô không có quan sát nào (ví dụ B1 sang B4).
select
    from_state,
    from_order,
    to_state,
    to_order,
    sum(n_loans) as n_loans
from mart.roll_rate
group by from_state, from_order, to_state, to_order
"""

SQL_PAGE4_CURE = """
-- Trang 4: cure rate theo bucket xuất phát (M10), lấy trực tiếp từ mart.roll_rate,
-- KHÔNG làm mart riêng (dùng định nghĩa trong docs/metric_dictionary.md).
select
    from_state,
    from_order,
    sum(n_loans)                                            as n_from,
    sum(n_loans) filter (where to_state = 'B0 Current')     as n_cured,
    sum(n_loans) filter (where to_state = 'Closed')          as n_closed
from mart.roll_rate
where from_state <> 'B0 Current'
group by from_state, from_order
order by from_order
"""


def join_channel_product(risk_rows, approval_rows):
    """Ghép 2 bảng (channel_type, contract_type) -> 1 dict lồng nhau:
    {contract_type: [{channel_type, n_mob12, n_ever30, risk_rate, n_decided,
    approval_rate}, ...]}. Inner join: chỉ giữ cặp tồn tại ở CẢ HAI mart (tự
    nhiên loại các cặp quá nhỏ không có sản phẩm đó ở mart kia, xem SQL ở trên).
    """
    approval_by_key = {(r["channel_type"], r["contract_type"]): r for r in approval_rows}
    out = {p: [] for p in PRODUCTS}
    for r in risk_rows:
        key = (r["channel_type"], r["contract_type"])
        a = approval_by_key.get(key)
        if a is None or r["contract_type"] not in out:
            continue
        out[r["contract_type"]].append({
            "channel_type": r["channel_type"],
            "n_mob12": r["n_mob12"],
            "n_ever30": r["n_ever30"],
            "risk_rate": r["risk_rate"],
            "n_decided": a["n_decided"],
            "approval_rate": a["approval_rate"],
        })
    for p in out:
        out[p].sort(key=lambda x: -x["risk_rate"])
    return out


def fetch_data(con):
    """Đọc toàn bộ dữ liệu cần cho 4 trang dashboard từ warehouse (chỉ đọc)."""
    products_sql = ", ".join(f"'{p}'" for p in PRODUCTS)
    channels_sql = ", ".join(f"'{c}'" for c in VINTAGE_CHART_CHANNELS)

    channel_product_risk = rows(con, SQL_PAGE2_CHANNEL_PRODUCT_RISK)
    channel_product_approval = rows(con, SQL_PAGE2_CHANNEL_PRODUCT_APPROVAL)

    data = {
        "footer_base": one(con, SQL_FOOTER_BASE),
        "page1_buckets": rows(con, SQL_PAGE1_BUCKETS),
        "page1_summary": one(con, SQL_PAGE1_SUMMARY),

        # Trang 2: dữ liệu đã tách theo sản phẩm (channel x contract_type).
        "page2_by_product": join_channel_product(channel_product_risk, channel_product_approval),
        "page2_product_avg_risk": {
            r["contract_type"]: r for r in rows(con, SQL_PAGE2_PRODUCT_AVG_RISK)
        },
        "page2_product_avg_approval": {
            r["contract_type"]: r for r in rows(con, SQL_PAGE2_PRODUCT_AVG_APPROVAL)
        },
        "page2_fpd_note": one(con, SQL_PAGE2_FPD_NOTE),
        "page2_approval_portfolio": one(con, """
            select sum(n_decided) as n_decided,
                   sum(n_approved + n_unused_offer) * 1.0 / sum(n_decided) as approval_rate
            from mart.funnel_by_channel
        """),

        # Trang 3: biểu đồ 1 theo sản phẩm, biểu đồ 2 theo kênh TRONG 1 sản phẩm.
        "page3_vintage_by_product": rows(
            con, SQL_PAGE3_VINTAGE_BY_PRODUCT.format(products=products_sql)
        ),
        "page3_vintage_portfolio": rows(con, SQL_PAGE3_VINTAGE_PORTFOLIO),
        "page3_vintage_channel_in_product": rows(
            con,
            SQL_PAGE3_VINTAGE_CHANNEL_IN_PRODUCT.format(
                product=VINTAGE_WITHIN_PRODUCT, channels=channels_sql
            ),
        ),

        "page4_rollrate_raw": rows(con, SQL_PAGE4_ROLLRATE),
        "page4_cure": rows(con, SQL_PAGE4_CURE),
    }
    return data


def build_full_rollrate_grid(raw_rows):
    """Ghép kết quả SQL_PAGE4_ROLLRATE với lưới trạng thái đầy đủ (FROM_STATES x
    TO_STATES) để ô không có quan sát nào (ví dụ B1 sang B4) hiện số 0 thay vì
    bị khuyết, dùng theo yêu cầu trong hướng dẫn gói việc."""
    by_key = {(r["from_state"], r["to_state"]): r["n_loans"] for r in raw_rows}
    n_from_total = {}
    for fs in FROM_STATES:
        n_from_total[fs] = sum(by_key.get((fs, ts), 0) for ts in TO_STATES)

    grid = {}
    max_rate = 0.0
    for fs in FROM_STATES:
        total = n_from_total[fs]
        for ts in TO_STATES:
            n = by_key.get((fs, ts), 0)
            rate = (n / total) if total else 0.0
            grid[(fs, ts)] = {"from_state": fs, "to_state": ts, "n_loans": n, "rate": rate}
            max_rate = max(max_rate, rate)
    return grid, max_rate


def export_marts_to_csv(con):
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    for table in MART_TABLES_TO_EXPORT:
        file_name = table.replace(".", "_") + ".csv"
        out_path = EXPORT_DIR / file_name
        # COPY chỉ ghi file ngoài, không đụng gì vào warehouse.duckdb (vẫn đang
        # mở ở chế độ read_only).
        con.sql(f"copy (select * from {table}) to '{out_path.as_posix()}' (header, delimiter ',')")
        print(f"  export  {out_path.relative_to(ROOT)}")


# =============================================================================
# Vẽ biểu đồ: tiện ích hình học SVG dùng chung
# =============================================================================

def tip(*lines):
    """Chuỗi tooltip nhiều dòng (\\n), đã escape, dùng cho thuộc tính data-tip."""
    return esc("\n".join(str(line) for line in lines if line is not None))


def svg_open(w, h, desc, extra_class=""):
    cls = ("chart-svg " + extra_class).strip()
    return (
        f'<svg class="{cls}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{esc(desc)}" xmlns="http://www.w3.org/2000/svg">'
    )


def hbar(fill, x, y, w, h, r=4):
    """Thanh ngang: bo tròn đầu xa (data-end), vuông góc tại baseline x (theo
    quy ước marks-and-anatomy của skill dataviz)."""
    if w is None or w <= 0:
        return ""
    rr = min(r, h / 2, w)
    if w <= rr * 1.001:
        return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}" />'
    d = (
        f"M{x:.1f},{y:.1f} "
        f"H{x + w - rr:.1f} "
        f"A{rr:.1f},{rr:.1f} 0 0 1 {x + w:.1f},{y + rr:.1f} "
        f"V{y + h - rr:.1f} "
        f"A{rr:.1f},{rr:.1f} 0 0 1 {x + w - rr:.1f},{y + h:.1f} "
        f"H{x:.1f} Z"
    )
    return f'<path d="{d}" fill="{fill}" />'


def nice_step(rough):
    if rough <= 0:
        return 1.0
    exp = math.floor(math.log10(rough))
    base = rough / (10 ** exp)
    nice = 1 if base <= 1 else 2 if base <= 2 else 5 if base <= 5 else 10
    return nice * (10 ** exp)


def nice_ticks(max_val, count=4):
    """Danh sách tick 'đẹp', bắt đầu từ 0, phủ hết tối thiểu max_val."""
    if max_val is None or max_val <= 0:
        return [0]
    step = nice_step(max_val / count)
    ticks, v = [], 0.0
    while v <= max_val + step * 0.001:
        ticks.append(round(v, 10))
        v += step
    return ticks


def pct_ticks(lo, hi):
    """Tick 'đẹp' trong khoảng [lo, hi] (đơn vị %), không bắt buộc bắt đầu từ 0."""
    span = max(hi - lo, 0.001)
    step = 5
    for candidate in (2, 5, 10, 20, 25):
        if span / candidate <= 6:
            step = candidate
            break
    start = math.ceil(lo / step) * step
    ticks, v = [], start
    while v <= hi + 0.001:
        ticks.append(v)
        v += step
    return ticks


def stack_labels(items, min_gap=15):
    """Nhãn bám theo cạnh phải đường: nếu 2 nhãn quá gần nhau theo trục dọc,
    đẩy chúng ra xa nhau (trên đẩy lên, dưới đẩy xuống), giữ thứ tự tương đối.
    items: list các dict có khóa 'y' (sẽ được sửa tại chỗ), đã sắp xếp theo y."""
    items = sorted(items, key=lambda it: it["y"])
    for i in range(1, len(items)):
        min_y = items[i - 1]["y"] + min_gap
        if items[i]["y"] < min_y:
            items[i]["y"] = min_y
    return items


def dual(builder, *args, **kwargs):
    """Vẽ 1 biểu đồ 2 lần (mode sáng / tối) và bọc trong 2 div, chuyển đổi bằng
    CSS theo prefers-color-scheme hoặc data-theme (xem CSS_BLOCK). Làm vậy vì
    các màu nội suy liên tục (heatmap) và các bước ordinal riêng cho dark KHÔNG
    thể đổi động bằng CSS var đơn giản (xem ghi chú ở bảng PALETTES)."""
    light_svg = builder(*args, palette=PALETTES["light"], **kwargs)
    dark_svg = builder(*args, palette=PALETTES["dark"], **kwargs)
    return f'<div class="viz-light">{light_svg}</div><div class="viz-dark">{dark_svg}</div>'


# =============================================================================
# Biểu đồ trang 1: cơ cấu nhóm quá hạn (thanh ngang, màu ordinal)
# =============================================================================

def build_bucket_chart(buckets, n_open, palette):
    W, H = 760, 300
    pad, label_w, right_reserve = 16, 176, 176
    row_h, gap = 40, 14
    track_x = pad + label_w
    track_w = W - track_x - right_reserve
    max_n = max(b["n_loans"] for b in buckets) or 1

    parts = [svg_open(W, H, "Cơ cấu nhóm quá hạn của hợp đồng đang mở")]
    for i, b in enumerate(buckets):
        y = pad + i * (row_h + gap)
        bar_h = row_h - 12
        bar_y = y + (row_h - bar_h) / 2
        w = track_w * (b["n_loans"] / max_n)
        color = palette["ordinal"][min(i, len(palette["ordinal"]) - 1)]
        share = b["n_loans"] / n_open if n_open else 0
        label = BUCKET_LABELS.get(b["dpd_bucket"], b["dpd_bucket"])
        value_txt = f"{fmt_int(b['n_loans'])} · {fmt_pct(share, 3)}"
        row_tip = tip(
            label,
            f"Số hợp đồng: {fmt_int(b['n_loans'])} ({fmt_pct(share, 3)} trên {fmt_int(n_open)} hợp đồng đang mở)",
            f"Dư nợ ước tính: {fmt_billion(b['exposure'])} tỷ đơn vị (không phải VND)",
        )
        parts.append(
            f'<rect class="hit" x="{pad}" y="{y}" width="{W - pad * 2}" height="{row_h}" '
            f'fill="transparent" tabindex="0" data-tip="{row_tip}" />'
        )
        parts.append(
            f'<text x="{pad}" y="{y + row_h / 2:.1f}" class="row-label" '
            f'dominant-baseline="middle">{esc(label)}</text>'
        )
        parts.append(hbar(color, track_x, bar_y, w, bar_h))
        parts.append(
            f'<text x="{track_x + w + 10:.1f}" y="{y + row_h / 2:.1f}" class="row-value" '
            f'dominant-baseline="middle">{esc(value_txt)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


# =============================================================================
# Biểu đồ trang 2: phân tán approval rate x ever30@MOB12, 1 khung / sản phẩm
# =============================================================================

def build_scatter_panel(product, product_rows, avg_risk, avg_approval,
                         x_lo, x_hi, y_max, n_max, palette):
    W, H = 300, 300
    left, right, top, bottom = 50, 16, 20, 34
    plot_w, plot_h = W - left - right, H - top - bottom
    color = palette["series"][PRODUCT_COLOR_SLOT[product]]
    surface = palette["surface"]

    def sx(approval_rate):
        pct = approval_rate * 100
        return left + (pct - x_lo) / (x_hi - x_lo) * plot_w

    def sy(rate):
        return top + plot_h - (rate / y_max) * plot_h if y_max else top + plot_h

    def r_of(n):
        r_min, r_max = 7, 26
        return r_min + math.sqrt(max(n, 0) / n_max) * (r_max - r_min) if n_max else r_min

    parts = [svg_open(W, H, f"Phân tán tỷ lệ duyệt và rủi ro, sản phẩm {PRODUCT_LABEL_VN.get(product, product)}")]

    # Gridline ngang (tick % rủi ro), theo quy ước: hairline màu, một bước lệch surface.
    for gy in nice_ticks(y_max, 4):
        yy = sy(gy)
        parts.append(
            f'<line x1="{left}" y1="{yy:.1f}" x2="{W - right}" y2="{yy:.1f}" class="gridline" />'
        )
        parts.append(
            f'<text x="{left - 6}" y="{yy:.1f}" class="axis-label" text-anchor="end" '
            f'dominant-baseline="middle">{fmt_pct(gy, 2)}</text>'
        )
    for gx in pct_ticks(x_lo, x_hi):
        xx = sx(gx / 100)
        parts.append(
            f'<text x="{xx:.1f}" y="{H - bottom + 16}" class="axis-label" text-anchor="middle">{gx:.0f}%</text>'
        )
    parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{H - bottom}" class="axis-line" />')
    parts.append(f'<line x1="{left}" y1="{H - bottom}" x2="{W - right}" y2="{H - bottom}" class="axis-line" />')

    # Đường tham chiếu: trung bình CỦA CHÍNH SẢN PHẨM NÀY (không phải toàn danh
    # mục gộp sản phẩm, để tránh dùng lại chính nguồn nhiễu mà review chỉ ra).
    if avg_risk and avg_approval:
        ry = sy(avg_risk["risk_rate"])
        rx = sx(avg_approval["approval_rate"])
        parts.append(
            f'<line x1="{left}" y1="{ry:.1f}" x2="{W - right}" y2="{ry:.1f}" class="refline" />'
        )
        parts.append(
            f'<line x1="{rx:.1f}" y1="{top}" x2="{rx:.1f}" y2="{H - bottom}" class="refline" />'
        )
        parts.append(
            f'<text x="{W - right - 2}" y="{ry - 4:.1f}" class="ref-label" text-anchor="end">'
            f"TB sản phẩm {fmt_pct(avg_risk['risk_rate'], 3)}</text>"
        )

    pts = []
    for r in product_rows:
        cx, cy = sx(r["approval_rate"]), sy(min(r["risk_rate"], y_max))
        rad = r_of(r["n_mob12"])
        pts.append({"r": r, "cx": cx, "cy": cy, "rad": rad, "y": cy - rad - 8})
    pts = stack_labels(pts, min_gap=13)

    for p in pts:
        r, cx, cy, rad = p["r"], p["cx"], p["cy"], p["rad"]
        small = r["n_mob12"] < 1000
        ratio = r["risk_rate"] / avg_risk["risk_rate"] if avg_risk and avg_risk["risk_rate"] else None
        point_tip = tip(
            f"{CHANNEL_SHORT.get(r['channel_type'], r['channel_type'])} · {PRODUCT_LABEL_VN.get(product, product)}",
            f"Tỷ lệ duyệt: {fmt_pct(r['approval_rate'], 1)} trên {fmt_int(r['n_decided'])} hồ sơ đã quyết định",
            f"Ever 30+@MOB12: {fmt_pct(r['risk_rate'], 3)} ({fmt_int(r['n_ever30'])} trên {fmt_int(r['n_mob12'])} hợp đồng)",
            f"So với TB sản phẩm này: {fmt_ratio(ratio, 2)} lần" if ratio else None,
            "* mẫu số dưới 1.000 hợp đồng, thận trọng khi diễn giải" if small else None,
        )
        ring_extra = ' stroke-dasharray="3 2"' if small else ""
        parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{rad + 2:.1f}" fill="{surface}" />'
        )
        parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{rad:.1f}" fill="{color}" fill-opacity="0.78" '
            f'stroke="{color}" stroke-width="1.5"{ring_extra} />'
        )
        parts.append(
            f'<circle class="hit" cx="{cx:.1f}" cy="{cy:.1f}" r="{max(rad + 10, 22):.1f}" '
            f'fill="transparent" tabindex="0" data-tip="{point_tip}" />'
        )
        short = CHANNEL_SHORT.get(r["channel_type"], r["channel_type"])
        parts.append(
            f'<text x="{cx:.1f}" y="{p["y"]:.1f}" class="point-label" text-anchor="middle">{esc(short)}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


def build_scatter_legend_svg(n_max, palette):
    """Chú thích kích thước bubble (r ~ số hợp đồng mẫu số MOB12), dùng chung
    cho cả 3 khung nhỏ."""
    W, H = 300, 74
    surface = palette["surface"]
    ink = palette["text_secondary"]
    steps = [max(1, round(n_max * f)) for f in (0.15, 0.5, 1.0)]
    parts = [svg_open(W, H, "Chú thích kích thước điểm theo số hợp đồng")]
    x = 40
    for n in steps:
        r = 7 + math.sqrt(n / n_max) * (26 - 7) if n_max else 7
        cy = H - 10 - r
        parts.append(f'<circle cx="{x}" cy="{cy:.1f}" r="{r:.1f}" fill="none" stroke="{ink}" stroke-width="1.3" />')
        parts.append(
            f'<text x="{x:.1f}" y="{H - 2}" class="axis-label" text-anchor="middle">{fmt_int(n)}</text>'
        )
        x += 90
    parts.append(f'<text x="0" y="12" class="axis-label">Kích thước điểm = số hợp đồng (mẫu số MOB 12)</text>')
    parts.append("</svg>")
    return "".join(parts)


# =============================================================================
# Biểu đồ trang 3: đường vintage (dùng chung cho cả 2 biểu đồ của trang 3)
# =============================================================================

def build_line_chart(series, ref_series, ref_label, palette, x_max=24):
    """series: list các dict {name, color, rows:[{mob,rate,n_loans,n_observed_full}]}.
    ref_series: list rows cùng dạng (hoặc None) vẽ thêm 1 đường tham chiếu màu
    trung tính (không tính vào bảng màu categorical)."""
    W, H = 780, 380
    left, right, top, bottom = 56, 132, 20, 40
    plot_w, plot_h = W - left - right, H - top - bottom
    marker_mobs = [m for m in (0, 3, 6, 9, 12, 15, 18, 21, 24) if m <= x_max]

    all_rates = [pt["rate"] for s in series for pt in s["rows"]]
    if ref_series:
        all_rates += [pt["rate"] for pt in ref_series]
    y_max = (max(all_rates) if all_rates else 0.01) * 1.18

    def sx(mob):
        return left + (mob / x_max) * plot_w

    def sy(rate):
        return top + plot_h - (min(rate, y_max) / y_max) * plot_h if y_max else top + plot_h

    parts = [svg_open(W, H, "Đường cong vintage ever 30 cộng theo tuổi hợp đồng (MOB)")]

    for gy in nice_ticks(y_max, 5):
        yy = sy(gy)
        parts.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{W - right}" y2="{yy:.1f}" class="gridline" />')
        parts.append(
            f'<text x="{left - 8}" y="{yy:.1f}" class="axis-label" text-anchor="end" '
            f'dominant-baseline="middle">{fmt_pct(gy, 2)}</text>'
        )
    for gx in (0, 3, 6, 9, 12, 15, 18, 21, 24):
        if gx > x_max:
            continue
        xx = sx(gx)
        parts.append(f'<text x="{xx:.1f}" y="{H - bottom + 18}" class="axis-label" text-anchor="middle">{gx}</text>')
    parts.append(
        f'<text x="{left + plot_w / 2:.1f}" y="{H - 6}" class="axis-title" text-anchor="middle">'
        "MOB (month on book, số tháng kể từ tháng hợp đồng mở)</text>"
    )
    parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{H - bottom}" class="axis-line" />')
    parts.append(f'<line x1="{left}" y1="{H - bottom}" x2="{W - right}" y2="{H - bottom}" class="axis-line" />')

    # Đường tham chiếu màu trung tính (không dùng màu categorical).
    end_labels = []
    if ref_series:
        pts_str = " ".join(f"{sx(p['mob']):.1f},{sy(p['rate']):.1f}" for p in ref_series)
        parts.append(f'<polyline points="{pts_str}" class="ref-line" fill="none" />')
        last = ref_series[-1]
        end_labels.append({"y": sy(last["rate"]), "text": ref_label, "muted": True})

    # Các dải hover dọc (1 dải / mob có dữ liệu) để gộp tooltip nhiều đường 1 lúc.
    mob_set = sorted({pt["mob"] for s in series for pt in s["rows"]})
    for idx, mob in enumerate(mob_set):
        x0 = sx(mob) - (plot_w / max(len(mob_set) - 1, 1)) / 2
        band_w = plot_w / max(len(mob_set) - 1, 1)
        lines = [f"MOB {mob}"]
        for s in series:
            match = next((p for p in s["rows"] if p["mob"] == mob), None)
            if match:
                lines.append(
                    f"{s['name']}: {fmt_pct(match['rate'], 3)} "
                    f"({fmt_int(match['n_ever30'] if 'n_ever30' in match else 0)}/{fmt_int(match['n_loans'])} hợp đồng, "
                    f"quan sát đủ {fmt_int(match['n_observed_full'])})"
                )
        if ref_series:
            match = next((p for p in ref_series if p["mob"] == mob), None)
            if match:
                lines.append(f"{ref_label}: {fmt_pct(match['rate'], 3)} ({fmt_int(match['n_loans'])} hợp đồng)")
        parts.append(
            f'<rect class="hit hit-band" data-cx="{sx(mob):.1f}" x="{max(x0, left):.1f}" y="{top}" '
            f'width="{band_w:.1f}" height="{plot_h}" fill="transparent" tabindex="0" data-tip="{tip(*lines)}" />'
        )

    for s in series:
        pts_str = " ".join(f"{sx(p['mob']):.1f},{sy(p['rate']):.1f}" for p in s["rows"])
        parts.append(f'<polyline points="{pts_str}" fill="none" stroke="{s["color"]}" stroke-width="2" '
                     f'stroke-linejoin="round" stroke-linecap="round" />')
        for m in marker_mobs:
            match = next((p for p in s["rows"] if p["mob"] == m), None)
            if match:
                cx, cy = sx(m), sy(match["rate"])
                parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5.5" fill="{palette["surface"]}" />')
                parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.5" fill="{s["color"]}" />')
        last = s["rows"][-1]
        end_labels.append({"y": sy(last["rate"]), "text": s["name"], "color": s["color"]})

    end_labels = stack_labels(end_labels, min_gap=16)
    for lab in end_labels:
        cls = "line-end-label muted" if lab.get("muted") else "line-end-label"
        dot = "" if lab.get("muted") else f'<circle cx="{W - right + 6}" cy="{lab["y"]:.1f}" r="3.5" fill="{lab["color"]}" />'
        parts.append(dot)
        parts.append(
            f'<text x="{W - right + 14}" y="{lab["y"]:.1f}" class="{cls}" dominant-baseline="middle">{esc(lab["text"])}</text>'
        )

    parts.append('<line class="crosshair" x1="0" y1="0" x2="0" y2="0" />'.replace(
        'x1="0" y1="0" x2="0" y2="0"', f'x1="{left}" y1="{top}" x2="{left}" y2="{H - bottom}"'
    ))
    parts.append("</svg>")
    return "".join(parts)


# =============================================================================
# Biểu đồ trang 4: ma trận roll rate (heatmap) và cure rate
# =============================================================================

def build_heatmap(grid, max_rate, palette):
    W = 90 + 8 * 80 + 90
    row_h, col_w = 54, 80
    left, top = 90, 44
    H = top + 5 * row_h + 16

    parts = [svg_open(W, H, "Ma trận roll rate: hợp đồng chuyển từ trạng thái nào sang trạng thái nào ở tháng kế tiếp")]

    for j, to_state in enumerate(TO_STATES):
        x = left + j * col_w
        parts.append(
            f'<text x="{x + col_w / 2:.1f}" y="{top - 12}" class="axis-label" text-anchor="middle">'
            f"{esc(TO_STATE_LABELS[to_state])}</text>"
        )
    parts.append(f'<text x="{left + 4 * col_w:.1f}" y="{top - 28}" class="axis-title" text-anchor="middle">Sang trạng thái tháng kế tiếp (t+1)</text>')

    for i, from_state in enumerate(FROM_STATES):
        y = top + i * row_h
        thin = from_state in ("B2 31-60", "B3 61-90")
        row_label = TO_STATE_LABELS[from_state] + (" *" if thin else "")
        parts.append(
            f'<text x="{left - 10}" y="{y + row_h / 2:.1f}" class="row-label" text-anchor="end" '
            f'dominant-baseline="middle">{esc(row_label)}</text>'
        )
        n_from_total = sum(c["n_loans"] for c in grid.values() if c["from_state"] == from_state)
        for j, to_state in enumerate(TO_STATES):
            x = left + j * col_w
            cell = grid[(from_state, to_state)]
            t = (cell["rate"] / max_rate) if max_rate else 0
            fill = interp_color(palette["seq_anchors"], t)
            ink = ink_for_fill(fill, palette)
            cell_tip = tip(
                f"{TO_STATE_LABELS[from_state]} → {TO_STATE_LABELS[to_state]}",
                f"Tỷ lệ: {fmt_pct(cell['rate'], 3)}",
                f"Số dòng hợp đồng-tháng: {fmt_int(cell['n_loans'])} trên {fmt_int(n_from_total)} (mẫu số hàng {TO_STATE_LABELS[from_state]})",
                "Ô này không có hợp đồng nào quan sát được; hiện số 0 để khớp lưới trạng thái đầy đủ."
                if cell["n_loans"] == 0 else None,
            )
            parts.append(f'<rect x="{x + 2}" y="{y + 2}" width="{col_w - 4}" height="{row_h - 4}" rx="4" fill="{fill}" />')
            parts.append(
                f'<rect class="hit" x="{x + 2}" y="{y + 2}" width="{col_w - 4}" height="{row_h - 4}" rx="4" '
                f'fill="transparent" tabindex="0" data-tip="{cell_tip}" />'
            )
            parts.append(
                f'<text x="{x + col_w / 2:.1f}" y="{y + row_h / 2 - 6:.1f}" text-anchor="middle" '
                f'class="cell-value" fill="{ink}">{fmt_pct(cell["rate"], 1)}</text>'
            )
            parts.append(
                f'<text x="{x + col_w / 2:.1f}" y="{y + row_h / 2 + 12:.1f}" text-anchor="middle" '
                f'class="cell-sub" fill="{ink}" fill-opacity="0.85">{fmt_int(cell["n_loans"])}</text>'
            )
    parts.append("</svg>")
    return "".join(parts)


def build_cure_chart(cure_rows, palette):
    W, H = 620, 210
    pad, label_w, right_reserve = 16, 60, 210
    row_h, gap = 38, 14
    track_x = pad + label_w
    track_w = W - track_x - right_reserve
    order_to_ordinal = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4}

    parts = [svg_open(W, H, "Cure rate theo bucket xuất phát: tỷ lệ quay về B0 ở tháng kế tiếp")]
    for i, r in enumerate(cure_rows):
        cure_rate = r["n_cured"] / r["n_from"] if r["n_from"] else 0.0
        y = pad + i * (row_h + gap)
        bar_h = row_h - 10
        bar_y = y + (row_h - bar_h) / 2
        w = track_w * cure_rate
        color = palette["ordinal"][order_to_ordinal.get(r["from_order"], i + 1)]
        thin = r["n_from"] < 15000
        label = TO_STATE_LABELS[r["from_state"]] + (" *" if thin else "")
        value_txt = f"{fmt_pct(cure_rate, 3)} ({fmt_int(r['n_cured'])}/{fmt_int(r['n_from'])})"
        row_tip = tip(
            f"Bucket xuất phát: {TO_STATE_LABELS[r['from_state']]}",
            f"Cure rate (quay về B0 tháng sau): {fmt_pct(cure_rate, 3)}",
            f"Số dòng: {fmt_int(r['n_cured'])} quay về B0 trên {fmt_int(r['n_from'])} dòng xuất phát",
            f"Sang thẳng Closed: {fmt_int(r['n_closed'])} ({fmt_pct(r['n_closed'] / r['n_from'] if r['n_from'] else 0, 2)})",
            "* mẫu số dưới 15.000 dòng toàn danh mục, thận trọng khi diễn giải" if thin else None,
        )
        parts.append(
            f'<rect class="hit" x="{pad}" y="{y}" width="{W - pad * 2}" height="{row_h}" '
            f'fill="transparent" tabindex="0" data-tip="{row_tip}" />'
        )
        parts.append(
            f'<text x="{pad}" y="{y + row_h / 2:.1f}" class="row-label" dominant-baseline="middle">{esc(label)}</text>'
        )
        parts.append(hbar(color, track_x, bar_y, w, bar_h))
        parts.append(
            f'<text x="{track_x + w + 10:.1f}" y="{y + row_h / 2:.1f}" class="row-value" '
            f'dominant-baseline="middle">{esc(value_txt)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


# =============================================================================
# Tiện ích dựng HTML (không phụ thuộc SVG)
# =============================================================================

def kpi_tile(label, value, subtitle=None):
    sub = f'<div class="kpi-sub">{subtitle}</div>' if subtitle else ""
    return (
        '<div class="kpi-tile">'
        f'<div class="kpi-label">{esc(label)}</div>'
        f'<div class="kpi-value">{value}</div>'
        f"{sub}"
        "</div>"
    )


def table_html(headers, body_rows, caption=None, small_note=None):
    thead = "".join(f"<th>{esc(h)}</th>" for h in headers)
    trs = "".join(f"<tr>{''.join(f'<td>{c}</td>' for c in row)}</tr>" for row in body_rows)
    cap = f"<caption>{esc(caption)}</caption>" if caption else ""
    note = f'<p class="table-note">{small_note}</p>' if small_note else ""
    return (
        f'<div class="table-wrap"><table>{cap}<thead><tr>{thead}</tr></thead>'
        f"<tbody>{trs}</tbody></table></div>{note}"
    )


def checkpoint_table(series, ref_rows, ref_label, mobs=(3, 6, 9, 12, 18, 24)):
    """Bảng số kèm theo biểu đồ đường: hàng = một mốc MOB, cột = từng đường.
    Mỗi ô ghi cả tỷ lệ LẪN mẫu số (n_loans) để đảm bảo mẫu số luôn hiện thường
    trực, không bị \"giấu sau hover\" (theo yêu cầu DASHBOARD_SPEC và nguyên tắc
    tooltip chỉ bổ sung, không được là cách duy nhất để đọc số, trong skill dataviz)."""
    headers = ["MOB"] + [s["name"] for s in series] + ([ref_label] if ref_rows else [])
    body = []
    for m in mobs:
        row = [str(m)]
        for s in series:
            match = next((p for p in s["rows"] if p["mob"] == m), None)
            row.append(f"{fmt_pct(match['rate'], 3)} ({fmt_int(match['n_loans'])})" if match else "n/a")
        if ref_rows:
            match = next((p for p in ref_rows if p["mob"] == m), None)
            row.append(f"{fmt_pct(match['rate'], 3)} ({fmt_int(match['n_loans'])})" if match else "n/a")
        body.append(row)
    return table_html(headers, body, small_note="Mỗi ô: tỷ lệ ever 30+ (mẫu số n_loans tại MOB đó).")


def warn_box(title, body_html):
    return (
        '<div class="warn-box">'
        '<div class="warn-title"><span class="warn-icon" aria-hidden="true">&#9888;</span>'
        f"{esc(title)}</div>"
        f'<div class="warn-body">{body_html}</div>'
        "</div>"
    )


def source_note(text):
    return f'<p class="source-note">{text}</p>'


# =============================================================================
# Trang 1
# =============================================================================

def page1_html(data):
    s = data["page1_summary"]
    n_open = s["n_open"]
    kpis = "".join([
        kpi_tile(
            "Số hợp đồng đang mở",
            fmt_int(n_open),
            "Tại tháng tương đối gần nhất (mob snapshot = -1), không phải tháng lịch",
        ),
        kpi_tile(
            "Tỷ lệ 30+ theo số lượng",
            fmt_pct(s["rate_30plus_count"], 3),
            f"{fmt_int(s['n_30plus'])} trên {fmt_int(n_open)} hợp đồng đang mở",
        ),
        kpi_tile(
            "Tỷ lệ 30+ theo dư nợ ước tính",
            fmt_pct(s["rate_30plus_exposure"], 3),
            f"{fmt_billion(s['exposure_30plus'])} trên {fmt_billion(s['exposure_total'])} tỷ đơn vị (không phải VND)",
        ),
    ])

    bucket_chart = dual(build_bucket_chart, data["page1_buckets"], n_open)
    bucket_table_rows = [
        (
            esc(BUCKET_LABELS.get(b["dpd_bucket"], b["dpd_bucket"])),
            fmt_int(b["n_loans"]),
            fmt_pct(b["n_loans"] / n_open, 3),
            fmt_billion(b["exposure"]) + " tỷ",
        )
        for b in data["page1_buckets"]
    ]

    intro = (
        "<p>Trang này trả lời: <strong>danh mục đang thế nào?</strong> "
        "DPD (days past due, số ngày quá hạn) được nhóm thành 5 bucket: "
        "B0 hiện tại (0 ngày), B1 (1-30 ngày), B2 (31-60 ngày), B3 (61-90 ngày), "
        "B4 (trên 90 ngày). “Quá hạn trên 30 ngày” (viết tắt “30+”) "
        "nghĩa là DPD lớn hơn 30, tức từ bucket B2 trở lên. Số liệu là ảnh chụp tại "
        "tháng tương đối gần nhất trong dữ liệu (mốc <code>-1</code>), không phải "
        "tháng lịch thật, và chỉ tính hợp đồng đang mở.</p>"
    )

    chart_section = (
        '<section class="card">'
        '<h3 class="card-title">Phần lớn danh mục vẫn sạch, nhưng vẫn có một đuôi quá hạn nặng</h3>'
        '<p class="card-subtitle">98,65% hợp đồng đang ở bucket B0 (hiện tại); phần đuôi B1-B4 rất mỏng '
        "nên các thanh dưới đây ngắn, xem đúng số ở nhãn cuối mỗi hàng.</p>"
        f"{bucket_chart}"
        f"{table_html(['Bucket', 'Số hợp đồng', 'Tỷ trọng', 'Dư nợ ước tính'], bucket_table_rows)}"
        + source_note(
            "Nguồn: <code>core.fct_loan_month</code> · Mã chỉ tiêu M02 (DPD bucket), "
            "M06 (tỷ lệ 30+ coincident) · Snapshot <code>months_balance = -1</code>."
        )
        + "</section>"
    )

    return (
        '<section class="page" id="page-1" role="tabpanel" aria-labelledby="tab-1">'
        '<h2 class="page-title">1. Tổng quan danh mục</h2>'
        f"{intro}"
        f'<div class="kpi-row">{kpis}</div>'
        f"{chart_section}"
        "</section>"
    )


# =============================================================================
# Trang 2
# =============================================================================

def page2_html(data):
    by_product = data["page2_by_product"]
    avg_risk = data["page2_product_avg_risk"]
    avg_appr = data["page2_product_avg_approval"]
    all_rows = [r for lst in by_product.values() for r in lst]

    x_lo = max(0.0, min(r["approval_rate"] for r in all_rows) * 100 - 5)
    x_hi = min(100.0, max(r["approval_rate"] for r in all_rows) * 100 + 5)
    y_max = max(r["risk_rate"] for r in all_rows) * 1.15
    n_max = max(r["n_mob12"] for r in all_rows)

    panels = []
    for p in PRODUCTS:
        panel_svg = dual(
            build_scatter_panel, p, by_product[p], avg_risk.get(p), avg_appr.get(p),
            x_lo, x_hi, y_max, n_max,
        )
        panels.append(
            '<div class="scatter-panel">'
            f'<h4>{esc(PRODUCT_LABEL_VN[p])}</h4>'
            f"{panel_svg}"
            "</div>"
        )
    legend_svg = dual(build_scatter_legend_svg, n_max)

    # Bảng hiệu suất kênh x sản phẩm, gộp 3 sản phẩm, sắp theo sản phẩm rồi rủi ro giảm dần.
    perf_rows = []
    for p in PRODUCTS:
        for r in by_product[p]:
            ratio = r["risk_rate"] / avg_risk[p]["risk_rate"] if avg_risk.get(p) and avg_risk[p]["risk_rate"] else None
            small = " *" if r["n_mob12"] < 1000 else ""
            perf_rows.append((
                esc(PRODUCT_LABEL_VN[p]),
                esc(r["channel_type"]) + small,
                fmt_int(r["n_decided"]),
                fmt_pct(r["approval_rate"], 1),
                fmt_int(r["n_mob12"]),
                fmt_int(r["n_ever30"]),
                fmt_pct(r["risk_rate"], 3),
                (fmt_ratio(ratio, 2) + " lần") if ratio is not None else "n/a",
            ))
    perf_table = table_html(
        ["Sản phẩm", "Kênh", "Hồ sơ quyết định", "Tỷ lệ duyệt", "Mẫu số MOB 12",
         "Số từng 30+", "Ever 30+@MOB12", "So với TB cùng sản phẩm"],
        perf_rows,
        small_note="* mẫu số MOB 12 dưới 1.000 hợp đồng: thận trọng khi diễn giải.",
    )

    # Bảng cơ cấu sản phẩm theo kênh (% trên tổng mẫu số MOB12 của kênh đó).
    channel_totals = {}
    for p in PRODUCTS:
        for r in by_product[p]:
            channel_totals[r["channel_type"]] = channel_totals.get(r["channel_type"], 0) + r["n_mob12"]
    mix_by_channel = {}
    for p in PRODUCTS:
        for r in by_product[p]:
            mix_by_channel.setdefault(r["channel_type"], {})[p] = r["n_mob12"]
    mix_rows = []
    for ch, total in sorted(channel_totals.items(), key=lambda kv: -kv[1]):
        cells = []
        for p in PRODUCTS:
            n = mix_by_channel.get(ch, {}).get(p, 0)
            share = n / total if total else 0
            cells.append(fmt_pct(share, 1))
        mix_rows.append((esc(ch), *cells, fmt_int(total)))
    mix_table = table_html(
        ["Kênh"] + [PRODUCT_LABEL_VN[p] for p in PRODUCTS] + ["Mẫu số MOB 12 (mọi sản phẩm)"],
        mix_rows,
    )

    fpd = data["page2_fpd_note"]
    fpd_body = (
        f"<p>FPD30 (first payment default 30, tức kỳ trả đầu tiên chưa trả đủ sau 30 ngày kể từ "
        f"ngày đến hạn) toàn danh mục chỉ đo được <strong>{fmt_pct(fpd['fpd30_rate'], 5)}</strong> "
        f"({fmt_int(fpd['n_fpd30'])} trên {fmt_int(fpd['n_loans'])} hợp đồng có kỳ 1 đến hạn trước "
        f"ít nhất 30 ngày), mức thấp bất thường so với cảm quan rủi ro tín dụng tiêu dùng.</p>"
        f"<p>Lý do: dữ liệu trả nợ gần như chỉ ghi các kỳ ĐÃ TRẢ. "
        f"<strong>{fmt_int(fpd['n_approved_no_installment'])}</strong> trên "
        f"{fmt_int(fpd['n_approved_total'])} hồ sơ được duyệt toàn danh mục "
        f"({fmt_pct(fpd['n_approved_no_installment'] / fpd['n_approved_total'], 2)}) "
        f"không có bất kỳ dòng kỳ 1 nào trong dữ liệu trả nợ, nên biến mất khỏi mẫu số thay vì được "
        f"tính là vỡ nợ. Vì vậy dashboard KHÔNG dùng FPD30 để so sánh kênh hay sản phẩm; trục rủi ro "
        f"chính dùng ever 30+@MOB12 (mart.vintage, bên trên).</p>"
    )

    intro = (
        "<p>Trang này trả lời: <strong>kênh và sản phẩm nào duyệt nhiều nhưng rủi ro sớm cao?</strong> "
        "Approval rate (tỷ lệ duyệt) là tỷ lệ hồ sơ được duyệt trên số hồ sơ đã có quyết định. "
        "Ever 30+@MOB12 là tỷ lệ hợp đồng từng quá hạn trên 30 ngày tính đến MOB 12 "
        "(month on book, số tháng kể từ tháng hợp đồng mở); xem trang 3 để hiểu đầy đủ vintage. "
        "Toàn danh mục duyệt <strong>79,02%</strong> trên 1.344.636 hồ sơ, nhưng con số gộp này "
        "<strong>không dùng để so sánh trực tiếp giữa các kênh</strong>: xem hộp giải thích ngay dưới đây.</p>"
    )

    confound_note = warn_box(
        "So sánh giữa các kênh bị nhiễu do cơ cấu sản phẩm",
        "<p>Nhiễu (confounding, tức một yếu tố thứ ba làm sai lệch kết luận về mối quan hệ đang xét) "
        "xảy ra ở đây vì hai lý do cộng lại: (1) bản thân từng loại sản phẩm đã có mức rủi ro rất khác "
        f"nhau tại MOB12: vay tiêu dùng trả góp {fmt_pct(avg_risk['Consumer loans']['risk_rate'], 3)}, "
        f"vay tiền mặt {fmt_pct(avg_risk['Cash loans']['risk_rate'], 3)}, "
        f"thẻ quay vòng {fmt_pct(avg_risk['Revolving loans']['risk_rate'], 3)}; "
        "(2) các kênh bán các sản phẩm này với tỷ trọng rất khác nhau (xem bảng cơ cấu sản phẩm dưới đây). "
        "Vì vậy 3 khung bên dưới tách riêng theo từng sản phẩm; chỉ so sánh kênh trong CÙNG một khung "
        "(cùng sản phẩm) mới công bằng.</p>",
    )

    concentration_note = (
        '<section class="card highlight-card">'
        '<h3 class="card-title">Phát hiện tập trung rủi ro (đã khử nhiễu sản phẩm)</h3>'
        "<p>Trong riêng vay tiêu dùng trả góp tại MOB 12: nhóm kênh Stone hoặc Country-wide, "
        "khách mới, nhóm lãi suất cao chiếm <strong>14,0%</strong> mẫu số nhưng gánh "
        "<strong>33,7%</strong> số hợp đồng từng quá hạn trên 30 ngày (2,130% so với 0,683% của phần "
        "còn lại, gấp 3,1 lần). Phát hiện này vẫn đứng vững sau khi kiểm soát yếu tố sản phẩm.</p>"
        + source_note("Nguồn: mart.vintage, lọc contract_type = 'Consumer loans', mob = 12.")
        + "</section>"
    )

    return (
        '<section class="page" id="page-2" role="tabpanel" aria-labelledby="tab-2" hidden>'
        '<h2 class="page-title">2. Kênh bán: tăng trưởng và rủi ro, tách theo sản phẩm</h2>'
        f"{intro}"
        f"{confound_note}"
        '<section class="card">'
        '<h3 class="card-title">Cơ cấu sản phẩm theo kênh (mẫu số MOB 12)</h3>'
        "<p class=\"card-subtitle\">Vì sao phải so trong cùng sản phẩm: Credit and cash offices bán "
        "85,2% vay tiền mặt và 0% vay tiêu dùng, còn Stone bán 96,9% vay tiêu dùng. Hai kênh gần "
        "như không cùng “thị trường sản phẩm” nên so trực tiếp rủi ro gộp là không công bằng.</p>"
        f"{mix_table}"
        "</section>"
        '<section class="card">'
        '<h3 class="card-title">Tỷ lệ duyệt so với rủi ro, TÁCH THEO SẢN PHẨM (mỗi khung 1 sản phẩm)</h3>'
        '<p class="card-subtitle">Trục ngang: tỷ lệ duyệt. Trục dọc: ever 30+@MOB12. Kích thước điểm: '
        "số hợp đồng (mẫu số MOB 12). Đường mờ: trung bình của CHÍNH sản phẩm đó (không phải toàn danh mục).</p>"
        f'<div class="scatter-grid">{"".join(panels)}</div>'
        f"{legend_svg}"
        + source_note(
            "Nguồn: mart.funnel_by_channel (M12, trục ngang), mart.vintage (M08, trục dọc) · "
            "Mỗi khung đã lọc đúng 1 loại sản phẩm (contract_type), ghi trong tiêu đề khung."
        )
        + "</section>"
        '<section class="card">'
        '<h3 class="card-title">Bảng số: hiệu suất từng cặp kênh &times; sản phẩm</h3>'
        f"{perf_table}"
        + source_note("Nguồn: mart.funnel_by_channel, mart.vintage · Mã chỉ tiêu M08, M12.")
        + "</section>"
        f"{concentration_note}"
        + warn_box(
            "Giới hạn dữ liệu: FPD30 chỉ mang tính minh hoạ, không dùng để xếp hạng",
            fpd_body,
        )
        + "</section>"
    )


# =============================================================================
# Trang 3
# =============================================================================

def page3_html(data):
    series_products = []
    for p in PRODUCTS:
        rows_p = sorted(
            [r for r in data["page3_vintage_by_product"] if r["contract_type"] == p],
            key=lambda r: r["mob"],
        )
        series_products.append({"name": PRODUCT_LABEL_VN[p], "color_slot": PRODUCT_COLOR_SLOT[p], "rows": rows_p})

    def with_color(series_list, palette):
        return [
            {"name": s["name"], "color": palette["series"][s["color_slot"]], "rows": s["rows"]}
            for s in series_list
        ]

    portfolio_rows = sorted(data["page3_vintage_portfolio"], key=lambda r: r["mob"])
    chartA = (
        '<div class="viz-light">'
        + build_line_chart(with_color(series_products, PALETTES["light"]), portfolio_rows, "Toàn danh mục", PALETTES["light"])
        + "</div><div class=\"viz-dark\">"
        + build_line_chart(with_color(series_products, PALETTES["dark"]), portfolio_rows, "Toàn danh mục", PALETTES["dark"])
        + "</div>"
    )

    series_channels = []
    for i, c in enumerate(VINTAGE_CHART_CHANNELS):
        rows_c = sorted(
            [r for r in data["page3_vintage_channel_in_product"] if r["channel_type"] == c],
            key=lambda r: r["mob"],
        )
        series_channels.append({"name": CHANNEL_SHORT.get(c, c), "color_slot": i, "rows": rows_c})
    consumer_ref = sorted(
        [r for r in data["page3_vintage_by_product"] if r["contract_type"] == VINTAGE_WITHIN_PRODUCT],
        key=lambda r: r["mob"],
    )
    ref_label_b = f"TB {PRODUCT_LABEL_VN[VINTAGE_WITHIN_PRODUCT].lower()} (mọi kênh)"
    chartB = (
        '<div class="viz-light">'
        + build_line_chart(with_color(series_channels, PALETTES["light"]), consumer_ref, ref_label_b, PALETTES["light"])
        + "</div><div class=\"viz-dark\">"
        + build_line_chart(with_color(series_channels, PALETTES["dark"]), consumer_ref, ref_label_b, PALETTES["dark"])
        + "</div>"
    )

    intro = (
        "<p>Trang này trả lời: <strong>nhóm hợp đồng nào xấu đi nhanh hơn khi so cùng tuổi hợp đồng?</strong> "
        "Vintage là cách theo dõi một nhóm hợp đồng (cohort) theo tuổi hợp đồng thay vì theo tháng lịch, "
        "để loại bỏ hiệu ứng “danh mục đang tăng trưởng nhanh” làm tỷ lệ trông có vẻ tốt hơn thật. "
        "MOB (month on book) là số tháng kể từ tháng hợp đồng mở (MOB 0). Ever 30+@MOBn là tỷ lệ hợp đồng "
        "TỪNG quá hạn trên 30 ngày tính đến MOB n. Biểu đồ 1 tách theo SẢN PHẨM (khác biệt lớn nhất trong "
        "dữ liệu, xem trang 2); biểu đồ 2 tách theo KÊNH nhưng chỉ trong MỘT sản phẩm để tránh nhiễu cơ cấu "
        "sản phẩm giống hệt trang 2.</p>"
    )

    caution = (
        "<p>Thận trọng ở MOB cao: số hợp đồng THẬT SỰ quan sát đủ tới MOB (cột “quan sát đủ” trong "
        "tooltip, khác mẫu số vì mẫu số còn gồm cả hợp đồng đã tất toán sớm) giảm nhanh. Toàn danh mục, tại "
        "MOB 24 chỉ còn 70.635 hợp đồng quan sát đủ trên mẫu số 679.223 (10,4%); phần lớn mẫu số ở MOB cao là "
        "hợp đồng tất toán sớm, gần như không bao giờ 30+, nên đoạn cuối đường có thể bị kéo thấp một cách "
        "giả tạo. Không diễn giải đoạn MOB trên 18-20 nếu không đối chiếu với mẫu số quan sát đủ.</p>"
    )

    return (
        '<section class="page" id="page-3" role="tabpanel" aria-labelledby="tab-3" hidden>'
        '<h2 class="page-title">3. Vintage: nhóm hợp đồng nào xấu đi nhanh hơn</h2>'
        f"{intro}"
        '<section class="card">'
        '<h3 class="card-title">Theo LOẠI SẢN PHẨM (gộp mọi kênh): thẻ quay vòng và vay tiêu dùng '
        "xấu đi nhanh hơn vay tiền mặt rõ rệt</h3>"
        '<p class="card-subtitle">Đang so sánh theo sản phẩm, KHÔNG tách kênh. Đường mờ nét đứt: toàn danh mục.</p>'
        f"{chartA}"
        + checkpoint_table(with_color(series_products, PALETTES["light"]), portfolio_rows, "Toàn danh mục")
        + source_note("Nguồn: mart.vintage · Mã chỉ tiêu M08 (vintage ever 30+@MOBn) · MOB 0-24.")
        + "</section>"
        '<section class="card">'
        f'<h3 class="card-title">Theo KÊNH, CHỈ TRONG {esc(PRODUCT_LABEL_VN[VINTAGE_WITHIN_PRODUCT].upper())} '
        "(đã lọc 1 sản phẩm để tránh nhiễu cơ cấu sản phẩm)</h3>"
        f'<p class="card-subtitle">Đang lọc contract_type = ‘{esc(VINTAGE_WITHIN_PRODUCT)}’. '
        "Đường mờ nét đứt: trung bình toàn bộ vay tiêu dùng trả góp (mọi kênh).</p>"
        f"{chartB}"
        + checkpoint_table(with_color(series_channels, PALETTES["light"]), consumer_ref, ref_label_b)
        + source_note("Nguồn: mart.vintage · Mã chỉ tiêu M08 · Lọc contract_type = 'Consumer loans', MOB 0-24.")
        + "</section>"
        f'<div class="chart-note">{caution}</div>'
        "</section>"
    )


# =============================================================================
# Trang 4
# =============================================================================

def page4_html(data):
    grid, max_rate = build_full_rollrate_grid(data["page4_rollrate_raw"])
    heatmap_svg = dual(build_heatmap, grid, max_rate)
    cure_svg = dual(build_cure_chart, data["page4_cure"])

    intro = (
        "<p>Trang này trả lời: <strong>khách quá hạn di chuyển ra sao, nhóm nào khó thu hồi nhất?</strong> "
        "Roll rate (tỷ lệ chuyển trạng thái) đo tỷ lệ hợp đồng chuyển từ bucket DPD i ở tháng t sang bucket j "
        "ở tháng t+1. Cure rate (tỷ lệ hồi phục) là tỷ lệ hợp đồng đang quá hạn (B1 trở lên) quay về B0 ngay "
        "tháng sau. Toàn bộ ma trận dưới đây dùng dữ liệu toàn danh mục (gộp mọi kênh, sản phẩm).</p>"
    )

    grid_note = (
        "<p>Ô <strong>B1 &rarr; B4</strong> không có hợp đồng nào quan sát được trong dữ liệu; ô này được "
        "điền số 0 để khớp lưới trạng thái đầy đủ (5 trạng thái xuất phát &times; 8 trạng thái đích) thay vì "
        "để trống. Hàng <strong>B2</strong> và <strong>B3</strong> (đánh dấu *) có mẫu số toàn danh mục khá "
        "mỏng (12.315 và 7.172 dòng), thận trọng khi diễn giải, đặc biệt nếu cắt thêm theo phân khúc.</p>"
    )

    return (
        '<section class="page" id="page-4" role="tabpanel" aria-labelledby="tab-4" hidden>'
        '<h2 class="page-title">4. Chuyển nhóm và thu hồi</h2>'
        f"{intro}"
        '<section class="card">'
        '<h3 class="card-title">Ma trận roll rate: phần lớn hợp đồng ở B1 quay lại B0, nhưng từ B3 trở lên gần như không quay đầu</h3>'
        '<p class="card-subtitle">Mỗi hàng cộng lại bằng 100%. Màu đậm hơn = tỷ lệ cao hơn (thang màu liên tục, '
        "không phải phân loại).</p>"
        f"{heatmap_svg}"
        f'<div class="chart-note">{grid_note}</div>'
        + source_note("Nguồn: mart.roll_rate · Mã chỉ tiêu M09 (roll rate).")
        + "</section>"
        '<section class="card">'
        '<h3 class="card-title">Cure rate theo bucket xuất phát: càng trễ hạn sâu càng khó hồi phục</h3>'
        '<p class="card-subtitle">Tỷ lệ hợp đồng đang ở bucket này tại tháng t quay về B0 tại tháng t+1.</p>'
        f"{cure_svg}"
        + source_note("Nguồn: mart.roll_rate (lấy trực tiếp, không có mart riêng) · Mã chỉ tiêu M10 (cure rate).")
        + "</section>"
        "</section>"
    )


def glossary_html():
    terms = [
        ("DPD", "Days past due, số ngày quá hạn tính đến kỳ quan sát."),
        ("MOB", "Month on book, số tháng kể từ tháng hợp đồng mở (MOB 0 là tháng mở)."),
        ("Bucket B0-B4", "Nhóm DPD: B0 = 0 ngày (hiện tại), B1 = 1-30, B2 = 31-60, B3 = 61-90, B4 = trên 90 ngày."),
        ("30+", "DPD lớn hơn 30 ngày, tức từ bucket B2 trở lên."),
        ("FPD30", "First payment default 30: kỳ trả đầu tiên chưa trả đủ sau 30 ngày kể từ ngày đến hạn."),
        ("Vintage", "Cách theo dõi 1 nhóm hợp đồng (cohort) theo tuổi hợp đồng (MOB) thay vì theo tháng lịch."),
        ("Ever 30+@MOBn", "Tỷ lệ hợp đồng TỪNG quá hạn trên 30 ngày tính đến MOB n (không phải đang quá hạn đúng lúc đó)."),
        ("Roll rate", "Tỷ lệ hợp đồng chuyển từ bucket DPD này sang bucket khác ở tháng kế tiếp."),
        ("Cure rate", "Tỷ lệ hợp đồng quá hạn (B1 trở lên) quay về B0 ngay tháng sau."),
        ("Approval rate", "Tỷ lệ hồ sơ được duyệt trên số hồ sơ đã có quyết định (duyệt hoặc từ chối)."),
        ("Take-up rate", "Tỷ lệ khách thực sự dùng khoản vay trên số hồ sơ được duyệt."),
        ("Exposure proxy", "Ước lượng số tiền còn phải thu của hợp đồng trong tháng (không phải số liệu kế toán chính thức)."),
        ("Coincident vs lagged", "Coincident: đo tại đúng kỳ quan sát. Lagged: đo tử số tại kỳ t nhưng mẫu số tại kỳ t-k."),
        ("Confounding (nhiễu)", "Một yếu tố thứ ba (ở đây là loại sản phẩm) làm sai lệch kết luận về mối quan hệ đang so sánh (ở đây là kênh và rủi ro)."),
        ("Mẫu số / tử số", "Mẫu số = tổng số quan sát dùng để chia; tử số = số quan sát thoả điều kiện đang đếm."),
    ]
    items = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in terms)
    return (
        '<details class="glossary"><summary>Giải thích thuật ngữ dùng trong dashboard (bấm để mở)</summary>'
        f'<dl class="glossary-list">{items}</dl>'
        "</details>"
    )


# =============================================================================
# CSS: bảng màu theo skill dataviz (references/palette.md), khai báo làm biến
# CSS để đổi sáng/tối bằng @media (prefers-color-scheme) VÀ data-theme (nút
# chuyển tay), theo đúng màu trong palette.md.
# =============================================================================

CSS_BLOCK = """
:root {
  color-scheme: light;
  --surface-1:      #fcfcfb;
  --page-plane:     #f9f9f7;
  --text-primary:   #0b0b0b;
  --text-secondary: #52514e;
  --text-muted:     #898781;
  --gridline:       #e1e0d9;
  --baseline:       #c3c2b7;
  --border:         rgba(11,11,11,0.10);
  --series-1:       #2a78d6;
  --series-2:       #eb6834;
  --series-3:       #1baf7a;
  --warn:           #eda100;
  --warn-soft:      #fdf1dc;
  --warn-text:      #6b4700;
  --card-shadow:    0 1px 2px rgba(11,11,11,0.06);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --surface-1:      #1a1a19;
    --page-plane:     #0d0d0d;
    --text-primary:   #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted:     #898781;
    --gridline:       #2c2c2a;
    --baseline:       #383835;
    --border:         rgba(255,255,255,0.10);
    --series-1:       #3987e5;
    --series-2:       #d95926;
    --series-3:       #199e70;
    --warn:           #c98500;
    --warn-soft:      #2a2210;
    --warn-text:      #ffd699;
    --card-shadow:    0 1px 2px rgba(0,0,0,0.4);
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface-1:      #1a1a19;
  --page-plane:     #0d0d0d;
  --text-primary:   #ffffff;
  --text-secondary: #c3c2b7;
  --text-muted:     #898781;
  --gridline:       #2c2c2a;
  --baseline:       #383835;
  --border:         rgba(255,255,255,0.10);
  --series-1:       #3987e5;
  --series-2:       #d95926;
  --series-3:       #199e70;
  --warn:           #c98500;
  --warn-soft:      #2a2210;
  --warn-text:      #ffd699;
  --card-shadow:    0 1px 2px rgba(0,0,0,0.4);
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--page-plane);
  color: var(--text-primary);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  line-height: 1.5;
}
code {
  font-family: ui-monospace, "Cascadia Code", Consolas, monospace;
  background: var(--gridline);
  padding: 0.05em 0.35em;
  border-radius: 4px;
  font-size: 0.92em;
}

.container { max-width: 1180px; margin: 0 auto; padding: 20px 20px 60px; }

.dash-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 16px; flex-wrap: wrap; margin-bottom: 6px;
}
.dash-title { font-size: 1.6rem; font-weight: 700; margin: 0 0 4px; }
.dash-subtitle { color: var(--text-secondary); margin: 0; max-width: 62ch; }
.theme-toggle {
  border: 1px solid var(--border); background: var(--surface-1); color: var(--text-primary);
  border-radius: 8px; padding: 8px 14px; font-size: 0.9rem; cursor: pointer;
}
.theme-toggle:hover { background: var(--gridline); }

.base-bar {
  margin: 14px 0 18px; padding: 10px 14px; border-radius: 8px;
  background: var(--surface-1); border: 1px solid var(--border);
  color: var(--text-secondary); font-size: 0.88rem;
}

.tabs { display: flex; gap: 6px; flex-wrap: wrap; border-bottom: 1px solid var(--border); margin-bottom: 22px; }
.tab-btn {
  border: none; background: transparent; color: var(--text-secondary);
  padding: 10px 16px; font-size: 0.95rem; cursor: pointer; border-radius: 8px 8px 0 0;
  border-bottom: 2px solid transparent; font-weight: 600;
}
.tab-btn:hover { background: var(--surface-1); color: var(--text-primary); }
.tab-btn[aria-selected="true"] { color: var(--series-1); border-bottom-color: var(--series-1); }

.page-title { font-size: 1.25rem; margin: 4px 0 10px; }
.page p { color: var(--text-secondary); }
.page p code { color: var(--text-primary); }

.kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin: 16px 0 22px; }
.kpi-tile {
  background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px;
  padding: 16px 18px; box-shadow: var(--card-shadow);
}
.kpi-label { color: var(--text-secondary); font-size: 0.85rem; margin-bottom: 6px; }
.kpi-value { font-size: 1.9rem; font-weight: 600; font-variant-numeric: proportional-nums; }
.kpi-sub { color: var(--text-muted); font-size: 0.8rem; margin-top: 6px; }

.card {
  background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px;
  padding: 18px 20px 16px; margin-bottom: 20px; box-shadow: var(--card-shadow);
}
.highlight-card { border-left: 4px solid var(--series-1); }
.card-title { margin: 0 0 4px; font-size: 1.05rem; }
.card-subtitle { margin: 0 0 12px; color: var(--text-secondary); font-size: 0.9rem; }
.chart-note { color: var(--text-secondary); font-size: 0.86rem; margin-top: 10px; }
.chart-note p { margin: 0.4em 0; color: inherit; }
.source-note { color: var(--text-muted); font-size: 0.78rem; margin: 10px 0 0; }

.chart-svg { width: 100%; height: auto; display: block; }
.viz-dark { display: none; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .viz-dark { display: block; }
  :root:not([data-theme="light"]) .viz-light { display: none; }
}
:root[data-theme="dark"] .viz-dark { display: block; }
:root[data-theme="dark"] .viz-light { display: none; }

.row-label { fill: var(--text-secondary); font-size: 12.5px; }
.row-value { fill: var(--text-primary); font-size: 12.5px; font-weight: 600; }
.axis-label { fill: var(--text-muted); font-size: 11px; }
.axis-title { fill: var(--text-secondary); font-size: 11.5px; }
.gridline { stroke: var(--gridline); stroke-width: 1; }
.axis-line { stroke: var(--baseline); stroke-width: 1; }
.refline { stroke: var(--text-muted); stroke-width: 1.3; stroke-dasharray: 5 4; }
.ref-label { fill: var(--text-muted); font-size: 10.5px; }
.point-label { fill: var(--text-secondary); font-size: 11px; font-weight: 600; pointer-events: none; }
.ref-line { stroke: var(--text-muted); stroke-width: 2; stroke-dasharray: 6 4; }
.line-end-label { fill: var(--text-primary); font-size: 12px; font-weight: 600; }
.line-end-label.muted { fill: var(--text-muted); font-weight: 500; font-size: 11px; }
.cell-value { font-size: 13px; font-weight: 700; }
.cell-sub { font-size: 10px; }
.crosshair { stroke: var(--text-muted); stroke-width: 1; opacity: 0; pointer-events: none; }
.hit { cursor: pointer; }
.hit:hover ~ .crosshair, .hit:focus ~ .crosshair { opacity: 1; }

.scatter-grid { display: flex; gap: 16px; flex-wrap: wrap; }
.scatter-panel { flex: 1 1 260px; min-width: 240px; }
.scatter-panel h4 { margin: 0 0 6px; font-size: 0.92rem; text-align: center; }

.table-wrap { overflow-x: auto; margin-top: 8px; }
table { border-collapse: collapse; width: 100%; font-size: 0.86rem; }
caption { text-align: left; color: var(--text-secondary); margin-bottom: 6px; font-size: 0.85rem; }
th, td { text-align: right; padding: 7px 10px; border-bottom: 1px solid var(--gridline); font-variant-numeric: tabular-nums; white-space: nowrap; }
th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) { text-align: left; font-variant-numeric: normal; }
thead th { color: var(--text-secondary); font-weight: 600; border-bottom: 1px solid var(--baseline); }
tbody tr:hover { background: var(--gridline); }
.table-note { color: var(--text-muted); font-size: 0.78rem; margin-top: 6px; }

.warn-box {
  border: 1px solid var(--warn); background: var(--warn-soft); border-radius: 10px;
  padding: 14px 16px; margin-bottom: 20px;
}
.warn-title { color: var(--warn-text); font-weight: 700; font-size: 0.95rem; margin-bottom: 6px; display: flex; align-items: center; gap: 8px; }
.warn-icon { color: var(--warn); font-size: 1.1rem; }
.warn-body { color: var(--text-secondary); font-size: 0.88rem; }
.warn-body p { margin: 0.4em 0; }

.glossary { margin: 26px 0; border: 1px solid var(--border); border-radius: 10px; padding: 12px 16px; background: var(--surface-1); }
.glossary summary { cursor: pointer; font-weight: 600; }
.glossary-list { display: grid; grid-template-columns: max-content 1fr; column-gap: 14px; row-gap: 6px; margin: 12px 0 0; font-size: 0.86rem; }
.glossary-list dt { font-weight: 700; color: var(--text-primary); }
.glossary-list dd { margin: 0; color: var(--text-secondary); }

.dash-footer { color: var(--text-muted); font-size: 0.8rem; margin-top: 30px; border-top: 1px solid var(--border); padding-top: 14px; }

#tooltip {
  position: fixed; z-index: 50; pointer-events: none; max-width: 300px;
  background: var(--text-primary); color: var(--surface-1); font-size: 0.8rem;
  padding: 8px 10px; border-radius: 8px; white-space: pre-line; line-height: 1.4;
  opacity: 0; transform: translate(-1000px, -1000px); transition: opacity 0.08s ease;
  box-shadow: 0 4px 14px rgba(0,0,0,0.25);
}
#tooltip.visible { opacity: 1; }

@media (max-width: 640px) {
  .dash-title { font-size: 1.3rem; }
  .kpi-value { font-size: 1.5rem; }
}
"""

# =============================================================================
# JS: chuyển tab, tooltip dùng chung, crosshair, nút sáng/tối. Không gọi thư
# viện ngoài (theo yêu cầu DASHBOARD_SPEC).
# =============================================================================

JS_BLOCK = """
(function () {
  "use strict";

  function initTabs() {
    var buttons = Array.prototype.slice.call(document.querySelectorAll(".tab-btn"));
    var pages = Array.prototype.slice.call(document.querySelectorAll(".page"));
    buttons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var target = btn.getAttribute("data-target");
        buttons.forEach(function (b) { b.setAttribute("aria-selected", String(b === btn)); });
        pages.forEach(function (p) { p.hidden = p.id !== target; });
        window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
      });
    });
  }

  function initTheme() {
    var btn = document.getElementById("theme-toggle");
    if (!btn) return;
    var root = document.documentElement;
    function apply(mode) {
      if (mode) { root.setAttribute("data-theme", mode); }
      else { root.removeAttribute("data-theme"); }
      btn.textContent = mode === "dark" ? "Chế độ sáng" : mode === "light" ? "Theo hệ thống" : "Chế độ tối";
    }
    var saved = null;
    try { saved = localStorage.getItem("dashboard-theme"); } catch (e) {}
    apply(saved);
    btn.addEventListener("click", function () {
      var current = root.getAttribute("data-theme");
      var next = current === null ? "dark" : current === "dark" ? "light" : null;
      apply(next);
      try {
        if (next) { localStorage.setItem("dashboard-theme", next); }
        else { localStorage.removeItem("dashboard-theme"); }
      } catch (e) {}
    });
  }

  function initTooltips() {
    var tip = document.getElementById("tooltip");
    if (!tip) return;
    var current = null;

    function show(el, evt) {
      var text = el.getAttribute("data-tip");
      if (!text) return;
      current = el;
      tip.textContent = text;
      tip.classList.add("visible");
      move(evt, el);
      el.classList.add("is-hover");
    }
    function move(evt, el) {
      var x = 16, y = 16;
      if (evt && typeof evt.clientX === "number") { x = evt.clientX + 14; y = evt.clientY + 14; }
      else if (el) {
        var rect = el.getBoundingClientRect();
        x = rect.left + rect.width / 2; y = rect.top;
      }
      var vw = window.innerWidth, vh = window.innerHeight;
      requestAnimationFrame(function () {
        var tw = tip.offsetWidth, th = tip.offsetHeight;
        var tx = Math.min(x, vw - tw - 12);
        var ty = Math.min(y, vh - th - 12);
        tip.style.transform = "translate(" + Math.max(tx, 8) + "px, " + Math.max(ty, 8) + "px)";
      });
    }
    function hide(el) {
      tip.classList.remove("visible");
      if (el) el.classList.remove("is-hover");
      current = null;
    }
    function moveCrosshair(el) {
      if (!el.classList.contains("hit-band")) return;
      var svg = el.closest("svg");
      if (!svg) return;
      var line = svg.querySelector(".crosshair");
      if (!line) return;
      var cx = el.getAttribute("data-cx");
      if (cx === null) return;
      line.setAttribute("x1", cx); line.setAttribute("x2", cx);
      line.style.opacity = "1";
    }
    function resetCrosshair(el) {
      var svg = el.closest("svg");
      if (!svg) return;
      var line = svg.querySelector(".crosshair");
      if (line) line.style.opacity = "0";
    }

    document.addEventListener("pointermove", function (evt) {
      var el = evt.target.closest ? evt.target.closest("[data-tip]") : null;
      if (el) {
        if (el !== current) { show(el, evt); moveCrosshair(el); }
        else { move(evt, el); }
      } else if (current) {
        hide(current);
      }
    });
    document.addEventListener("pointerleave", function () { if (current) { resetCrosshair(current); hide(current); } }, true);
    document.querySelectorAll("[data-tip]").forEach(function (el) {
      el.addEventListener("focus", function () { show(el, null); moveCrosshair(el); });
      el.addEventListener("blur", function () { resetCrosshair(el); hide(el); });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initTabs();
    initTheme();
    initTooltips();
  });
})();
"""


def build_html(data):
    footer_base = data["footer_base"]
    tabs = [
        ("page-1", "1. Tổng quan"),
        ("page-2", "2. Kênh & sản phẩm"),
        ("page-3", "3. Vintage"),
        ("page-4", "4. Chuyển nhóm & thu hồi"),
    ]
    tab_btns = "".join(
        f'<button class="tab-btn" id="tab-{i+1}" data-target="{pid}" role="tab" '
        f'aria-selected="{"true" if i == 0 else "false"}">{esc(label)}</button>'
        for i, (pid, label) in enumerate(tabs)
    )

    pages_html = page1_html(data) + page2_html(data) + page3_html(data) + page4_html(data)

    payload = {
        "generated_note": "Số liệu tổng hợp từ data/warehouse.duckdb (chỉ đọc), xem scripts/build_dashboard.py",
        "footer_base": footer_base,
        "page1_buckets": data["page1_buckets"],
        "page1_summary": data["page1_summary"],
        "page2_by_product": data["page2_by_product"],
        "page2_product_avg_risk": data["page2_product_avg_risk"],
        "page2_product_avg_approval": data["page2_product_avg_approval"],
        "page2_fpd_note": data["page2_fpd_note"],
        "page3_vintage_by_product": data["page3_vintage_by_product"],
        "page3_vintage_portfolio": data["page3_vintage_portfolio"],
        "page3_vintage_channel_in_product": data["page3_vintage_channel_in_product"],
        "page4_cure": data["page4_cure"],
    }
    json_blob = json.dumps(payload, ensure_ascii=False, indent=1)

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dashboard giám sát danh mục tín dụng</title>
<style>{CSS_BLOCK}</style>
</head>
<body>
<div class="container">
  <header class="dash-header">
    <div>
      <h1 class="dash-title">Dashboard giám sát danh mục tín dụng</h1>
      <p class="dash-subtitle">Dữ liệu Home Credit Default Risk (Kaggle), portfolio luyện tập cho vị trí
      Credit Risk Analyst (chuyên viên phân tích rủi ro tín dụng). Không phải số liệu VND thật, chỉ dùng
      để so sánh tương đối và luyện kỹ năng.</p>
    </div>
    <button id="theme-toggle" class="theme-toggle" type="button">Chế độ tối</button>
  </header>
  <p class="base-bar">
    Danh mục: {fmt_int(footer_base['n_loans_total'])} hợp đồng có lịch sử tháng,
    {fmt_int(footer_base['n_loan_months'])} dòng hợp đồng-tháng. Thời gian là <strong>tháng tương đối</strong>
    (mốc <code>-96</code> đến <code>-1</code>), <strong>không quy đổi được sang tháng lịch thật</strong>.
    Danh mục chỉ gồm khoản vay <strong>trước đây</strong> của khách có hồ sơ mới trong dữ liệu (không phải
    toàn bộ lịch sử vay của khách). Đơn vị tiền trong dữ liệu Kaggle không phải VND.
  </p>
  <nav class="tabs" role="tablist">{tab_btns}</nav>
  {pages_html}
  {glossary_html()}
  <footer class="dash-footer">
    <p>Sinh tự động bằng <code>scripts/build_dashboard.py</code> từ <code>data/warehouse.duckdb</code>
    (chỉ đọc). Mã chỉ tiêu tham chiếu <code>docs/metric_dictionary.md</code>. Số liệu đã tổng hợp được
    nhúng trong thẻ <code>&lt;script type="application/json" id="dashboard-data"&gt;</code> bên dưới để
    tái sử dụng hoặc kiểm chứng lại.</p>
  </footer>
</div>
<div id="tooltip" role="status" aria-live="polite"></div>
<script type="application/json" id="dashboard-data">
{json_blob}
</script>
<script>{JS_BLOCK}</script>
</body>
</html>
"""


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if not DB_PATH.exists():
        sys.exit(f"{DB_PATH} not found. Chạy scripts/build.py trước.")

    con = duckdb.connect(str(DB_PATH), read_only=True)
    # 1 thread: sum() trên số thực (float) có thể ra kết quả khác nhau vài chữ
    # số cuối tùy thứ tự cộng dồn song song. Ép 1 thread để script chạy lại
    # nhiều lần cho đúng 1 kết quả (yêu cầu trong DASHBOARD_SPEC).
    con.execute("PRAGMA threads=1")
    print("Đọc dữ liệu từ warehouse (read_only)")
    data = fetch_data(con)

    print("Xuất CSV cho Power BI")
    export_marts_to_csv(con)
    con.close()

    print("Dựng HTML")
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    html_out = build_html(data)
    out_path = DASHBOARD_DIR / "index.html"
    out_path.write_text(html_out, encoding="utf-8")
    print(f"  ok  {out_path.relative_to(ROOT)}  ({len(html_out):,} ký tự)")

    # In nhanh vài con số để tự đối chiếu với VERIFIED_NUMBERS.md
    print("\nKiểm tra nhanh (đối chiếu với VERIFIED_NUMBERS.md):")
    s = data["page1_summary"]
    print(f"  Số hợp đồng đang mở: {fmt_int(s['n_open'])}")
    for b in data["page1_buckets"]:
        print(f"    {b['dpd_bucket']}: {fmt_int(b['n_loans'])} ({fmt_pct(b['n_loans'] / s['n_open'], 3)})")
    print(f"  FPD30 toàn danh mục: {fmt_pct(data['page2_fpd_note']['fpd30_rate'], 5)}")


if __name__ == "__main__":
    main()
