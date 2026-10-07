# -*- coding: utf-8 -*-
"""Sinh phần Report (PBIR) của PBIP: theme Editorial Newsroom, 4 trang, 48 visual.

Bản thiết kế chính thức nằm ở powerbi/_brief/report-spec.md, khối YAML
"Design Brief:". File này dịch khối đó ra JSON. Mọi tên trang, dòng dẫn (dek),
tiêu đề visual có số và ghi chú LƯU Ý lấy từ scripts/headlines.py, vốn sinh từ
data/export/findings.json; file này không gõ cứng chuỗi có số nào. Kiểm đồng bộ
với bản HTML: python scripts/check_headlines_sync.py.

Bốn điều không được đổi nếu không đọc kỹ trước:

1. Phiên bản schema PBIR. Cố tình dùng bản Microsoft ĐÃ PUBLISH (visualContainer
   2.9.0, report 3.3.0, page 2.1.0), không dùng bản mà Power BI Desktop 2.157 tự
   ghi ra (2.12.0, 3.4.0, 2.3.1). Bản mới hơn trả về HTTP 404 trên
   developer.microsoft.com, nên powerbi-report-author không tải được và BỎ QUA
   hẳn lớp kiểm JSON Schema. Giữ bản cũ để còn lớp kiểm đó; chính nó đã bắt được
   lỗi thiếu reportVersionAtImport khi dựng project này. Hệ quả: ở lần đầu
   Desktop chuyển đổi một PBIP vừa sinh từ script, nó nâng URL schema và ghi lại
   file theo dạng chuẩn của nó (một lần, không phải mỗi lần mở). Diff đó vô hại.

2. ID trang và visual sinh bằng SHA-1 của "trang|khóa" chứ không ngẫu nhiên,
   nên chạy lại cho ra đúng ID cũ và git diff chỉ hiện phần thật sự đổi.

3. Tên file theme phải đổi hậu tố mỗi lần sửa nội dung theme. Desktop cache
   theme theo tên file, giữ nguyên tên thì sửa xong reload vẫn ra màu cũ.

4. FONT_DISPLAY KHÔNG được đổi lại thành Georgia. Xem chú thích ngay tại hằng
   khai báo FONT_DISPLAY.
"""
import hashlib
import json
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import headlines  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
RPT = ROOT / "powerbi" / "CreditPortfolio.Report"
DEF = RPT / "definition"
PAGES = DEF / "pages"
RESOURCES = RPT / "StaticResources" / "RegisteredResources"

SCHEMA_VIS = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json"
SCHEMA_PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
SCHEMA_RPT = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json"
SCHEMA_PBIR = "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json"
SCHEMA_PLAT = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"

THEME_NAME = "CreditPortfolio-Editorial-9c4f2a68.json"

# ---------------------------------------------------------------- bảng màu
# Tông Editorial Newsroom: nền kem, mực đen, ĐÚNG MỘT màu nhấn mustard.
CREAM = "#FAF7F0"   # nền trang
CREAM2 = "#F0EADC"  # nền ngoài canvas
INK = "#0F172A"     # chữ chính, chuỗi dữ liệu chính
STONE = "#5C5349"   # chữ phụ, xám đậm
GREY = "#938A7F"    # mảng dữ liệu nền
GREY_L = "#C2B9AC"  # mảng dữ liệu nền nhạt
RULE = "#E3DACB"    # kẻ ngang trong bảng
MUSTARD = "#D4A30A"  # màu nhấn duy nhất

# Font tiêu đề serif. TUYỆT ĐỐI KHÔNG dùng Georgia: file font Georgia THIẾU 19 ký
# tự tiếng Việt thường gặp: ấ ầ ẩ ẫ ậ ế ề ể ễ ệ ố ồ ổ ỗ ộ ơ ư ớ ứ.
# Khi thiếu glyph, Windows ghép dấu rời lên ký tự gốc, nên "gấp" hiện thành "gâ´p",
# "lần" thành "lâ`n", "hồi" thành "hô`i". Đã kiểm bằng bảng mã (cmap) của từng
# font: Cambria, Times New Roman, Constantia, Palatino Linotype đều đủ cả 19 ký tự;
# Cambria giữ chất serif editorial tốt nhất nên chọn Cambria. Muốn đổi font thì
# phải kiểm lại 19 ký tự trên.
FONT_DISPLAY = "Cambria"
FONT_BODY = "Segoe UI"
FONT_BODY_SB = "Segoe UI Semibold"

UNKNOWN = "(không rõ)"
OTHER_CHANNEL = "Khác"

# Đối tượng tô mustard ở từng trang: đúng đối tượng mà câu kết luận nói tới.
# Trùng lựa chọn trong scripts/build_dashboard.py.
HL_P1_BUCKET = "B1 1-30"
HL_P1_CHANNEL = "Credit and cash offices"
HL_P2_CHANNELS = ("Contact center", "Stone")  # cũng ghi cứng trong DAX measure Highlight/Base của build_pbip_model.py
HL_P3_CHANNEL = "Contact center"  # như trên
HL_P3_PRODUCT = "Revolving loans"
HL_P4_FROM = "B1 1-30"
THIN_P4_FROM = "B3 61-90"  # dưới ngưỡng 1.000 lượt: tô xám nhạt hơn để báo mẫu mỏng

# ---------------------------------------------------------------- lưới 12x12
# Cột: lề 24, bề ngang dùng được 1232, 12 cột rộng 88, rãnh 16, bước 104.
# Hàng nội dung: bắt đầu y=160, 8 hàng cao 56, rãnh 16, bước 56.
# Vùng [c1, r1, c2, r2] đánh số từ 1, biên phải và dưới là mở (không lấy).
MARGIN, COL_PITCH, ROW_PITCH, GUTTER = 24, 104, 56, 16
CONTENT_Y0 = 160
ROW_FIRST = 3  # hàng 1-2 của lưới là dải masthead, nội dung bắt đầu ở hàng 3


def region(c1, r1, c2, r2):
    """Đổi toạ độ lưới sang (x, y, w, h) pixel. Mọi giá trị chia hết cho 8."""
    x = MARGIN + (c1 - 1) * COL_PITCH
    w = (c2 - c1) * COL_PITCH - GUTTER
    y = CONTENT_Y0 + (r1 - ROW_FIRST) * ROW_PITCH
    h = (r2 - r1) * ROW_PITCH - GUTTER
    return x, y, w, h


def slot(rect, i, n, gap=GUTTER):
    """Chia một vùng thành n ô bằng nhau theo chiều ngang, lấy ô thứ i (đếm từ 0)."""
    x, y, w, h = rect
    cw = (w - gap * (n - 1)) // n
    return x + i * (cw + gap), y, cw, h


