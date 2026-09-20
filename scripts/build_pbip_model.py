# -*- coding: utf-8 -*-
"""Sinh phần SemanticModel (TMDL) của PBIP cho project credit-portfolio-monitoring."""
import json, os, uuid, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PBI  = ROOT / "powerbi"
SM   = PBI / "CreditPortfolio.SemanticModel"
DEF  = SM / "definition"
T    = DEF / "tables"
for d in (T,):
    d.mkdir(parents=True, exist_ok=True)

def w(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    print("wrote", path.relative_to(ROOT))

# ---------------------------------------------------------------- .platform
w(SM / ".platform", json.dumps({
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
    "metadata": {"type": "SemanticModel", "displayName": "CreditPortfolio"},
    "config": {"version": "2.0", "logicalId": str(uuid.uuid4())},
}, indent=2, ensure_ascii=False))

w(SM / "definition.pbism", json.dumps({
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
    "version": "4.2",
    "settings": {"qnaEnabled": True},
}, indent=2))

# ---------------------------------------------------------------- database / model
w(DEF / "database.tmdl", "database CreditPortfolio\n\tcompatibilityLevel: 1550\n")

w(DEF / "model.tmdl", """model Model
\tculture: en-US
\tdefaultPowerBIDataSourceVersion: powerBI_V3
\tsourceQueryCulture: en-US

ref table 'Dim Channel'
ref table 'Dim Product'
ref table Funnel
ref table FPD
ref table Vintage
ref table RollRate
ref table Snapshot
""")

# ---------------------------------------------------------------- tham số đường dẫn
w(DEF / "expressions.tmdl", '''/// Thư mục chứa 5 file CSV xuất từ mart (scripts/build_dashboard.py và scripts/export_snapshot.py).
/// Đổi giá trị này nếu clone repo về máy khác.
expression DataFolder = "{}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]
'''.format(str(ROOT / "data" / "export").replace("\\", "\\\\")))

# ---------------------------------------------------------------- helper M
def partition(table, csvname, typed):
    """Sinh partition M đọc 1 file CSV trong DataFolder."""
    cols = ", ".join('{{"{}", {}}}'.format(c, t) for c, t in typed)
    # Không vá nhãn phân khúc ở tầng model. Ba nhãn '(không rõ)', 'Unknown' và
    # 'Khác' khác nghĩa nhau và do tầng mart quyết định (xem sql/mart/*.sql).
    # Vá ở đây sẽ che mất lỗi mart và làm hai tầng nói hai chuyện khác nhau.
    last = '#"Đã ép kiểu dữ liệu từng cột"'
    tail = "\n"
    return (
        "\tpartition {t} = m\n"
        "\t\tmode: import\n"
        "\t\tsource =\n"
        "\t\t\tlet\n"
        "\t\t\t\t// Đọc CSV mart xuất từ DuckDB, ép UTF-8 để giữ dấu tiếng Việt\n"
        '\t\t\t\t#"Đã đọc file CSV" = Csv.Document(\n'
        '\t\t\t\t\tFile.Contents(DataFolder & "\\{f}"),\n'
        "\t\t\t\t\t[Delimiter = \",\", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]\n"
        "\t\t\t\t),\n"
        '\t\t\t\t#"Đã nâng dòng đầu thành tiêu đề" = Table.PromoteHeaders(#"Đã đọc file CSV", [PromoteAllScalars = true]),\n'
        '\t\t\t\t#"Đã ép kiểu dữ liệu từng cột" = Table.TransformColumnTypes(#"Đã nâng dòng đầu thành tiêu đề", {{{cols}}})'
        "{tail}"
        "\t\t\tin\n"
        "\t\t\t\t{last}\n"
    ).format(t=table, f=csvname, cols=cols, tail=tail, last=last)

def col(name, dtype, desc=None, hidden=False, fmt=None, summarize=None, sortby=None):
    s = ""
    if desc:
        s += "\t/// {}\n".format(desc)
    s += "\tcolumn {}\n".format(name if " " not in name else "'%s'" % name)
    s += "\t\tdataType: {}\n".format(dtype)
    if hidden:
        s += "\t\tisHidden\n"
    if fmt:
        s += "\t\tformatString: {}\n".format(fmt)
    if summarize:
        s += "\t\tsummarizeBy: {}\n".format(summarize)
    if sortby:
        s += "\t\tsortByColumn: '{}'\n".format(sortby)
    s += "\t\tsourceColumn: {}\n".format(name)
    return s + "\n"

def measure(name, dax, fmt, desc):
    lines = dax.strip("\n").split("\n")
    s = "".join("\t/// {}\n".format(d) for d in desc.split("\n"))
    if len(lines) == 1:
        s += "\tmeasure '{}' = {}\n".format(name, lines[0].strip())
    else:
        s += "\tmeasure '{}' = ```\n".format(name)
        for ln in lines:
            s += "\t\t\t{}\n".format(ln)
        s += "\t\t\t```\n"
    s += "\t\tformatString: {}\n".format(fmt)
    return s + "\n"

TXT, INT, NUM = "type text", "Int64.Type", "type number"

# ---------------------------------------------------------------- Funnel
funnel_cols = [("channel_type",TXT),("contract_type",TXT),("client_type",TXT),("yield_group",TXT),
    ("n_applications",INT),("n_approved",INT),("n_unused_offer",INT),("n_refused",INT),("n_canceled",INT),
    ("credit_amount_approved_total",NUM),("credit_amount_approved_median",NUM),
    ("n_offered",INT),("n_decided",INT),("approval_rate",NUM),("take_up_rate",NUM)]

w(T / "Funnel.tmdl",
"/// Phễu duyệt hồ sơ theo kênh (M12). Grain: kênh x sản phẩm x loại khách x nhóm lãi suất.\n"
"table Funnel\n\n"
+ measure("Applications", "SUM(Funnel[n_applications])", "#,##0", "Số hồ sơ nộp vào.")
+ measure("Decided", "SUM(Funnel[n_decided])", "#,##0", "Số hồ sơ đã có quyết định: duyệt, duyệt nhưng khách không dùng, hoặc từ chối.\nĐây là mẫu số của Approval Rate.")
+ measure("Offered", "SUM(Funnel[n_offered])", "#,##0", "Số hồ sơ được duyệt, tính cả trường hợp khách không nhận tiền.")
+ measure("Approval Rate", "DIVIDE([Offered], [Decided])", "0.0%",
          "M12. Tỷ lệ duyệt = (duyệt + duyệt nhưng không dùng) / đã có quyết định.\nCộng tử và mẫu trước rồi mới chia, không lấy trung bình cột approval_rate.")
+ measure("Take-up Rate", "DIVIDE(SUM(Funnel[n_approved]), [Offered])", "0.0%",
          "M12. Trong số hồ sơ được duyệt, bao nhiêu phần trăm khách thật sự nhận tiền.")
+ measure("Credit Approved", "SUM(Funnel[credit_amount_approved_total])", "#,##0",
          "Tổng hạn mức đã duyệt. Visual tự chọn đơn vị hiển thị.")
+ "".join([
    col("channel_type","string","Kênh bán đã gom nhóm. ẨN: slicer dùng Dim Channel[Kênh].",hidden=True),
    col("contract_type","string","Loại sản phẩm. ẨN: slicer dùng Dim Product[Sản phẩm].",hidden=True),
    col("client_type","string","Khách mới hay khách cũ."),
    col("yield_group","string","Nhóm lãi suất do Home Credit gán."),
    col("n_applications","int64",summarize="sum"), col("n_approved","int64",summarize="sum"),
    col("n_unused_offer","int64",summarize="sum"), col("n_refused","int64",summarize="sum"),
    col("n_canceled","int64",summarize="sum"), col("credit_amount_approved_total","double",summarize="sum"),
    col("credit_amount_approved_median","double",summarize="none"),
    col("n_offered","int64",summarize="sum"), col("n_decided","int64",summarize="sum"),
    col("approval_rate","double","Tỷ lệ tính sẵn ở grain gốc. ẨN có chủ đích: gộp nhiều dòng phải dùng measure [Approval Rate], không được lấy trung bình cột này.",hidden=True,summarize="none"),
    col("take_up_rate","double","Tỷ lệ tính sẵn ở grain gốc. ẨN có chủ đích, xem [Take-up Rate].",hidden=True,summarize="none"),
  ])
+ partition("Funnel","mart_funnel_by_channel.csv",funnel_cols))

# ---------------------------------------------------------------- FPD
fpd_cols = [("contract_type",TXT),("channel_type",TXT),("client_type",TXT),("yield_group",TXT),
    ("n_loans",INT),("n_fpd30",INT),("fpd30_rate",NUM),("n_fpd30_late_rule",INT),
    ("fpd30_late_rule_rate",NUM),("n_approved_no_installment",INT)]

w(T / "FPD.tmdl",
"/// Rủi ro sớm FPD30 theo phân khúc (M11). CHẶN DƯỚI, không phải số cuối cùng: xem vùng mù dữ liệu ở docs/metric_dictionary.md mục M11.\n"
"table FPD\n\n"
+ measure("FPD Base Loans", "SUM(FPD[n_loans])", "#,##0", "Số hợp đồng trong mẫu số FPD30.")
+ measure("FPD30 Loans", "SUM(FPD[n_fpd30])", "#,##0", "Số hợp đồng trễ hạn ngay kỳ trả góp đầu tiên trên 30 ngày.")
+ measure("FPD30 Rate", "DIVIDE([FPD30 Loans], [FPD Base Loans])", "0.0%",
          "M11. Tỷ lệ FPD30. ĐÂY LÀ CHẶN DƯỚI: dữ liệu chỉ ghi kỳ đã trả nên có thiên lệch sống sót,\nvùng mù 77.885 hồ sơ. Không dùng riêng số này để xếp hạng kênh hay sản phẩm.")
+ measure("FPD Blind Spot Loans", "SUM(FPD[n_approved_no_installment])", "#,##0",
          "Số hợp đồng được duyệt nhưng không có dòng trả góp nào, tức vùng mù không quan sát được FPD.")
+ "".join([
    col("contract_type","string",hidden=True), col("channel_type","string",hidden=True),
    col("client_type","string"), col("yield_group","string"),
    col("n_loans","int64",summarize="sum"), col("n_fpd30","int64",summarize="sum"),
    col("fpd30_rate","double","ẨN có chủ đích: dùng measure [FPD30 Rate].",hidden=True,summarize="none"),
    col("n_fpd30_late_rule","int64",summarize="sum"),
    col("fpd30_late_rule_rate","double","ẨN có chủ đích.",hidden=True,summarize="none"),
    col("n_approved_no_installment","int64",summarize="sum"),
  ])
+ partition("FPD","mart_fpd_by_segment.csv",fpd_cols))
print("-- funnel + fpd done")

# ---------------------------------------------------------------- Vintage
vin_cols = [("source",TXT),("contract_type",TXT),("channel_type",TXT),("client_type",TXT),
    ("yield_group",TXT),("tenor_group",TXT),("mob",INT),("n_loans",INT),("n_observed_full",INT),
    ("n_closed_early",INT),("n_ever_30_plus",INT),("n_ever_30_plus_tolerant",INT),
    ("ever_30_plus_rate",NUM),("ever_30_plus_rate_tolerant",NUM)]

w(T / "Vintage.tmdl",
"/// Vintage: tỷ lệ TỪNG quá hạn 30+ theo tuổi hợp đồng (M08). Mẫu số đã loại hợp đồng có cờ is_partial_history.\n"
"table Vintage\n\n"
+ measure("Vintage Loans", "SUM(Vintage[n_loans])", "#,##0", "Số hợp đồng trong mẫu số vintage tại MOB đang lọc.")
+ measure("Ever 30 Plus Loans", "SUM(Vintage[n_ever_30_plus])", "#,##0", "Số hợp đồng từng quá hạn trên 30 ngày tính đến MOB đang lọc.")
+ measure("Ever 30 Plus Rate", "DIVIDE([Ever 30 Plus Loans], [Vintage Loans])", "0.0%",
          "M08. Tỷ lệ từng quá hạn 30+ tại MOB đang lọc. Cộng tử và mẫu trước rồi chia.\nKhông có bộ lọc MOB thì số này gộp mọi MOB và vô nghĩa, hãy dùng [Ever 30 Plus MOB12].")
+ measure("Ever 30 Plus MOB12", """
DIVIDE(
    CALCULATE(SUM(Vintage[n_ever_30_plus]), Vintage[mob] = 12),
    CALCULATE(SUM(Vintage[n_loans]), Vintage[mob] = 12)
)""", "0.0%",
          "M08 tại MOB 12, trục rủi ro chính của project.\nCố định đúng mob = 12 bằng CALCULATE nên không phụ thuộc slicer MOB.\nDùng thay FPD30 vì FPD có thiên lệch sống sót.")
+ measure("Vintage Loans MOB12", 'CALCULATE(SUM(Vintage[n_loans]), Vintage[mob] = 12)', "#,##0",
          "Mẫu số của [Ever 30 Plus MOB12]. Dùng cột này khi đặt cạnh tỷ lệ tại MOB 12:\n[Vintage Loans] cộng qua MỌI mob nên lớn hơn nhiều lần và không phải mẫu số của tỷ lệ bên cạnh.")
+ measure("Ever 30 Plus MOB12 Tolerant", """
DIVIDE(
    CALCULATE(SUM(Vintage[n_ever_30_plus_tolerant]), Vintage[mob] = 12),
    CALCULATE(SUM(Vintage[n_loans]), Vintage[mob] = 12)
)""", "0.0%",
          "Bản dùng cột DPD có dung sai (SK_DPD_DEF). Chỉ tiêu PHỤ để đối chiếu, không phải trục chính.")
+ "".join([
    col("source","string","pos_cash hay credit_card, cho biết hợp đồng đến từ bảng nguồn nào."),
    col("contract_type","string",hidden=True), col("channel_type","string",hidden=True),
    col("client_type","string"), col("yield_group","string"),
    col("tenor_group","string","Nhóm kỳ hạn."),
    col("mob","int64","Months on book: hợp đồng đã chạy bao nhiêu tháng.",fmt="0",summarize="none"),
    col("n_loans","int64",summarize="sum"), col("n_observed_full","int64",summarize="sum"),
    col("n_closed_early","int64",summarize="sum"), col("n_ever_30_plus","int64",summarize="sum"),
    col("n_ever_30_plus_tolerant","int64",summarize="sum"),
    col("ever_30_plus_rate","double","ẨN có chủ đích: dùng measure [Ever 30 Plus Rate].",hidden=True,summarize="none"),
    col("ever_30_plus_rate_tolerant","double","ẨN có chủ đích.",hidden=True,summarize="none"),
  ])
+ partition("Vintage","mart_vintage.csv",vin_cols))

# ---------------------------------------------------------------- Roll Rate
roll_cols = [("source",TXT),("contract_type",TXT),("channel_type",TXT),("from_state",TXT),
    ("from_order",INT),("to_state",TXT),("to_order",INT),("n_loans",INT),("n_from",INT),
    ("roll_rate",NUM),("n_month_gap",INT),("n_exposure_null",INT),("n_exposure_null_from",INT),
    ("exposure_from",NUM),("exposure_from_total",NUM),("exposure_roll_rate",NUM),("exposure_to",NUM)]

w(T / "RollRate.tmdl",
"/// Ma trận chuyển nhóm nợ giữa hai tháng liền kề (M09) và cure rate (M10).\n"
"/// Grain: nguồn x sản phẩm x kênh x bucket xuất phát x bucket đích.\n"
"table RollRate\n\n"
+ measure("Roll Loans", "SUM(RollRate[n_loans])", "#,##0", "Số hợp đồng chuyển từ bucket xuất phát sang bucket đích.")
+ measure("Roll Base Loans", """
CALCULATE(
    SUM(RollRate[n_loans]),
    REMOVEFILTERS(RollRate[to_state], RollRate[to_order])
)""", "#,##0",
          "Mẫu số của roll rate: tổng hợp đồng ở bucket xuất phát, cộng qua MỌI bucket đích.\nDùng REMOVEFILTERS chứ KHÔNG cộng cột n_from: n_from là window sum lặp lại trên từng dòng to_state,\ncộng thẳng sẽ nhân số lên nhiều lần.\nPHẢI bỏ lọc cả to_order: to_state có sortByColumn là to_order nên bộ lọc cột trong ma trận\nkéo theo cả hai; chỉ bỏ to_state thì mẫu số vẫn bị ghim về một ô và mọi ô ra 100%.")
+ measure("Roll Rate", "DIVIDE([Roll Loans], [Roll Base Loans])", "0.0%",
          "M09. Tỷ lệ chuyển từ bucket xuất phát sang bucket đích trong tháng kế tiếp.")
+ measure("Cure Rate", """
DIVIDE(
    CALCULATE(
        SUM(RollRate[n_loans]),
        REMOVEFILTERS(RollRate[to_state], RollRate[to_order]),
        RollRate[to_state] = "B0 Current"
    ),
    [Roll Base Loans]
)""", "0.0%",
          "M10. Trong số hợp đồng đang quá hạn ở bucket xuất phát, bao nhiêu phần trăm quay về B0 Current tháng sau.\nLọc bỏ from_state = B0 Current khi đọc, vì B0 về B0 không phải là cure.")
+ measure("Exposure From", "SUM(RollRate[exposure_from])", "#,##0",
          "Dư nợ proxy ở bucket xuất phát. Visual tự chọn đơn vị hiển thị.")
+ "".join([
    col("source","string"), col("contract_type","string",hidden=True), col("channel_type","string",hidden=True),
    col("from_state","string","Bucket nợ ở tháng t.",sortby="from_order"),
    col("from_order","int64","Thứ tự bucket xuất phát, dùng để sắp xếp.",hidden=True,fmt="0",summarize="none"),
    col("to_state","string","Bucket nợ ở tháng t+1, có thêm Closed, Missing, Other.",sortby="to_order"),
    col("to_order","int64","Thứ tự bucket đích, dùng để sắp xếp.",hidden=True,fmt="0",summarize="none"),
    col("n_loans","int64",summarize="sum"),
    col("n_from","int64","Window sum lặp lại trên mỗi dòng to_state. ẨN có chủ đích: cộng cột này sẽ nhân số lên. Dùng [Roll Base Loans].",hidden=True,summarize="none"),
    col("roll_rate","double","ẨN có chủ đích: dùng measure [Roll Rate].",hidden=True,summarize="none"),
    col("n_month_gap","int64",hidden=True,summarize="sum"),
    col("n_exposure_null","int64",hidden=True,summarize="sum"),
    col("n_exposure_null_from","int64",hidden=True,summarize="sum"),
    col("exposure_from","double",summarize="sum"),
    col("exposure_from_total","double",hidden=True,summarize="none"),
    col("exposure_roll_rate","double","ẨN có chủ đích.",hidden=True,summarize="none"),
    col("exposure_to","double",hidden=True,summarize="sum"),
  ])
+ partition("RollRate","mart_roll_rate.csv",roll_cols))
print("-- vintage + rollrate done")

# ---------------------------------------------------------------- Dim tables
def dim(table, disp, srccol, tables, desc):
    parts = ",\n".join('\t\t\t\t\tTable.SelectColumns({}, {{"{}"}})'.format(t, srccol) for t in tables)
    return (
"/// {desc}\n"
"table '{table}'\n\n"
"\t/// {desc}\n"
"\tcolumn '{disp}'\n"
"\t\tdataType: string\n"
"\t\tsummarizeBy: none\n"
"\t\tsourceColumn: {disp}\n\n"
"\tpartition '{table}' = m\n"
"\t\tmode: import\n"
"\t\tsource =\n"
"\t\t\tlet\n"
"\t\t\t\t// Gom giá trị từ cả bốn bảng mart để không thiếu giá trị nào chỉ có ở một bảng\n"
'\t\t\t\t#"Đã gộp giá trị từ bốn bảng mart" = Table.Combine({{\n{parts}\n\t\t\t\t}}),\n'
'\t\t\t\t#"Đã bỏ giá trị trùng" = Table.Distinct(#"Đã gộp giá trị từ bốn bảng mart"),\n'
'\t\t\t\t#"Đã sắp xếp theo thứ tự chữ cái" = Table.Sort(#"Đã bỏ giá trị trùng", {{{{"{srccol}", Order.Ascending}}}}),\n'
'\t\t\t\t#"Đã đổi tên cột cho dễ đọc" = Table.RenameColumns(#"Đã sắp xếp theo thứ tự chữ cái", {{{{"{srccol}", "{disp}"}}}})\n'
"\t\t\tin\n"
'\t\t\t\t#"Đã đổi tên cột cho dễ đọc"\n'
    ).format(table=table, disp=disp, srccol=srccol, parts=parts, desc=desc)

FACTS = ["Funnel", "FPD", "Vintage", "RollRate", "Snapshot"]
w(T / "Dim Channel.tmdl", dim("Dim Channel", "Kênh", "channel_type", FACTS,
    "Danh mục kênh bán dùng chung. Slicer nên lấy từ bảng này để lọc đồng thời cả bốn bảng mart."))
w(T / "Dim Product.tmdl", dim("Dim Product", "Sản phẩm", "contract_type", FACTS,
    "Danh mục loại sản phẩm dùng chung. Slicer nên lấy từ bảng này để lọc đồng thời cả bốn bảng mart."))

# ---------------------------------------------------------------- relationships
rel = []
for f in ["Funnel", "FPD", "Vintage", "RollRate", "Snapshot"]:
    nm = f.strip("'")
    rel.append(
        "relationship 'Dim Channel to {nm}'\n"
        "\tfromColumn: {f}.channel_type\n"
        "\ttoColumn: 'Dim Channel'.Kênh\n".format(nm=nm, f=f))
    rel.append(
        "relationship 'Dim Product to {nm}'\n"
        "\tfromColumn: {f}.contract_type\n"
        "\ttoColumn: 'Dim Product'.'Sản phẩm'\n".format(nm=nm, f=f))
w(DEF / "relationships.tmdl", "\n".join(rel))

# model.tmdl cần ref cho hai bảng dim đã thêm
m = (DEF / "model.tmdl").read_text(encoding="utf-8")
if "ref table 'Dim Channel'" not in m:
    raise SystemExit("model.tmdl thiếu ref dim")
print("== xong SemanticModel ==")

# ---------------------------------------------------------------- Snapshot (mart thứ 5)
snap_cols = [("contract_type",TXT),("channel_type",TXT),("dpd_bucket",TXT),("dpd_bucket_order",INT),
    ("n_loans",INT),("exposure",NUM),("n_30_plus",INT),("exposure_30_plus",NUM)]

w(T / "Snapshot.tmdl",
"/// Ảnh chụp danh mục đang mở tại tháng quan sát gần nhất (months_balance = -1), theo bucket quá hạn.\n"
"/// Mã chỉ tiêu M02 và M06. Grain: sản phẩm x kênh x bucket.\n"
"table Snapshot\n\n"
+ measure("Open Loans", "SUM(Snapshot[n_loans])", "#,##0",
          "Số hợp đồng đang mở tại tháng quan sát gần nhất.")
+ measure("Loans 30+", "SUM(Snapshot[n_30_plus])", "#,##0",
          "Số hợp đồng đang quá hạn trên 30 ngày tại tháng quan sát.")
+ measure("Rate 30+ Coincident", "DIVIDE([Loans 30+], [Open Loans])", "0.00%",
          "M06. Tỷ lệ 30+ coincident: đang quá hạn trên 30 ngày trên tổng hợp đồng đang mở.\nĐây là ảnh chụp một thời điểm, khác với vintage vốn nhìn theo tuổi hợp đồng.")
+ measure("Open Exposure", "SUM(Snapshot[exposure])", "#,##0",
          "Dư nợ proxy của hợp đồng đang mở. Visual tự chọn đơn vị hiển thị.")
+ measure("Exposure 30+", "SUM(Snapshot[exposure_30_plus])", "#,##0",
          "Dư nợ proxy đang quá hạn trên 30 ngày.")
+ measure("Exposure Rate 30+", "DIVIDE([Exposure 30+], [Open Exposure])", "0.00%",
          "M06 tính theo dư nợ thay vì theo số hợp đồng. Thường cao hơn bản đếm hợp đồng\nvì hợp đồng quá hạn hay có dư nợ lớn hơn trung bình.")
+ "".join([
    col("contract_type","string","Loại sản phẩm. ẨN: slicer dùng Dim Product[Sản phẩm].",hidden=True),
    col("channel_type","string","Kênh bán. ẨN: slicer dùng Dim Channel[Kênh].",hidden=True),
    col("dpd_bucket","string","Nhóm quá hạn theo số ngày: B0 Current, B1 1-30, B2 31-60, B3 61-90, B4 90+.",sortby="dpd_bucket_order"),
    col("dpd_bucket_order","int64","Thứ tự bucket, dùng để sắp xếp.",hidden=True,fmt="0",summarize="none"),
    col("n_loans","int64",summarize="sum"),
    col("exposure","double",summarize="sum"),
    col("n_30_plus","int64",summarize="sum"),
    col("exposure_30_plus","double",summarize="sum"),
  ])
+ partition("Snapshot","mart_portfolio_snapshot.csv",snap_cols))
print("== xong Snapshot ==")
