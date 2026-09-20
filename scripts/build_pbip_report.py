# -*- coding: utf-8 -*-
"""Sinh phần Report (PBIR) của PBIP: theme, 4 trang, visual."""
import json, hashlib, pathlib, shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent
RPT  = ROOT / "powerbi" / "CreditPortfolio.Report"
DEF  = RPT / "definition"
PAGES = DEF / "pages"
if PAGES.exists():
    shutil.rmtree(PAGES)

SCHEMA_VIS  = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json"
SCHEMA_PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
SCHEMA_RPT  = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json"
SCHEMA_PBIR = "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json"
SCHEMA_PLAT = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"

THEME_NAME = "CreditPortfolio-7c1a9e3b.json"

# Phiên bản schema PBIR: cố tình dùng bản Microsoft ĐÃ PUBLISH, không dùng bản mà
# Power BI Desktop 2.157 tự ghi ra (visualContainer 2.12.0, report 3.4.0, page 2.3.1).
# Bản mới hơn trả về HTTP 404 trên developer.microsoft.com, nên powerbi-report-author
# không tải được và BỎ QUA hẳn lớp kiểm JSON Schema. Giữ bản cũ để còn lớp kiểm đó
# (chính nó đã bắt được lỗi thiếu reportVersionAtImport khi dựng project này).
# Hệ quả: mỗi lần mở Desktop, nó nâng URL schema lên và git hiện diff. Diff đó vô hại,
# commit hay bỏ đều được.

def jw(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")

def hid(*parts):
    """ID hex ổn định (tái tạo được) thay vì ngẫu nhiên, để diff git sạch."""
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:20]

# ---------------------------------------------------------------- expressions
def fcol(table, column):
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": column}}

def fmeas(table, measure):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": table}}, "Property": measure}}

def proj(table, name, kind):
    f = fcol(table, name) if kind == "col" else fmeas(table, name)
    return {"field": f, "queryRef": "{}.{}".format(table, name), "nativeQueryRef": name}

def visual(page, key, vtype, x, y, w, h, roles, z, title=None, objects=None, sort=None):
    """roles: {'RoleName': [(table, field, 'col'|'meas'), ...]}"""
    qs = {r: {"projections": [proj(t, f, k) for t, f, k in items]} for r, items in roles.items()}
    v = {"visualType": vtype, "query": {"queryState": qs}}
    if sort:
        v["query"]["sortDefinition"] = sort
    objs = dict(objects or {})
    if title is not None:
        objs["title"] = [{"properties": {
            "text": {"expr": {"Literal": {"Value": "'" + title.replace("'", "''") + "'"}}},
            "show": {"expr": {"Literal": {"Value": "true"}}}}}]
    if objs:
        v["visualContainerObjects"] = {k: val for k, val in objs.items() if k in ("title", "subTitle", "background", "border", "visualHeader")}
        inner = {k: val for k, val in objs.items() if k not in v["visualContainerObjects"]}
        if inner:
            v["objects"] = inner
    name = hid(page, key)
    return name, {"$schema": SCHEMA_VIS, "name": name,
                  "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z},
                  "visual": v}

def textbox(page, key, x, y, w, h, runs, z):
    name = hid(page, key)
    paragraphs = [{"textRuns": runs}]
    return name, {"$schema": SCHEMA_VIS, "name": name,
        "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z},
        "visual": {"visualType": "textbox",
                   "objects": {"general": [{"properties": {"paragraphs": paragraphs}}]}}}

def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def card(page, key, table, measure, label, x, y, w, h, z):
    """Thẻ KPI: dùng nhãn riêng của cardVisual thay vì title của container.

    Đặt title ở container sẽ hiện SONG SONG với nhãn mặc định (tên measure) và
    hai dòng chữ đè lên nhau. Ba object dưới đây đều cần selector {"id": "default"},
    thiếu selector là thuộc tính im lặng không áp dụng.
    """
    sel = {"id": "default"}
    objs = {
        "label": [{"properties": {"show": lit("true"),
                                  "text": lit("'" + label.replace("'", "''") + "'"),
                                  "fontSize": lit("10D"),
                                  "fontColor": {"solid": {"color": lit("'#52514e'")}}},
                   "selector": sel}],
        "value": [{"properties": {"fontSize": lit("28D"),
                                  "fontColor": {"solid": {"color": lit("'#0b0b0b'")}}},
                   "selector": sel}],
        # viền chữ nhật bên trong thẻ, không kế thừa từ theme nên phải tắt ở từng visual
        "outline": [{"properties": {"show": lit("false")}, "selector": sel}],
    }
    return visual(page, key, "cardVisual", x, y, w, h,
                  {"Data": [(table, measure, "meas")]}, z, objects=objs)


