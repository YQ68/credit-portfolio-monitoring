# -*- coding: utf-8 -*-
"""Sinh phần SemanticModel (TMDL) của PBIP cho project credit-portfolio-monitoring.

Cách dùng:
    python scripts/build_pbip_model.py [--data-folder <đường dẫn tới data/export>]

Tham số DataFolder (thư mục chứa 5 file CSV) lấy theo thứ tự ưu tiên:
    1. tham số dòng lệnh --data-folder
    2. biến môi trường CPM_DATA_FOLDER
    3. đường dẫn mẫu trung tính DEFAULT_DATA_FOLDER bên dưới.
Bản commit lên git PHẢI sinh bằng đường dẫn mẫu (không truyền gì), để file không
lộ thư mục cá nhân của máy dựng. Khi mở trên máy mình, sinh lại với đường dẫn
thật, hoặc sửa tham số DataFolder trong Power BI Desktop.

Định nghĩa quá hạn chính là SK_DPD_DEF (DPD có ngưỡng trọng yếu): các cột không
hậu tố (n_ever_30_plus, n_30_plus...). Cột hậu tố _no_threshold theo SK_DPD,
chỉ dùng làm độ nhạy.

Generator cố tình không sinh lineageTag: Desktop tự gán ở lần lưu đầu (đúng
khuyến nghị của Microsoft), đồng thời nâng compatibilityLevel.
"""
import argparse
import json
import os
import pathlib
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
PBI = ROOT / "powerbi"
SM = PBI / "CreditPortfolio.SemanticModel"
DEF = SM / "definition"
T = DEF / "tables"

DEFAULT_DATA_FOLDER = r"C:\path\to\credit-portfolio-monitoring\data\export"

# logicalId cố định (uuid5 theo tên) để chạy lại không sinh diff.
LOGICAL_ID = str(uuid.uuid5(uuid.NAMESPACE_URL,
                            "https://github.com/credit-portfolio-monitoring/CreditPortfolio.SemanticModel"))


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data-folder", default=None,
                    help="Thư mục chứa 5 file CSV (mặc định: biến môi trường CPM_DATA_FOLDER, "
                         "sau đó là đường dẫn mẫu trung tính).")
    return ap.parse_args()


def w(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    print("wrote", path.relative_to(ROOT))


# ---------------------------------------------------------------- tiện ích M và TMDL
def partition(table, csvname, typed):
    """Sinh partition M đọc 1 file CSV trong DataFolder.

    Ép kiểu với culture "en-US" tường minh: CSV dùng dấu chấm thập phân. Thiếu tham
    số culture thì Power Query đọc theo locale của máy, máy đặt vi-VN sẽ đọc "0.0006"
    thành số sai.
    """
    cols = ", ".join('{{"{}", {}}}'.format(c, t) for c, t in typed)
    # Không vá nhãn phân khúc ở tầng model. Ba nhãn '(không rõ)', 'Unknown' và
    # 'Khác' khác nghĩa nhau và do tầng mart quyết định (xem sql/mart/*.sql).
    last = '#"Đã ép kiểu dữ liệu từng cột"'
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
        '\t\t\t\t#"Đã ép kiểu dữ liệu từng cột" = Table.TransformColumnTypes(#"Đã nâng dòng đầu thành tiêu đề", {{{cols}}}, "en-US")\n'
        "\t\t\tin\n"
        "\t\t\t\t{last}\n"
    ).format(t=table, f=csvname, cols=cols, last=last)


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
    if fmt is not None:
        s += "\t\tformatString: {}\n".format(fmt)
    return s + "\n"


TXT, INT, NUM = "type text", "Int64.Type", "type number"
PCT3 = "0.000%"   # tỷ lệ 30+ rất mỏng (cỡ 0,05%), cần 3 chữ số thập phân
PCT1 = "0.0%"
RATIO = "0.00"