# ---------------------------------------------------------------- tiện ích JSON
def jw(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")


def hid(*parts):
    """ID hex ổn định (tái tạo được) thay vì ngẫu nhiên, để diff git sạch."""
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:20]


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def q(v):
    """Chuỗi trong PBIR: bọc nháy đơn, nháy đơn trong chuỗi thì nhân đôi."""
    return lit("'" + str(v).replace("'", "''") + "'")


def dec(v):
    return lit("%sD" % v)


def flag(v):
    return lit("true" if v else "false")


def solid(hex_color):
    return {"solid": {"color": q(hex_color)}}


# ---------------------------------------------------------------- biểu thức field
def fcol(table, column):
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": column}}


def fmeas(table, measure):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": table}}, "Property": measure}}


# Tên hiển thị tiếng Việt đặt ở tầng PBIR (projection.displayName), KHÔNG đụng tới
# model. Khóa là tên thật trong model; queryRef và nativeQueryRef vẫn giữ tên gốc nên
# selector metadata, sort và filter không bị ảnh hưởng. Cột hoặc measure không có
# trong bảng này thì giữ tên model (các cột dim đã là tiếng Việt sẵn: Kênh, Sản phẩm).
# Một visual cần tên khác thì truyền phần tử thứ tư trong bộ (table, field, kind, tên).
DISPLAY = {
    # Snapshot (trang 1)
    "dpd_bucket": "Nhóm quá hạn",
    "Open Loans": "Hợp đồng mở",
    "Loans 30+": "Số 30+",
    "Rate 30+ Coincident": "Tỷ lệ 30+",
    # Funnel (trang 2)
    "Applications": "Số hồ sơ",
    "Approval Rate": "Tỷ lệ duyệt thô",
    "Approval Standardized Ratio": "Duyệt so với kỳ vọng",
    "Take-up Rate Consumer": "Take-up vay tiêu dùng",
    # Vintage (trang 2, 3)
    "Ever 30 Plus MOB12": "Từng 30+ tại MOB 12",
    "Ever 30 Plus MOB12 No Threshold": "Không áp ngưỡng (SK_DPD)",
    "Vintage Loans MOB12": "Mẫu số tại MOB 12",
    "Ever 30 Plus Rate": "Tỷ lệ từng 30+",
    "Ever 30 Plus Loans MOB12": "Ca quan sát",
    "Expected 30 Plus MOB12": "Ca kỳ vọng",
    "SMR MOB12": "SMR",
    "SMR MOB12 CI Low": "Cận dưới 95%",
    "SMR MOB12 CI High": "Cận trên 95%",
    "Expected 30 Plus MOB12 Cohort": "Ca kỳ vọng (sản phẩm × đợt)",
    "SMR MOB12 Cohort": "SMR sản phẩm × đợt",
    "SMR MOB12 Cohort CI Low": "Cận dưới 95%",
    "SMR MOB12 Cohort CI High": "Cận trên 95%",
    "Ratio vs Cash Crude": "Đ.n. chính",
    "Ratio vs Cash MH Cohort": "Kiểm soát đợt",
    "Ratio vs Cash Due Only": "Đ.n. giữa",
    "Ratio vs Cash No Threshold": "Không ngưỡng",
    "Cohort Ever 30 Plus Rate": "Tỷ lệ từng 30+",
    "origination_cohort": "Đợt mở",
    "mob": "MOB",
    # RollRate (trang 4)
    "from_state": "Nhóm xuất phát",
    "to_state": "Nhóm đến",
    "Roll Rate": "Tỷ lệ chuyển nhóm",
    "Roll Base Loans": "Số lượt hợp đồng-tháng",
    "Cure Rate": "Cure rate",
    "Exposure From": "Dư nợ cộng dồn qua tháng",  # đơn vị tỷ do columnFormatting gắn hậu tố
}


def proj(table, name, kind, display=None):
    f = fcol(table, name) if kind == "col" else fmeas(table, name)
    out = {"field": f, "queryRef": "{}.{}".format(table, name), "nativeQueryRef": name}
    label = display or DISPLAY.get(name)
    if label:
        out["displayName"] = label
    return out


def projections(items):
    return {"projections": [proj(*it) for it in items]}


def scope_sel(table, column, value):
    """Selector trỏ đúng một giá trị của một cột. Chỉ ComparisonKind 0 được honor."""
    return {"data": [{"scopeId": {"Comparison": {
        "ComparisonKind": 0,
        "Left": fcol(table, column),
        "Right": {"Literal": {"Value": "'" + str(value).replace("'", "''") + "'"}}}}}]}


def sort_by_measure(table, measure, direction="Descending"):
    return {"sort": [{"field": fmeas(table, measure), "direction": direction}], "isDefaultSort": True}


def exclude(table, column, values, seed):
    """Bộ lọc mức visual: loại bỏ một hoặc vài giá trị.

    Trong filter.Where, SourceRef dùng "Source" (alias khai báo ở From), KHÔNG
    dùng "Entity"; ở trường field ngoài cùng thì ngược lại. Sai chỗ này thì bộ
    lọc im lặng không chạy.
    """
    if isinstance(values, str):
        values = [values]
    alias = "f"
    return {
        "name": "Filter" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:24],
        "field": fcol(table, column),
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": alias, "Entity": table, "Type": 0}],
            "Where": [{"Condition": {"Not": {"Expression": {"In": {
                "Expressions": [{"Column": {
                    "Expression": {"SourceRef": {"Source": alias}}, "Property": column}}],
                "Values": [[{"Literal": {"Value": "'" + str(v).replace("'", "''") + "'"}}] for v in values],
            }}}}}],
        },
        "howCreated": "User",
    }


# ---------------------------------------------------------------- dựng visual
def pad(t=8, b=8, l=8, r=8):
    """Khai báo bất kỳ VCO nào là Power BI bỏ padding kế thừa từ theme và đặt về 0.
    Vì vậy mọi visual trong báo cáo này đều khai báo padding tường minh."""
    return [{"properties": {"top": dec(t), "bottom": dec(b), "left": dec(l), "right": dec(r)}}]


def base_vco(alt=None, padding=None):
    vco = {
        "background": [{"properties": {"show": flag(False)}}],
        "border": [{"properties": {"show": flag(False)}}],
        "visualHeader": [{"properties": {"show": flag(False)}}],
        "padding": padding if padding is not None else pad(),
    }
    if alt:
        vco["general"] = [{"properties": {"altText": q(alt)}}]
    return vco


def title_vco(text, size=None):
    """Tiêu đề visual là câu kết luận có số, nên dài; bật titleWrap cho xuống dòng.
    size: cỡ chữ riêng cho visual hẹp mà câu dài (Power BI cắt tiêu đề quá ba dòng)."""
    props = {"show": flag(True), "text": q(text), "fontColor": solid(INK), "titleWrap": flag(True)}
    if size:
        props["fontSize"] = dec(size)
    return [{"properties": props}]


