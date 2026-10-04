# -*- coding: utf-8 -*-
"""Sinh phan Report (PBIR) cua PBIP: theme Editorial Newsroom, 4 trang, visual.

Ban thiet ke chinh thuc nam o powerbi/_brief/report-spec.md, khoi YAML
"Design Brief:". File nay chi dich khoi do ra JSON, khong tu quyet dinh gi them.

Ba dieu khong duoc doi neu khong doc ky truoc:

1. Phien ban schema PBIR. Co tinh dung ban Microsoft DA PUBLISH, khong dung ban
   ma Power BI Desktop 2.157 tu ghi ra (visualContainer 2.12.0, report 3.4.0,
   page 2.3.1). Ban moi hon tra ve HTTP 404 tren developer.microsoft.com, nen
   powerbi-report-author khong tai duoc va BO QUA han lop kiem JSON Schema.
   Giu ban cu de con lop kiem do; chinh no da bat duoc loi thieu
   reportVersionAtImport khi dung project nay. He qua: moi lan mo Desktop, no
   nang URL schema len va git hien diff. Diff do vo hai.

2. ID trang va visual sinh bang SHA-1 cua "trang|khoa" chu khong ngau nhien,
   nen chay lai cho ra dung ID cu va git diff chi hien phan that su doi.

3. Ten file theme phai doi hau to moi lan sua noi dung theme. Desktop cache
   theme theo ten file, giu nguyen ten thi sua xong reload van ra mau cu.

4. FONT_DISPLAY KHONG duoc doi lai thanh Georgia. Xem chu thich ngay tai hang
   khai bao FONT_DISPLAY.
"""
import json, hashlib, pathlib, shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent
RPT = ROOT / "powerbi" / "CreditPortfolio.Report"
DEF = RPT / "definition"
PAGES = DEF / "pages"
RESOURCES = RPT / "StaticResources" / "RegisteredResources"
# Moi lan chay xoa sach ca pages/ lan RegisteredResources/ roi ghi lai tu dau, de
# khong con sot file theme cu khong ai tham chieu (moi lan doi noi dung theme thi
# ten file doi hau to, ban cu se nam lai neu khong don).
for stale in (PAGES, RESOURCES):
    if stale.exists():
        shutil.rmtree(stale)

SCHEMA_VIS = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json"
SCHEMA_PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
SCHEMA_RPT = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json"
SCHEMA_PBIR = "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json"
SCHEMA_PLAT = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"

THEME_NAME = "CreditPortfolio-Editorial-9c4f2a68.json"

# ---------------------------------------------------------------- bang mau
# Tong Editorial Newsroom: nen kem, muc den, DUNG MOT mau nhan mustard.
CREAM = "#FAF7F0"   # nen trang
CREAM2 = "#F0EADC"  # nen ngoai canvas
INK = "#0F172A"     # chu chinh, chuoi du lieu chinh
STONE = "#5C5349"   # chu phu, xam dam
GREY = "#938A7F"    # mang du lieu nen
GREY_L = "#C2B9AC"  # mang du lieu nen nhat
RULE = "#E3DACB"    # ke ngang trong bang
MUSTARD = "#D4A30A"  # mau nhan duy nhat

# Font tieu de serif. TUYET DOI KHONG dung Georgia: file font Georgia THIEU 19 ky
# tu tieng Viet thuong gap: ấ ầ ẩ ẫ ậ ế ề ể ễ ệ ố ồ ổ ỗ ộ ơ ư ớ ứ.
# Khi thieu glyph, Windows ghep dau roi len ky tu goc, nen "gấp" hien thanh "gâ´p",
# "lần" thanh "lâ`n", "xếp" thanh "xê´p", "hồi" thanh "hô`i", "dốc" thanh "dô´c",
# "nhất" thanh "nhâ´t". Da kiem bang ma (cmap) cua tung font: Cambria, Times New
# Roman, Constantia, Palatino Linotype deu du ca 19 ky tu; Cambria giu chat serif
# editorial tot nhat nen chon Cambria. Muon doi font thi phai kiem lai 19 ky tu tren.
FONT_DISPLAY = "Cambria"
FONT_BODY = "Segoe UI"
FONT_BODY_SB = "Segoe UI Semibold"

# ---------------------------------------------------------------- luoi 12x12
# Cot: le 24, be ngang dung duoc 1232, 12 cot rong 88, ranh 16 -> buoc 104.
# Hang noi dung: bat dau y=160, 8 hang cao 56, ranh 16 -> buoc 56.
# Vung [c1, r1, c2, r2] theo kieu 1-indexed, bien phai va duoi la mo (exclusive).
MARGIN, COL_PITCH, ROW_PITCH, GUTTER = 24, 104, 56, 16
CONTENT_Y0 = 160
ROW_FIRST = 3  # hang 1-2 cua luoi la dai masthead, noi dung bat dau o hang 3