def main():
    args = parse_args()
    data_folder = args.data_folder or os.environ.get("CPM_DATA_FOLDER") or DEFAULT_DATA_FOLDER
    T.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------ .platform, pbism, database, model
    w(SM / ".platform", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": "CreditPortfolio"},
        "config": {"version": "2.0", "logicalId": LOGICAL_ID},
    }, indent=2, ensure_ascii=False))

    w(SM / "definition.pbism", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2",
        "settings": {"qnaEnabled": True},
    }, indent=2))

    w(DEF / "database.tmdl", "database CreditPortfolio\n\tcompatibilityLevel: 1550\n")

    # culture en-US. Đã thử vi-VN: Desktop vẫn hiển thị nhãn số theo locale của ứng
    # dụng (0.094%), nên đổi culture không đem lại gì; giữ en-US như bản đã kiểm.
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

    w(DEF / "expressions.tmdl", '''/// Thư mục chứa 5 file CSV xuất từ mart (scripts/build_dashboard.py).
/// Giá trị trong git là đường dẫn mẫu: đổi thành đường dẫn tuyệt đối tới data/export trên máy bạn,
/// hoặc sinh lại bằng: python scripts/build_pbip_model.py --data-folder <đường dẫn>.
expression DataFolder = "{}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]
'''.format(data_folder.replace("\\", "\\\\")))

    # ------------------------------------------------------------ Funnel
    funnel_cols = [("channel_type", TXT), ("contract_type", TXT), ("client_type", TXT), ("yield_group", TXT),
                   ("n_applications", INT), ("n_approved", INT), ("n_unused_offer", INT), ("n_refused", INT),
                   ("n_canceled", INT), ("credit_amount_approved_total", NUM),
                   ("credit_amount_approved_median", NUM), ("n_offered", INT), ("n_decided", INT),
                   ("approval_rate", NUM), ("take_up_rate", NUM)]

    w(T / "Funnel.tmdl",
      "/// Phễu duyệt hồ sơ theo kênh (M12). Grain: kênh x sản phẩm x loại khách x nhóm lãi suất.\n"
      "table Funnel\n\n"
      + measure("Applications", "SUM(Funnel[n_applications])", "#,##0", "Số hồ sơ nộp vào.")
      + measure("Decided", "SUM(Funnel[n_decided])", "#,##0",
                "Số hồ sơ đã có quyết định: duyệt, duyệt nhưng khách không dùng, hoặc từ chối.\nĐây là mẫu số của Approval Rate.")
      + measure("Offered", "SUM(Funnel[n_offered])", "#,##0",
                "Số hồ sơ được duyệt, tính cả trường hợp khách không nhận tiền.")
      + measure("Approval Rate", "DIVIDE([Offered], [Decided])", PCT1,
                "M12. Tỷ lệ duyệt thô = (duyệt + duyệt nhưng không dùng) / đã có quyết định.\nPhụ thuộc mạnh vào cơ cấu sản phẩm của kênh: so kênh thì dùng [Approval Standardized Ratio].")
      + measure("Approval Expected", """
SUMX(
    VALUES(Funnel[contract_type]),
    VAR decided = [Decided]
    VAR productRate =
        CALCULATE(
            [Approval Rate],
            REMOVEFILTERS('Dim Channel'),
            REMOVEFILTERS(Funnel[channel_type])
        )
    RETURN decided * productRate
)""", "#,##0",
                "Số hồ sơ được duyệt KỲ VỌNG nếu kênh có tỷ lệ duyệt của từng sản phẩm trên toàn danh mục.\nChuẩn hoá gián tiếp theo sản phẩm, khớp approval.channel_standardized.expected trong findings.json.")
      + measure("Approval Standardized Ratio", "DIVIDE([Offered], [Approval Expected])", RATIO,
                "Số được duyệt / số kỳ vọng theo cơ cấu sản phẩm. 1,00 nghĩa là kênh duyệt đúng mức sản phẩm của nó.")
      + measure("Take-up Rate", "DIVIDE(SUM(Funnel[n_approved]), [Offered])", PCT1,
                "M12. Trong số hồ sơ được duyệt, bao nhiêu phần trăm khách thật sự nhận tiền.\nChỉ có nghĩa ở vay tiêu dùng (Unused offer gần như chỉ có ở sản phẩm này), xem [Take-up Rate Consumer].")
      + measure("Take-up Rate Consumer",
                'CALCULATE([Take-up Rate], KEEPFILTERS(Funnel[contract_type] = "Consumer loans"))', PCT1,
                "Take-up chỉ tính trên vay tiêu dùng. Trống nếu kênh không bán vay tiêu dùng.")
      + measure("Credit Approved", "SUM(Funnel[credit_amount_approved_total])", "#,##0",
                "Tổng hạn mức đã duyệt. Visual tự chọn đơn vị hiển thị.")
      + "".join([
          col("channel_type", "string", "Kênh bán đã gom nhóm. ẨN: slicer dùng Dim Channel[Kênh].", hidden=True),
          col("contract_type", "string", "Loại sản phẩm. ẨN: slicer dùng Dim Product[Sản phẩm].", hidden=True),
          col("client_type", "string", "Khách mới hay khách cũ."),
          col("yield_group", "string", "Nhóm lãi suất do Home Credit gán."),
          col("n_applications", "int64", summarize="sum"), col("n_approved", "int64", summarize="sum"),
          col("n_unused_offer", "int64", summarize="sum"), col("n_refused", "int64", summarize="sum"),
          col("n_canceled", "int64", summarize="sum"),
          col("credit_amount_approved_total", "double", summarize="sum"),
          col("credit_amount_approved_median", "double", summarize="none"),
          col("n_offered", "int64", summarize="sum"), col("n_decided", "int64", summarize="sum"),
          col("approval_rate", "double", "Tỷ lệ tính sẵn ở grain gốc. ẨN có chủ đích: gộp nhiều dòng phải dùng measure [Approval Rate], không được lấy trung bình cột này.", hidden=True, summarize="none"),
          col("take_up_rate", "double", "Tỷ lệ tính sẵn ở grain gốc. ẨN có chủ đích, xem [Take-up Rate].", hidden=True, summarize="none"),
      ])
      + partition("Funnel", "mart_funnel_by_channel.csv", funnel_cols))

    # ------------------------------------------------------------ FPD
    fpd_cols = [("contract_type", TXT), ("channel_type", TXT), ("client_type", TXT), ("yield_group", TXT),
                ("n_loans", INT), ("n_fpd30", INT), ("fpd30_rate", NUM), ("n_fpd30_late_rule", INT),
                ("fpd30_late_rule_rate", NUM), ("n_approved_not_activated", INT),
                ("n_approved_scheduled_no_installment", INT)]

    w(T / "FPD.tmdl",
      "/// Rủi ro sớm FPD30 theo phân khúc (M11), trên hợp đồng đã kích hoạt (có kỳ 1 trong lịch trả gốc).\n"
      "/// Thẻ quay vòng không có trong mẫu số. Tử số rất mỏng nên không dùng làm trục rủi ro.\n"
      "table FPD\n\n"
      + measure("FPD Base Loans", "SUM(FPD[n_loans])", "#,##0", "Số hợp đồng trong mẫu số FPD30.")
      + measure("FPD30 Loans", "SUM(FPD[n_fpd30])", "#,##0",
                "Số hợp đồng trả chưa đủ 95% kỳ 1 trong 30 ngày sau hạn.")
      + measure("FPD30 Rate", "DIVIDE([FPD30 Loans], [FPD Base Loans])", PCT3,
                "M11. Tỷ lệ FPD30 trên hợp đồng đã kích hoạt. Tử số rất mỏng (99 ca toàn danh mục),\nkhông dùng riêng số này để xếp hạng kênh hay sản phẩm.")
      + measure("Approved Not Activated", "SUM(FPD[n_approved_not_activated])", "#,##0",
                "Hồ sơ được duyệt nhưng không có lịch trả, tức không kích hoạt. Không thuộc mẫu số FPD30.")
      + "".join([
          col("contract_type", "string", hidden=True), col("channel_type", "string", hidden=True),
          col("client_type", "string"), col("yield_group", "string"),
          col("n_loans", "int64", summarize="sum"), col("n_fpd30", "int64", summarize="sum"),
          col("fpd30_rate", "double", "ẨN có chủ đích: dùng measure [FPD30 Rate].", hidden=True, summarize="none"),
          col("n_fpd30_late_rule", "int64", "FPD30 theo ngày: có lần trả trễ quá 30 ngày.", summarize="sum"),
          col("fpd30_late_rule_rate", "double", "ẨN có chủ đích.", hidden=True, summarize="none"),
          col("n_approved_not_activated", "int64", "Duyệt, không có lịch trả.", summarize="sum"),
          col("n_approved_scheduled_no_installment", "int64", "Duyệt, có lịch trả, không có dòng kỳ 1.", summarize="sum"),
      ])
      + partition("FPD", "mart_fpd_by_segment.csv", fpd_cols))

    # ------------------------------------------------------------ Vintage
    vin_cols = [("source", TXT), ("contract_type", TXT), ("channel_type", TXT), ("client_type", TXT),
                ("yield_group", TXT), ("tenor_group", TXT), ("origination_cohort", TXT),
                ("origination_cohort_start", INT), ("mob", INT), ("n_loans", INT),
                ("n_observed_full", INT), ("n_closed_early", INT), ("n_ever_30_plus", INT),
                ("n_ever_30_plus_no_threshold", INT), ("n_ever_30_plus_due_only", INT), ("ever_30_plus_rate", NUM),
                ("ever_30_plus_rate_no_threshold", NUM)]

    w(T / "Vintage.tmdl",
      "/// Vintage: tỷ lệ TỪNG quá hạn 30+ theo tuổi hợp đồng (M08), định nghĩa SK_DPD_DEF.\n"
      "/// Mẫu số: hợp đồng đã biết kết quả đến MOB n, đã loại is_partial_history.\n"
      "table Vintage\n\n"
      + measure("Vintage Loans", "SUM(Vintage[n_loans])", "#,##0",
                "Số hợp đồng trong mẫu số vintage tại MOB đang lọc.")
      + measure("Ever 30 Plus Loans", "SUM(Vintage[n_ever_30_plus])", "#,##0",
                "Số hợp đồng từng quá hạn trên 30 ngày (SK_DPD_DEF) tính đến MOB đang lọc.")
      + measure("Ever 30 Plus Rate", "DIVIDE([Ever 30 Plus Loans], [Vintage Loans])", PCT3,
                "M08. Tỷ lệ từng quá hạn 30+ tại MOB đang lọc. Cộng tử và mẫu trước rồi chia.\nKhông có bộ lọc MOB thì số này gộp mọi MOB và vô nghĩa, hãy dùng [Ever 30 Plus MOB12].")
      + measure("Ever 30 Plus Loans MOB12", "CALCULATE(SUM(Vintage[n_ever_30_plus]), Vintage[mob] = 12)", "#,##0",
                "Số ca từng 30+ tại MOB 12. Đây là số ca QUAN SÁT (O) của SMR.")
      + measure("Vintage Loans MOB12", "CALCULATE(SUM(Vintage[n_loans]), Vintage[mob] = 12)", "#,##0",
                "Mẫu số của [Ever 30 Plus MOB12]. Dùng cột này khi đặt cạnh tỷ lệ tại MOB 12:\n[Vintage Loans] cộng qua MỌI mob nên lớn hơn nhiều lần và không phải mẫu số của tỷ lệ bên cạnh.")
      + measure("Ever 30 Plus MOB12", "DIVIDE([Ever 30 Plus Loans MOB12], [Vintage Loans MOB12])", PCT3,
                "M08 tại MOB 12, trục rủi ro chính của project.\nCố định đúng mob = 12 bằng CALCULATE nên không phụ thuộc slicer MOB.")
      + measure("Ever 30 Plus MOB12 No Threshold", """
DIVIDE(
    CALCULATE(SUM(Vintage[n_ever_30_plus_no_threshold]), Vintage[mob] = 12),
    [Vintage Loans MOB12]
)""", PCT3,
                "Độ nhạy: cùng mẫu số nhưng tử số theo SK_DPD (không áp ngưỡng trọng yếu).\nPhần chênh so với [Ever 30 Plus MOB12] phần lớn là khoản dư lẻ sau kỳ trả cuối.")
      + measure("Expected 30 Plus MOB12", """
SUMX(
    VALUES(Vintage[contract_type]),
    VAR loans = [Vintage Loans MOB12]
    VAR productRate =
        CALCULATE(
            [Ever 30 Plus MOB12],
            REMOVEFILTERS('Dim Channel'),
            REMOVEFILTERS(Vintage[channel_type])
        )
    RETURN loans * productRate
)""", "#,##0.0",
                "Số ca KỲ VỌNG (E) tại MOB 12 nếu kênh có tỷ lệ của từng sản phẩm trên toàn danh mục.\nKhớp channel_comparison.mob12.smr_by_channel[].primary.expected trong findings.json.")
      + measure("SMR MOB12", "DIVIDE([Ever 30 Plus Loans MOB12], [Expected 30 Plus MOB12])", RATIO,
                "SMR = O / E. Trên 1: kênh xấu hơn mức sản phẩm của chính nó. Tử số dưới 10 thì không kết luận.")
      + measure("SMR MOB12 CI Low", """
VAR O = [Ever 30 Plus Loans MOB12]
VAR E = [Expected 30 Plus MOB12]
VAR z = 1.959963985
RETURN
    IF(E > 0, IF(O = 0, 0, O * POWER(1 - 1 / (9 * O) - z / (3 * SQRT(O)), 3) / E))""", RATIO,
                "Cận dưới khoảng tin cậy 95% của SMR, xấp xỉ Byar (cùng công thức với compute_findings.py).")
      + measure("SMR MOB12 CI High", """
VAR O1 = [Ever 30 Plus Loans MOB12] + 1
VAR E = [Expected 30 Plus MOB12]
VAR z = 1.959963985
RETURN
    IF(E > 0, O1 * POWER(1 - 1 / (9 * O1) + z / (3 * SQRT(O1)), 3) / E)""", RATIO,
                "Cận trên khoảng tin cậy 95% của SMR, xấp xỉ Byar.")
      + measure("Ever 30 Plus MOB12 Due Only", """
DIVIDE(
    CALCULATE(SUM(Vintage[n_ever_30_plus_due_only]), Vintage[mob] = 12),
    [Vintage Loans MOB12]
)""", PCT3,
                "Định nghĩa giữa: cùng mẫu số, tử số là SK_DPD 30+ ở tháng còn kỳ phải trả.")
      + measure("Expected 30 Plus MOB12 Cohort", """
SUMX(
    SUMMARIZE(Vintage, Vintage[contract_type], Vintage[origination_cohort]),
    VAR loans = [Vintage Loans MOB12]
    VAR stratumRate =
        CALCULATE(
            [Ever 30 Plus MOB12],
            REMOVEFILTERS('Dim Channel'),
            REMOVEFILTERS(Vintage[channel_type])
        )
    RETURN loans * stratumRate
)""", "#,##0.0",
                "Số ca KỲ VỌNG (E) tại MOB 12 nếu kênh có tỷ lệ của từng tầng sản phẩm × đợt mở 12 tháng trên toàn danh mục.\nKhớp origination_cohort.mob12.smr_by_channel.product_x_cut12.primary[].expected trong findings.json.")
      + measure("SMR MOB12 Cohort", "DIVIDE([Ever 30 Plus Loans MOB12], [Expected 30 Plus MOB12 Cohort])", RATIO,
                "SMR kiểm soát cả sản phẩm lẫn đợt mở = O / E theo tầng sản phẩm × đợt. Tử số dưới 10 thì không kết luận.")
      + measure("SMR MOB12 Few Cases Note", 'IF([Ever 30 Plus Loans MOB12] < 5, "quá ít ca")', None,
                "Ghi chú cho kênh có dưới 5 ca quan sát tại MOB 12. Dùng làm khoá sắp đầu tiên của bảng SMR để kênh quá ít ca xuống cuối.")
      + measure("SMR MOB12 Cohort CI Low", """
VAR O = [Ever 30 Plus Loans MOB12]
VAR E = [Expected 30 Plus MOB12 Cohort]
VAR z = 1.959963985
RETURN
    IF(E > 0, IF(O = 0, 0, O * POWER(1 - 1 / (9 * O) - z / (3 * SQRT(O)), 3) / E))""", RATIO,
                "Cận dưới khoảng tin cậy 95% của [SMR MOB12 Cohort], xấp xỉ Byar.")
      + measure("SMR MOB12 Cohort CI High", """
VAR O1 = [Ever 30 Plus Loans MOB12] + 1
VAR E = [Expected 30 Plus MOB12 Cohort]
VAR z = 1.959963985
RETURN
    IF(E > 0, O1 * POWER(1 - 1 / (9 * O1) + z / (3 * SQRT(O1)), 3) / E)""", RATIO,
                "Cận trên khoảng tin cậy 95% của [SMR MOB12 Cohort], xấp xỉ Byar.")
      + measure("Ratio vs Cash Crude", """
DIVIDE(
    [Ever 30 Plus MOB12],
    CALCULATE([Ever 30 Plus MOB12], REMOVEFILTERS('Dim Product'), Vintage[contract_type] = "Cash loans")
)""", RATIO,
                "Tỷ số thô tỷ lệ từng 30+ tại MOB 12 của sản phẩm đang lọc so với vay tiền mặt (định nghĩa chính).")
      + measure("Ratio vs Cash MH Cohort", """
VAR cashRows = CALCULATETABLE(Vintage, REMOVEFILTERS('Dim Product'), Vintage[contract_type] = "Cash loans", Vintage[mob] = 12)
VAR prodRows = CALCULATETABLE(Vintage, Vintage[mob] = 12)
VAR strata = DISTINCT(SELECTCOLUMNS(CALCULATETABLE(Vintage, REMOVEFILTERS('Dim Product'), Vintage[mob] = 12), "c", Vintage[origination_cohort_start]))
VAR num =
    SUMX(strata,
        VAR c = [c]
        VAR k1 = SUMX(FILTER(prodRows, Vintage[origination_cohort_start] = c), Vintage[n_ever_30_plus])
        VAR n1 = SUMX(FILTER(prodRows, Vintage[origination_cohort_start] = c), Vintage[n_loans])
        VAR n0 = SUMX(FILTER(cashRows, Vintage[origination_cohort_start] = c), Vintage[n_loans])
        RETURN IF(n1 + n0 > 0, k1 * n0 / (n1 + n0)))
VAR den =
    SUMX(strata,
        VAR c = [c]
        VAR k0 = SUMX(FILTER(cashRows, Vintage[origination_cohort_start] = c), Vintage[n_ever_30_plus])
        VAR n1 = SUMX(FILTER(prodRows, Vintage[origination_cohort_start] = c), Vintage[n_loans])
        VAR n0 = SUMX(FILTER(cashRows, Vintage[origination_cohort_start] = c), Vintage[n_loans])
        RETURN IF(n1 + n0 > 0, k0 * n1 / (n1 + n0)))
RETURN
    IF(SELECTEDVALUE(Vintage[contract_type]) <> "Cash loans", DIVIDE(num, den))""", RATIO,
                "Tỷ số Mantel-Haenszel so với vay tiền mặt, gộp qua đợt mở 12 tháng (định nghĩa chính).\nKhớp origination_cohort.mob12.product_ratio_vs_cash.<sản phẩm>.primary.mh_cut12.ratio.")
      + measure("Ratio vs Cash Due Only", """
DIVIDE(
    [Ever 30 Plus MOB12 Due Only],
    CALCULATE([Ever 30 Plus MOB12 Due Only], REMOVEFILTERS('Dim Product'), Vintage[contract_type] = "Cash loans")
)""", RATIO,
                "Tỷ số thô so với vay tiền mặt theo định nghĩa giữa.")
      + measure("Ratio vs Cash No Threshold", """
DIVIDE(
    [Ever 30 Plus MOB12 No Threshold],
    CALCULATE([Ever 30 Plus MOB12 No Threshold], REMOVEFILTERS('Dim Product'), Vintage[contract_type] = "Cash loans")
)""", RATIO,
                "Tỷ số thô so với vay tiền mặt khi không áp ngưỡng trọng yếu (SK_DPD).")
      + measure("Cohort Ever 30 Plus Rate", """
VAR m = SELECTEDVALUE(Vintage[mob])
VAR s = MIN(Vintage[origination_cohort_start])
RETURN
    IF(NOT ISBLANK(m) && HASONEVALUE(Vintage[origination_cohort]) && s + 11 <= -1 - m, [Ever 30 Plus Rate])""", PCT3,
                "[Ever 30 Plus Rate] của một đợt mở, chỉ tại MOB mà mọi hợp đồng của đợt đã đủ tuổi\n(tháng cuối của đợt <= -1 - MOB). Khớp origination_cohort.curve_by_cohort_labeled_products.")
      # Hai cặp measure TRÌNH BÀY, chỉ để tô màu trong small multiples. Power BI bỏ qua
      # selector màu theo từng danh mục khi visual có Rows (small multiples), nên tách
      # giá trị thành hai measure: một cho kênh được nhấn (tô mustard), một cho phần còn
      # lại (xám), mỗi ô chỉ có một trong hai. Danh sách kênh trùng HL_P2_CHANNELS và
      # HL_P3_CHANNEL trong scripts/build_pbip_report.py.
      + measure("Highlight Ever 30 Plus MOB12",
                """IF(SELECTEDVALUE('Dim Channel'[Kênh]) IN {"Contact center", "Stone"}, [Ever 30 Plus MOB12])""", PCT3,
                "Trình bày: [Ever 30 Plus MOB12] chỉ cho Contact center và Stone (trang 2), để tô mustard.")
      + measure("Base Ever 30 Plus MOB12",
                """IF(NOT(SELECTEDVALUE('Dim Channel'[Kênh]) IN {"Contact center", "Stone"}), [Ever 30 Plus MOB12])""", PCT3,
                "Trình bày: [Ever 30 Plus MOB12] cho các kênh còn lại (trang 2), tô xám.")
      + measure("Highlight Ever 30 Plus Rate",
                """IF(SELECTEDVALUE('Dim Channel'[Kênh]) = "Contact center", [Ever 30 Plus Rate])""", PCT3,
                "Trình bày: [Ever 30 Plus Rate] chỉ cho Contact center (trang 3), để tô mustard.")
      + measure("Base Ever 30 Plus Rate",
                """IF(SELECTEDVALUE('Dim Channel'[Kênh]) <> "Contact center", [Ever 30 Plus Rate])""", PCT3,
                "Trình bày: [Ever 30 Plus Rate] cho các kênh còn lại (trang 3), tô mực.")
      + "".join([
          col("source", "string", "pos_cash hay credit_card, cho biết hợp đồng đến từ bảng nguồn nào."),
          col("contract_type", "string", hidden=True), col("channel_type", "string", hidden=True),
          col("client_type", "string"), col("yield_group", "string"),
          col("tenor_group", "string", "Nhóm kỳ hạn."),
          col("origination_cohort", "string", "Đợt mở: nhóm 12 tháng của tháng mở hợp đồng, tính tương đối so với ngày nộp hồ sơ hiện tại.", sortby="origination_cohort_start"),
          col("origination_cohort_start", "int64", "Tháng tương đối đầu đợt mở, dùng để sắp xếp đợt.", hidden=True, fmt="0", summarize="none"),
          col("mob", "int64", "Months on book: hợp đồng đã chạy bao nhiêu tháng.", fmt="0", summarize="none"),
          col("n_loans", "int64", summarize="sum"), col("n_observed_full", "int64", summarize="sum"),
          col("n_closed_early", "int64", summarize="sum"),
          col("n_ever_30_plus", "int64", "Từng 30+ theo SK_DPD_DEF (định nghĩa chính).", summarize="sum"),
          col("n_ever_30_plus_no_threshold", "int64", "Từng 30+ theo SK_DPD, chỉ dùng làm độ nhạy.", summarize="sum"),
          col("n_ever_30_plus_due_only", "int64", "Từng 30+ theo định nghĩa giữa (SK_DPD 30+ ở tháng còn kỳ phải trả).", summarize="sum"),
          col("ever_30_plus_rate", "double", "ẨN có chủ đích: dùng measure [Ever 30 Plus Rate].", hidden=True, summarize="none"),
          col("ever_30_plus_rate_no_threshold", "double", "ẨN có chủ đích.", hidden=True, summarize="none"),
      ])
      + partition("Vintage", "mart_vintage.csv", vin_cols))

    # ------------------------------------------------------------ RollRate
    roll_cols = [("source", TXT), ("contract_type", TXT), ("channel_type", TXT), ("from_state", TXT),
                 ("from_order", INT), ("to_state", TXT), ("to_order", INT), ("n_loans", INT), ("n_from", INT),
                 ("roll_rate", NUM), ("n_month_gap", INT), ("n_exposure_null", INT),
                 ("n_exposure_null_from", INT), ("exposure_from", NUM), ("exposure_from_total", NUM),
                 ("exposure_roll_rate", NUM), ("exposure_to", NUM)]

    w(T / "RollRate.tmdl",
      "/// Ma trận chuyển nhóm nợ giữa hai tháng liền kề (M09) và cure rate (M10), bucket theo SK_DPD_DEF.\n"
      "/// Grain: nguồn x sản phẩm x kênh x bucket xuất phát x bucket đích.\n"
      "table RollRate\n\n"
      + measure("Roll Loans", "SUM(RollRate[n_loans])", "#,##0",
                "Số lượt hợp đồng-tháng chuyển từ bucket xuất phát sang bucket đích.")
      + measure("Roll Base Loans", """
CALCULATE(
    SUM(RollRate[n_loans]),
    REMOVEFILTERS(RollRate[to_state], RollRate[to_order])
)""", "#,##0",
                "Mẫu số của roll rate: tổng lượt ở bucket xuất phát, cộng qua MỌI bucket đích.\nDùng REMOVEFILTERS chứ KHÔNG cộng cột n_from: n_from là window sum lặp lại trên từng dòng to_state,\ncộng thẳng sẽ nhân số lên nhiều lần.\nPHẢI bỏ lọc cả to_order: to_state có sortByColumn là to_order nên bộ lọc cột trong ma trận\nkéo theo cả hai; chỉ bỏ to_state thì mẫu số vẫn bị ghim về một ô và mọi ô ra 100%.")
      + measure("Roll Rate", "DIVIDE([Roll Loans], [Roll Base Loans])", PCT1,
                "M09. Tỷ lệ chuyển từ bucket xuất phát sang bucket đích trong tháng kế tiếp.")
      + measure("Cure Rate", """
DIVIDE(
    CALCULATE(
        SUM(RollRate[n_loans]),
        REMOVEFILTERS(RollRate[to_state], RollRate[to_order]),
        RollRate[to_state] = "B0 Current",
        KEEPFILTERS(RollRate[from_state] <> "B0 Current")
    ),
    CALCULATE([Roll Base Loans], KEEPFILTERS(RollRate[from_state] <> "B0 Current"))
)""", PCT1,
                "M10. Trong số lượt đang quá hạn ở bucket xuất phát, bao nhiêu phần trăm quay về B0 Current tháng sau.\nChỉ tính trên B1 đến B4: dòng B0 Current trả về trống (B0 về B0 không phải cure),\ndòng tổng là cure chung của mọi lượt đang quá hạn.")
      + measure("Exposure From", "SUM(RollRate[exposure_from])", "#,##0",
                "Dư nợ proxy ở bucket xuất phát, CỘNG DỒN qua mọi tháng: một hợp đồng ở B0 nhiều tháng\nđược cộng mỗi tháng một lần. Không phải dư nợ tại một thời điểm.")
      + "".join([
          col("source", "string"), col("contract_type", "string", hidden=True),
          col("channel_type", "string", hidden=True),
          col("from_state", "string", "Bucket nợ ở tháng t.", sortby="from_order"),
          col("from_order", "int64", "Thứ tự bucket xuất phát, dùng để sắp xếp.", hidden=True, fmt="0", summarize="none"),
          col("to_state", "string", "Bucket nợ ở tháng t+1, có thêm Closed, Missing, Other.", sortby="to_order"),
          col("to_order", "int64", "Thứ tự bucket đích, dùng để sắp xếp.", hidden=True, fmt="0", summarize="none"),
          col("n_loans", "int64", summarize="sum"),
          col("n_from", "int64", "Window sum lặp lại trên mỗi dòng to_state. ẨN có chủ đích: cộng cột này sẽ nhân số lên. Dùng [Roll Base Loans].", hidden=True, summarize="none"),
          col("roll_rate", "double", "ẨN có chủ đích: dùng measure [Roll Rate].", hidden=True, summarize="none"),
          col("n_month_gap", "int64", hidden=True, summarize="sum"),
          col("n_exposure_null", "int64", hidden=True, summarize="sum"),
          col("n_exposure_null_from", "int64", hidden=True, summarize="sum"),
          col("exposure_from", "double", summarize="sum"),
          col("exposure_from_total", "double", hidden=True, summarize="none"),
          col("exposure_roll_rate", "double", "ẨN có chủ đích.", hidden=True, summarize="none"),
          col("exposure_to", "double", hidden=True, summarize="sum"),
      ])
      + partition("RollRate", "mart_roll_rate.csv", roll_cols))

    # ------------------------------------------------------------ Snapshot
    snap_cols = [("contract_type", TXT), ("channel_type", TXT), ("dpd_bucket", TXT), ("dpd_bucket_order", INT),
                 ("n_loans", INT), ("exposure", NUM), ("n_30_plus", INT), ("exposure_30_plus", NUM),
                 ("n_loans_exposure_known", INT), ("n_30_plus_exposure_known", INT),
                 ("n_30_plus_no_threshold", INT), ("exposure_30_plus_no_threshold", NUM)]

    w(T / "Snapshot.tmdl",
      "/// Ảnh chụp danh mục đang mở tại tháng quan sát gần nhất (months_balance = -1), bucket theo SK_DPD_DEF.\n"
      "/// Mã chỉ tiêu M02 và M06. Grain: sản phẩm x kênh x bucket.\n"
      "table Snapshot\n\n"
      + measure("Open Loans", "SUM(Snapshot[n_loans])", "#,##0",
                "Số hợp đồng đang mở tại tháng quan sát gần nhất.")
      + measure("Loans 30+", "SUM(Snapshot[n_30_plus])", "#,##0",
                "Số hợp đồng đang quá hạn trên 30 ngày tại tháng quan sát.")
      + measure("Rate 30+ Coincident", "DIVIDE([Loans 30+], [Open Loans])", PCT3,
                "M06. Tỷ lệ 30+ coincident trên MỌI hợp đồng đang mở. Dùng cho xếp hạng kênh và bảng sản phẩm.\nKhông đặt cạnh thẻ tỷ lệ theo dư nợ: hai số khác tập, xem [Rate 30+ Exposure Known].")
      + measure("Loans Exposure Known", "SUM(Snapshot[n_loans_exposure_known])", "#,##0",
                "Số hợp đồng đang mở có dư nợ proxy, tức tập của thẻ tỷ lệ theo dư nợ.")
      + measure("Loans 30+ Exposure Known", "SUM(Snapshot[n_30_plus_exposure_known])", "#,##0",
                "Số hợp đồng đang 30+ trong tập có dư nợ proxy.")
      + measure("Rate 30+ Exposure Known", "DIVIDE([Loans 30+ Exposure Known], [Loans Exposure Known])", PCT3,
                "M06 tính trên CÙNG tập với [Exposure Rate 30+] (hợp đồng có dư nợ proxy), để hai thẻ KPI so được với nhau.")
      + measure("Open Exposure", "SUM(Snapshot[exposure])", "#,##0",
                "Dư nợ proxy của hợp đồng đang mở. Visual tự chọn đơn vị hiển thị.")
      + measure("Exposure 30+", "SUM(Snapshot[exposure_30_plus])", "#,##0",
                "Dư nợ proxy đang quá hạn trên 30 ngày.")
      + measure("Exposure Rate 30+", "DIVIDE([Exposure 30+], [Open Exposure])", PCT3,
                "M06 tính theo dư nợ. Tập hợp đồng có dư nợ proxy, trùng tập của [Rate 30+ Exposure Known].")
      + measure("Rate 30+ No Threshold", "DIVIDE(SUM(Snapshot[n_30_plus_no_threshold]), [Open Loans])", PCT3,
                "Độ nhạy: tỷ lệ 30+ theo SK_DPD (không áp ngưỡng trọng yếu) trên mọi hợp đồng đang mở.")
      + measure("Exposure Rate 30+ No Threshold",
                "DIVIDE(SUM(Snapshot[exposure_30_plus_no_threshold]), [Open Exposure])", PCT3,
                "Độ nhạy: tỷ lệ dư nợ 30+ theo SK_DPD. Gần như không đổi so với định nghĩa chính,\nvì phần 30+ chỉ có theo SK_DPD là khoản dư lẻ.")
      + "".join([
          col("contract_type", "string", "Loại sản phẩm. ẨN: slicer dùng Dim Product[Sản phẩm].", hidden=True),
          col("channel_type", "string", "Kênh bán. ẨN: slicer dùng Dim Channel[Kênh].", hidden=True),
          col("dpd_bucket", "string", "Nhóm quá hạn theo SK_DPD_DEF: B0 Current, B1 1-30, B2 31-60, B3 61-90, B4 90+.", sortby="dpd_bucket_order"),
          col("dpd_bucket_order", "int64", "Thứ tự bucket, dùng để sắp xếp.", hidden=True, fmt="0", summarize="none"),
          col("n_loans", "int64", summarize="sum"),
          col("exposure", "double", summarize="sum"),
          col("n_30_plus", "int64", summarize="sum"),
          col("exposure_30_plus", "double", summarize="sum"),
          col("n_loans_exposure_known", "int64", "Hợp đồng có dư nợ proxy.", summarize="sum"),
          col("n_30_plus_exposure_known", "int64", "Hợp đồng 30+ có dư nợ proxy.", summarize="sum"),
          col("n_30_plus_no_threshold", "int64", "Độ nhạy SK_DPD. Không khớp dpd_bucket của dòng.", summarize="sum"),
          col("exposure_30_plus_no_threshold", "double", "Độ nhạy SK_DPD.", summarize="sum"),
      ])
      + partition("Snapshot", "mart_portfolio_snapshot.csv", snap_cols))

    # ------------------------------------------------------------ bảng danh mục dùng chung
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
            "\t\t\t\t// Gom giá trị từ cả năm bảng mart để không thiếu giá trị nào chỉ có ở một bảng\n"
            '\t\t\t\t#"Đã gộp giá trị từ năm bảng mart" = Table.Combine({{\n{parts}\n\t\t\t\t}}),\n'
            '\t\t\t\t#"Đã bỏ giá trị trùng" = Table.Distinct(#"Đã gộp giá trị từ năm bảng mart"),\n'
            '\t\t\t\t#"Đã sắp xếp theo thứ tự chữ cái" = Table.Sort(#"Đã bỏ giá trị trùng", {{{{"{srccol}", Order.Ascending}}}}),\n'
            '\t\t\t\t#"Đã đổi tên cột cho dễ đọc" = Table.RenameColumns(#"Đã sắp xếp theo thứ tự chữ cái", {{{{"{srccol}", "{disp}"}}}})\n'
            "\t\t\tin\n"
            '\t\t\t\t#"Đã đổi tên cột cho dễ đọc"\n'
        ).format(table=table, disp=disp, srccol=srccol, parts=parts, desc=desc)

    facts = ["Funnel", "FPD", "Vintage", "RollRate", "Snapshot"]
    w(T / "Dim Channel.tmdl", dim("Dim Channel", "Kênh", "channel_type", facts,
                                   "Danh mục kênh bán dùng chung. Slicer nên lấy từ bảng này để lọc đồng thời cả năm bảng mart."))
    w(T / "Dim Product.tmdl", dim("Dim Product", "Sản phẩm", "contract_type", facts,
                                   "Danh mục loại sản phẩm dùng chung. Slicer nên lấy từ bảng này để lọc đồng thời cả năm bảng mart."))

    # ------------------------------------------------------------ quan hệ
    rel = []
    for f in facts:
        rel.append("relationship 'Dim Channel to {f}'\n"
                   "\tfromColumn: {f}.channel_type\n"
                   "\ttoColumn: 'Dim Channel'.Kênh\n".format(f=f))
        rel.append("relationship 'Dim Product to {f}'\n"
                   "\tfromColumn: {f}.contract_type\n"
                   "\ttoColumn: 'Dim Product'.'Sản phẩm'\n".format(f=f))
    w(DEF / "relationships.tmdl", "\n".join(rel))
    print("== xong SemanticModel, DataFolder =", data_folder)


if __name__ == "__main__":
    main()