def container(page, key, rect, z, visual_body, vco, filters=None):
    name = hid(page, key)
    x, y, w, h = rect
    out = {
        "$schema": SCHEMA_VIS,
        "name": name,
        "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z},
        "visual": dict(visual_body),
    }
    if vco:
        out["visual"]["visualContainerObjects"] = vco
    if filters:
        out["filterConfig"] = {"filters": filters}
    return name, out


def chart(page, key, vtype, rect, roles, z, title, alt, objects=None,
          sort=None, filters=None, padding=None, title_size=None):
    """roles: {'RoleName': [(table, field, 'col'|'meas'[, tên hiển thị]), ...]}"""
    qs = {r: projections(items) for r, items in roles.items()}
    body = {"visualType": vtype, "query": {"queryState": qs}}
    if sort:
        body["query"]["sortDefinition"] = sort
    if objects:
        body["objects"] = objects
    vco = base_vco(alt, padding)
    # Đặt title thì Power BI tự sinh thêm một phụ đề ghép tên field. Tắt nó đi,
    # nếu không mỗi biểu đồ sẽ có hai dòng chữ chồng nhau.
    vco["title"] = title_vco(title, title_size)
    vco["subTitle"] = [{"properties": {"show": flag(False)}}]
    return container(page, key, rect, z, body, vco, filters)


def textbox(page, key, rect, paragraphs, z, alt=None):
    body = {"visualType": "textbox",
            "objects": {"general": [{"properties": {"paragraphs": paragraphs}}]}}
    vco = base_vco(alt, pad(0, 0, 0, 0))
    return container(page, key, rect, z, body, vco)


def run(text, size, font=FONT_BODY, color=INK, weight=None, italic=False):
    st = {"fontFamily": font, "fontSize": "%dpt" % size, "color": color}
    if weight:
        st["fontWeight"] = weight
    if italic:
        st["fontStyle"] = "italic"
    return {"value": text, "textStyle": st}


def para(runs, align="left"):
    return {"textRuns": runs, "horizontalTextAlignment": align}


def rule(page, key, rect, z, color=INK):
    """Kẻ ngang mảnh. Phải dùng shape chứ không dùng textbox: textbox bị Desktop
    ép chiều cao tối thiểu khoảng 24px bất kể position.height ghi gì."""
    body = {"visualType": "shape", "objects": {
        "shape": [{"properties": {"tileShape": q("rectangle")}}],
        "fill": [{"properties": {"fillColor": solid(color), "transparency": dec(0)},
                  "selector": {"id": "default"}}],
        "outline": [{"properties": {"show": flag(False)}, "selector": {"id": "default"}}],
    }}
    vco = {
        "background": [{"properties": {"show": flag(False)}}],
        "border": [{"properties": {"show": flag(False)}}],
        "padding": pad(0, 0, 0, 0),
    }
    return container(page, key, rect, z, body, vco)


def card(page, key, table, measure, label, rect, z, alt):
    """Thẻ KPI. Ba lưu ý:

    - Mọi object của cardVisual đều cần selector {"id": "default"}; thiếu selector
      thì thuộc tính validate sạch nhưng không có tác dụng nào.
    - Dùng nhãn riêng của card (label.text) chứ không đặt title ở container:
      đặt title thì nó hiện SONG SONG với nhãn mặc định và hai dòng chữ đè lên nhau.
    - Nhãn tĩnh, không chứa số. Mẫu số của từng thẻ nói trong ghi chú LƯU Ý.
    """
    sel = {"id": "default"}
    objects = {
        "label": [{"properties": {
            "show": flag(True), "text": q(label),
            "fontFamily": q(FONT_BODY_SB), "fontSize": dec(9),
            "fontColor": solid(STONE), "position": q("aboveValue"),
            "horizontalAlignment": q("left")}, "selector": sel}],
        "value": [{"properties": {
            "fontFamily": q(FONT_BODY_SB), "fontSize": dec(32),
            "fontColor": solid(INK), "horizontalAlignment": q("left")}, "selector": sel}],
        "outline": [{"properties": {"show": flag(False)}, "selector": sel}],
        # Kẻ ngang mảnh trên đỉnh mỗi thẻ: chữ ký S10 áp vào thẻ KPI.
        "accentBar": [{"properties": {
            "show": flag(True), "position": q("Top"),
            "color": solid(INK), "width": dec(2), "transparency": dec(0)}, "selector": sel}],
    }
    body = {"visualType": "cardVisual",
            "query": {"queryState": {"Data": projections([(table, measure, "meas")])}},
            "objects": objects}
    # padding của cardVisual là VCO và cần selector {"id": "default"}; thiếu
    # selector thì nó validate sạch nhưng không có tác dụng nào.
    card_pad = {"top": dec(10), "bottom": dec(4), "left": dec(0), "right": dec(8)}
    vco = base_vco(alt, [{"properties": card_pad},
                         {"properties": card_pad, "selector": {"id": "default"}}])
    vco["title"] = [{"properties": {"show": flag(False)}}]
    vco["subTitle"] = [{"properties": {"show": flag(False)}}]
    return container(page, key, rect, z, body, vco)


def slicer(page, key, table, column, header, rect, z, alt):
    """Slicer dropdown. Chiều cao 80 = 60 chrome + 8 + 8 padding, theo công thức
    sizing trong references/authoring/slicers.md. Không được hạ xuống 48 hay thu
    nhỏ font để 'vừa khung': làm thế chỉ giấu phần bị cắt."""
    body = {"visualType": "slicer",
            "query": {"queryState": {"Values": projections([(table, column, "col")])}},
            "objects": {
                "data": [{"properties": {"mode": q("Dropdown")}}],
                # slicer dùng "textSize" chứ không phải "fontSize" như các visual khác
                "header": [{"properties": {
                    "show": flag(True), "text": q(header),
                    "fontFamily": q(FONT_BODY_SB), "textSize": dec(9),
                    "fontColor": solid(STONE)}}],
                "items": [{"properties": {
                    "fontFamily": q(FONT_BODY), "textSize": dec(10),
                    "fontColor": solid(INK)}}],
            }}
    vco = base_vco(alt, pad(8, 8, 8, 8))
    vco["title"] = [{"properties": {"show": flag(False)}}]
    return container(page, key, rect, z, body, vco)