def region(c1, r1, c2, r2):
    """Doi toa do luoi sang (x, y, w, h) pixel. Moi gia tri chia het cho 8."""
    x = MARGIN + (c1 - 1) * COL_PITCH
    w = (c2 - c1) * COL_PITCH - GUTTER
    y = CONTENT_Y0 + (r1 - ROW_FIRST) * ROW_PITCH
    h = (r2 - r1) * ROW_PITCH - GUTTER
    return x, y, w, h


def slot(rect, i, n, gap=GUTTER):
    """Chia mot vung thanh n o bang nhau theo chieu ngang, lay o thu i (0-based)."""
    x, y, w, h = rect
    cw = (w - gap * (n - 1)) // n
    return x + i * (cw + gap), y, cw, h


# ---------------------------------------------------------------- tien ich JSON
def jw(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")


def hid(*parts):
    """ID hex on dinh (tai tao duoc) thay vi ngau nhien, de diff git sach."""
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:20]


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def q(v):
    """Chuoi trong PBIR: boc nhay don, nhay don trong chuoi thi nhan doi."""
    return lit("'" + str(v).replace("'", "''") + "'")


def dec(v):
    return lit("%sD" % v)


def flag(v):
    return lit("true" if v else "false")


def solid(hex_color):
    return {"solid": {"color": q(hex_color)}}


# ---------------------------------------------------------------- bieu thuc field
def fcol(table, column):
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": column}}


def fmeas(table, measure):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": table}}, "Property": measure}}


# Ten hien thi tieng Viet dat o tang PBIR (projection.displayName), KHONG dung toi
# model. Khoa la ten that trong model; queryRef va nativeQueryRef van giu ten goc nen
# selector metadata, sort va filter khong bi anh huong. Cot/measure khong co trong
# bang nay thi giu ten model (cac cot dim da la tieng Viet san: Kênh, Sản phẩm).
DISPLAY = {
    # Snapshot (trang 1)
    "dpd_bucket": "Nhóm quá hạn",
    "Open Loans": "Số hợp đồng mở",
    "Rate 30+ Coincident": "Tỷ lệ 30+ hiện tại",
    # Funnel (trang 2)
    "Applications": "Số hồ sơ",
    "Approval Rate": "Tỷ lệ duyệt",
    "Take-up Rate": "Tỷ lệ nhận vay",
    # Vintage (trang 2, 3)
    "Ever 30 Plus MOB12": "Từng 30+ tại MOB 12",
    "Vintage Loans MOB12": "Mẫu số tại MOB 12",
    "Ever 30 Plus Rate": "Tỷ lệ từng 30+",
    "mob": "MOB",
    # RollRate (trang 4)
    "from_state": "Nhóm xuất phát",
    "to_state": "Nhóm đến",
    "Roll Rate": "Tỷ lệ chuyển nhóm",
    "Roll Base Loans": "Số lượt hợp đồng-tháng",
    "Cure Rate": "Cure rate",
    "Exposure From": "Dư nợ xuất phát",
}


def proj(table, name, kind):
    f = fcol(table, name) if kind == "col" else fmeas(table, name)
    out = {"field": f, "queryRef": "{}.{}".format(table, name), "nativeQueryRef": name}
    if name in DISPLAY:
        out["displayName"] = DISPLAY[name]
    return out


def scope_sel(table, column, value):
    """Selector tro dung mot gia tri cua mot cot. Chi ComparisonKind 0 duoc honor."""
    return {"data": [{"scopeId": {"Comparison": {
        "ComparisonKind": 0,
        "Left": fcol(table, column),
        "Right": {"Literal": {"Value": "'" + str(value).replace("'", "''") + "'"}}}}}]}


def sort_by_measure(table, measure, direction="Descending"):
    return {"sort": [{"field": fmeas(table, measure), "direction": direction}], "isDefaultSort": True}


def sort_by_column(table, column, direction="Descending"):
    return {"sort": [{"field": fcol(table, column), "direction": direction}], "isDefaultSort": True}


def exclude(table, column, value, seed):
    """Bo loc muc visual: loai bo dung mot gia tri.

    Trong filter.Where, SourceRef dung "Source" (alias khai bao o From), KHONG
    dung "Entity"; o truong field ngoai cung thi nguoc lai. Sai cho nay thi bo
    loc im lang khong chay.
    """
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
                "Values": [[{"Literal": {"Value": "'" + str(value).replace("'", "''") + "'"}}]],
            }}}}}],
        },
        "howCreated": "User",
    }


UNKNOWN = "(không rõ)"

# ---------------------------------------------------------------- dung visual
# 15 khoa VCO dung chung cho moi loai visual. Danh sach nay de loc objects nao
# thuoc visualContainerObjects, con lai roi vao objects (dinh dang rieng tung loai).
VCO_KEYS = {"title", "subTitle", "divider", "spacing", "background", "padding",
            "lockAspect", "general", "border", "dropShadow", "visualLink",
            "visualTooltip", "stylePreset", "visualHeader", "visualHeaderTooltip"}


def pad(t=8, b=8, l=8, r=8):
    """Khai bao bat ky VCO nao la Power BI bo padding ke thua tu theme va dat ve 0.
    Vi vay moi visual trong bao cao nay deu khai bao padding tuong minh."""
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