def run(text, size=11, bold=False, color=None, italic=False):
    # Desktop ghi fontSize của textbox dạng chuỗi có đơn vị ("16pt"), không phải số
    st = {"fontSize": "%dpt" % size}
    if bold: st["fontWeight"] = "bold"
    if italic: st["fontStyle"] = "italic"
    if color: st["color"] = color
    return {"value": text, "textStyle": st}

# ---------------------------------------------------------------- bố cục chung 1280x720
X0, W_ALL = 24, 1232
Y_TITLE, H_TITLE = 16, 46
Y_SLICER, H_SLICER = 68, 60
Y_KPI, H_KPI = 138, 104
Y_CHART_KPI = 258          # khi trang có hàng KPI
Y_CHART_PLAIN = 138        # khi trang không có hàng KPI
W_HALF, GAP = 608, 16

def head(page, title, sub):
    """Tiêu đề trang + 2 slicer dùng chung, trả về list (name, json)."""
    out = []
    out.append(textbox(page, "title", X0, Y_TITLE, W_ALL, H_TITLE,
        [run(title, 16, bold=True, color="#0b0b0b"), run("   " + sub, 10, color="#898781")], 9000))
    out.append(visual(page, "sl_channel", "slicer", X0, Y_SLICER, 300, H_SLICER,
        {"Values": [("Dim Channel", "Kênh", "col")]}, 8000, title="Kênh bán"))
    out.append(visual(page, "sl_product", "slicer", X0 + 300 + GAP, Y_SLICER, 300, H_SLICER,
        {"Values": [("Dim Product", "Sản phẩm", "col")]}, 8100, title="Loại sản phẩm"))
    return out

def note(page, key, x, y, w, h, text, z=7000):
    return textbox(page, key, x, y, w, h,
                   [run("⚠ ", 11, bold=True, color="#eda100"), run(text, 10, color="#52514e")], z)

PAGE_DEFS = []

# ================================================================ TRANG 1
p1 = "ReportSection" + hid("page", "tong-quan")[:24]
v1 = head(p1, "1. Tổng quan danh mục", "Ảnh chụp tại tháng quan sát gần nhất (M02, M06)")
kpis = [("Snapshot", "Open Loans",          "Hợp đồng đang mở"),
        ("Snapshot", "Rate 30+ Coincident", "Tỷ lệ 30+ hiện tại"),
        ("Snapshot", "Open Exposure",            "Dư nợ proxy"),
        ("Snapshot", "Exposure Rate 30+",   "Tỷ lệ 30+ theo dư nợ")]
W_KPI = (W_ALL - 3 * GAP) // 4
for i, (t, m, label) in enumerate(kpis):
    v1.append(card(p1, "kpi%d" % i, t, m, label,
                   X0 + i * (W_KPI + GAP), Y_KPI, W_KPI, H_KPI, 1000 + i))
v1.append(visual(p1, "buckets", "clusteredBarChart", X0, Y_CHART_KPI, W_HALF, 440,
    {"Category": [("Snapshot", "dpd_bucket", "col")], "Y": [("Snapshot", "Open Loans", "meas")]},
    2000, title="Cơ cấu nhóm quá hạn: phần lớn danh mục vẫn sạch"))
v1.append(visual(p1, "by_product", "clusteredBarChart", X0 + W_HALF + GAP, Y_CHART_KPI, W_HALF, 440,
    {"Category": [("Dim Product", "Sản phẩm", "col")],
     "Series":   [("Snapshot", "dpd_bucket", "col")],
     "Y":        [("Snapshot", "Open Loans", "meas")]},
    2100, title="Cơ cấu bucket theo loại sản phẩm"))
PAGE_DEFS.append((p1, "1. Tổng quan danh mục", v1))