def navigator(page, key, rect, z, alt):
    """Điều hướng 4 trang. Sửa anti-pattern 'Multi-page report without navigation'.

    pageNavigator thuộc nhóm visual cần MỘT cặp entry: một entry không selector
    và một entry có selector id. Trang đang mở nhận gạch chân mustard."""
    def states(props_by_state):
        out = [{"properties": props_by_state.get("default", {})}]
        for state, props in props_by_state.items():
            out.append({"properties": props, "selector": {"id": state}})
        return out

    off = {"show": flag(False)}
    body = {"visualType": "pageNavigator", "objects": {
        "fill": states({"default": dict(off), "selected": dict(off), "hover": dict(off)}),
        "outline": states({"default": dict(off), "selected": dict(off), "hover": dict(off)}),
        "text": states({
            "default": {"fontFamily": q(FONT_BODY), "fontSize": dec(10),
                        "fontColor": solid(STONE), "bold": flag(False),
                        "horizontalAlignment": q("center")},
            "selected": {"fontFamily": q(FONT_BODY_SB), "fontSize": dec(10),
                         "fontColor": solid(INK), "bold": flag(True),
                         "horizontalAlignment": q("center")},
            "hover": {"fontFamily": q(FONT_BODY), "fontSize": dec(10),
                      "fontColor": solid(INK), "horizontalAlignment": q("center")},
        }),
        "accentBar": states({
            "default": {"show": flag(False)},
            "selected": {"show": flag(True), "position": q("Bottom"),
                         "color": solid(MUSTARD), "width": dec(3), "transparency": dec(0)},
        }),
    }}
    vco = base_vco(alt, pad(0, 0, 0, 0))
    return container(page, key, rect, z, body, vco)


# ---------------------------------------------------------------- mảnh định dạng dùng lại
def axis(show=True, size=9, title=None, color=STONE):
    p = {"show": flag(show), "gridlineShow": flag(False),
         "fontFamily": q(FONT_BODY), "fontSize": dec(size), "labelColor": solid(color)}
    if title:
        p["showAxisTitle"] = flag(True)
        p["titleText"] = q(title)
        p["axisStyle"] = q("showTitleOnly")
        p["titleFontFamily"] = q(FONT_BODY)
        p["titleFontSize"] = dec(9)
        p["titleColor"] = solid(STONE)
    else:
        p["showAxisTitle"] = flag(False)
    return [{"properties": p}]


def shared_value_axis():
    """sharedAxis buộc mọi ô nhỏ dùng chung thang trục giá trị. Thiếu nó là rơi
    vào anti-pattern 'Unshared small-multiple axes': mỗi ô một thang, không so được."""
    return [{"properties": {
        "show": flag(True), "sharedAxis": flag(True), "gridlineShow": flag(False),
        "showAxisTitle": flag(False), "fontFamily": q(FONT_BODY),
        "fontSize": dec(8), "labelColor": solid(STONE)}}]


def sm_layout(rows, cols):
    return [{"properties": {
        "layoutType": q("custom"), "rowCount": lit("%dL" % rows), "columnCount": lit("%dL" % cols),
        "gridLineShow": flag(False), "gridPadding": dec(8)}}]


def sm_header():
    return [{"properties": {
        "show": flag(True), "fontFamily": q(FONT_BODY_SB), "fontSize": dec(9),
        "fontColor": solid(INK), "position": q("top")}}]


def datalabels(size=9, units=0, precision=None):
    p = {"show": flag(True), "fontFamily": q(FONT_BODY), "fontSize": dec(size),
         "color": solid(INK), "labelDisplayUnits": lit("%dD" % units)}
    if precision is not None:
        p["labelPrecision"] = lit("%dD" % precision)
    return [{"properties": p}]


def no_legend():
    return [{"properties": {"show": flag(False)}}]


def points(default_color, highlights=()):
    """S6 Highlight-and-grey: một màu nền cho tất cả, rồi trả màu cho đúng phần tử
    mang thông điệp. Trên biểu đồ một chuỗi phải dùng defaultColor làm nền; dùng
    fill không selector thì cột biến mất."""
    out = [{"properties": {"defaultColor": solid(default_color)}}]
    for table, column, value, color in highlights:
        out.append({"properties": {"fill": solid(color)},
                    "selector": scope_sel(table, column, value)})
    return out


def measure_colors(table, pairs):
    """Màu theo measure (selector metadata). Dùng cho cặp measure trình bày
    Highlight / Base: selector theo danh mục không có tác dụng trong small multiples."""
    return [{"properties": {"fill": solid(color)}, "selector": {"metadata": "%s.%s" % (table, m)}}
            for m, color in pairs]


def table_style(row_pad=2, size=9):
    """Bảng và ma trận: chỉ kẻ ngang, không kẻ dọc, nền ô trùng nền trang."""
    return {
        "columnHeaders": [{"properties": {
            "columnAdjustment": q("growToFit"), "autoSizeColumnWidth": flag(True),
            "fontFamily": q(FONT_BODY_SB), "fontSize": dec(size),
            "fontColor": solid(INK), "backColor": solid(CREAM)}}],
        "values": [{"properties": {
            "fontFamily": q(FONT_BODY), "fontSize": dec(size),
            "fontColorPrimary": solid(INK), "fontColorSecondary": solid(INK),
            "backColorPrimary": solid(CREAM), "backColorSecondary": solid(CREAM)}}],
        "grid": [{"properties": {
            "gridHorizontal": flag(True), "gridHorizontalColor": solid(RULE),
            "gridHorizontalWeight": dec(1),
            "gridVertical": flag(False), "rowPadding": dec(row_pad)}}],
    }


def table_vco(alt, title, title_size=None):
    vco = base_vco(alt, pad())
    vco["title"] = title_vco(title, title_size)
    vco["subTitle"] = [{"properties": {"show": flag(False)}}]
    # Style preset mặc định đè lên màu ô mình tự đặt; phải tắt hẳn.
    vco["stylePreset"] = [{"properties": {"name": q("None")}}]
    return vco


def data_table(page, key, vtype, rect, roles, z, title, alt, sort=None, filters=None,
               row_pad=2, size=9, extra=None, totals=True, title_size=None):
    qs = {r: projections(items) for r, items in roles.items()}
    body = {"visualType": vtype, "query": {"queryState": qs}}
    if sort:
        body["query"]["sortDefinition"] = sort
    objs = table_style(row_pad, size)
    if not totals:
        objs["total"] = [{"properties": {"totals": flag(False)}}]
    if extra:
        objs.update(extra)
    body["objects"] = objs
    return container(page, key, rect, z, body, table_vco(alt, title, title_size), filters)


# ---------------------------------------------------------------- dải masthead và chân trang
KICKER = "GIÁM SÁT DANH MỤC CHO VAY TIÊU DÙNG"