def container(page, key, vtype, rect, z, visual_body, vco, filters=None):
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
          sort=None, filters=None, padding=None):
    """roles: {'RoleName': [(table, field, 'col'|'meas'), ...]}"""
    qs = {r: {"projections": [proj(t, f, k) for t, f, k in items]} for r, items in roles.items()}
    body = {"visualType": vtype, "query": {"queryState": qs}}
    if sort:
        body["query"]["sortDefinition"] = sort
    if objects:
        body["objects"] = objects
    vco = base_vco(alt, padding)
    # Dat title thi Power BI tu sinh them mot phu de ghep ten field. Tat no di,
    # neu khong moi bieu do se co hai dong chu chong nhau.
    vco["title"] = [{"properties": {"show": flag(True), "text": q(title),
                                    "fontColor": solid(INK)}}]
    vco["subTitle"] = [{"properties": {"show": flag(False)}}]
    return container(page, key, vtype, rect, z, body, vco, filters)


def textbox(page, key, rect, paragraphs, z, alt=None):
    body = {"visualType": "textbox",
            "objects": {"general": [{"properties": {"paragraphs": paragraphs}}]}}
    vco = base_vco(alt, pad(0, 0, 0, 0))
    return container(page, key, "textbox", rect, z, body, vco)


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
    """Ke ngang manh. Phai dung shape chu khong dung textbox: textbox bi Desktop
    ep chieu cao toi thieu khoang 24px bat ke position.height ghi gi."""
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
    return container(page, key, "shape", rect, z, body, vco)