# ================================================================ TRANG 2
p2 = "ReportSection" + hid("page", "kenh-ban")[:24]
v2 = head(p2, "2. Kênh bán: tăng trưởng và rủi ro", "So sánh BẮT BUỘC kiểm soát cơ cấu sản phẩm (M08, M12)")
v2.append(visual(p2, "scatter", "scatterChart", X0, Y_CHART_PLAIN, W_HALF, 396,
    {"Category": [("Dim Channel", "Kênh", "col")],
     "X":        [("Funnel", "Approval Rate", "meas")],
     "Y":        [("Vintage", "Ever 30 Plus MOB12", "meas")],
     "Size":     [("Funnel", "Applications", "meas")]},
    2000, title="Duyệt nhiều có đi kèm rủi ro cao? (bong bóng = số hồ sơ)"))
v2.append(visual(p2, "risk_by_ch", "clusteredBarChart", X0 + W_HALF + GAP, Y_CHART_PLAIN, W_HALF, 396,
    {"Category": [("Dim Channel", "Kênh", "col")],
     "Series":   [("Dim Product", "Sản phẩm", "col")],
     "Y":        [("Vintage", "Ever 30 Plus MOB12", "meas")]},
    2100, title="Ever 30+@MOB12 theo kênh, TÁCH THEO sản phẩm"))
v2.append(visual(p2, "funnel_tbl", "tableEx", X0, 544, W_HALF, 152,
    {"Values": [("Dim Channel", "Kênh", "col"),
                ("Funnel", "Applications", "meas"),
                ("Funnel", "Approval Rate", "meas"),
                ("Funnel", "Take-up Rate", "meas")]},
    2200, title="Phễu duyệt theo kênh"))
v2.append(note(p2, "warn", X0 + W_HALF + GAP, 544, W_HALF, 152,
    "Khoảng cách thô 8 lần giữa Stone và Credit and cash offices phần lớn là nhiễu cơ cấu sản phẩm. "
    "So trong cùng sản phẩm chỉ còn 2,0 lần và 4,4 lần. FPD30 không dùng làm trục rủi ro vì thiên lệch "
    "sống sót (vùng mù 77.885 hồ sơ), trục chính là Ever 30+@MOB12."))
PAGE_DEFS.append((p2, "2. Kênh bán và rủi ro", v2))

# ================================================================ TRANG 3
p3 = "ReportSection" + hid("page", "vintage")[:24]
v3 = head(p3, "3. Vintage: nhóm nào xấu đi nhanh hơn", "Tỷ lệ TỪNG quá hạn 30+ theo tuổi hợp đồng (M08)")
v3.append(visual(p3, "vin_product", "lineChart", X0, Y_CHART_PLAIN, W_HALF, 396,
    {"Category": [("Vintage", "mob", "col")],
     "Series":   [("Dim Product", "Sản phẩm", "col")],
     "Y":        [("Vintage", "Ever 30 Plus Rate", "meas")]},
    2000, title="Đường vintage theo loại sản phẩm"))
v3.append(visual(p3, "vin_channel", "lineChart", X0 + W_HALF + GAP, Y_CHART_PLAIN, W_HALF, 396,
    {"Category": [("Vintage", "mob", "col")],
     "Series":   [("Dim Channel", "Kênh", "col")],
     "Y":        [("Vintage", "Ever 30 Plus Rate", "meas")]},
    2100, title="Đường vintage theo kênh bán"))
v3.append(visual(p3, "vin_tbl", "tableEx", X0, 544, W_HALF, 152,
    {"Values": [("Dim Channel", "Kênh", "col"),
                ("Vintage", "Ever 30 Plus MOB12", "meas"),
                ("Vintage", "Vintage Loans MOB12", "meas")]},
    2200, title="Xếp hạng kênh tại MOB 12"))
v3.append(note(p3, "warn", X0 + W_HALF + GAP, 544, W_HALF, 152,
    "Mẫu số vintage đã loại hợp đồng có cờ dim_loan.is_partial_history. Đường cong duỗi dần ở MOB cao "
    "vì số hợp đồng quan sát đủ giảm đi, không phải vì rủi ro dừng lại. Đọc kèm cột Vintage Loans MOB12 để biết mẫu số."))
PAGE_DEFS.append((p3, "3. Vintage", v3))

# ================================================================ TRANG 4
p4 = "ReportSection" + hid("page", "roll-rate")[:24]
v4 = head(p4, "4. Chuyển nhóm và thu hồi", "Ma trận roll rate giữa hai tháng liền kề (M09, M10)")
v4.append(visual(p4, "matrix", "pivotTable", X0, Y_CHART_PLAIN, W_HALF, 396,
    {"Rows":    [("RollRate", "from_state", "col")],
     "Columns": [("RollRate", "to_state", "col")],
     "Values":  [("RollRate", "Roll Rate", "meas")]},
    2000, title="Từ bucket tháng t (dòng) sang bucket tháng t+1 (cột)"))