def chrome(page, H):
    """Tám phần tử lặp lại ở cả 4 trang: kicker, điều hướng, tên trang kèm dek,
    hai slicer, hai kẻ ngang, ghi chú chân trang. Toạ độ cố định, không thuộc lưới
    nội dung. Tên trang, dek và LƯU Ý lấy từ headlines."""
    out = [
        rule(page, "rule_header", (24, 144, 1232, 2), 100, INK),
        rule(page, "rule_footer", (24, 616, 1232, 2), 110, GREY_L),
        textbox(page, "kicker", (24, 16, 400, 24),
                [para([run(KICKER, 9, FONT_BODY_SB, MUSTARD, weight="bold")])],
                200, alt="Dòng nhận diện báo cáo."),
        textbox(page, "masthead", (24, 48, 608, 88), [
            para([run(H["title"], 28, FONT_DISPLAY, INK, weight="bold")]),
            # Dek dài hơn khoảng 170 ký tự thì cỡ 10 tràn quá hai dòng của khung: hạ về 9.
            para([run(H["dek"], 10 if len(H["dek"]) <= 170 else 9, FONT_BODY, STONE)]),
        ], 210, alt="Tên trang: " + H["title"]),
        slicer(page, "sl_channel", "Dim Channel", "Kênh", "KÊNH BÁN",
               (648, 56, 296, 80), 220, "Bộ lọc kênh bán, lọc đồng thời mọi visual trên trang."),
        slicer(page, "sl_product", "Dim Product", "Sản phẩm", "LOẠI SẢN PHẨM",
               (960, 56, 296, 80), 230, "Bộ lọc loại sản phẩm, lọc đồng thời mọi visual trên trang."),
        navigator(page, "nav", (648, 16, 608, 32), 240, "Điều hướng giữa bốn trang của báo cáo."),
        textbox(page, "caveat", (24, 624, 1232, 88), [
            para([run("LƯU Ý   ", 8, FONT_BODY_SB, MUSTARD, weight="bold"),
                  run(H["caveat"], 8, FONT_BODY, STONE)])
        ], 900, alt="Ghi chú cảnh báo của trang."),
    ]
    return out


HL = headlines.texts(headlines.build())
PAGE_DEFS = []

# ================================================================ TRANG 1
# Executive Summary, variant A Hero-Right.
H1 = HL[1]
V1 = H1["visuals"]
p1 = "ReportSection" + hid("page", "tong-quan")[:24]
v1 = chrome(p1, H1)

R_KPIS = region(1, 3, 9, 5)
R_HERO = region(9, 3, 13, 7)
R_DRIVERS = region(1, 5, 9, 11)
R_WATCH = region(9, 7, 13, 11)

# Hai thẻ tỷ lệ tính trên CÙNG một tập: hợp đồng có dư nợ proxy.
KPIS = [
    ("Open Loans", "HỢP ĐỒNG ĐANG MỞ", "Tổng số hợp đồng đang mở tại tháng quan sát gần nhất."),
    ("Rate 30+ Exposure Known", "TỶ LỆ 30+ THEO HỢP ĐỒNG",
     "Tỷ lệ hợp đồng đang quá hạn trên 30 ngày, trong tập hợp đồng có dư nợ proxy."),
    ("Open Exposure", "DƯ NỢ PROXY ĐANG MỞ", "Tổng dư nợ proxy của các hợp đồng đang mở."),
    ("Exposure Rate 30+", "TỶ LỆ 30+ THEO DƯ NỢ",
     "Tỷ lệ dư nợ đang quá hạn trên 30 ngày, cùng tập với thẻ tỷ lệ theo hợp đồng."),
]
for i, (m, label, alt) in enumerate(KPIS):
    v1.append(card(p1, "kpi%d" % i, "Snapshot", m, label, slot(R_KPIS, i, 4), 1000 + i, alt))

v1.append(chart(
    p1, "bucket_mix", "clusteredBarChart", R_HERO,
    {"Category": [("Snapshot", "dpd_bucket", "col")],
     "Y": [("Snapshot", "Open Loans", "meas")]},
    1100, V1["bucket_mix"],
    "Biểu đồ thanh số hợp đồng ở phần đuôi quá hạn B1 đến B4 (đã bỏ B0 Current để phần đuôi "
    "đọc được). Nhóm B1 1-30 lớn nhất và được tô mustard.",
    objects={
        # Thứ tự bucket là thứ tự có nghĩa (dpd_bucket sortByColumn dpd_bucket_order),
        # nên KHÔNG sắp xếp theo giá trị.
        "dataPoint": points(GREY, [("Snapshot", "dpd_bucket", HL_P1_BUCKET, MUSTARD)]),
        "categoryAxis": axis(True, 9),
        "valueAxis": axis(False, 9),
        # Đơn vị hiển thị Auto (0D) chọn một đơn vị chung cho cả chuỗi theo giá trị
        # lớn nhất, nên số lớn thành "1K" còn 63, 40, 56 thành "0K". Dùng None (1D)
        # để nhãn hiện số nguyên đầy đủ.
        "labels": datalabels(9, units=1),
        "legend": no_legend(),
    },
    # Bỏ B0 Current: nó chiếm 99,2% và ép bốn thanh đuôi về gần 0, màu nhấn không còn thấy.
    # Tỷ trọng B0 đã nói ở dek; bản HTML vẽ thêm một thanh 100% cho phần này.
    filters=[exclude("Snapshot", "dpd_bucket", "B0 Current", p1 + "|bucket_mix")]))

v1.append(chart(
    p1, "rate_by_channel", "clusteredBarChart", R_DRIVERS,
    {"Category": [("Dim Channel", "Kênh", "col")],
     "Y": [("Snapshot", "Rate 30+ Coincident", "meas")]},
    1200, V1["rate_by_channel"],
    "Biểu đồ thanh tỷ lệ quá hạn 30+ hiện tại theo kênh bán, sắp xếp giảm dần, đã loại nhóm "
    "(không rõ). Credit and cash offices đứng đầu và được tô mustard.",
    objects={
        "dataPoint": points(GREY, [("Dim Channel", "Kênh", HL_P1_CHANNEL, MUSTARD)]),
        "categoryAxis": axis(True, 9),
        "valueAxis": axis(False, 9),
        "labels": datalabels(9),
        "legend": no_legend(),
    },
    sort=sort_by_measure("Snapshot", "Rate 30+ Coincident"),
    filters=[exclude("Dim Channel", "Kênh", UNKNOWN, p1 + "|rate_by_channel")]))

v1.append(data_table(
    p1, "product_table", "tableEx", R_WATCH,
    {"Values": [("Dim Product", "Sản phẩm", "col"),
                ("Snapshot", "Open Loans", "meas"),
                ("Snapshot", "Loans 30+", "meas"),
                ("Snapshot", "Rate 30+ Coincident", "meas")]},
    1300, V1["product_table"],
    "Bảng số hợp đồng mở, số hợp đồng 30+ và tỷ lệ 30+ theo loại sản phẩm, gồm cả nhóm (không rõ), "
    "sắp xếp giảm dần theo tỷ lệ.",
    sort=sort_by_measure("Snapshot", "Rate 30+ Coincident"), row_pad=0))

PAGE_DEFS.append((p1, H1["tab"], v1))

# ================================================================ TRANG 2
# Comparative Benchmark, variant A Side-by-Side.
H2 = HL[2]
V2 = H2["visuals"]
p2 = "ReportSection" + hid("page", "kenh-ban")[:24]
v2 = chrome(p2, H2)

# Bố cục 2 cột. Trellis (3 ô sản phẩm, mỗi ô 6 thanh kênh) bên trái cao đủ 8 hàng:
# Power BI ép mỗi thanh danh mục tối thiểu khoảng 26px và thuộc tính
# categoryAxis.preferredCategoryWidth không hạ được ngưỡng đó trong small multiples.
# Bảng SMR và bảng duyệt xếp chồng bên phải, mỗi khối 4 hàng.
R_MIX = region(1, 3, 7, 11)
R_HEADLINE = region(7, 3, 13, 7)
R_CONTEXT = region(7, 7, 13, 11)

