# -*- coding: utf-8 -*-
"""Một nguồn câu chữ duy nhất cho dashboard HTML và báo cáo Power BI.

Mọi tiêu đề trang, dòng phụ đề (dek), tiêu đề visual có số và ghi chú LƯU Ý của
4 trang được sinh ở đây TỪ data/export/findings.json (sinh bởi
scripts/compute_findings.py). Hai generator scripts/build_dashboard.py và
scripts/build_pbip_report.py chỉ import hàm build() rồi đặt chuỗi vào đúng chỗ,
không gõ cứng chuỗi có số nào.

Mỗi con số trong câu đi kèm "nguồn gốc" (provenance): đường dẫn khóa trong
findings.json, hoặc một phép cộng, trừ, chia giữa các khóa. Nhờ vậy
scripts/check_headlines_sync.py tính lại được từng con số từ findings.json một
cách độc lập và báo lỗi nếu câu chữ lệch số.

Cú pháp đường dẫn: khóa nối bằng dấu chấm; phần tử danh sách chọn bằng
[trường=giá trị] hoặc [trường1=giá trị1,trường2=giá trị2]. Ví dụ:
    snapshot.buckets[dpd_bucket=B1 1-30].k
    vintage.mob12.by_product_channel[contract_type=Revolving loans,channel_type=Stone].primary.rate

Định dạng số kiểu Việt Nam: chấm ngăn nghìn, phẩy thập phân. Khoảng tin cậy 95%
viết trong ngoặc vuông, cùng đơn vị với số đứng trước, không lặp dấu %.

Chạy thử: python scripts/headlines.py  (in toàn bộ câu chữ ra màn hình)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FINDINGS_PATH = ROOT / "data" / "export" / "findings.json"


# ---------------------------------------------------------------------------
# Đường dẫn khóa và giá trị kèm nguồn gốc
# ---------------------------------------------------------------------------

_SEG = re.compile(r"([^.\[]+)(?:\[([^\]]+)\])?")


def split_path(path):
    """Tách đường dẫn thành các bước (khóa, bộ chọn hoặc None)."""
    steps = []
    for part in _split_top(path):
        m = _SEG.fullmatch(part)
        if not m:
            raise ValueError("Đường dẫn sai cú pháp: %r" % path)
        key, sel = m.group(1), m.group(2)
        cond = None
        if sel:
            cond = dict(kv.split("=", 1) for kv in sel.split(","))
        steps.append((key, cond))
    return steps


def _split_top(path):
    """Tách theo dấu chấm nằm ngoài ngoặc vuông (giá trị bộ chọn được chứa dấu chấm)."""
    out, buf, depth = [], "", 0
    for ch in path:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        if ch == "." and depth == 0:
            out.append(buf)
            buf = ""
        else:
            buf += ch
    out.append(buf)
    return out


def resolve(data, path):
    """Lấy giá trị theo đường dẫn. Bộ chọn phải khớp đúng một phần tử."""
    cur = data
    for key, cond in split_path(path):
        # Chỉ số danh sách dạng số, ví dụ ci95.0 là cận dưới, ci95.1 là cận trên.
        cur = cur[int(key)] if isinstance(cur, list) and key.isdigit() else cur[key]
        if cond is not None:
            hits = [x for x in cur if all(str(x.get(k)) == v for k, v in cond.items())]
            if len(hits) != 1:
                raise KeyError("Bộ chọn %r khớp %d phần tử trong %r" % (cond, len(hits), path))
            cur = hits[0]
    return cur


def evaluate(data, expr):
    """Tính một biểu thức nguồn gốc: {"path": ...} hoặc {"op": "+-/", "a", "b"}."""
    if "path" in expr:
        v = resolve(data, expr["path"])
        if not isinstance(v, (int, float)):
            raise TypeError("Khóa %r không phải số: %r" % (expr["path"], v))
        return v
    a, b = evaluate(data, expr["a"]), evaluate(data, expr["b"])
    return {"+": a + b, "-": a - b, "/": a / b}[expr["op"]]


class V:
    """Một giá trị số kèm biểu thức nguồn gốc của nó."""

    def __init__(self, value, expr):
        self.value, self.expr = value, expr

    def _op(self, other, op):
        val = {"+": self.value + other.value, "-": self.value - other.value,
               "/": self.value / other.value}[op]
        return V(val, {"op": op, "a": self.expr, "b": other.expr})

    def __add__(self, other):
        return self._op(other, "+")

    def __sub__(self, other):
        return self._op(other, "-")

    def __truediv__(self, other):
        return self._op(other, "/")


class Findings:
    def __init__(self, data):
        self.data = data

    def __call__(self, path):
        return V(resolve(self.data, path), {"path": path})


# ---------------------------------------------------------------------------
# Định dạng số kiểu Việt Nam. Dùng chung cho headlines và trình kiểm tra.
# ---------------------------------------------------------------------------

def fmt_num(x, decimals=1):
    s = f"{x:,.{decimals}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_int(x):
    return f"{int(round(x)):,}".replace(",", ".")


def format_value(kind, decimals, value):
    """kind: int (số nguyên), num (số thập phân), pct (tỷ lệ ra %),
    pctci (tỷ lệ ra phần trăm nhưng không kèm dấu %), bil (đơn vị thô ra tỷ)."""
    if kind == "int":
        return fmt_int(value)
    if kind == "num":
        return fmt_num(value, decimals)
    if kind == "pct":
        return fmt_num(value * 100, decimals) + "%"
    if kind == "pctci":
        return fmt_num(value * 100, decimals)
    if kind == "bil":
        return fmt_num(value / 1e9, decimals)
    raise ValueError(kind)


class Text:
    """Gom các con số của MỘT câu cùng nguồn gốc. Gọi .done(chuỗi) để chốt."""

    def __init__(self):
        self.numbers = []

    def _reg(self, v, kind, decimals):
        s = format_value(kind, decimals, v.value)
        self.numbers.append({"text": s, "kind": kind, "decimals": decimals, "expr": v.expr})
        return s

    def int(self, v):
        return self._reg(v, "int", 0)

    def num(self, v, d=2):
        return self._reg(v, "num", d)

    def pct(self, v, d=1):
        return self._reg(v, "pct", d)

    def bil(self, v, d=1):
        return self._reg(v, "bil", d)

    def ci_pct(self, lo, hi, d=1):
        return "[%s; %s]" % (self._reg(lo, "pctci", d), self._reg(hi, "pctci", d))

    def ci_num(self, lo, hi, d=2):
        return "[%s; %s]" % (self._reg(lo, "num", d), self._reg(hi, "num", d))

    def done(self, text):
        for n in self.numbers:
            if n["text"] not in text:
                raise ValueError("Số %r đăng ký nhưng không có trong câu: %s" % (n["text"], text))
        for bad in (chr(0x2014), chr(0x2013)):
            if bad in text:
                raise ValueError("Câu chứa em dash hoặc en dash: " + text)
        return {"text": text, "numbers": self.numbers}


def plain(text):
    """Câu không có con số nào cần truy nguồn."""
    return Text().done(text)


# ---------------------------------------------------------------------------
# Nội dung 4 trang
# ---------------------------------------------------------------------------

def _rate_ci(T, node, d_rate, d_ci):
    """'0,167% [0,137; 0,203]' từ một nút tỷ lệ {rate, ci95}."""
    return "%s %s" % (T.pct(node("rate"), d_rate),
                      T.ci_pct(node("ci95[0]"), node("ci95[1]"), d_ci))


class _Node:
    """Tiện ích: f.node('a.b') rồi gọi node('rate') thay vì viết lại tiền tố."""

    def __init__(self, f, prefix):
        self.f, self.prefix = f, prefix

    def __call__(self, rest):
        # Cho phép viết ci95[0] / ci95[1] cho gọn; quy về đường dẫn ci95.0 / ci95.1.
        rest = rest.replace("ci95[0]", "ci95.0").replace("ci95[1]", "ci95.1")
        return self.f(self.prefix + "." + rest)


OC = "origination_cohort.mob12"
RC = "review_checks"


def _smr_node(f, scheme, ch, tag="primary", mob="mob12"):
    return _Node(f, f"origination_cohort.{mob}.smr_by_channel.{scheme}.{tag}[channel_type={ch}]")


def _num_ci(T, node, d=2):
    """'1,65 [1,21; 2,18]' từ một nút {smr hoặc ratio, ci95}."""
    key = "smr" if "smr_by_channel" in node.prefix else "ratio"
    return "%s %s" % (T.num(node(key), d), T.ci_num(node("ci95[0]"), node("ci95[1]"), d))


def page1(f):
    N = lambda p: _Node(f, p)
    b0 = N("snapshot.buckets[dpd_bucket=B0 Current]")
    b1 = N("snapshot.buckets[dpd_bucket=B1 1-30]")
    b4 = N("snapshot.buckets[dpd_bucket=B4 90+]")
    b4n = N("snapshot.buckets_no_threshold[dpd_bucket=B4 90+]")
    ks = "snapshot.kpi_same_set.exposure_known_set"
    same = N(ks + ".contracts_30_plus_exposure_known")
    allo = N(ks + ".contracts_30_plus_all_open")
    exu = N("snapshot.kpi_same_set.excluding_unknown.contracts_30_plus_all_open")
    cco = N("snapshot.by_channel[channel_type=Credit and cash offices].primary")
    cco_cash = N(RC + ".snapshot_by_product_channel[contract_type=Cash loans,channel_type=Credit and cash offices].primary")
    cash = N("snapshot.by_product[contract_type=Cash loans].primary")
    late = N(RC + ".snapshot_cash_loans_30_plus_timing.all_cash_loans")
    miss = N(RC + ".snapshot_exposure_missing")
    unk = "snapshot.unknown_group"

    T = Text()
    dek = T.done(f"{T.pct(b0('rate'), 2)} hợp đồng đang mở không quá hạn; 30+ chỉ "
                 f"{T.pct(same('rate'), 3)} theo số hợp đồng và "
                 f"{T.pct(f(ks + '.exposure_30_plus_share'), 3)} theo dư nợ, dồn vào vay tiền mặt quá hạn muộn: "
                 f"{T.int(late('first_30_plus_after_mob12.k'))} trên {T.int(late('n'))} ca lần đầu 30+ sau MOB 12")

    T = Text()
    hero = T.done(f"Đuôi quá hạn chủ yếu là B1 1-30: {T.int(b1('k'))} hợp đồng, "
                  f"so với {T.int(allo('k'))} từ B2 trở lên")

    # M3: không xếp hạng kênh bằng số thô; tỷ lệ theo kênh phản ánh cơ cấu sản phẩm.
    T = Text()
    chan = T.done(f"Tỷ lệ 30+ hiện tại theo kênh phản ánh sản phẩm, không xếp hạng kênh: {T.int(cco_cash('k'))} "
                  f"trên {T.int(cco('k'))} ca của Credit and cash offices là vay tiền mặt")

    T = Text()
    prod = T.done(f"Vay tiền mặt gánh {T.int(cash('k'))} trên {T.int(allo('k'))} ca 30+ đang mở, "
                  f"tỷ lệ {_rate_ci(T, cash, 3, 3)}")

    bn = lambda b: f(f"snapshot.buckets_no_threshold[dpd_bucket={b}].exposure")
    exp_nt = (bn("B2 31-60") + bn("B3 61-90") + bn("B4 90+")) / f(ks + ".exposure_total")
    T = Text()
    caveat = T.done(
        f"Ảnh chụp tại tháng quan sát gần nhất ({T.int(f('snapshot.n_open'))} hợp đồng mở). "
        f"Hai thẻ tỷ lệ tính trên cùng một tập {T.int(same('n'))} hợp đồng có dư nợ proxy, tức bỏ "
        f"{T.int(miss('n_contracts'))} hợp đồng thiếu dư nợ chứa {T.int(miss('n_30_plus'))} trên {T.int(allo('k'))} ca 30+, "
        f"toàn bộ thuộc nhóm (không rõ); bỏ hẳn nhóm (không rõ) cũng ra {T.pct(exu('rate'), 3)} "
        f"({T.int(exu('k'))} / {T.int(exu('n'))}). Biểu đồ kênh và bảng sản phẩm tính trên mọi hợp đồng mở "
        f"(30+ là {T.pct(allo('rate'), 3)}); khoảng tin cậy giữa các kênh chồng nhau và mỗi kênh bán một rổ sản phẩm "
        f"khác nhau, nên biểu đồ không dùng để xếp hạng kênh. Nhóm (không rõ) chiếm "
        f"{T.pct(f(unk + '.share_of_open.rate'), 2)} hợp đồng mở nhưng "
        f"{T.int(f(unk + '.share_of_30_plus.k'))} trên {T.int(allo('k'))} ca 30+: giữ trong bảng, "
        f"loại khỏi biểu đồ kênh. Độ nhạy: nếu không áp ngưỡng trọng yếu (SK_DPD) thì có "
        f"{T.int(f(unk + '.share_of_30_plus_no_threshold.n'))} hợp đồng 30+ và B4 90+ là "
        f"{T.int(b4n('k'))} thay vì {T.int(b4('k'))}, nhưng tỷ lệ dư nợ 30+ chỉ từ "
        f"{T.pct(f(ks + '.exposure_30_plus_share'), 3)} lên {T.pct(exp_nt, 3)}: phần chênh là khoản dư lẻ.")

    T = Text()
    kpi_rate = T.done(f"{T.int(same('k'))} trên {T.int(same('n'))} hợp đồng có dư nợ proxy")
    T = Text()
    kpi_exp = T.done(f"Trên {T.bil(f(ks + '.exposure_total'), 1)} tỷ dư nợ proxy, "
                     "cùng tập hợp đồng với thẻ tỷ lệ theo hợp đồng")
    T = Text()
    kpi_open = T.done(f"Gồm cả {T.int(f(ks + '.n_loans_exposure_unknown'))} hợp đồng thiếu dư nợ proxy")

    return {
        "n": 1, "key": "tong-quan", "tab": "1. Tổng quan",
        "title": plain("Tổng quan danh mục"), "dek": dek, "caveat": caveat,
        "visuals": {"bucket_mix": hero, "rate_by_channel": chan, "product_table": prod},
        "notes": {"kpi_open": kpi_open, "kpi_rate": kpi_rate, "kpi_exposure_rate": kpi_exp},
    }


def page2(f):
    N = lambda p: _Node(f, p)
    cell = lambda p, ch: N(f"vintage.mob12.by_product_channel[contract_type={p},channel_type={ch}].primary")
    std = lambda ch: f(f"approval.channel_standardized[channel_type={ch}].standardized_ratio")
    sc = N(OC + ".stone_vs_country_wide.primary.mh_product_3_strata")
    sc_c = N(OC + ".stone_vs_country_wide.primary.mh_product_x_cut12")
    sc_d = N(OC + ".stone_vs_country_wide.due_only.mh_product_x_cut12")
    sx = lambda ch, tag="primary": _smr_node(f, "product_x_cut12", ch, tag)
    sp = lambda ch: _smr_node(f, "product_only", ch)
    mix_cco = N(OC + ".mix_channel_product_cohort.cut3[channel_type=Credit and cash offices,"
                     "contract_type=Revolving loans,origination_cohort_start=-35]")
    mix_cc = N(OC + ".mix_channel_product_cohort.cut3[channel_type=Contact center,"
                    "contract_type=Revolving loans,origination_cohort_start=-35]")
    cc_card = lambda ch: N(OC + f".smr_by_channel.product_x_cut12.primary[channel_type={ch}]"
                                ".by_product[contract_type=Revolving loans]")

    T = Text()
    dek = T.done("Kiểm soát cả sản phẩm lẫn đợt mở: Contact center vẫn trên kỳ vọng (SMR "
                 + _num_ci(T, sx("Contact center")) + "), Stone trên kỳ vọng theo định nghĩa chính ("
                 + _num_ci(T, sx("Stone")) + "), Credit and cash offices không còn khác ("
                 + _num_ci(T, sx("Credit and cash offices")) + ")")

    T = Text()
    trellis = T.done(
        f"Trong thẻ, Contact center {T.pct(cell('Revolving loans', 'Contact center')('rate'), 3)} và Stone "
        f"{T.pct(cell('Revolving loans', 'Stone')('rate'), 3)} so với Credit and cash offices "
        f"{T.pct(cell('Revolving loans', 'Credit and cash offices')('rate'), 3)} tại MOB 12, nhưng "
        f"{T.pct(mix_cco('share_of_channel_product'), 1)} thẻ của kênh sau mở từ -35 trở về sau, "
        f"Contact center chỉ {T.pct(mix_cc('share_of_channel_product'), 1)}")

    T = Text()
    smr_t = T.done(
        f"Chuẩn hoá thêm đợt mở: Contact center từ {T.num(sp('Contact center')('smr'), 2)} xuống "
        + _num_ci(T, sx("Contact center")) + f", Credit and cash offices từ {T.num(sp('Credit and cash offices')('smr'), 2)} lên "
        + _num_ci(T, sx("Credit and cash offices")) + "; phần vượt của Contact center nằm ở thẻ ("
        + f"{T.int(cc_card('Contact center')('observed'))} ca so với {T.num(cc_card('Contact center')('expected'), 1)} kỳ vọng)")

    T = Text()
    appr = T.done(f"Tỷ lệ duyệt chênh do cơ cấu sản phẩm: chuẩn hoá thì Credit and cash offices "
                  f"{T.num(std('Credit and cash offices'), 2)} và Stone {T.num(std('Stone'), 2)} lần kỳ vọng")

    T = Text()
    obs = lambda ch: f(f"channel_comparison.mob12.smr_by_channel[channel_type={ch}].primary.observed")
    caveat = T.done(
        "SMR = số ca từng 30+ tại MOB 12 chia số ca kỳ vọng nếu kênh có tỷ lệ của từng tầng (sản phẩm × đợt mở "
        "12 tháng) trên toàn danh mục có nhãn; khoảng tin cậy 95% Byar. Mỗi SMR so một kênh với kỳ vọng của chính "
        "nó; không chia hai SMR cho nhau để so hai kênh. Kiểm soát đợt mở là phân tích hậu nghiệm, thêm sau lần "
        "soát độc lập thứ hai. Theo định nghĩa giữa (SK_DPD 30+ ở tháng còn kỳ phải trả), Contact center "
        f"{_num_ci(T, sx('Contact center', 'due_only'))}, Stone {_num_ci(T, sx('Stone', 'due_only'))}: chỉ "
        "Contact center giữ. Stone / Country-wide gộp Mantel-Haenszel qua ba sản phẩm "
        f"{_num_ci(T, sc)}, qua sản phẩm × đợt {_num_ci(T, sc_c)}, theo định nghĩa giữa {_num_ci(T, sc_d)}; "
        "các cặp khác chỉ để mô tả. AP+ (Cash loan) có "
        f"{T.int(obs('AP+ (Cash loan)'))} ca và Khác {T.int(obs('Khác'))} ca: tử số quá nhỏ, không kết luận. "
        "Tỷ lệ duyệt = (duyệt + duyệt không dùng) / đã có quyết định; take-up chỉ tính cho vay tiêu dùng. "
        f"Nhóm (không rõ) không có kênh nên bị loại. FPD30 không dùng làm trục rủi ro: chỉ "
        f"{T.int(f('fpd30.total.amount_rule.k'))} ca trên {T.int(f('fpd30.total.amount_rule.n'))} hợp đồng.")

    T = Text()
    trellis_sub = T.done(
        f"Vay tiêu dùng: Stone {T.pct(cell('Consumer loans', 'Stone')('rate'), 3)} so với Country-wide "
        f"{T.pct(cell('Consumer loans', 'Country-wide')('rate'), 3)}. Vay tiền mặt: Country-wide "
        f"{T.pct(cell('Cash loans', 'Country-wide')('rate'), 3)} so với Credit and cash offices "
        f"{T.pct(cell('Cash loans', 'Credit and cash offices')('rate'), 3)}.")

    return {
        "n": 2, "key": "kenh-ban", "tab": "2. Kênh bán",
        "title": plain("Kênh bán và rủi ro"), "dek": dek, "caveat": caveat,
        "visuals": {"mix_trellis": trellis, "smr": smr_t, "approval": appr},
        "notes": {"trellis_sub": trellis_sub},
    }


def page3(f):
    N = lambda p: _Node(f, p)
    pr = lambda p, tag, key: N(f"{OC}.product_ratio_vs_cash.{p}.{tag}.{key}")
    cc = lambda m: f(f"vintage.{m}.by_channel[channel_type=Contact center].primary.rate")
    prod = lambda p: N(f"vintage.mob12.by_product[contract_type={p}].primary")
    unk = N("vintage.mob12.by_product[contract_type=(không rõ)].primary")
    tot = lambda s: N(f"{OC}.cohort_vintage.cut12.total_labeled_products[origination_cohort_start={s}].primary")
    ovn = lambda p: N(f"{OC}.cohort_vintage.cut12.oldest_vs_newest_aged[contract_type={p}].primary")
    cards = N(OC + ".cards_by_channel_cohort[channel_type=Contact center]")
    old_cc = N(OC + ".cards_by_channel_cohort[channel_type=Contact center].cut3[origination_cohort_start=-96].primary")
    ug = N(RC + ".unknown_application_group")

    T = Text()
    rv = pr("Revolving loans", "primary", "mh_cut12")
    dek = T.done(f"Kiểm soát đợt mở, thẻ quay vòng vẫn rủi ro nhất: gấp {_num_ci(T, rv)} lần vay tiền mặt tại "
                 f"MOB 12; vay tiêu dùng so với vay tiền mặt đổi chiều theo định nghĩa và kiểm soát, "
                 "không kết luận được")

    # Visual mới (agent dựng giao diện sẽ vẽ): đường vintage theo đợt mở.
    T = Text()
    cohort = T.done(
        f"Đợt mở cũ xấu hơn hẳn đợt gần: ever 30+ tại MOB 12 là {_rate_ci(T, tot(-96), 3, 3)} ở đợt -96 đến -85, "
        f"{_rate_ci(T, tot(-24), 3, 3)} ở đợt -24 đến -13; trong cùng sản phẩm đợt cũ nhất gấp "
        f"{T.num(ovn('Cash loans')('ratio'), 1)} lần (vay tiền mặt) đến {T.num(ovn('Consumer loans')('ratio'), 0)} lần "
        "(vay tiêu dùng)")

    T = Text()
    trellis = T.done(f"Số thô theo kênh: Contact center cao nhất tại MOB 6, MOB 12 và MOB 24 ({T.pct(cc('mob6'), 3)}, "
                     f"{T.pct(cc('mob12'), 3)}, {T.pct(cc('mob24'), 3)}), nhưng {T.int(old_cc('k'))} trên "
                     f"{T.int(cards('total.k'))} ca thẻ của kênh tại MOB 12 là thẻ mở từ -60 trở về trước")

    T = Text()
    by_prod = T.done(f"Số thô tại MOB 12: thẻ quay vòng {_rate_ci(T, prod('Revolving loans'), 3, 3)}, vay tiền mặt "
                     f"{T.pct(prod('Cash loans')('rate'), 3)}, vay tiêu dùng {T.pct(prod('Consumer loans')('rate'), 3)}")

    T = Text()
    sens = T.done(
        "Vay tiêu dùng / vay tiền mặt tuỳ cách đo: "
        f"{T.num(pr('Consumer loans', 'primary', 'crude')('ratio'), 2)} theo định nghĩa chính, "
        f"{T.num(pr('Consumer loans', 'primary', 'mh_cut12')('ratio'), 2)} khi kiểm soát đợt mở, "
        f"{T.num(pr('Consumer loans', 'due_only', 'crude')('ratio'), 2)} theo định nghĩa giữa, "
        f"{T.num(pr('Consumer loans', 'no_threshold', 'crude')('ratio'), 2)} khi không áp ngưỡng trọng yếu")

    m24 = "vintage.mob24.total"
    T = Text()
    caveat = T.done(
        "Mẫu số: hợp đồng đã biết kết quả đến MOB n, loại is_partial_history; tại MOB 24 chỉ "
        f"{T.int(f(m24 + '.n_observed_full'))} hợp đồng "
        f"({T.pct(f(m24 + '.n_observed_full') / f(m24 + '.primary.n'), 1)}) quan sát đủ. "
        "Đợt mở = nhóm 12 tháng của tháng mở hợp đồng, tính tương đối so với ngày nộp hồ sơ hiện tại của từng khách, "
        "không phải tháng lịch; đường theo đợt chỉ vẽ MOB mà cả đợt đã đủ tuổi. Không phân biệt được chất lượng "
        "giải ngân cải thiện thật với chọn lọc mẫu (khách vừa quá hạn gần đây ít có hồ sơ mới). Kiểm soát đợt mở là "
        "hậu nghiệm; tỷ số thẻ / vay tiền mặt qua ba cách cắt đợt từ "
        f"{T.num(pr('Revolving loans', 'primary', 'mh_cut12')('ratio'), 2)} đến "
        f"{T.num(pr('Revolving loans', 'primary', 'mh_cut3')('ratio'), 2)}. "
        f"Nhóm (không rõ) có {T.int(unk('n'))} hợp đồng tại MOB 12 nhưng tỷ lệ {T.pct(unk('rate'), 3)} và gánh "
        f"{T.int(unk('k'))} trên {T.int(f('vintage.mob12.total.primary.k'))} ca; vintage của nhóm chỉ dựa trên "
        f"{T.int(ug('n_vintage_base_mob0'))} hợp đồng, và nếu hợp đồng dừng sớm của nhóm được coi là đã đóng như nhóm "
        f"có hồ sơ thì tỷ lệ là {T.pct(ug('mob12_if_unknown_end_state_treated_as_closed.rate'), 2)}. Hai biểu đồ đường "
        "loại nhóm này để không kéo lệch thang chung, bảng bên phải giữ lại. Toàn danh mục "
        f"{T.pct(f('vintage.mob12.total.primary.rate'), 3)}, không gồm nhóm này "
        f"{T.pct(f('vintage.mob12.total_excluding_unknown_application.primary.rate'), 3)}.")

    return {
        "n": 3, "key": "vintage", "tab": "3. Vintage",
        "title": plain("Vintage theo MOB và đợt mở"), "dek": dek, "caveat": caveat,
        "visuals": {"cohort": cohort, "trellis": trellis, "by_product": by_prod, "sensitivity": sens},
        "notes": {},
    }


def page4(f):
    N = lambda p: _Node(f, p)
    st = lambda s: N(f"roll_cure.primary.all[from_state={s}]")
    nt = lambda s: N(f"roll_cure.no_threshold.all[from_state={s}]")
    b1, b2, b3, b4 = st("B1 1-30"), st("B2 31-60"), st("B3 61-90"), st("B4 90+")
    mhc = N("origination_cohort.cure_b1_vs_b2_by_cohort.mh_b1_over_b2")
    rt = N(RC + ".roll_totals")
    cs = N(RC + ".collections_sample_size_by_contract")
    cs5 = N(RC + ".collections_sample_size_by_contract.by_absolute_increase[absolute_increase_pp=5.0]")

    def cure_ci(T, s):
        return "%s %s" % (T.pct(s("cure_to_b0.rate"), 1),
                          T.ci_pct(s("cure_to_b0.ci95.0"), s("cure_to_b0.ci95.1"), 1))

    T = Text()
    dek = T.done(f"Cửa sổ thu hồi đóng nhanh sau B1: cure {cure_ci(T, b1)} ở B1, còn {cure_ci(T, b2)} ở B2 "
                 f"và {T.pct(b4('cure_to_b0.rate'), 1)} ở B4; trong từng đợt mở B1 vẫn gấp {_num_ci(T, mhc)} lần B2")

    T = Text()
    matrix = T.done(f"B1 hiếm khi rơi tiếp: mỗi tháng chỉ {T.pct(b1('roll_forward.rate'), 3)} sang B2, "
                    f"{T.pct(b1('cure_to_b0.rate'), 1)} quay về B0")

    T = Text()
    cure = T.done(f"Cure {T.pct(b1('cure_to_b0.rate'), 1)} ở B1, {T.pct(b2('cure_to_b0.rate'), 1)} ở B2, "
                  f"{T.pct(b4('cure_to_b0.rate'), 1)} ở B4; B3 chỉ {T.int(b3('n_from'))} lượt, chưa đủ mẫu")

    T = Text()
    scale = T.done(f"Mẫu số từng nhóm: B1 có {T.int(b1('n_from'))} lượt, B2 chỉ {T.int(b2('n_from'))} "
                   f"và B3 {T.int(b3('n_from'))}")

    T = Text()
    caveat = T.done(
        "Lượt hợp đồng-tháng từ tháng t sang t+1, toàn danh mục; một hợp đồng góp nhiều lượt nên các lượt không độc "
        f"lập. Cure = quay về B0 Current tháng sau; dòng B0 không có cure nên để trống. Dòng Tổng của bảng cộng mọi "
        f"nhóm xuất phát kể cả B0 ({T.int(rt('n_from_all_states'))} lượt); cure gộp B1 trở lên là "
        f"{T.pct(rt('cure_b1_plus.rate'), 1)} trên {T.int(rt('cure_b1_plus.n'))} lượt, không phải cure của dòng Tổng. "
        f"Nhóm dưới {T.int(f('meta.min_n_to_interpret'))} lượt (B3) "
        "không diễn giải. Cột dư nợ là dư nợ proxy cộng dồn qua mọi tháng xuất phát, không phải dư nợ tại "
        "một thời điểm. Mẫu số cộng n_loans qua mọi nhóm đến, KHÔNG cộng cột n_from (window sum lặp lại). "
        f"Thử nghiệm thu hồi tính theo hợp đồng: cure ở lần đầu vào B1 là {T.pct(cs('first_b1_cure_baseline.rate'), 1)}, "
        f"phát hiện mức tăng {T.num(cs5('absolute_increase_pp'), 0)} điểm phần trăm cần {T.int(cs5('n_per_arm'))} hợp đồng "
        f"mỗi nhánh. Độ nhạy SK_DPD: cure B1 {T.pct(nt('B1 1-30')('cure_to_b0.rate'), 1)}, B1 sang B2 "
        f"{T.pct(nt('B1 1-30')('roll_forward.rate'), 3)}.")

    return {
        "n": 4, "key": "thu-hoi", "tab": "4. Thu hồi",
        "title": plain("Chuyển nhóm và thu hồi"), "dek": dek, "caveat": caveat,
        "visuals": {"matrix": matrix, "cure": cure, "roll_tbl": scale},
        "notes": {},
    }


def load_findings(path=FINDINGS_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build(findings=None):
    """Trả về danh sách 4 trang. Mỗi trang: n, key, tab, title, dek, caveat,
    visuals {khóa visual: câu}, notes {khóa: câu chỉ dùng ở bản HTML}. Mỗi câu là
    dict {"text", "numbers"}; numbers là danh sách con số kèm nguồn gốc."""
    f = Findings(findings if findings is not None else load_findings())
    return [page1(f), page2(f), page3(f), page4(f)]


def texts(pages):
    """Rút gọn: {trang n: {"title", "dek", "caveat", "visuals": {khóa: chuỗi}, "notes": {...}}}."""
    out = {}
    for p in pages:
        out[p["n"]] = {
            "tab": p["tab"], "title": p["title"]["text"], "dek": p["dek"]["text"],
            "caveat": p["caveat"]["text"],
            "visuals": {k: v["text"] for k, v in p["visuals"].items()},
            "notes": {k: v["text"] for k, v in p["notes"].items()},
        }
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for n, p in texts(build()).items():
        print("=" * 70, "\nTRANG", n, p["title"])
        print("  dek:", p["dek"])
        for k, v in p["visuals"].items():
            print("  [%s] %s" % (k, v))
        for k, v in p["notes"].items():
            print("  (ghi chú HTML %s) %s" % (k, v))
        print("  LƯU Ý:", p["caveat"])