v4.append(visual(p4, "cure", "clusteredBarChart", X0 + W_HALF + GAP, Y_CHART_PLAIN, W_HALF, 396,
    {"Category": [("RollRate", "from_state", "col")],
     "Y":        [("RollRate", "Cure Rate", "meas")]},
    2100, title="Cure rate rơi rất nhanh theo độ sâu quá hạn"))
v4.append(visual(p4, "roll_tbl", "tableEx", X0, 544, W_HALF, 152,
    {"Values": [("RollRate", "from_state", "col"),
                ("RollRate", "Roll Base Loans", "meas"),
                ("RollRate", "Cure Rate", "meas"),
                ("RollRate", "Exposure From", "meas")]},
    2200, title="Quy mô từng bucket xuất phát"))
v4.append(note(p4, "warn", X0 + W_HALF + GAP, 544, W_HALF, 152,
    "Cure rate rơi từ 50,1% ở B1 xuống 7,0% ở B3: can thiệp thu hồi phải dồn vào B1. "
    "Đọc cure rate thì lọc bỏ dòng from_state = B0 Current, vì B0 về B0 không phải là cure. "
    "Mẫu số dùng measure [Roll Base Loans], KHÔNG cộng cột n_from."))
PAGE_DEFS.append((p4, "4. Chuyển nhóm và thu hồi", v4))

# ---------------------------------------------------------------- ghi ra đĩa
order = []
for pname, disp, visuals in PAGE_DEFS:
    jw(PAGES / pname / "page.json", {
        "$schema": SCHEMA_PAGE, "name": pname, "displayName": disp,
        "displayOption": "FitToPage", "height": 720, "width": 1280})
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
    "themeCollection": {"customTheme": {"name": THEME_NAME, "reportVersionAtImport": {"visual": "2.9.0", "report": "3.3.0", "page": "2.1.0"}, "type": "RegisteredResources"}},
    "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources",
        "items": [{"name": THEME_NAME, "path": THEME_NAME, "type": "CustomTheme"}]}],
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
print("pages:", len(order), "| visuals:", sum(len(v) for _, _, v in PAGE_DEFS))

# ---------------------------------------------------------------- theme
# Bảng màu lấy nguyên từ PALETTES["light"] trong scripts/build_dashboard.py
# để báo cáo Power BI và dashboard/index.html nhìn như một hệ.
jw(RPT / "StaticResources" / "RegisteredResources" / THEME_NAME, {
    "name": THEME_NAME,
    "dataColors": ["#2a78d6", "#eb6834", "#1baf7a", "#5598e7", "#1c5cab",
                   "#86b6ef", "#104281", "#c98500"],
    "good": "#1baf7a", "neutral": "#eda100", "bad": "#eb6834",
    "maximum": "#104281", "center": "#5598e7", "minimum": "#e8f1fc", "null": "#e1e0d9",
    "background": "#fcfcfb",
    "secondaryBackground": "#f9f9f7",
    "firstLevelElements": "#0b0b0b",
    "secondLevelElements": "#52514e",
    "thirdLevelElements": "#e1e0d9",
    "fourthLevelElements": "#898781",
    "tableAccent": "#2a78d6",
    "textClasses": {
        "callout": {"fontSize": 32, "fontFace": "Segoe UI Semibold", "color": "#0b0b0b"},
        "title":   {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": "#0b0b0b"},
        "header":  {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": "#0b0b0b"},
        "label":   {"fontSize": 10, "fontFace": "Segoe UI", "color": "#0b0b0b"}},
    "visualStyles": {
        "*": {"*": {
            "background": [{"show": True, "color": {"solid": {"color": "#fcfcfb"}}, "transparency": 0}],
            "border":     [{"show": True, "color": {"solid": {"color": "#e1e0d9"}}, "radius": 6}],
            "visualHeader": [{"show": False}]}},
        "page": {"*": {"background": [{"color": {"solid": {"color": "#f9f9f7"}}, "transparency": 0}],
                       "outspace":   [{"color": {"solid": {"color": "#f9f9f7"}}}]}}}})
print("theme:", THEME_NAME)