v2.append(chart(
    # barChart là thanh ngang XẾP CHỒNG: mỗi kênh chỉ có một trong hai measure trình bày
    # (Highlight hoặc Base) nên mỗi thanh vẫn là một thanh, đúng vị trí.
    p2, "mix_trellis", "barChart", R_MIX,
    {"Category": [("Dim Channel", "Kênh", "col")],
     "Y": [("Vintage", "Highlight Ever 30 Plus MOB12", "meas", "Contact center và Stone"),
           ("Vintage", "Base Ever 30 Plus MOB12", "meas", "Kênh khác")],
     "Rows": [("Dim Product", "Sản phẩm", "col")]},
    1100, V2["mix_trellis"],
    "Ba ô nhỏ, mỗi ô một loại sản phẩm, dùng chung thang trục giá trị: tỷ lệ từng 30+ tại MOB 12 "
    "theo kênh. Contact center và Stone được tô mustard; chênh lệch lớn nhất nằm ở thẻ quay vòng.",
    objects={
        "dataPoint": measure_colors("Vintage", [("Highlight Ever 30 Plus MOB12", MUSTARD),
                                                ("Base Ever 30 Plus MOB12", GREY)]),
        "categoryAxis": axis(True, 9),
        "valueAxis": shared_value_axis(),
        "smallMultiplesLayout": sm_layout(1, 3),
        "subheader": sm_header(),
        "labels": datalabels(8),
        "legend": no_legend(),
    },
    # Kênh Khác có mẫu số dưới 1.000 ở hai trong ba sản phẩm, một ca lẻ kéo giãn thang chung.
    filters=[exclude("Dim Product", "Sản phẩm", UNKNOWN, p2 + "|mix_trellis"),
             exclude("Dim Channel", "Kênh", [UNKNOWN, OTHER_CHANNEL], p2 + "|mix_trellis|channel")]))

v2.append(data_table(
    p2, "smr", "tableEx", R_HEADLINE,
    {"Values": [("Dim Channel", "Kênh", "col"),
                ("Vintage", "Ever 30 Plus Loans MOB12", "meas"),
                ("Vintage", "SMR MOB12", "meas", "SMR chỉ SP"),
                ("Vintage", "Expected 30 Plus MOB12 Cohort", "meas", "Kỳ vọng SP × đợt"),
                ("Vintage", "SMR MOB12 Cohort", "meas", "SMR SP × đợt"),
                ("Vintage", "SMR MOB12 Cohort CI Low", "meas", "Cận dưới"),
                ("Vintage", "SMR MOB12 Cohort CI High", "meas", "Cận trên"),
                ("Vintage", "SMR MOB12 Few Cases Note", "meas", "Ghi chú")]},
    1200, V2["smr"],
    "Bảng SMR theo kênh tại MOB 12: số ca quan sát, SMR chỉ chuẩn hoá theo sản phẩm, số ca kỳ vọng "
    "và SMR khi chuẩn hoá theo sản phẩm × đợt mở 12 tháng kèm khoảng tin cậy 95%, sắp giảm dần theo "
    "SMR sản phẩm × đợt; kênh dưới 5 ca quan sát xếp cuối, ghi chú quá ít ca, không kết luận.",
    # Khoá 1: ghi chú tăng dần (trống trước, kênh dưới 5 ca xuống cuối); khoá 2: SMR giảm dần.
    sort={"sort": [{"field": fmeas("Vintage", "SMR MOB12 Few Cases Note"), "direction": "Ascending"},
                   {"field": fmeas("Vintage", "SMR MOB12 Cohort"), "direction": "Descending"}],
          "isDefaultSort": True},
    filters=[exclude("Dim Channel", "Kênh", UNKNOWN, p2 + "|smr")],
    row_pad=0, size=8, totals=False, title_size=11))

v2.append(data_table(
    p2, "approval", "tableEx", R_CONTEXT,
    {"Values": [("Dim Channel", "Kênh", "col"),
                ("Funnel", "Applications", "meas"),
                ("Funnel", "Approval Rate", "meas"),
                ("Funnel", "Approval Standardized Ratio", "meas"),
                ("Funnel", "Take-up Rate Consumer", "meas")]},
    1300, V2["approval"],
    "Bảng phễu duyệt theo kênh: số hồ sơ, tỷ lệ duyệt thô, tỷ số duyệt so với kỳ vọng theo cơ cấu "
    "sản phẩm và take-up của vay tiêu dùng.",
    sort=sort_by_measure("Funnel", "Applications"),
    filters=[exclude("Dim Channel", "Kênh", UNKNOWN, p2 + "|approval")],
    row_pad=0, size=8, totals=False))

PAGE_DEFS.append((p2, H2["tab"], v2))

# ================================================================ TRANG 3
# Analytical Canvas, variant C Small-Multiples-Grid.
H3 = HL[3]
V3 = H3["visuals"]
p3 = "ReportSection" + hid("page", "vintage")[:24]
v3 = chrome(p3, H3)

# Hàng trên: vintage theo đợt mở (visual chính của trang), theo sản phẩm và bảng độ
# nhạy tỷ số. Hàng dưới: trellis 7 kênh trải hết bề ngang, hẹp hơn thì ô quá dẹt.
R_COHORT = region(1, 3, 6, 7)
R_PRODUCT = region(6, 3, 9, 7)
R_SENS = region(9, 3, 13, 7)
R_TRELLIS = region(1, 7, 13, 11)
HL_P3_COHORT = "-96 đến -85"  # đợt cũ nhất, trùng scripts/build_dashboard.py
YOUNG_COHORT = "-12 đến -1"   # chỉ có MOB 0, không thành đường

v3.append(chart(
    p3, "cohort", "lineChart", R_COHORT,
    {"Category": [("Vintage", "mob", "col")],
     "Series": [("Vintage", "origination_cohort", "col")],
     "Y": [("Vintage", "Cohort Ever 30 Plus Rate", "meas")]},
    1000, V3["cohort"],
    "Bảy đường vintage, mỗi đường một đợt mở 12 tháng, chỉ vẽ MOB mà cả đợt đã đủ tuổi, sản phẩm có nhãn. "
    "Đợt cũ nhất -96 đến -85 tô mustard, nằm cao nhất; các đợt gần hơn thấp dần.",
    objects={
        "dataPoint": points(GREY_L, [("Vintage", "origination_cohort", HL_P3_COHORT, MUSTARD)]),
        "lineStyles": [{"properties": {"strokeWidth": dec(2), "showMarker": flag(False)}}],
        "categoryAxis": axis(True, 9, "MOB, số tháng kể từ khi mở hợp đồng"),
        "valueAxis": axis(True, 9),
        "legend": [{"properties": {
            "show": flag(True), "position": q("Top"), "showTitle": flag(False),
            "fontFamily": q(FONT_BODY), "fontSize": dec(7), "labelColor": solid(STONE)}}],
        "labels": [{"properties": {"show": flag(False)}}],
    },
    filters=[exclude("Dim Product", "Sản phẩm", UNKNOWN, p3 + "|cohort"),
             exclude("Vintage", "origination_cohort", YOUNG_COHORT, p3 + "|cohort|young")],
    title_size=11))