def card(page, key, table, measure, label, rect, z, alt):
    """The KPI. Ba luu y:

    - Moi object cua cardVisual deu can selector {"id": "default"}; thieu selector
      thi thuoc tinh validate sach nhung khong co tac dung nao.
    - Dung nhan rieng cua card (label.text) chu khong dat title o container:
      dat title thi no hien SONG SONG voi nhan mac dinh va hai dong chu de len nhau.
    - Nhan mang luon ngu canh (mau so) de the khong chi la mot con so tran.
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
        # Ke ngang manh tren dinh moi the: chu ky S10 ap vao the KPI.
        "accentBar": [{"properties": {
            "show": flag(True), "position": q("Top"),
            "color": solid(INK), "width": dec(2), "transparency": dec(0)}, "selector": sel}],
    }
    body = {"visualType": "cardVisual",
            "query": {"queryState": {"Data": {"projections": [proj(table, measure, "meas")]}}},
            "objects": objects}
    # padding cua cardVisual la VCO va can selector {"id": "default"}; thieu
    # selector thi no validate sach nhung khong co tac dung nao.
    card_pad = {"top": dec(10), "bottom": dec(4), "left": dec(0), "right": dec(8)}
    vco = base_vco(alt, [{"properties": card_pad},
                         {"properties": card_pad, "selector": {"id": "default"}}])
    vco["title"] = [{"properties": {"show": flag(False)}}]
    vco["subTitle"] = [{"properties": {"show": flag(False)}}]
    return container(page, key, "cardVisual", rect, z, body, vco)


def slicer(page, key, table, column, header, rect, z, alt):
    """Slicer dropdown. Chieu cao 80 = 60 chrome + 8 + 8 padding, theo cong thuc
    sizing trong references/authoring/slicers.md. Khong duoc ha xuong 48 hay thu
    nho font de 'vua khung': lam the chi giau phan bi cat."""
    body = {"visualType": "slicer",
            "query": {"queryState": {"Values": {"projections": [proj(table, column, "col")]}}},
            "objects": {
                "data": [{"properties": {"mode": q("Dropdown")}}],
                # slicer dung "textSize" chu khong phai "fontSize" nhu cac visual khac
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
    return container(page, key, "slicer", rect, z, body, vco)


def navigator(page, key, rect, z, alt):
    """Dieu huong 4 trang. Sua anti-pattern 'Multi-page report without navigation'.

    pageNavigator thuoc nhom visual can MOT cap entry: mot entry khong selector
    va mot entry co selector id. Trang dang mo nhan gach chan mustard."""
    def states(props_by_state):
        out = []
        base = props_by_state.get("default", {})
        out.append({"properties": base})
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
    return container(page, key, "pageNavigator", rect, z, body, vco)


# ---------------------------------------------------------------- manh dinh dang dung lai
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


def datalabels(size=9, units=0, precision=None):
    p = {"show": flag(True), "fontFamily": q(FONT_BODY), "fontSize": dec(size),
         "color": solid(INK), "labelDisplayUnits": lit("%dD" % units)}
    if precision is not None:
        p["labelPrecision"] = lit("%dD" % precision)
    return [{"properties": p}]


def points(default_color, highlights=()):
    """S6 Highlight-and-grey: mot mau nen cho tat ca, roi tra mau mustard cho
    dung phan tu mang thong diep. Tren bieu do mot chuoi phai dung defaultColor
    lam nen; dung fill khong selector thi cot bien mat."""
    out = [{"properties": {"defaultColor": solid(default_color)}}]
    for table, column, value, color in highlights:
        out.append({"properties": {"fill": solid(color)},
                    "selector": scope_sel(table, column, value)})
    return out


def table_style(row_pad=2, size=9):
    """Bang va ma tran: chi ke ngang, khong ke doc, nen o trung nen trang."""
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


def table_vco(alt, title):
    vco = base_vco(alt, pad())
    vco["title"] = [{"properties": {"show": flag(True), "text": q(title),
                                    "fontColor": solid(INK)}}]
    vco["subTitle"] = [{"properties": {"show": flag(False)}}]
    # Style preset mac dinh de len mau o do minh tu dat; phai tat han.
    vco["stylePreset"] = [{"properties": {"name": q("None")}}]
    return vco


def data_table(page, key, vtype, rect, roles, z, title, alt, sort=None, filters=None,
               row_pad=2, size=9, extra=None):
    qs = {r: {"projections": [proj(t, f, k) for t, f, k in items]} for r, items in roles.items()}
    body = {"visualType": vtype, "query": {"queryState": qs}}
    if sort:
        body["query"]["sortDefinition"] = sort
    objs = table_style(row_pad, size)
    if extra:
        objs.update(extra)
    body["objects"] = objs
    return container(page, key, vtype, rect, z, body, table_vco(alt, title), filters)


# ---------------------------------------------------------------- dai masthead va chan trang
KICKER = "GIÁM SÁT DANH MỤC CHO VAY TIÊU DÙNG"


def chrome(page, title, dek, caveat):
    """Bay phan tu lap lai o ca 4 trang: kicker, dieu huong, ten trang, hai slicer,
    hai ke ngang, ghi chu chan trang. Toa do co dinh, khong thuoc luoi noi dung."""
    out = []
    out.append(rule(page, "rule_header", (24, 144, 1232, 2), 100, INK))
    out.append(rule(page, "rule_footer", (24, 616, 1232, 2), 110, GREY_L))
    out.append(textbox(page, "kicker", (24, 16, 400, 24),
                       [para([run(KICKER, 9, FONT_BODY_SB, MUSTARD, weight="bold")])],
                       200, alt="Dòng nhận diện báo cáo."))
    out.append(textbox(page, "masthead", (24, 48, 608, 88), [
        para([run(title, 28, FONT_DISPLAY, INK, weight="bold")]),
        para([run(dek, 11, FONT_BODY, STONE)]),
    ], 210, alt="Tên trang: " + title))
    out.append(slicer(page, "sl_channel", "Dim Channel", "Kênh", "KÊNH BÁN",
                      (648, 56, 296, 80), 220,
                      "Bộ lọc kênh bán, lọc đồng thời mọi visual trên trang."))
    out.append(slicer(page, "sl_product", "Dim Product", "Sản phẩm", "LOẠI SẢN PHẨM",
                      (960, 56, 296, 80), 230,
                      "Bộ lọc loại sản phẩm, lọc đồng thời mọi visual trên trang."))
    out.append(navigator(page, "nav", (648, 16, 608, 32), 240,
                         "Điều hướng giữa bốn trang của báo cáo."))
    out.append(textbox(page, "caveat", (24, 632, 1232, 48), [
        para([run("LƯU Ý   ", 9, FONT_BODY_SB, MUSTARD, weight="bold"),
              run(caveat, 9, FONT_BODY, STONE)])
    ], 900, alt="Ghi chú cảnh báo của trang."))
    return out


PAGE_DEFS = []

# ================================================================ TRANG 1
# Executive Summary, variant A Hero-Right.
p1 = "ReportSection" + hid("page", "tong-quan")[:24]
v1 = chrome(
    p1,
    "Tổng quan danh mục",
    "98,65% danh mục vẫn sạch, nhưng đuôi B4 90+ đông gấp ba lần B2 và B3 cộng lại",
    "Ảnh chụp tại tháng quan sát gần nhất của từng hợp đồng. Tỷ lệ 30+ ở đây là coincident, "
    "đo tại một thời điểm, khác với tỷ lệ vintage theo tuổi hợp đồng ở trang 3. Biểu đồ xếp hạng "
    "kênh đã lọc bỏ nhóm (không rõ) vì nhóm đó không biết được phân khúc; bốn thẻ KPI vẫn tính đủ danh mục.")

R_KPIS = region(1, 3, 9, 5)
R_HERO = region(9, 3, 13, 7)
R_DRIVERS = region(1, 5, 9, 11)
R_WATCH = region(9, 7, 13, 11)

KPIS = [
    ("Open Loans", "HỢP ĐỒNG ĐANG MỞ", "Tổng số hợp đồng đang mở tại tháng quan sát gần nhất."),
    ("Rate 30+ Coincident", "TỶ LỆ 30+ THEO HỢP ĐỒNG", "Tỷ lệ hợp đồng đang quá hạn từ 30 ngày trở lên."),
    ("Open Exposure", "DƯ NỢ PROXY ĐANG MỞ", "Tổng dư nợ proxy của các hợp đồng đang mở."),
    ("Exposure Rate 30+", "TỶ LỆ 30+ THEO DƯ NỢ", "Tỷ lệ dư nợ đang quá hạn từ 30 ngày trở lên."),
]
for i, (m, label, alt) in enumerate(KPIS):
    v1.append(card(p1, "kpi%d" % i, "Snapshot", m, label, slot(R_KPIS, i, 4), 1000 + i, alt))

BUCKET_COLORS = [("B0 Current", GREY_L), ("B1 1-30", GREY), ("B2 31-60", STONE),
                 ("B3 61-90", INK), ("B4 90+", MUSTARD)]
v1.append(chart(
    p1, "bucket_mix", "clusteredBarChart", R_HERO,
    {"Category": [("Snapshot", "dpd_bucket", "col")],
     "Y": [("Snapshot", "Open Loans", "meas")]},
    1100,
    "B4 90+ đông gấp ba lần B2 và B3 gộp",
    "Biểu đồ thanh cơ cấu danh mục theo nhóm quá hạn: B0 Current 142.474 hợp đồng, "
    "B1 1.362, B2 89, B3 58, B4 438. Nhóm B4 90+ được tô mustard.",
    objects={
        # Thu tu bucket la thu tu co nghia (dpd_bucket sortByColumn dpd_bucket_order),
        # nen KHONG sap xep theo gia tri.
        "dataPoint": points(GREY_L, [("Snapshot", "dpd_bucket", val, col)
                                     for val, col in BUCKET_COLORS]),
        "categoryAxis": axis(True, 9),
        "valueAxis": axis(False, 9),
        # Don vi hien thi Auto (0D) chon mot don vi chung cho ca chuoi theo gia tri
        # lon nhat, nen 142.474 thanh "142K" con 89, 58, 438 thanh "0K". Dung None (1D)
        # de nhan hien so nguyen day du.
        "labels": datalabels(9, units=1),
        "legend": [{"properties": {"show": flag(False)}}],
    }))

v1.append(chart(
    p1, "rate_by_channel", "clusteredBarChart", R_DRIVERS,
    {"Category": [("Dim Channel", "Kênh", "col")],
     "Y": [("Snapshot", "Rate 30+ Coincident", "meas")]},
    1200,
    "Stone dẫn đầu tỷ lệ 30+ hiện tại, 0,55% so với 0,23% của Credit and cash offices",
    "Biểu đồ thanh tỷ lệ quá hạn 30+ hiện tại theo kênh bán, sắp xếp giảm dần. "
    "Stone 0,55% đứng đầu và được tô mustard, Khác 0,00% thấp nhất.",
    objects={
        "dataPoint": points(GREY, [("Dim Channel", "Kênh", "Stone", MUSTARD)]),
        "categoryAxis": axis(True, 9),
        "valueAxis": axis(False, 9),
        "labels": datalabels(9),
        "legend": [{"properties": {"show": flag(False)}}],
    },
    sort=sort_by_measure("Snapshot", "Rate 30+ Coincident"),
    filters=[exclude("Dim Channel", "Kênh", UNKNOWN, p1 + "|rate_by_channel")]))

v1.append(data_table(
    p1, "product_table", "tableEx", R_WATCH,
    {"Values": [("Dim Product", "Sản phẩm", "col"),
                ("Snapshot", "Open Loans", "meas"),
                ("Snapshot", "Rate 30+ Coincident", "meas")]},
    1300,
    "Tỷ lệ 30+ theo loại sản phẩm",
    "Bảng quy mô và tỷ lệ quá hạn 30+ theo loại sản phẩm, sắp xếp giảm dần theo tỷ lệ.",
    sort=sort_by_measure("Snapshot", "Rate 30+ Coincident")))

PAGE_DEFS.append((p1, "1. Tổng quan", v1))

# ================================================================ TRANG 2
# Comparative Benchmark, variant A Side-by-Side.
p2 = "ReportSection" + hid("page", "kenh-ban")[:24]
v2 = chrome(
    p2,
    "Kênh bán và rủi ro",
    "Khoảng cách thô 8,1 lần giữa các kênh co lại còn 2,0 và 4,4 lần khi so trong cùng sản phẩm",
    "Khoảng cách thô 8,1 lần giữa Stone và Credit and cash offices phần lớn là nhiễu cơ cấu sản phẩm; "
    "so trong cùng sản phẩm chỉ còn 2,0 lần (vay tiêu dùng trả góp) và 4,4 lần (vay tiền mặt). "
    "FPD30 không dùng làm trục rủi ro vì thiên lệch sống sót, vùng mù 77.885 hồ sơ. Ba visual đã lọc bỏ nhóm (không rõ).")

# Bo cuc 2 cot. Trellis (3 o san pham, moi o 7 thanh kenh) ben trai cao du 8 hang:
# Power BI ep moi thanh danh muc toi thieu khoang 26px va thuoc tinh
# categoryAxis.preferredCategoryWidth khong ha duoc nguong do trong small multiples,
# nen 7 thanh can ~182px chi rieng vung ve. O cao 4 hang (208) chi chua duoc 3 kenh
# va hien thanh cuon doc, lam hong muc dich so sanh. Scatter va bang pheu xep chong
# ben phai, moi khoi 4 hang.
R_MIX = region(1, 3, 7, 11)
R_HEADLINE = region(7, 3, 13, 7)
R_CONTEXT = region(7, 7, 13, 11)

v2.append(chart(
    p2, "scatter", "scatterChart", R_HEADLINE,
    {"Category": [("Dim Channel", "Kênh", "col")],
     "X": [("Funnel", "Approval Rate", "meas")],
     "Y": [("Vintage", "Ever 30 Plus MOB12", "meas")],
     "Size": [("Funnel", "Applications", "meas")]},
    1200,
    "Duyệt rộng, rủi ro cao: Stone duyệt 89,8%, xấu nhất 1,07%",
    "Biểu đồ phân tán, trục ngang tỷ lệ duyệt, trục dọc tỷ lệ từng quá hạn 30+ tại MOB 12, "
    "kích thước bong bóng theo số hồ sơ. Stone ở góc trên phải và được tô mustard; "
    "Credit and cash offices duyệt 66,4% và chỉ 0,13%.",
    objects={
        "dataPoint": points(GREY, [("Dim Channel", "Kênh", "Stone", MUSTARD)]),
        "categoryAxis": axis(True, 9, "Tỷ lệ duyệt"),
        "valueAxis": axis(True, 9, "Từng 30+ tại MOB 12"),
        "categoryLabels": [{"properties": {
            "show": flag(True), "fontFamily": q(FONT_BODY), "fontSize": dec(9),
            "color": solid(STONE)}}],
        "legend": [{"properties": {"show": flag(False)}}],
    },
    filters=[exclude("Dim Channel", "Kênh", UNKNOWN, p2 + "|scatter")]))

v2.append(data_table(
    p2, "funnel_tbl", "tableEx", R_CONTEXT,
    {"Values": [("Dim Channel", "Kênh", "col"),
                ("Funnel", "Applications", "meas"),
                ("Funnel", "Approval Rate", "meas"),
                ("Funnel", "Take-up Rate", "meas")]},
    1300,
    "Phễu duyệt theo kênh, kèm tỷ lệ khách nhận khoản vay",
    "Bảng số hồ sơ, tỷ lệ duyệt và tỷ lệ khách nhận khoản vay theo từng kênh bán, "
    "sắp xếp giảm dần theo số hồ sơ.",
    sort=sort_by_measure("Funnel", "Applications"),
    filters=[exclude("Dim Channel", "Kênh", UNKNOWN, p2 + "|funnel_tbl")],
    row_pad=0))

v2.append(chart(
    p2, "mix_trellis", "clusteredBarChart", R_MIX,
    {"Category": [("Dim Channel", "Kênh", "col")],
     "Y": [("Vintage", "Ever 30 Plus MOB12", "meas")],
     "Rows": [("Dim Product", "Sản phẩm", "col")]},
    1100,
    "Cùng một sản phẩm, cùng một thang: khoảng cách co lại",
    "Ba ô nhỏ, mỗi ô một loại sản phẩm, dùng chung thang trục giá trị. "
    "Trong vay tiêu dùng trả góp, Stone 1,07% so với Regional / Local 0,53%; "
    "trong vay tiền mặt, Country-wide 0,44% so với Credit and cash offices 0,10%.",
    objects={
        "dataPoint": points(GREY, [("Dim Channel", "Kênh", "Stone", MUSTARD)]),
        "categoryAxis": axis(True, 9),
        # sharedAxis buoc moi o nho dung chung thang truc gia tri. Thieu no la
        # roi vao anti-pattern 'Unshared small-multiple axes': moi o mot thang,
        # nhin thi giong nhau nhung khong so duoc.
        "valueAxis": [{"properties": {
            "show": flag(True), "sharedAxis": flag(True), "gridlineShow": flag(False),
            "showAxisTitle": flag(False), "fontFamily": q(FONT_BODY),
            "fontSize": dec(8), "labelColor": solid(STONE)}}],
        "smallMultiplesLayout": [{"properties": {
            "layoutType": q("custom"), "rowCount": lit("1L"), "columnCount": lit("3L"),
            "gridLineShow": flag(False), "gridPadding": dec(8)}}],
        "subheader": [{"properties": {
            "show": flag(True), "fontFamily": q(FONT_BODY_SB), "fontSize": dec(9),
            "fontColor": solid(INK), "position": q("top")}}],
        "legend": [{"properties": {"show": flag(False)}}],
    },
    sort=sort_by_measure("Vintage", "Ever 30 Plus MOB12"),
    filters=[exclude("Dim Product", "Sản phẩm", UNKNOWN, p2 + "|mix_trellis")]))

PAGE_DEFS.append((p2, "2. Kênh bán", v2))

# ================================================================ TRANG 3
# Analytical Canvas, variant C Small-Multiples-Grid.
p3 = "ReportSection" + hid("page", "vintage")[:24]
v3 = chrome(
    p3,
    "Vintage theo MOB",
    "So cùng tuổi hợp đồng: vay tiêu dùng trả góp xấu gấp bảy lần vay tiền mặt tại MOB 12",
    "Mẫu số vintage đã loại hợp đồng có cờ is_partial_history. Đuôi MOB cao duỗi dần vì số hợp đồng "
    "quan sát đủ giảm đi, không phải vì rủi ro dừng lại, nên đọc kèm cột mẫu số tại MOB 12. "
    "Ba visual đã lọc bỏ nhóm (không rõ), nhóm có tỷ lệ 6,72% và sẽ kéo lệch thang trục dùng chung.")

R_TRELLIS = region(1, 3, 13, 7)
R_PRODUCT = region(1, 7, 7, 11)
R_RANK = region(7, 7, 13, 11)

v3.append(chart(
    p3, "trellis", "lineChart", R_TRELLIS,
    {"Category": [("Vintage", "mob", "col")],
     "Y": [("Vintage", "Ever 30 Plus Rate", "meas")],
     "Rows": [("Dim Channel", "Kênh", "col")]},
    1100,
    "Bảy kênh trên cùng một thang: Stone và Country-wide dựng dốc sớm nhất",
    "Bảy ô nhỏ, mỗi ô một kênh bán, cùng thang trục giá trị. Trục ngang là MOB từ 0 đến 37, "
    "trục dọc là tỷ lệ từng quá hạn 30 ngày trở lên. Stone và Country-wide dựng dốc trong "
    "mười hai tháng đầu rồi đi ngang.",
    objects={
        "dataPoint": [{"properties": {"defaultColor": solid(INK)}}],
        "lineStyles": [{"properties": {"strokeWidth": dec(2), "showMarker": flag(False)}}],
        "categoryAxis": axis(True, 8),
        "valueAxis": [{"properties": {
            "show": flag(True), "sharedAxis": flag(True), "gridlineShow": flag(False),
            "showAxisTitle": flag(False), "fontFamily": q(FONT_BODY),
            "fontSize": dec(8), "labelColor": solid(STONE)}}],
        "smallMultiplesLayout": [{"properties": {
            "layoutType": q("custom"), "rowCount": lit("2L"), "columnCount": lit("4L"),
            "gridLineShow": flag(False), "gridPadding": dec(8)}}],
        "subheader": [{"properties": {
            "show": flag(True), "fontFamily": q(FONT_BODY_SB), "fontSize": dec(9),
            "fontColor": solid(INK), "position": q("top")}}],
        "legend": [{"properties": {"show": flag(False)}}],
        "labels": [{"properties": {"show": flag(False)}}],
    },
    filters=[exclude("Dim Channel", "Kênh", UNKNOWN, p3 + "|trellis")]))

v3.append(chart(
    p3, "by_product", "lineChart", R_PRODUCT,
    {"Category": [("Vintage", "mob", "col")],
     "Series": [("Dim Product", "Sản phẩm", "col")],
     "Y": [("Vintage", "Ever 30 Plus Rate", "meas")]},
    1200,
    "Vay tiêu dùng trả góp xấu gấp bảy lần vay tiền mặt tại MOB 12",
    "Ba đường vintage theo loại sản phẩm. Consumer loans tô mustard đạt 0,89% tại MOB 12, "
    "Revolving loans 0,68%, Cash loans 0,13%.",
    objects={
        "dataPoint": points(GREY, [
            ("Dim Product", "Sản phẩm", "Consumer loans", MUSTARD),
            ("Dim Product", "Sản phẩm", "Revolving loans", STONE),
            ("Dim Product", "Sản phẩm", "Cash loans", GREY_L)]),
        "lineStyles": [{"properties": {"strokeWidth": dec(2), "showMarker": flag(False)}}],
        "categoryAxis": axis(True, 9, "MOB, số tháng kể từ khi mở hợp đồng"),
        "valueAxis": axis(True, 9),
        "legend": [{"properties": {
            "show": flag(True), "position": q("Top"), "showTitle": flag(False),
            "fontFamily": q(FONT_BODY), "fontSize": dec(9), "labelColor": solid(STONE)}}],
        "labels": [{"properties": {"show": flag(False)}}],
    },
    filters=[exclude("Dim Product", "Sản phẩm", UNKNOWN, p3 + "|by_product")]))

v3.append(data_table(
    p3, "rank_tbl", "tableEx", R_RANK,
    {"Values": [("Dim Channel", "Kênh", "col"),
                ("Vintage", "Ever 30 Plus MOB12", "meas"),
                ("Vintage", "Vintage Loans MOB12", "meas")]},
    1300,
    "Xếp hạng kênh tại MOB 12, kèm mẫu số ghim cùng ngữ cảnh",
    "Bảng xếp hạng bảy kênh theo tỷ lệ từng quá hạn 30+ tại MOB 12, kèm cột mẫu số "
    "là số hợp đồng quan sát được tại đúng MOB 12.",
    sort=sort_by_measure("Vintage", "Ever 30 Plus MOB12"),
    filters=[exclude("Dim Channel", "Kênh", UNKNOWN, p3 + "|rank_tbl")],
    row_pad=0))

PAGE_DEFS.append((p3, "3. Vintage", v3))

# ================================================================ TRANG 4
# Operational Monitor, variant C Incident-First.
p4 = "ReportSection" + hid("page", "roll-rate")[:24]
v4 = chrome(
    p4,
    "Chuyển nhóm và thu hồi",
    "Cửa sổ thu hồi đóng lại sau B1: cure rate rơi từ 50,1% xuống 7,0% chỉ sau hai nhóm",
    "Cure rate rơi từ 50,1% ở B1 xuống 7,0% ở B3, nên can thiệp thu hồi phải dồn vào B1. "
    "Biểu đồ cure đã lọc bỏ dòng B0 Current vì B0 về B0 không phải là cure. Mẫu số dùng measure "
    "[Roll Base Loans], KHÔNG cộng cột n_from vì n_from là window sum lặp lại trên mỗi dòng bucket đến.")

R_QUEUE = region(1, 3, 13, 7)
R_CURE = region(1, 7, 7, 11)
R_SCALE = region(7, 7, 13, 11)

v4.append(data_table(
    p4, "matrix", "pivotTable", R_QUEUE,
    {"Rows": [("RollRate", "from_state", "col")],
     "Columns": [("RollRate", "to_state", "col")],
     "Values": [("RollRate", "Roll Rate", "meas")]},
    1100,
    "Từ nhóm quá hạn tháng t (dòng) sang nhóm tháng t+1 (cột)",
    "Ma trận chuyển nhóm: dòng là nhóm quá hạn tháng này, cột là nhóm tháng sau. "
    "B1 1-30 có 50,1% quay về B0 Current và 38,5% ở lại B1.",
    extra={"rowHeaders": [{"properties": {
        "fontFamily": q(FONT_BODY_SB), "fontSize": dec(9), "fontColor": solid(INK),
        "backColor": solid(CREAM)}}]}))

v4.append(chart(
    p4, "cure", "clusteredBarChart", R_CURE,
    {"Category": [("RollRate", "from_state", "col")],
     "Y": [("RollRate", "Cure Rate", "meas")]},
    1200,
    "Cửa sổ thu hồi đóng nhanh: 50,1% ở B1 còn 7,0% ở B3",
    "Biểu đồ thanh cure rate theo nhóm quá hạn xuất phát, đã bỏ B0 Current. "
    "B1 1-30 đạt 50,1% và được tô mustard, B2 17,3%, B3 7,0%, B4 2,0%.",
    objects={
        "dataPoint": points(GREY, [("RollRate", "from_state", "B1 1-30", MUSTARD)]),
        "categoryAxis": axis(True, 9),
        "valueAxis": axis(False, 9),
        "labels": datalabels(9),
        "legend": [{"properties": {"show": flag(False)}}],
    },
    filters=[exclude("RollRate", "from_state", "B0 Current", p4 + "|cure")]))

v4.append(data_table(
    p4, "roll_tbl", "tableEx", R_SCALE,
    {"Values": [("RollRate", "from_state", "col"),
                ("RollRate", "Roll Base Loans", "meas"),
                ("RollRate", "Cure Rate", "meas"),
                ("RollRate", "Exposure From", "meas")]},
    1300,
    "Mẫu số từng nhóm xuất phát, đặt cạnh cure rate",
    "Bảng số lượt hợp đồng-tháng, cure rate và dư nợ của từng nhóm quá hạn xuất phát. "
    "Cure 7,0% của B3 chỉ dựa trên 7.172 lượt, khác hẳn 259.546 lượt của B1.",
    # Measure trong model de formatString #,##0 nen hien 2,259,476,831,810. Xu ly o
    # tang visual: columnFormatting theo selector metadata (queryRef cua cot), don vi
    # hien thi ty (1000000000D) va 1 chu so thap phan de nhom B2 ... B4 con doc duoc.
    extra={"columnFormatting": [{
        "properties": {"labelDisplayUnits": lit("1000000000D"),
                       "labelPrecision": lit("1D")},
        "selector": {"metadata": "RollRate.Exposure From"}}]}))

PAGE_DEFS.append((p4, "4. Thu hồi", v4))

# ---------------------------------------------------------------- ghi ra dia
order = []
for pname, disp, visuals in PAGE_DEFS:
    jw(PAGES / pname / "page.json", {
        "$schema": SCHEMA_PAGE, "name": pname, "displayName": disp,
        "displayOption": "FitToPage", "height": 720, "width": 1280,
        # Page background khong co thuoc tinh show, no luon hien. Them show vao
        # la schema tu choi.
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
        # reportVersionAtImport la bat buoc du tai lieu trinh bay no nhu tuy chon;
        # thieu truong nay thi validate bao loi schema va Desktop co the khong nap.
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

# ---------------------------------------------------------------- theme
# Tong Editorial Newsroom. dataColors la mot thang mu c-xam co mustard o slot 5:
# bieu do nhieu chuoi lay 4 mau dau (toan xam) lam nen, con mustard duoc gan
# tuong minh bang dataPoint.fill cho dung phan tu mang thong diep.
jw(RPT / "StaticResources" / "RegisteredResources" / THEME_NAME, {
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
        # Khong vien, khong nen, khong thanh chrome: nen kem xuyen qua moi visual,
        # cau truc do hai ke ngang manh va khoang trang ganh.
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