v3.append(chart(
    p3, "trellis", "lineChart", R_TRELLIS,
    {"Category": [("Vintage", "mob", "col")],
     # Hai measure trình bày: ô Contact center chỉ có Highlight (mustard), ô khác chỉ có Base.
     # Không dùng Series trùng Rows: Desktop báo lỗi "Data shapes must contain at least one group".
     "Y": [("Vintage", "Base Ever 30 Plus Rate", "meas", "Kênh khác"),
           ("Vintage", "Highlight Ever 30 Plus Rate", "meas", "Contact center")],
     "Rows": [("Dim Channel", "Kênh", "col")]},
    1100, V3["trellis"],
    "Bảy ô nhỏ, mỗi ô một kênh bán, cùng thang trục giá trị. Trục ngang là MOB, trục dọc là tỷ lệ "
    "từng quá hạn 30 ngày trở lên. Contact center tô mustard, cao nhất ở mọi MOB.",
    objects={
        "dataPoint": measure_colors("Vintage", [("Base Ever 30 Plus Rate", INK),
                                                ("Highlight Ever 30 Plus Rate", MUSTARD)]),
        "lineStyles": [{"properties": {"strokeWidth": dec(2), "showMarker": flag(False)}}],
        "categoryAxis": axis(True, 8),
        "valueAxis": shared_value_axis(),
        "smallMultiplesLayout": sm_layout(2, 4),
        "subheader": sm_header(),
        "legend": no_legend(),
        "labels": [{"properties": {"show": flag(False)}}],
    },
    filters=[exclude("Dim Channel", "Kênh", UNKNOWN, p3 + "|trellis")],
    title_size=11))

v3.append(chart(
    p3, "by_product", "lineChart", R_PRODUCT,
    {"Category": [("Vintage", "mob", "col")],
     "Series": [("Dim Product", "Sản phẩm", "col")],
     "Y": [("Vintage", "Ever 30 Plus Rate", "meas")]},
    1200, V3["by_product"],
    "Ba đường vintage theo loại sản phẩm. Thẻ quay vòng tô mustard, tách xa hai đường còn lại; "
    "vay tiền mặt và vay tiêu dùng gần như trùng nhau.",
    objects={
        "dataPoint": points(GREY, [
            ("Dim Product", "Sản phẩm", HL_P3_PRODUCT, MUSTARD),
            ("Dim Product", "Sản phẩm", "Cash loans", STONE),
            ("Dim Product", "Sản phẩm", "Consumer loans", GREY_L)]),
        "lineStyles": [{"properties": {"strokeWidth": dec(2), "showMarker": flag(False)}}],
        "categoryAxis": axis(True, 9, "MOB, số tháng kể từ khi mở hợp đồng"),
        "valueAxis": axis(True, 9),
        "legend": [{"properties": {
            "show": flag(True), "position": q("Top"), "showTitle": flag(False),
            "fontFamily": q(FONT_BODY), "fontSize": dec(9), "labelColor": solid(STONE)}}],
        "labels": [{"properties": {"show": flag(False)}}],
    },
    filters=[exclude("Dim Product", "Sản phẩm", UNKNOWN, p3 + "|by_product")],
    title_size=11))

v3.append(data_table(
    p3, "sensitivity", "tableEx", R_SENS,
    {"Values": [("Dim Product", "Sản phẩm", "col"),
                ("Vintage", "Ratio vs Cash Crude", "meas"),
                ("Vintage", "Ratio vs Cash MH Cohort", "meas"),
                ("Vintage", "Ratio vs Cash Due Only", "meas"),
                ("Vintage", "Ratio vs Cash No Threshold", "meas")]},
    1300, V3["sensitivity"],
    "Bảng độ nhạy tại MOB 12: tỷ số tỷ lệ từng 30+ của thẻ quay vòng và vay tiêu dùng so với vay "
    "tiền mặt theo bốn cách đo: định nghĩa chính, kiểm soát đợt mở, định nghĩa giữa, không áp ngưỡng.",
    sort=sort_by_measure("Vintage", "Ratio vs Cash Crude"),
    filters=[exclude("Dim Product", "Sản phẩm", [UNKNOWN, "Cash loans"], p3 + "|sensitivity")],
    row_pad=0, size=8, totals=False, title_size=9))

PAGE_DEFS.append((p3, H3["tab"], v3))

# ================================================================ TRANG 4
# Operational Monitor, variant C Incident-First.
H4 = HL[4]
V4 = H4["visuals"]
p4 = "ReportSection" + hid("page", "roll-rate")[:24]
v4 = chrome(p4, H4)

R_QUEUE = region(1, 3, 13, 7)
R_CURE = region(1, 7, 7, 11)
R_SCALE = region(7, 7, 13, 11)

v4.append(data_table(
    p4, "matrix", "pivotTable", R_QUEUE,
    {"Rows": [("RollRate", "from_state", "col")],
     "Columns": [("RollRate", "to_state", "col")],
     "Values": [("RollRate", "Roll Rate", "meas")]},
    1100, V4["matrix"],
    "Ma trận chuyển nhóm: dòng là nhóm quá hạn tháng này, cột là nhóm tháng sau. Hơn một nửa B1 "
    "quay về B0 Current, rất ít rơi tiếp sang B2.",
    extra={"rowHeaders": [{"properties": {
        "fontFamily": q(FONT_BODY_SB), "fontSize": dec(9), "fontColor": solid(INK),
        "backColor": solid(CREAM)}}]}))

v4.append(chart(
    p4, "cure", "clusteredBarChart", R_CURE,
    {"Category": [("RollRate", "from_state", "col")],
     "Y": [("RollRate", "Cure Rate", "meas")]},
    1200, V4["cure"],
    "Biểu đồ thanh cure rate theo nhóm quá hạn xuất phát, đã bỏ B0 Current. B1 1-30 tô mustard; "
    "B3 61-90 tô xám nhạt vì dưới ngưỡng mẫu.",
    objects={
        "dataPoint": points(GREY, [("RollRate", "from_state", HL_P4_FROM, MUSTARD),
                                   ("RollRate", "from_state", THIN_P4_FROM, GREY_L)]),
        "categoryAxis": axis(True, 9),
        "valueAxis": axis(False, 9),
        "labels": datalabels(9),
        "legend": no_legend(),
    },
    filters=[exclude("RollRate", "from_state", "B0 Current", p4 + "|cure")]))

v4.append(data_table(
    p4, "roll_tbl", "tableEx", R_SCALE,
    {"Values": [("RollRate", "from_state", "col"),
                ("RollRate", "Roll Base Loans", "meas"),
                ("RollRate", "Cure Rate", "meas"),
                ("RollRate", "Exposure From", "meas")]},
    1300, V4["roll_tbl"],
    "Bảng số lượt hợp đồng-tháng, cure rate và dư nợ proxy cộng dồn của từng nhóm xuất phát. "
    "Dòng B0 không có cure.",
    # Measure trong model để formatString #,##0 nên hiện số rất dài. Xử lý ở tầng
    # visual: columnFormatting theo selector metadata (queryRef của cột), đơn vị
    # hiển thị tỷ (1000000000D) và 1 chữ số thập phân để nhóm B2 đến B4 còn đọc được.
    extra={"columnFormatting": [{
        "properties": {"labelDisplayUnits": lit("1000000000D"),
                       "labelPrecision": lit("1D")},
        "selector": {"metadata": "RollRate.Exposure From"}}]}))

PAGE_DEFS.append((p4, H4["tab"], v4))


# ---------------------------------------------------------------- ghi ra đĩa
def write_all():
    # Mỗi lần chạy xoá sạch cả pages/ lẫn RegisteredResources/ rồi ghi lại từ đầu, để
    # không còn sót file theme cũ không ai tham chiếu (mỗi lần đổi nội dung theme thì
    # tên file đổi hậu tố, bản cũ sẽ nằm lại nếu không dọn).
    for stale in (PAGES, RESOURCES):
        if stale.exists():
            shutil.rmtree(stale)

    order = []
    for pname, disp, visuals in PAGE_DEFS:
        jw(PAGES / pname / "page.json", {
            "$schema": SCHEMA_PAGE, "name": pname, "displayName": disp,
            "displayOption": "FitToPage", "height": 720, "width": 1280,
            # Page background không có thuộc tính show, nó luôn hiện. Thêm show vào
            # là schema từ chối.
            "objects": {
                "background": [{"properties": {"color": solid(CREAM), "transparency": dec(0)}}],
                "outspace": [{"properties": {"color": solid(CREAM2), "transparency": dec(0)}}],
            }})
        for vname, vjson in visuals:
            jw(PAGES / pname / "visuals" / vname / "visual.json", vjson)
        order.append(pname)

    jw(PAGES / "pages.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": order, "activePageName": order[0]})

    jw(DEF / "version.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0"})

    jw(DEF / "report.json", {
        "$schema": SCHEMA_RPT,
        "themeCollection": {"customTheme": {
            "name": THEME_NAME,
            # reportVersionAtImport là bắt buộc dù tài liệu trình bày nó như tuỳ chọn;
            # thiếu trường này thì validate báo lỗi schema và Desktop có thể không nạp.
            "reportVersionAtImport": {"visual": "2.9.0", "report": "3.3.0", "page": "2.1.0"},
            "type": "RegisteredResources"}},
        "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources",
                              "items": [{"name": THEME_NAME, "path": THEME_NAME, "type": "CustomTheme"}]}],
        # Thu gọn panel Filters khi mở báo cáo. Mọi bộ lọc người đọc cần đã có sẵn dạng
        # slicer trên trang; để panel bung ra thì nó chiếm khoảng 1/5 bề ngang và lọt vào
        # mọi ảnh chụp. Vẫn giữ visible để ai cần thì tự bung ra.
        "objects": {"outspacePane": [{"properties": {"expanded": lit("false")}}]},
        "settings": {"useStylableVisualContainerHeader": True, "defaultFilterActionIsDataFilter": True,
                     "useEnhancedTooltips": False}})

    jw(RPT / "definition.pbir", {"$schema": SCHEMA_PBIR, "version": "4.0",
                                 "datasetReference": {"byPath": {"path": "../CreditPortfolio.SemanticModel"}}})

    jw(RPT / ".platform", {"$schema": SCHEMA_PLAT,
                           "metadata": {"type": "Report", "displayName": "CreditPortfolio"},
                           "config": {"version": "2.0", "logicalId": "b4f6a1c2-90de-4f31-8a77-2c5e9d1b3a08"}})

    jw(ROOT / "powerbi" / "CreditPortfolio.pbip", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0",
        "artifacts": [{"report": {"path": "CreditPortfolio.Report"}}],
        "settings": {"enableAutoRecovery": True}})

    # ------------------------------------------------------------ theme
    # Tông Editorial Newsroom. dataColors là một thang mực-xám có mustard ở slot 5:
    # biểu đồ nhiều chuỗi lấy 4 màu đầu (toàn xám) làm nền, còn mustard được gán
    # tường minh bằng dataPoint.fill cho đúng phần tử mang thông điệp.
    jw(RESOURCES / THEME_NAME, {
        "name": THEME_NAME,
        "dataColors": [INK, STONE, GREY, GREY_L, MUSTARD, "#78716C", "#A8A29E", "#E0D8C9"],
        "good": "#4D7C0F", "neutral": MUSTARD, "bad": "#9A3412",
        "maximum": INK, "center": GREY, "minimum": "#F0EADC", "null": "#E0D8C9",
        "background": CREAM,
        "secondaryBackground": CREAM2,
        "firstLevelElements": INK,
        "secondLevelElements": STONE,
        "thirdLevelElements": RULE,
        "fourthLevelElements": "#8A817A",
        "tableAccent": INK,
        "textClasses": {
            "callout": {"fontSize": 32, "fontFace": FONT_BODY_SB, "color": INK},
            "title": {"fontSize": 13, "fontFace": FONT_DISPLAY, "color": INK},
            "header": {"fontSize": 10, "fontFace": FONT_BODY_SB, "color": INK},
            "label": {"fontSize": 9, "fontFace": FONT_BODY, "color": STONE}},
        "visualStyles": {
            # Không viền, không nền, không thanh chrome: nền kem xuyên qua mọi visual,
            # cấu trúc do hai kẻ ngang mảnh và khoảng trắng gánh.
            "*": {"*": {
                "background": [{"show": False}],
                "border": [{"show": False}],
                "visualHeader": [{"show": False}]}},
            "tableEx": {"*": {"columnHeaders": [
                {"autoSizeColumnWidth": True, "columnAdjustment": "growToFit"}]}},
            "pivotTable": {"*": {"columnHeaders": [
                {"autoSizeColumnWidth": True, "columnAdjustment": "growToFit"}]}},
            "page": {"*": {
                "background": [{"color": {"solid": {"color": CREAM}}, "transparency": 0}],
                "outspace": [{"color": {"solid": {"color": CREAM2}}}]}}}})

    print("pages:", len(order), "| visuals:", sum(len(v) for _, _, v in PAGE_DEFS))
    print("theme:", THEME_NAME)


if __name__ == "__main__":
    write_all()
