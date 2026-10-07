"""Tính mọi con số dùng cho kết luận và ghi ra data/export/findings.json.

Cách dùng:
    PYTHONUTF8=1 .venv/Scripts/python.exe scripts/compute_findings.py

findings.json là NGUỒN SỰ THẬT DUY NHẤT cho các câu kết luận trong README, memo, dashboard
và Power BI. Mọi tỷ lệ đi kèm tử số, mẫu số và khoảng tin cậy 95%. Không chép tay số vào
tài liệu: trích từ file này.

Đọc data/warehouse.duckdb ở chế độ CHỈ ĐỌC, một luồng (PRAGMA threads=1) để tổng số thực
tất định. Mọi truy vấn có order by, số thực làm tròn 10 chữ số, JSON ghi với sort_keys.

Định nghĩa quá hạn chính: SK_DPD_DEF (DPD có ngưỡng trọng yếu, cột dpd/is_30_plus).
Độ nhạy: SK_DPD (không áp ngưỡng trọng yếu, hậu tố _no_threshold).

Phương pháp thống kê (chỉ dùng thư viện chuẩn của Python):
    - Tỷ lệ: khoảng Wilson 95%.
    - Tỷ số hai tỷ lệ (rate ratio, thực chất là risk ratio): khoảng log theo Katz. Nếu một
      tử số bằng 0 thì cộng 0,5 vào mọi ô (hiệu chỉnh Haldane) và ghi cờ.
    - So kênh có kiểm soát sản phẩm: chuẩn hoá gián tiếp, SMR = quan sát / kỳ vọng, kỳ vọng
      tính bằng tỷ lệ của từng sản phẩm trên toàn danh mục có nhãn. Khoảng Byar (xấp xỉ
      Poisson chính xác), không tính bất định của tỷ lệ tham chiếu. Kèm tỷ số Mantel-Haenszel
      gộp qua sản phẩm cho từng cặp kênh (phương sai Greenland-Robins).
    - Cỡ mẫu: hai tỷ lệ độc lập, hai phía, alpha 0,05, power 0,8, chia nhánh 1:1.
    - Đợt mở hợp đồng (origination_cohort, thêm sau lần soát thứ hai): vintage theo đợt mở và
      phân tầng sản phẩm × đợt cho SMR và Mantel-Haenszel, ba cách cắt đợt để kiểm độ nhạy.
"""
import json
import math
import sys
from itertools import combinations
from pathlib import Path
from statistics import NormalDist

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "warehouse.duckdb"
OUT_PATH = ROOT / "data" / "export" / "findings.json"

Z = NormalDist().inv_cdf(0.975)          # 1,959964
Z_POWER = NormalDist().inv_cdf(0.80)     # 0,841621
MIN_N = 1000          # mẫu số tối thiểu để diễn giải một ô (quy ước của project)
MOBS = [6, 12, 24]
UNKNOWN = "(không rõ)"
PRODUCTS = ["Cash loans", "Consumer loans", "Revolving loans"]
# Kênh có nhãn thật; 'Khác', 'Unknown', '(không rõ)' không đưa vào so sánh cặp kênh.
NON_CHANNELS = {UNKNOWN, "Khác", "Unknown"}
DIGITS = 10


# ---------------------------------------------------------------------------
# Thống kê
# ---------------------------------------------------------------------------

def rnd(x):
    if x is None:
        return None
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return round(float(x), DIGITS)


def prop(k, n):
    """Tỷ lệ k/n kèm khoảng Wilson 95%."""
    k, n = int(k or 0), int(n or 0)
    if n == 0:
        return {"k": k, "n": n, "rate": None, "ci95": [None, None], "enough_n": False}
    p = k / n
    denom = 1 + Z * Z / n
    centre = (p + Z * Z / (2 * n)) / denom
    half = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / denom
    return {"k": k, "n": n, "rate": rnd(p), "ci95": [rnd(max(0.0, centre - half)), rnd(min(1.0, centre + half))],
            "enough_n": n >= MIN_N}


def ratio(k1, n1, k0, n0):
    """Tỷ số (k1/n1) / (k0/n0), khoảng log Katz 95%."""
    k1, n1, k0, n0 = int(k1), int(n1), int(k0), int(n0)
    out = {"numerator": prop(k1, n1), "reference": prop(k0, n0), "method": "katz_log"}
    if n1 < MIN_N or n0 < MIN_N:
        # Dưới ngưỡng diễn giải của project: không tính tỷ số (tránh tỷ số vô nghĩa do hiệu chỉnh Haldane).
        out.update({"ratio": None, "ci95": [None, None], "significant": None, "haldane": False,
                    "skipped": "n_below_min"})
        return out
    haldane = k1 == 0 or k0 == 0
    a, b = (k1 + 0.5, k0 + 0.5) if haldane else (k1, k0)
    m1, m0 = (n1 + 1, n0 + 1) if haldane else (n1, n0)
    rr = (a / m1) / (b / m0)
    se = math.sqrt(1 / a - 1 / m1 + 1 / b - 1 / m0)
    lo, hi = rr * math.exp(-Z * se), rr * math.exp(Z * se)
    out.update({"ratio": rnd(rr), "ci95": [rnd(lo), rnd(hi)],
                "significant": bool(lo > 1 or hi < 1), "haldane": haldane})
    return out


def byar_ci(obs, exp):
    """Khoảng 95% cho O/E, O xem như Poisson (xấp xỉ Byar)."""
    if exp <= 0:
        return [None, None]
    if obs == 0:
        return [0.0, rnd(-math.log(0.025) / exp)]
    lo = obs * (1 - 1 / (9 * obs) - Z / (3 * math.sqrt(obs))) ** 3
    o1 = obs + 1
    hi = o1 * (1 - 1 / (9 * o1) + Z / (3 * math.sqrt(o1))) ** 3
    return [rnd(lo / exp), rnd(hi / exp)]


def mantel_haenszel_rr(strata):
    """strata: list (k1, n1, k0, n0). Trả RR gộp và khoảng 95% (Greenland-Robins)."""
    strata = [s for s in strata if s[1] > 0 and s[3] > 0]
    num = sum(k1 * n0 / (n1 + n0) for k1, n1, k0, n0 in strata)
    den = sum(k0 * n1 / (n1 + n0) for k1, n1, k0, n0 in strata)
    if num == 0 or den == 0:
        return {"ratio": None, "ci95": [None, None], "significant": None, "n_strata": len(strata)}
    var_num = sum((n1 * n0 * (k1 + k0) - k1 * k0 * (n1 + n0)) / (n1 + n0) ** 2
                  for k1, n1, k0, n0 in strata)
    rr = num / den
    se = math.sqrt(var_num / (num * den))
    lo, hi = rr * math.exp(-Z * se), rr * math.exp(Z * se)
    return {"ratio": rnd(rr), "ci95": [rnd(lo), rnd(hi)], "significant": bool(lo > 1 or hi < 1),
            "n_strata": len(strata), "method": "mantel_haenszel_greenland_robins"}


def n_per_arm(p1, rel_change):
    """Cỡ mẫu mỗi nhánh để phát hiện p2 = p1 * (1 + rel_change)."""
    if not p1:
        return None
    p2 = p1 * (1 + rel_change)
    pbar = (p1 + p2) / 2
    num = (Z * math.sqrt(2 * pbar * (1 - pbar)) + Z_POWER * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    return int(math.ceil(num / (p1 - p2) ** 2))


# ---------------------------------------------------------------------------
# Truy vấn
# ---------------------------------------------------------------------------

def rows(con, sql, params=None):
    rel = con.execute(sql, params or [])
    cols = [d[0] for d in rel.description]
    return [dict(zip(cols, r)) for r in rel.fetchall()]


def one(con, sql, params=None):
    return rows(con, sql, params)[0]


def portfolio(con):
    base = one(con, """
        select
            (select count(*) from core.dim_loan)                                        as n_loans,
            (select count(*) from core.dim_loan where source = 'pos_cash')              as n_loans_installment,
            (select count(*) from core.dim_loan where source = 'credit_card')           as n_loans_card,
            (select count(*) from core.dim_loan where not has_application)              as n_loans_no_application,
            (select count(*) from core.fct_loan_month)                                  as n_loan_months,
            (select count(*) from stg.previous_application
              where is_last_appl_per_contract and is_last_appl_in_day)                  as n_applications_dedup,
            (select count(*) from stg.previous_application
              where is_last_appl_per_contract and is_last_appl_in_day
                and application_status = 'Approved')                                    as n_approved_dedup,
            (select min(months_balance) from core.fct_loan_month)                       as first_month,
            (select max(months_balance) from core.fct_loan_month)                       as last_month
    """)
    end_states = rows(con, """
        select end_state, count(*) as n_loans,
               count(*) filter (where not is_partial_history) as n_not_partial
        from core.dim_loan group by end_state order by end_state
    """)
    by_product = rows(con, """
        select case when has_application then coalesce(contract_type, 'Unknown') else '(không rõ)' end as contract_type,
               count(*) as n_loans
        from core.dim_loan group by 1 order by 1
    """)
    vintage_base = one(con, """
        select count(*) as n_eligible,
               count(*) filter (where is_partial_history) as n_partial_history,
               count(*) filter (where end_state = 'never_open') as n_never_open
        from core.dim_loan
    """)
    vintage_base["n_vintage_base"] = one(con, """
        select count(*) as n from core.dim_loan where end_state <> 'never_open' and not is_partial_history
    """)["n"]
    return {"totals": base, "end_state": end_states, "by_product": by_product, "vintage_base": vintage_base}


def snapshot(con):
    """Danh mục đang mở tại months_balance = -1 (mart.portfolio_snapshot)."""
    buckets = rows(con, """
        select dpd_bucket, dpd_bucket_order, sum(n_loans) as n_loans, sum(exposure) as exposure
        from mart.portfolio_snapshot group by 1, 2 order by 2
    """)
    buckets_nt = rows(con, """
        select dpd_bucket_no_threshold as dpd_bucket, dpd_bucket_order_no_threshold as dpd_bucket_order,
               count(*) as n_loans, sum(exposure_proxy) as exposure
        from core.fct_loan_month where is_open and months_balance = -1
        group by 1, 2 order by 2
    """)
    n_open = sum(b["n_loans"] for b in buckets)
    for b in buckets + buckets_nt:
        b.update(prop(b["n_loans"], n_open))
        b["exposure"] = rnd(b["exposure"])

    def kpi(where):
        r = one(con, f"""
            select sum(n_loans) as n_loans, sum(n_30_plus) as n_30_plus,
                   sum(n_loans_exposure_known) as n_loans_exp, sum(n_30_plus_exposure_known) as n_30_plus_exp,
                   sum(exposure) as exposure, sum(exposure_30_plus) as exposure_30_plus,
                   sum(n_30_plus_no_threshold) as n_30_plus_nt,
                   sum(exposure_30_plus_no_threshold) as exposure_30_plus_nt
            from mart.portfolio_snapshot where {where}
        """)
        return {
            "contracts_30_plus_all_open": prop(r["n_30_plus"], r["n_loans"]),
            "contracts_30_plus_exposure_known": prop(r["n_30_plus_exp"], r["n_loans_exp"]),
            "exposure_30_plus_share": rnd((r["exposure_30_plus"] or 0) / r["exposure"]) if r["exposure"] else None,
            "exposure_total": rnd(r["exposure"]),
            "exposure_30_plus": rnd(r["exposure_30_plus"]),
            "n_loans_exposure_unknown": int(r["n_loans"] - r["n_loans_exp"]),
            "no_threshold": {
                "contracts_30_plus_all_open": prop(r["n_30_plus_nt"], r["n_loans"]),
                "exposure_30_plus_share": rnd((r["exposure_30_plus_nt"] or 0) / r["exposure"]) if r["exposure"] else None,
            },
        }

    unknown_share = one(con, """
        select sum(n_loans) filter (where channel_type = '(không rõ)') as n_unknown,
               sum(n_loans) as n_all,
               sum(n_30_plus) filter (where channel_type = '(không rõ)') as k_unknown,
               sum(n_30_plus) as k_all,
               sum(n_30_plus_no_threshold) filter (where channel_type = '(không rõ)') as k_unknown_nt,
               sum(n_30_plus_no_threshold) as k_all_nt,
               sum(n_loans_exposure_known) filter (where channel_type = '(không rõ)') as n_unknown_exp
        from mart.portfolio_snapshot
    """)
    by_product = rows(con, """
        select contract_type, sum(n_loans) as n, sum(n_30_plus) as k, sum(n_30_plus_no_threshold) as k_nt
        from mart.portfolio_snapshot group by 1 order by 1
    """)
    by_channel = rows(con, """
        select channel_type, sum(n_loans) as n, sum(n_30_plus) as k, sum(n_30_plus_no_threshold) as k_nt
        from mart.portfolio_snapshot group by 1 order by 1
    """)
    return {
        "note": "Hợp đồng đang mở tại months_balance = -1 (tháng tương đối). Bucket theo SK_DPD_DEF.",
        "n_open": n_open,
        "buckets": buckets,
        "buckets_no_threshold": buckets_nt,
        "kpi_same_set": {
            "note": ("Hai thẻ KPI phải tính trên CÙNG một tập. Tập khuyến nghị: hợp đồng đang mở có "
                     "exposure_proxy (cột *_exposure_known), gồm cả phần '(không rõ)' còn exposure "
                     "(thẻ tín dụng). 'excluding_unknown' bỏ hẳn nhóm '(không rõ)'."),
            "exposure_known_set": kpi("true"),
            "excluding_unknown": kpi("channel_type <> '(không rõ)'"),
        },
        "unknown_group": {
            "share_of_open": prop(unknown_share["n_unknown"], unknown_share["n_all"]),
            "share_of_30_plus": prop(unknown_share["k_unknown"], unknown_share["k_all"]),
            "share_of_30_plus_no_threshold": prop(unknown_share["k_unknown_nt"], unknown_share["k_all_nt"]),
            "n_with_exposure": int(unknown_share["n_unknown_exp"] or 0),
        },
        "by_product": [{"contract_type": r["contract_type"], "primary": prop(r["k"], r["n"]),
                        "no_threshold": prop(r["k_nt"], r["n"])} for r in by_product],
        "by_channel": [{"channel_type": r["channel_type"], "primary": prop(r["k"], r["n"]),
                        "no_threshold": prop(r["k_nt"], r["n"])} for r in by_channel],
    }


def vintage_cells(con, mob, dims, where="true"):
    cols = ", ".join(dims)
    gb = f"group by {cols} order by {cols}" if dims else ""
    sel = f"{cols}," if dims else ""
    return rows(con, f"""
        select {sel} sum(n_loans) as n, sum(n_ever_30_plus) as k,
               sum(n_ever_30_plus_no_threshold) as k_nt, sum(n_observed_full) as n_full
        from mart.vintage where mob = ? and {where} {gb}
    """, [mob])


def fmt_cells(cells, dims):
    out = []
    for c in cells:
        d = {k: c[k] for k in dims}
        d.update({"primary": prop(c["k"], c["n"]), "no_threshold": prop(c["k_nt"], c["n"]),
                  "n_observed_full": int(c["n_full"])})
        out.append(d)
    return out


def vintage(con):
    res = {"note": ("ever 30+@MOBn. Mẫu số: hợp đồng đã biết kết quả đến MOB n (max_mob >= n hoặc "
                    "end_state in ('closed','closed_inferred')), loại is_partial_history và never_open. "
                    "primary theo SK_DPD_DEF, no_threshold theo SK_DPD.")}
    for mob in [0] + MOBS:
        key = f"mob{mob}"
        res[key] = {
            "total": fmt_cells(vintage_cells(con, mob, []), [])[0],
            "total_excluding_unknown_application": fmt_cells(
                vintage_cells(con, mob, [], "contract_type <> '(không rõ)'"), [])[0],
            "by_product": fmt_cells(vintage_cells(con, mob, ["contract_type"]), ["contract_type"]),
            "by_channel": fmt_cells(vintage_cells(con, mob, ["channel_type"]), ["channel_type"]),
            "by_product_channel": fmt_cells(vintage_cells(con, mob, ["contract_type", "channel_type"]),
                                            ["contract_type", "channel_type"]),
        }
    # Tỷ số giữa sản phẩm tại MOB 12, tham chiếu vay tiền mặt.
    m12 = {r["contract_type"]: r for r in vintage_cells(con, 12, ["contract_type"])}
    res["mob12_product_ratios_vs_cash"] = {
        p: {"primary": ratio(m12[p]["k"], m12[p]["n"], m12["Cash loans"]["k"], m12["Cash loans"]["n"]),
            "no_threshold": ratio(m12[p]["k_nt"], m12[p]["n"], m12["Cash loans"]["k_nt"], m12["Cash loans"]["n"])}
        for p in ["Consumer loans", "Revolving loans"]
    }
    return res


def channel_comparison(con):
    """So kênh: số thô, SMR (chuẩn hoá gián tiếp theo sản phẩm), cặp kênh trong từng sản phẩm."""
    out = {}
    for mob in MOBS:
        cells = vintage_cells(con, mob, ["contract_type", "channel_type"],
                              "contract_type <> '(không rõ)' and contract_type <> 'Unknown'")
        prod_tot = {}
        for c in cells:
            t = prod_tot.setdefault(c["contract_type"], {"n": 0, "k": 0, "k_nt": 0})
            t["n"] += c["n"]; t["k"] += c["k"]; t["k_nt"] += c["k_nt"]
        channels = sorted({c["channel_type"] for c in cells})
        smr = []
        for ch in channels:
            cc = [c for c in cells if c["channel_type"] == ch]
            item = {"channel_type": ch, "n": int(sum(c["n"] for c in cc))}
            for tag, kk in (("primary", "k"), ("no_threshold", "k_nt")):
                obs = sum(c[kk] for c in cc)
                exp = sum(c["n"] * prod_tot[c["contract_type"]][kk] / prod_tot[c["contract_type"]]["n"] for c in cc)
                ci = byar_ci(obs, exp)
                item[tag] = {"observed": int(obs), "expected": rnd(exp), "smr": rnd(obs / exp) if exp else None,
                             "ci95": ci, "significant": (ci[0] is not None and (ci[0] > 1 or ci[1] < 1)),
                             "crude": prop(obs, item["n"])}
            item["product_mix"] = {c["contract_type"]: rnd(c["n"] / item["n"]) for c in cc}
            smr.append(item)

        # Cặp kênh trong từng sản phẩm (chỉ kênh có nhãn thật, mỗi ô >= MIN_N).
        idx = {(c["contract_type"], c["channel_type"]): c for c in cells}
        real = [ch for ch in channels if ch not in NON_CHANNELS]
        pairs = []
        for a, b in combinations(real, 2):
            per_product = {}
            strata, strata_nt = [], []
            for p in PRODUCTS:
                ca, cb = idx.get((p, a)), idx.get((p, b))
                if not ca or not cb or ca["n"] < MIN_N or cb["n"] < MIN_N:
                    per_product[p] = None
                    continue
                per_product[p] = {"primary": ratio(ca["k"], ca["n"], cb["k"], cb["n"]),
                                  "no_threshold": ratio(ca["k_nt"], ca["n"], cb["k_nt"], cb["n"])}
                strata.append((ca["k"], ca["n"], cb["k"], cb["n"]))
                strata_nt.append((ca["k_nt"], ca["n"], cb["k_nt"], cb["n"]))
            n_ok = sum(v is not None for v in per_product.values())
            if n_ok == 0:
                continue
            pairs.append({"channel_a": a, "channel_b": b, "n_products_comparable": n_ok,
                          "by_product": per_product,
                          "pooled_mh": {"primary": mantel_haenszel_rr(strata),
                                        "no_threshold": mantel_haenszel_rr(strata_nt)}})

        # Cặp định hướng rõ: Stone là tử số, so với từng kênh khác, trong từng sản phẩm và gộp MH.
        key_pairs = []
        for other in ["Country-wide", "Regional / Local", "Credit and cash offices"]:
            per_product, strata, strata_nt = {}, [], []
            for p in PRODUCTS:
                ca, cb = idx.get((p, "Stone")), idx.get((p, other))
                if not ca or not cb:
                    per_product[p] = None
                    continue
                per_product[p] = {"primary": ratio(ca["k"], ca["n"], cb["k"], cb["n"]),
                                  "no_threshold": ratio(ca["k_nt"], ca["n"], cb["k_nt"], cb["n"])}
                if ca["n"] >= MIN_N and cb["n"] >= MIN_N:
                    strata.append((ca["k"], ca["n"], cb["k"], cb["n"]))
                    strata_nt.append((ca["k_nt"], ca["n"], cb["k_nt"], cb["n"]))
            key_pairs.append({"numerator_channel": "Stone", "reference_channel": other, "by_product": per_product,
                              "pooled_mh": {"primary": mantel_haenszel_rr(strata),
                                            "no_threshold": mantel_haenszel_rr(strata_nt)}})

        # Số thô Stone so với Credit and cash offices (cặp đã dùng cho câu "8,1 lần" cũ).
        raw = {r["channel_type"]: r for r in vintage_cells(con, mob, ["channel_type"])}
        crude_pair = None
        if "Stone" in raw and "Credit and cash offices" in raw:
            s, c = raw["Stone"], raw["Credit and cash offices"]
            crude_pair = {"primary": ratio(s["k"], s["n"], c["k"], c["n"]),
                          "no_threshold": ratio(s["k_nt"], s["n"], c["k_nt"], c["n"])}
        out[f"mob{mob}"] = {
            "reference_rates_by_product": {p: {"primary": prop(t["k"], t["n"]), "no_threshold": prop(t["k_nt"], t["n"])}
                                           for p, t in sorted(prod_tot.items())},
            "smr_by_channel": smr,
            "pairs_within_product": pairs,
            "stone_vs_others": key_pairs,
            "pairs_in_all_three_products": [f"{p['channel_a']} / {p['channel_b']}" for p in pairs
                                            if p["n_products_comparable"] == 3],
            "crude_stone_vs_credit_cash_offices": crude_pair,
        }
    out["note"] = ("SMR = số ca quan sát / số ca kỳ vọng nếu kênh có tỷ lệ của từng sản phẩm trên toàn danh "
                   "mục có nhãn. SMR > 1 là kênh xấu hơn mức sản phẩm của nó. Khoảng Byar, không tính bất định "
                   "của tỷ lệ tham chiếu. Cặp kênh: ratio = kênh A / kênh B, chỉ tính khi cả hai ô >= 1.000 hợp đồng.")
    return out


def segment(con):
    """Phân khúc rủi ro cao trong vay tiêu dùng: loại khách × nhóm lãi suất."""
    out = {"definition": ("Trong vay tiêu dùng trả góp (Consumer loans): client_type = 'New' và "
                          "yield_group = 'high'. Chọn vì là hai thuộc tính có sẵn lúc duyệt, đơn giản, "
                          "không dùng điều kiện kênh. Lưu ý: tổ hợp này được nêu từ phân tích cũ theo "
                          "SK_DPD, tức đã nhìn dữ liệu trước; kết quả dưới đây không phải kiểm định "
                          "xác nhận độc lập.")}
    where_cl = "contract_type = 'Consumer loans'"
    for mob in MOBS:
        cells = vintage_cells(con, mob, ["client_type", "yield_group"], where_cl)
        tot_n = sum(c["n"] for c in cells); tot_k = sum(c["k"] for c in cells); tot_knt = sum(c["k_nt"] for c in cells)
        k_combos = len([c for c in cells if c["n"] >= MIN_N])
        z_bonf = NormalDist().inv_cdf(1 - 0.025 / max(k_combos, 1))
        grid = []
        for c in cells:
            rest_n, rest_k, rest_knt = tot_n - c["n"], tot_k - c["k"], tot_knt - c["k_nt"]
            grid.append({"client_type": c["client_type"], "yield_group": c["yield_group"],
                         "share_of_loans": rnd(c["n"] / tot_n), "share_of_cases": rnd(c["k"] / tot_k) if tot_k else None,
                         "primary": prop(c["k"], c["n"]), "no_threshold": prop(c["k_nt"], c["n"]),
                         "ratio_vs_rest": ratio(c["k"], c["n"], rest_k, rest_n),
                         "ratio_vs_rest_no_threshold": ratio(c["k_nt"], c["n"], rest_knt, rest_n)})
        seg = next(g for g in grid if g["client_type"] == "New" and g["yield_group"] == "high")
        # Ratio CI hiệu chỉnh Bonferroni cho số tổ hợp đã xem xét.
        r = seg["ratio_vs_rest"]
        k1, n1 = r["numerator"]["k"], r["numerator"]["n"]
        k0, n0 = r["reference"]["k"], r["reference"]["n"]
        if k1 and k0:
            se = math.sqrt(1 / k1 - 1 / n1 + 1 / k0 - 1 / n0)
            bonf = [rnd(r["ratio"] * math.exp(-z_bonf * se)), rnd(r["ratio"] * math.exp(z_bonf * se))]
        else:
            bonf = [None, None]
        out[f"mob{mob}"] = {
            "consumer_total": prop(tot_k, tot_n),
            "consumer_total_no_threshold": prop(tot_knt, tot_n),
            "n_combinations_considered": len(cells),
            "n_combinations_with_n_ge_1000": k_combos,
            "segment_new_high": seg,
            "segment_ratio_ci95_bonferroni": bonf,
            "grid": grid,
        }
    # KHÁM PHÁ, hậu kiểm (post hoc): chỉ theo nhóm lãi suất, mọi loại khách. Không dùng làm kết luận
    # chính vì được thêm sau khi nhìn bảng grid; ghi lại để người đọc biết đã xem.
    exploratory = {}
    for mob in MOBS:
        yg = vintage_cells(con, mob, ["yield_group"], where_cl)
        tn = sum(c["n"] for c in yg); tk = sum(c["k"] for c in yg); tknt = sum(c["k_nt"] for c in yg)
        exploratory[f"mob{mob}"] = [{"yield_group": c["yield_group"], "share_of_loans": rnd(c["n"] / tn),
                                     "share_of_cases": rnd(c["k"] / tk) if tk else None,
                                     "primary": prop(c["k"], c["n"]),
                                     "ratio_vs_rest": ratio(c["k"], c["n"], tk - c["k"], tn - c["n"]),
                                     "ratio_vs_rest_no_threshold": ratio(c["k_nt"], c["n"], tknt - c["k_nt"], tn - c["n"])}
                                    for c in yg]
    out["exploratory_post_hoc_yield_group_only"] = exploratory

    # Độ ổn định theo kỳ hạn tại MOB 12.
    by_tenor = []
    tenor_rows = rows(con, f"""
        select tenor_group,
               (client_type = 'New' and yield_group = 'high') as is_seg,
               sum(n_loans) as n, sum(n_ever_30_plus) as k, sum(n_ever_30_plus_no_threshold) as k_nt
        from mart.vintage where mob = 12 and {where_cl}
        group by 1, 2 order by 1, 2
    """)
    for tg in sorted({r["tenor_group"] for r in tenor_rows}):
        s = next((r for r in tenor_rows if r["tenor_group"] == tg and r["is_seg"]), None)
        o = next((r for r in tenor_rows if r["tenor_group"] == tg and not r["is_seg"]), None)
        if not s or not o:
            continue
        by_tenor.append({"tenor_group": tg, "segment": prop(s["k"], s["n"]), "rest": prop(o["k"], o["n"]),
                         "ratio": ratio(s["k"], s["n"], o["k"], o["n"]),
                         "ratio_no_threshold": ratio(s["k_nt"], s["n"], o["k_nt"], o["n"])})
    out["mob12_by_tenor"] = by_tenor

    # Đối chiếu với nhóm cũ: Stone hoặc Country-wide × New × high (trong vay tiêu dùng).
    old = rows(con, f"""
        select (channel_type in ('Stone', 'Country-wide') and client_type = 'New' and yield_group = 'high') as is_old,
               sum(n_loans) as n, sum(n_ever_30_plus) as k, sum(n_ever_30_plus_no_threshold) as k_nt
        from mart.vintage where mob = 12 and {where_cl} group by 1 order by 1
    """)
    s = next(r for r in old if r["is_old"]); o = next(r for r in old if not r["is_old"])
    tot_k = s["k"] + o["k"]; tot_knt = s["k_nt"] + o["k_nt"]; tot_n = s["n"] + o["n"]
    out["old_segment_stone_countrywide_new_high_mob12"] = {
        "share_of_loans": rnd(s["n"] / tot_n), "share_of_cases": rnd(s["k"] / tot_k),
        "share_of_cases_no_threshold": rnd(s["k_nt"] / tot_knt),
        "segment": prop(s["k"], s["n"]), "rest": prop(o["k"], o["n"]),
        "ratio": ratio(s["k"], s["n"], o["k"], o["n"]),
        "ratio_no_threshold": ratio(s["k_nt"], s["n"], o["k_nt"], o["n"]),
    }
    # Trong phân khúc New × high: điều kiện kênh có thêm thông tin không?
    ch = rows(con, f"""
        select (channel_type in ('Stone', 'Country-wide')) as is_sc,
               sum(n_loans) as n, sum(n_ever_30_plus) as k, sum(n_ever_30_plus_no_threshold) as k_nt
        from mart.vintage where mob = 12 and {where_cl} and client_type = 'New' and yield_group = 'high'
        group by 1 order by 1
    """)
    s = next((r for r in ch if r["is_sc"]), None); o = next((r for r in ch if not r["is_sc"]), None)
    out["mob12_within_new_high_channel_condition"] = {
        "stone_or_countrywide": prop(s["k"], s["n"]) if s else None,
        "other_channels": prop(o["k"], o["n"]) if o else None,
        "share_of_segment_loans_in_stone_or_countrywide": rnd(s["n"] / (s["n"] + o["n"])) if s and o else None,
        "ratio": ratio(s["k"], s["n"], o["k"], o["n"]) if s and o else None,
    }
    return out


def roll_cure(con):
    out = {"note": ("Lượt hợp đồng-tháng đang mở tại tháng t (t <= -2) theo bucket, trạng thái tháng t+1. "
                    "cure = về B0; roll_forward = sang bucket kế tiếp (B4 thì là ở lại B4). "
                    "enough_n: mẫu số >= 1.000 lượt.")}
    for tag, table in (("primary", "mart.roll_rate"), ("no_threshold", "mart.roll_rate_no_threshold")):
        res = {}
        for scope, where in (("all", "true"), ("pos_cash", "source = 'pos_cash'"), ("credit_card", "source = 'credit_card'")):
            cells = rows(con, f"""
                select from_state, from_order, to_state, sum(n_loans) as n
                from {table} where {where} group by 1, 2, 3 order by 2, 3
            """)
            states = []
            for fs, fo in sorted({(c["from_state"], c["from_order"]) for c in cells}, key=lambda x: x[1]):
                row = {c["to_state"]: int(c["n"]) for c in cells if c["from_state"] == fs}
                n_from = sum(row.values())
                nxt = {0: "B1 1-30", 1: "B2 31-60", 2: "B3 61-90", 3: "B4 90+", 4: "B4 90+"}[fo]
                states.append({"from_state": fs, "n_from": n_from, "to_counts": dict(sorted(row.items())),
                               "cure_to_b0": prop(row.get("B0 Current", 0), n_from),
                               "roll_forward": prop(row.get(nxt, 0), n_from),
                               "to_closed": prop(row.get("Closed", 0), n_from),
                               "to_missing": prop(row.get("Missing", 0), n_from),
                               "enough_n": n_from >= MIN_N})
            res[scope] = states
        out[tag] = res
    return out


def approval(con):
    cells = rows(con, """
        select contract_type, channel_type,
               sum(n_applications) as n_app, sum(n_decided) as n_dec, sum(n_offered) as n_off,
               sum(n_approved) as n_appr, sum(n_unused_offer) as n_unused, sum(n_refused) as n_ref
        from mart.funnel_by_channel group by 1, 2 order by 1, 2
    """)
    prod = {}
    for c in cells:
        t = prod.setdefault(c["contract_type"], {"n_dec": 0, "n_off": 0, "n_appr": 0, "n_unused": 0})
        for k in t:
            t[k] += c[k]
    within = [{"contract_type": c["contract_type"], "channel_type": c["channel_type"],
               "approval_rate": prop(c["n_off"], c["n_dec"]),
               "n_applications": int(c["n_app"])} for c in cells]
    channels = sorted({c["channel_type"] for c in cells})
    std = []
    for ch in channels:
        cc = [c for c in cells if c["channel_type"] == ch and c["contract_type"] in prod]
        obs = sum(c["n_off"] for c in cc)
        exp = sum(c["n_dec"] * prod[c["contract_type"]]["n_off"] / prod[c["contract_type"]]["n_dec"]
                  for c in cc if prod[c["contract_type"]]["n_dec"])
        n_dec = sum(c["n_dec"] for c in cc)
        std.append({"channel_type": ch, "crude": prop(obs, n_dec), "observed": int(obs), "expected": rnd(exp),
                    "standardized_ratio": rnd(obs / exp) if exp else None,
                    "expected_rate_given_product_mix": rnd(exp / n_dec) if n_dec else None})
    take_up = [{"channel_type": c["channel_type"], "take_up_rate": prop(c["n_appr"], c["n_off"])}
               for c in cells if c["contract_type"] == "Consumer loans"]
    return {
        "note": ("approval_rate = (Approved + Unused offer) / (Approved + Unused offer + Refused), hồ sơ đã lọc trùng. "
                 "standardized_ratio = số được duyệt / số kỳ vọng nếu kênh có tỷ lệ duyệt của từng sản phẩm "
                 "(chuẩn hoá gián tiếp, mô tả, không có khoảng tin cậy vì mẫu số rất lớn). "
                 "Take-up chỉ báo cho vay tiêu dùng vì Unused offer gần như chỉ có ở sản phẩm này."),
        "by_product": {p: {"approval_rate": prop(t["n_off"], t["n_dec"]), "n_unused_offer": int(t["n_unused"]),
                           "take_up_rate": prop(t["n_appr"], t["n_off"])} for p, t in sorted(prod.items())},
        "within_product": within,
        "channel_standardized": std,
        "take_up_consumer_by_channel": take_up,
    }


def fpd(con):
    tot = one(con, """
        select sum(n_loans) as n, sum(n_fpd30) as k, sum(n_fpd30_late_rule) as k_late,
               sum(n_approved_not_activated) as n_not_act,
               sum(n_approved_scheduled_no_installment) as n_sched_no_inst
        from mart.fpd_by_segment
    """)
    by_product = rows(con, """
        select contract_type, sum(n_loans) as n, sum(n_fpd30) as k, sum(n_fpd30_late_rule) as k_late,
               sum(n_approved_not_activated) as n_not_act
        from mart.fpd_by_segment group by 1 order by 1
    """)
    by_pc = rows(con, """
        select contract_type, channel_type, sum(n_loans) as n, sum(n_fpd30) as k, sum(n_fpd30_late_rule) as k_late
        from mart.fpd_by_segment group by 1, 2 having sum(n_loans) > 0 order by 1, 2
    """)
    return {
        "note": ("FPD30 theo kỳ 1 của lịch trả gốc (version nhỏ nhất khác 0). amount_rule: trả chưa đủ 95% số "
                 "tiền trong 30 ngày sau hạn. late_rule: có lần trả kỳ 1 trễ quá 30 ngày. Hồ sơ duyệt không có "
                 "lịch trả (không kích hoạt) không thuộc mẫu số."),
        "total": {"amount_rule": prop(tot["k"], tot["n"]), "late_rule": prop(tot["k_late"], tot["n"]),
                  "n_approved_not_activated": int(tot["n_not_act"]),
                  "n_approved_scheduled_no_installment": int(tot["n_sched_no_inst"])},
        "by_product": [{"contract_type": r["contract_type"], "amount_rule": prop(r["k"], r["n"]),
                        "late_rule": prop(r["k_late"], r["n"]), "n_approved_not_activated": int(r["n_not_act"])}
                       for r in by_product],
        "by_product_channel": [{"contract_type": r["contract_type"], "channel_type": r["channel_type"],
                                "amount_rule": prop(r["k"], r["n"]), "late_rule": prop(r["k_late"], r["n"])}
                               for r in by_pc],
    }


EARLY_SQL = """
with firsts as (
    select sk_id_prev,
           min(mob) filter (where dpd > 0)   as first_1_plus,
           min(mob) filter (where dpd > 30)  as first_30_plus
    from core.fct_loan_month group by sk_id_prev
),
loans as (
    select d.sk_id_prev, d.max_mob, d.end_state,
           case when d.has_application then coalesce(d.contract_type, 'Unknown') else '(không rõ)' end as contract_type,
           d.has_application and d.contract_type = 'Consumer loans' and d.client_type = 'New'
               and d.yield_group = 'high' as is_seg,
           f.first_1_plus, f.first_30_plus
    from core.dim_loan d left join firsts f using (sk_id_prev)
    where d.end_state <> 'never_open' and not d.is_partial_history
)
select g.mob, l.contract_type, l.is_seg,
       count(*) as n,
       count(*) filter (where l.first_1_plus <= g.mob)  as k_1_plus,
       count(*) filter (where l.first_30_plus <= g.mob) as k_30_plus
from loans l join (select unnest([3, 6, 12]) as mob) g
  on l.max_mob >= g.mob or l.end_state in ('closed', 'closed_inferred')
group by 1, 2, 3 order by 1, 2, 3
"""


def sample_size(con, seg_out, roll_out):
    cells = rows(con, EARLY_SQL)

    def agg(mob, pred):
        cc = [c for c in cells if c["mob"] == mob and pred(c)]
        return sum(c["n"] for c in cc), sum(c["k_1_plus"] for c in cc), sum(c["k_30_plus"] for c in cc)

    seg_size = one(con, """
        select sum(n_loans) as n from mart.vintage
        where mob = 0 and contract_type = 'Consumer loans' and client_type = 'New' and yield_group = 'high'
    """)["n"]
    consumer_size = one(con, "select sum(n_loans) as n from mart.vintage where mob = 0 and contract_type = 'Consumer loans'")["n"]
    candidates = []
    for pop_name, pred, size in (("segment_consumer_new_high", lambda c: c["is_seg"], seg_size),
                                 ("consumer_loans_all", lambda c: c["contract_type"] == "Consumer loans", consumer_size)):
        for mob in (3, 6, 12):
            n, k1, k30 = agg(mob, pred)
            for metric, k in (("ever_30_plus", k30), ("ever_1_plus", k1)):
                p = prop(k, n)
                need = n_per_arm(p["rate"], -0.20)
                candidates.append({"population": pop_name, "metric": f"{metric}@MOB{mob}", "baseline": p,
                                   "n_per_arm_rel_minus_20pct": need,
                                   "total_both_arms": 2 * need if need else None,
                                   "population_size_in_data_mob0": int(size),
                                   "multiple_of_population_size": rnd(2 * need / size) if need else None})
    # Chỉ tiêu sớm có liên quan tới chỉ tiêu đích không: trong vay tiêu dùng đã biết kết quả đến MOB 12,
    # so ever 30+@MOB12 giữa nhóm từng 1+ đến MOB 6 và nhóm chưa từng.
    v = rows(con, """
        with firsts as (
            select sk_id_prev, min(mob) filter (where dpd > 0) as f1, min(mob) filter (where dpd > 30) as f30
            from core.fct_loan_month group by sk_id_prev
        )
        select coalesce(f.f1 <= 6, false) as early_1_plus_by_mob6,
               count(*) as n, count(*) filter (where f.f30 <= 12) as k
        from core.dim_loan d left join firsts f using (sk_id_prev)
        where d.end_state <> 'never_open' and not d.is_partial_history
          and d.has_application and d.contract_type = 'Consumer loans'
          and (d.max_mob >= 12 or d.end_state in ('closed', 'closed_inferred'))
        group by 1 order by 1
    """)
    e1 = next(r for r in v if r["early_1_plus_by_mob6"]); e0 = next(r for r in v if not r["early_1_plus_by_mob6"])
    early_validation = {
        "population": "Consumer loans, đã biết kết quả đến MOB 12",
        "ever_30_plus_mob12_if_ever_1_plus_by_mob6": prop(e1["k"], e1["n"]),
        "ever_30_plus_mob12_if_not": prop(e0["k"], e0["n"]),
        "ratio": ratio(e1["k"], e1["n"], e0["k"], e0["n"]),
        "share_of_mob12_cases_preceded_by_1_plus_by_mob6": rnd(e1["k"] / (e1["k"] + e0["k"])) if (e1["k"] + e0["k"]) else None,
    }

    # Thử nghiệm nhắc nợ sớm ở B1: phát hiện cure rate tăng tương đối 20%.
    b1 = next(s for s in roll_out["primary"]["all"] if s["from_state"] == "B1 1-30")
    cure = b1["cure_to_b0"]
    roll = b1["roll_forward"]
    collections = {
        "b1_cure_rate_baseline": cure,
        "n_per_arm_cure_rel_plus_20pct": n_per_arm(cure["rate"], 0.20),
        "b1_roll_to_b2_baseline": roll,
        "n_per_arm_roll_rel_minus_20pct": n_per_arm(roll["rate"], -0.20),
        "b1_transitions_in_data": b1["n_from"],
    }
    return {"note": ("Hai tỷ lệ độc lập, hai phía, alpha 0,05, power 0,8, chia 1:1, phát hiện thay đổi tương đối "
                     "20%. population_size_in_data_mob0 là số hợp đồng của nhóm trong toàn bộ dữ liệu (không có "
                     "chiều thời gian lịch nên không quy ra được số tháng tuyển mẫu). ever_1_plus theo SK_DPD_DEF > 0."),
            "approval_experiment": candidates, "collections_experiment": collections,
            "early_indicator_validation": early_validation}


UNKNOWN_SQL = """
with firsts as (
    select sk_id_prev, min(mob) filter (where is_30_plus) as m30,
           min(mob) filter (where is_30_plus_no_threshold) as m30_nt
    from core.fct_loan_month group by sk_id_prev
),
l as (
    select d.sk_id_prev, d.max_mob, d.end_state,
           case when d.has_application then coalesce(d.contract_type, 'Unknown') else '(không rõ)' end as contract_type,
           coalesce(d.installments_remaining_at_last, -1) = 0 as rem0,
           f.m30, f.m30_nt
    from core.dim_loan d left join firsts f using (sk_id_prev)
    where d.end_state <> 'never_open' and not d.is_partial_history
)
select r.rule, g.mob, l.contract_type,
       count(*) as n, count(*) filter (where l.m30 <= g.mob) as k, count(*) filter (where l.m30_nt <= g.mob) as k_nt
from l
cross join (select unnest([6, 12, 24]) as mob) g
cross join (select unnest(['main', 'legacy', 'legacy_plus_rem0']) as rule) r
where l.max_mob >= g.mob
   or l.end_state = 'closed'
   or (r.rule = 'main' and l.end_state = 'closed_inferred')
   or (r.rule = 'legacy_plus_rem0' and l.end_state in ('closed_inferred', 'unknown') and l.rem0)
group by 1, 2, 3 order by 1, 2, 3
"""


def unknown_sensitivity(con):
    prof = rows(con, """
        select case when d.end_state in ('closed_inferred', 'unknown') and d.last_observed_month >= -4 then 'stop_-2_to_-4'
                    when d.end_state in ('closed_inferred', 'unknown') then 'stop_-17_or_earlier' end as stop_group,
               d.source, d.end_state, count(*) as n,
               count(*) filter (where d.installments_remaining_at_last = 0) as n_rem0,
               median(d.installments_remaining_at_last) as median_rem
        from core.dim_loan d where d.end_state in ('closed_inferred', 'unknown')
        group by 1, 2, 3 order by 1, 2, 3
    """)
    gap = one(con, """
        select count(*) filter (where last_observed_month between -16 and -5) as n_stop_between_5_16
        from core.dim_loan where end_state in ('closed_inferred', 'unknown')
    """)
    cells = rows(con, UNKNOWN_SQL)
    res = {}
    for rule in ("main", "legacy", "legacy_plus_rem0"):
        r = {}
        for mob in MOBS:
            cc = [c for c in cells if c["rule"] == rule and c["mob"] == mob]
            r[f"mob{mob}"] = {
                "total": {"primary": prop(sum(c["k"] for c in cc), sum(c["n"] for c in cc)),
                          "no_threshold": prop(sum(c["k_nt"] for c in cc), sum(c["n"] for c in cc))},
                "by_product": {c["contract_type"]: {"primary": prop(c["k"], c["n"]), "no_threshold": prop(c["k_nt"], c["n"])}
                               for c in cc},
            }
        res[rule] = r
    return {"note": ("main: 'closed_inferred' (hồ sơ có DAYS_TERMINATION) coi như đã đóng, đang dùng trong mart. "
                     "legacy: quy tắc trước 2026-10-04 (chỉ 'closed' theo Completed). legacy_plus_rem0: quy tắc cũ "
                     "cộng thêm mọi hợp đồng dừng sớm còn 0 kỳ coi như đã đóng."),
            "profile": [{**p, "median_rem": rnd(p["median_rem"])} for p in prof],
            "n_stop_between_minus5_and_minus16": int(gap["n_stop_between_5_16"]),
            "vintage_by_rule": res}


# ---------------------------------------------------------------------------
# Đợt mở hợp đồng (origination cohort): biến gây nhiễu thứ hai, thêm sau lần soát thứ hai
# ---------------------------------------------------------------------------

# Mỗi cách cắt nhận first_open_month (tháng tương đối của MOB 0) và trả (khóa sắp xếp, nhãn, tháng cuối).
def _cut12(m):
    s = -96 + 12 * ((m + 96) // 12)
    return s, f"{s} đến {s + 11}", s + 11


def _cut24(m):
    s = -96 + 24 * ((m + 96) // 24)
    return s, f"{s} đến {s + 23}", s + 23


def _cut3(m):
    if m <= -60:
        return -96, "-60 trở về trước", -60
    if m <= -36:
        return -59, "-59 đến -36", -36
    return -35, "-35 trở về sau", -1


COHORT_CUTS = {"cut12": _cut12, "cut3": _cut3, "cut24": _cut24}
COHORT_CUT_NOTE = {
    "cut12": ("Chính: mỗi 12 tháng của first_open_month (một năm tương đối), căn từ tháng -96 nên đợt cuối kết "
              "thúc đúng tháng -1. Đủ mịn để thấy xu hướng, đủ dày để hầu hết ô sản phẩm × đợt có trên 1.000 "
              "hợp đồng. Đây là cột origination_cohort của mart.vintage."),
    "cut3": ("Độ nhạy 1: 3 nhóm do người soát độc lập tự đặt (-60 trở về trước, -59 đến -36, -35 trở về sau). "
             "Mốc đặt sau khi nhìn dữ liệu."),
    "cut24": "Độ nhạy 2: mỗi 24 tháng, căn từ tháng -96 (4 đợt).",
}

COHORT_SQL = """
with firsts as (
    select sk_id_prev,
           min(mob) filter (where is_30_plus)                as m30,
           min(mob) filter (where is_30_plus_no_threshold)   as m30_nt,
           min(mob) filter (where (source = 'credit_card' and is_30_plus)
                               or (source = 'pos_cash' and is_30_plus_no_threshold and installments_remaining > 0))
                                                             as m30_due,
           min(mob) filter (where is_30_plus_no_threshold
                               and (source = 'credit_card' or installments_remaining > 0))
                                                             as m30_due_card_raw,
           min(mob) filter (where dpd > 0)                   as m1
    from core.fct_loan_month group by sk_id_prev
),
loans as (
    select d.sk_id_prev, d.first_open_month, d.max_mob, d.end_state,
           case when d.has_application then coalesce(d.contract_type, 'Unknown') else '(không rõ)' end as contract_type,
           case
               when not d.has_application then '(không rõ)'
               when d.channel_type is null then 'Unknown'
               when d.channel_type in ('Car dealer', 'Channel of corporate sales') then 'Khác'
               else d.channel_type
           end as channel_type,
           f.m30, f.m30_nt, f.m30_due, f.m30_due_card_raw, f.m1
    from core.dim_loan d left join firsts f using (sk_id_prev)
    where d.end_state <> 'never_open' and not d.is_partial_history
)
select g.mob, l.contract_type, l.channel_type, l.first_open_month,
       count(*) as n,
       count(*) filter (where l.max_mob >= g.mob)            as n_full,
       count(*) filter (where l.m30 <= g.mob)                as k,
       count(*) filter (where l.m30_nt <= g.mob)             as k_nt,
       count(*) filter (where l.m30_due <= g.mob)            as k_due,
       count(*) filter (where l.m30_due_card_raw <= g.mob)   as k_due_card_raw,
       count(*) filter (where l.m1 <= g.mob)                 as k1
from loans l join (select unnest([6, 12, 24]) as mob) g
  on l.max_mob >= g.mob or l.end_state in ('closed', 'closed_inferred')
group by 1, 2, 3, 4 order by 1, 2, 3, 4
"""

KFIELDS = ("n", "n_full", "k", "k_nt", "k_due", "k_due_card_raw", "k1")


def _labeled(c):
    return c["contract_type"] not in (UNKNOWN, "Unknown")


def _agg(cells, keyfn):
    out = {}
    for c in cells:
        t = out.setdefault(keyfn(c), {f_: 0 for f_ in KFIELDS})
        for f_ in KFIELDS:
            t[f_] += c[f_]
    return out


def _smr(cells, stratum, kk):
    """SMR theo kênh, chuẩn hoá gián tiếp theo tầng stratum(c), kèm O và E tách theo sản phẩm."""
    ref = _agg(cells, stratum)
    out = []
    for ch in sorted({c["channel_type"] for c in cells}):
        cc = [c for c in cells if c["channel_type"] == ch]
        obs = sum(c[kk] for c in cc)
        exp = 0.0
        by_p = {}
        for c in cc:
            r = ref[stratum(c)]
            e = c["n"] * r[kk] / r["n"] if r["n"] else 0.0
            exp += e
            bp = by_p.setdefault(c["contract_type"], {"n": 0, "observed": 0, "expected": 0.0})
            bp["n"] += c["n"]
            bp["observed"] += c[kk]
            bp["expected"] += e
        ci = byar_ci(obs, exp)
        out.append({"channel_type": ch, "n": int(sum(c["n"] for c in cc)), "observed": int(obs),
                    "expected": rnd(exp), "smr": rnd(obs / exp) if exp else None, "ci95": ci,
                    "significant": (ci[0] is not None and (ci[0] > 1 or ci[1] < 1)),
                    "by_product": [{"contract_type": p, "n": int(v["n"]), "observed": int(v["observed"]),
                                    "expected": rnd(v["expected"]), "excess": rnd(v["observed"] - v["expected"])}
                                   for p, v in sorted(by_p.items())]})
    return out


def _mh_pair(cells, sel1, sel0, stratum, kk):
    """Tỷ số gộp Mantel-Haenszel (nhóm 1 / nhóm 0) qua các tầng stratum(c)."""
    a1 = _agg([c for c in cells if sel1(c)], stratum)
    a0 = _agg([c for c in cells if sel0(c)], stratum)
    strata, by = [], []
    for s in sorted(set(a1) & set(a0), key=str):
        t1, t0 = a1[s], a0[s]
        strata.append((t1[kk], t1["n"], t0[kk], t0["n"]))
        by.append({"stratum": " | ".join(str(x) for x in s) if isinstance(s, tuple) else str(s),
                   "group1": prop(t1[kk], t1["n"]), "group0": prop(t0[kk], t0["n"])})
    res = mantel_haenszel_rr(strata)
    res["by_stratum"] = by
    return res


def origination_cohort(con):
    raw = rows(con, COHORT_SQL)
    for c in raw:
        for f_ in KFIELDS:
            c[f_] = int(c[f_])
        for name, fn in COHORT_CUTS.items():
            c[name] = fn(c["first_open_month"])

    # Đối chiếu: cách cắt chính phải khớp mart.vintage (cùng định nghĩa, đường đếm độc lập).
    mart = rows(con, """
        select mob, contract_type, channel_type, origination_cohort_start as s,
               sum(n_loans) as n, sum(n_ever_30_plus) as k, sum(n_ever_30_plus_due_only) as k_due,
               sum(n_ever_30_plus_no_threshold) as k_nt
        from mart.vintage where mob in (6, 12, 24) group by 1, 2, 3, 4 order by 1, 2, 3, 4
    """)
    mine = _agg(raw, lambda c: (c["mob"], c["contract_type"], c["channel_type"], c["cut12"][0]))
    for m in mart:
        t = mine.get((m["mob"], m["contract_type"], m["channel_type"], m["s"]))
        if not t or (t["n"], t["k"], t["k_due"], t["k_nt"]) != (m["n"], m["k"], m["k_due"], m["k_nt"]):
            raise SystemExit(f"COHORT_SQL lệch mart.vintage tại {m}: {t}")
    if len(mart) != len(mine):
        raise SystemExit("COHORT_SQL và mart.vintage khác số ô")

    out = {"note": ("Đợt mở hợp đồng = nhóm của core.dim_loan.first_open_month (tháng tương đối của MOB 0 so với "
                    "ngày nộp hồ sơ hiện tại của từng khách; không phải tháng lịch). Hai cách dùng: (1) vintage theo "
                    "đợt (cohort_vintage): chỉ giữ hợp đồng mở đủ sớm để có thể quan sát tới MOB n "
                    "(first_open_month <= -1 - n), vì đợt chưa đủ tuổi chỉ có hợp đồng đã đóng sớm trong mẫu số; "
                    "(2) phân tầng (smr_by_channel, product_ratio_vs_cash, stone_vs_country_wide): giữ nguyên mẫu "
                    "số của vintage chính, đợt chỉ là tầng. due_only: định nghĩa giữa (trả góp: SK_DPD > 30 ở "
                    "tháng còn kỳ phải trả; thẻ: SK_DPD_DEF). due_only_card_raw: như due_only nhưng thẻ theo SK_DPD."),
           "cuts": COHORT_CUT_NOTE,
           "reconciles_with_mart_vintage": True}

    m0 = rows(con, """
        select origination_cohort, origination_cohort_start, sum(n_loans) as n
        from mart.vintage where mob = 0 group by 1, 2 order by 2
    """)
    out["mob0_size_by_cohort"] = [{"origination_cohort": r["origination_cohort"],
                                   "origination_cohort_start": r["origination_cohort_start"], "n": int(r["n"])}
                                  for r in m0]

    for mob in MOBS:
        cm = [c for c in raw if c["mob"] == mob]
        lab = [c for c in cm if _labeled(c)]
        res = {}

        # (a) Vintage theo đợt: chỉ hợp đồng đủ tuổi tới MOB n.
        aged = [c for c in lab if c["first_open_month"] <= -1 - mob]
        cv = {}
        for name in COHORT_CUTS:
            by_pc = _agg(aged, lambda c, nm=name: (c["contract_type"], c[nm][0], c[nm][1]))
            by_c = _agg(aged, lambda c, nm=name: (c[nm][0], c[nm][1]))
            items = [{"contract_type": p, "origination_cohort": lbl, "origination_cohort_start": s,
                      "primary": prop(t["k"], t["n"]), "due_only": prop(t["k_due"], t["n"]),
                      "n_observed_full": t["n_full"]}
                     for (p, s, lbl), t in sorted(by_pc.items(), key=lambda x: (x[0][0], x[0][1]))]
            tot = [{"origination_cohort": lbl, "origination_cohort_start": s, "primary": prop(t["k"], t["n"]),
                    "due_only": prop(t["k_due"], t["n"]), "n_observed_full": t["n_full"]}
                   for (s, lbl), t in sorted(by_c.items())]
            old_vs_new = []
            for p in PRODUCTS:
                its = [i for i in items if i["contract_type"] == p]
                if len(its) >= 2:
                    o, nw = its[0], its[-1]
                    old_vs_new.append({"contract_type": p, "oldest": o["origination_cohort"],
                                       "newest_aged": nw["origination_cohort"],
                                       "primary": ratio(o["primary"]["k"], o["primary"]["n"],
                                                        nw["primary"]["k"], nw["primary"]["n"])})
            cv[name] = {"by_product": items, "total_labeled_products": tot, "oldest_vs_newest_aged": old_vs_new}
        res["cohort_vintage"] = cv

        # Cơ cấu đợt theo kênh × sản phẩm (mẫu số đầy đủ của MOB n).
        mix = {}
        for name in ("cut12", "cut3"):
            a = _agg(lab, lambda c, nm=name: (c["channel_type"], c["contract_type"], c[nm][0], c[nm][1]))
            tot = _agg(lab, lambda c: (c["channel_type"], c["contract_type"]))
            mix[name] = [{"channel_type": ch, "contract_type": p, "origination_cohort": lbl,
                          "origination_cohort_start": s, "n": t["n"],
                          "share_of_channel_product": rnd(t["n"] / tot[(ch, p)]["n"]),
                          "primary": prop(t["k"], t["n"])}
                         for (ch, p, s, lbl), t in sorted(a.items())]
        res["mix_channel_product_cohort"] = mix

        # (b) SMR theo kênh: chỉ sản phẩm (đối chiếu) và sản phẩm × đợt, ba cách cắt, hai định nghĩa.
        smr = {"product_only": {}}
        for tag, kk in (("primary", "k"), ("due_only", "k_due")):
            smr["product_only"][tag] = _smr(lab, lambda c: c["contract_type"], kk)
            for name in COHORT_CUTS:
                smr.setdefault(f"product_x_{name}", {})[tag] = _smr(
                    lab, lambda c, nm=name: (c["contract_type"], c[nm][0]), kk)
        res["smr_by_channel"] = smr

        # (c) Tỷ số sản phẩm (tham chiếu vay tiền mặt): số thô và gộp MH qua đợt.
        a = _agg(lab, lambda c: c["contract_type"])
        pr = {}
        for p in ("Revolving loans", "Consumer loans"):
            item = {}
            for tag, kk in (("primary", "k"), ("due_only", "k_due"), ("due_only_card_raw", "k_due_card_raw"),
                            ("no_threshold", "k_nt")):
                d = {"crude": ratio(a[p][kk], a[p]["n"], a["Cash loans"][kk], a["Cash loans"]["n"])}
                for name in COHORT_CUTS:
                    d[f"mh_{name}"] = _mh_pair(lab, lambda c, pp=p: c["contract_type"] == pp,
                                               lambda c: c["contract_type"] == "Cash loans",
                                               lambda c, nm=name: c[nm][0], kk)
                item[tag] = d
            pr[p] = item
        res["product_ratio_vs_cash"] = pr

        # Stone so với Country-wide: MH qua 3 sản phẩm (như cũ), qua 2 sản phẩm, qua sản phẩm × đợt.
        st = lambda c: c["channel_type"] == "Stone"
        cw = lambda c: c["channel_type"] == "Country-wide"
        two = [c for c in lab if c["contract_type"] in ("Consumer loans", "Revolving loans")]
        sc = {}
        for tag, kk in (("primary", "k"), ("due_only", "k_due")):
            sc[tag] = {
                "mh_product_3_strata": _mh_pair(lab, st, cw, lambda c: c["contract_type"], kk),
                "mh_product_2_strata_consumer_card": _mh_pair(two, st, cw, lambda c: c["contract_type"], kk),
                "mh_product_x_cut12": _mh_pair(lab, st, cw, lambda c: (c["contract_type"], c["cut12"][0]), kk),
                "mh_product_x_cut3": _mh_pair(lab, st, cw, lambda c: (c["contract_type"], c["cut3"][0]), kk),
                "mh_product_x_cut24": _mh_pair(lab, st, cw, lambda c: (c["contract_type"], c["cut24"][0]), kk),
            }
        res["stone_vs_country_wide"] = sc

        # Thẻ của từng kênh theo đợt: ca thẻ tập trung ở đợt nào.
        cards = [c for c in cm if c["contract_type"] == "Revolving loans"]
        cbc = []
        for ch in ("Contact center", "Stone", "Credit and cash offices", "Country-wide"):
            sub = [c for c in cards if c["channel_type"] == ch]
            tot_k = sum(c["k"] for c in sub)
            item = {"channel_type": ch, "total": prop(tot_k, sum(c["n"] for c in sub))}
            for name in ("cut12", "cut3"):
                ag = _agg(sub, lambda c, nm=name: (c[nm][0], c[nm][1]))
                item[name] = [{"origination_cohort": lbl, "origination_cohort_start": s,
                               "primary": prop(t["k"], t["n"]),
                               "share_of_cases": rnd(t["k"] / tot_k) if tot_k else None}
                              for (s, lbl), t in sorted(ag.items())]
            cbc.append(item)
        res["cards_by_channel_cohort"] = cbc
        out[f"mob{mob}"] = res

    # Đường cong theo đợt cho visual trang 3.
    curve = rows(con, """
        select origination_cohort, origination_cohort_start, mob,
               sum(n_loans) as n, sum(n_ever_30_plus) as k
        from mart.vintage
        where contract_type not in ('(không rõ)', 'Unknown')
          and origination_cohort_start + 11 <= -1 - mob
        group by 1, 2, 3 order by 2, 3
    """)
    curves = {}
    for r in curve:
        cur = curves.setdefault(r["origination_cohort"], {"origination_cohort": r["origination_cohort"],
                                                          "origination_cohort_start": r["origination_cohort_start"],
                                                          "points": []})
        cur["points"].append({"mob": int(r["mob"]), "n": int(r["n"]), "k": int(r["k"]),
                              "rate": rnd(r["k"] / r["n"]) if r["n"] else None})
    # Cure B1 so với B2 trong từng đợt mở (lượt hợp đồng-tháng, cùng quy tắc với mart.roll_rate).
    cure = rows(con, """
        with m as (
            select f.sk_id_prev, f.months_balance, f.is_open, f.dpd_bucket_order,
                   lead(f.months_balance) over w as nm, lead(f.is_open) over w as nopen,
                   lead(f.dpd_bucket_order) over w as nb
            from core.fct_loan_month f
            window w as (partition by sk_id_prev order by months_balance)
        )
        select -96 + 12 * ((d.first_open_month + 96) // 12) as s, m.dpd_bucket_order as b, count(*) as n,
               count(*) filter (where m.nm = m.months_balance + 1 and m.nopen and m.nb = 0) as k
        from m join core.dim_loan d using (sk_id_prev)
        where m.is_open and m.months_balance < -1 and m.dpd_bucket_order in (1, 2)
        group by 1, 2 order by 1, 2
    """)
    strata, by = [], []
    for s_ in sorted({r["s"] for r in cure}):
        r1 = next(r for r in cure if r["s"] == s_ and r["b"] == 1)
        r2 = next((r for r in cure if r["s"] == s_ and r["b"] == 2), None)
        by.append({"origination_cohort": f"{s_} đến {s_ + 11}", "origination_cohort_start": s_,
                   "cure_b1": prop(r1["k"], r1["n"]), "cure_b2": prop(r2["k"], r2["n"]) if r2 else None})
        if r2:
            strata.append((int(r1["k"]), int(r1["n"]), int(r2["k"]), int(r2["n"])))
    out["cure_b1_vs_b2_by_cohort"] = {
        "note": ("Lượt hợp đồng-tháng (không độc lập), toàn bộ hợp đồng kể cả is_partial_history, đợt theo "
                 "first_open_month. mh_b1_over_b2: tỷ số cure B1 / cure B2 gộp Mantel-Haenszel qua đợt."),
        "by_cohort": by, "mh_b1_over_b2": mantel_haenszel_rr(strata)}

    out["curve_by_cohort_labeled_products"] = {
        "note": ("Nguồn: mart.vintage, sản phẩm có nhãn, cách cắt 12 tháng. Mỗi đợt chỉ có điểm tại MOB mà mọi hợp "
                 "đồng của đợt đã có thể quan sát tới (tháng cuối của đợt <= -1 - MOB). Cơ cấu sản phẩm đổi theo "
                 "đợt, nên đọc kèm cohort_vintage.cut12.by_product."),
        "cohorts": sorted(curves.values(), key=lambda x: x["origination_cohort_start"])}
    return out


def review_checks(con, vintage_out, channel_out, roll_out, seg_out):
    """Các con số trả lời lần soát thứ hai (Y3 đến Y9, M1, các mục nhỏ)."""
    out = {}

    # Y4: cỡ mẫu cho thẻ Contact center.
    cc = rows(con, """
        with firsts as (
            select sk_id_prev, min(mob) filter (where dpd > 0) as f1, min(mob) filter (where dpd > 30) as f30
            from core.fct_loan_month group by sk_id_prev
        )
        select g.mob, count(*) as n, count(*) filter (where f.f1 <= g.mob) as k1,
               count(*) filter (where f.f30 <= g.mob) as k30
        from core.dim_loan d left join firsts f using (sk_id_prev)
        join (select unnest([0, 6, 12]) as mob) g
          on d.max_mob >= g.mob or d.end_state in ('closed', 'closed_inferred')
        where d.end_state <> 'never_open' and not d.is_partial_history and d.has_application
          and d.contract_type = 'Revolving loans' and d.channel_type = 'Contact center'
        group by 1 order by 1
    """)
    ccm = {r["mob"]: r for r in cc}
    b6 = prop(ccm[6]["k1"], ccm[6]["n"])
    b12 = prop(ccm[12]["k30"], ccm[12]["n"])
    n6 = n_per_arm(b6["rate"], -0.20)
    n12 = n_per_arm(b12["rate"], -0.20)
    out["sample_size_card_contact_center"] = {
        "population_size_in_data_mob0": int(ccm[0]["n"]),
        "ever_1_plus_mob6": b6, "n_per_arm_ever_1_plus_mob6_rel_minus_20pct": n6,
        "ever_30_plus_mob12": b12, "n_per_arm_ever_30_plus_mob12_rel_minus_20pct": n12,
        "multiple_of_population_size_ever_1_plus": rnd(2 * n6 / ccm[0]["n"]) if n6 else None,
        "multiple_of_population_size_ever_30_plus": rnd(2 * n12 / ccm[0]["n"]) if n12 else None,
    }

    # Y5: phần cơ học và phần dự báo thật của ever 1+@MOB6 trong vay tiêu dùng.
    e = one(con, """
        with firsts as (
            select sk_id_prev, min(mob) filter (where dpd > 0) as f1, min(mob) filter (where dpd > 30) as f30
            from core.fct_loan_month group by sk_id_prev
        )
        select count(*) filter (where f.f30 <= 12)                                  as k_all,
               count(*) filter (where f.f30 <= 6)                                   as k_by6,
               count(*) filter (where f.f30 between 7 and 12)                       as k_7_12,
               count(*) filter (where f.f30 between 7 and 12 and f.f1 <= 6)         as k_7_12_early,
               count(*) filter (where f.f1 <= 6 and coalesce(f.f30 > 6, true))      as n_early_not30_by6,
               count(*) filter (where coalesce(f.f1 > 6, true))                     as n_not_early,
               count(*) filter (where coalesce(f.f1 > 6, true) and f.f30 between 7 and 12) as k_7_12_not_early
        from core.dim_loan d left join firsts f using (sk_id_prev)
        where d.end_state <> 'never_open' and not d.is_partial_history
          and d.has_application and d.contract_type = 'Consumer loans'
          and (d.max_mob >= 12 or d.end_state in ('closed', 'closed_inferred'))
    """)
    out["early_indicator_decomposition_consumer"] = {
        "note": ("Vay tiêu dùng, đã biết kết quả đến MOB 12. Ca 30+ đến MOB 6 thì chắc chắn đã 1+ đến MOB 6 "
                 "(phần cơ học). Phần dự báo thật: ca lần đầu 30+ ở MOB 7 đến 12, so hợp đồng đã từng 1+ đến MOB 6 "
                 "(và chưa 30+ đến MOB 6) với hợp đồng chưa từng 1+ đến MOB 6."),
        "cases_ever_30_plus_mob12": int(e["k_all"]),
        "cases_first_30_plus_by_mob6_mechanical": int(e["k_by6"]),
        "cases_first_30_plus_mob7_to_12": int(e["k_7_12"]),
        "share_mob7_to_12_cases_preceded_by_1_plus_by_mob6": prop(e["k_7_12_early"], e["k_7_12"]),
        "first_30_plus_mob7_to_12_if_1_plus_by_mob6": prop(e["k_7_12_early"], e["n_early_not30_by6"]),
        "first_30_plus_mob7_to_12_if_not": prop(e["k_7_12_not_early"], e["n_not_early"]),
        "ratio_non_mechanical": ratio(e["k_7_12_early"], e["n_early_not30_by6"],
                                      e["k_7_12_not_early"], e["n_not_early"]),
    }

    # Y6: cỡ mẫu thử nghiệm thu hồi, đơn vị là hợp đồng (lần đầu ở B1), mức tăng tuyệt đối.
    b1 = one(con, """
        with m as (
            select sk_id_prev, months_balance, is_open, dpd_bucket_order,
                   lead(months_balance) over w as nm, lead(is_open) over w as nopen,
                   lead(dpd_bucket_order) over w as nb
            from core.fct_loan_month
            window w as (partition by sk_id_prev order by months_balance)
        ),
        firstb1 as (
            select sk_id_prev,
                   arg_min(case when nm = months_balance + 1 and nopen and nb = 0 then 1 else 0 end,
                           months_balance) as cured
            from m where is_open and months_balance < -1 and dpd_bucket_order = 1
            group by sk_id_prev
        )
        select count(*) as n, sum(cured) as k from firstb1
    """)
    base = prop(b1["k"], b1["n"])
    per_pp = []
    for pp in (0.03, 0.05, 0.10):
        p1 = base["rate"]
        p2 = p1 + pp
        pbar = (p1 + p2) / 2
        num = (Z * math.sqrt(2 * pbar * (1 - pbar)) + Z_POWER * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
        per_pp.append({"absolute_increase_pp": rnd(pp * 100), "target_rate": rnd(p2),
                       "n_per_arm": int(math.ceil(num / pp ** 2))})
    b1row = next(s for s in roll_out["primary"]["all"] if s["from_state"] == "B1 1-30")
    out["collections_sample_size_by_contract"] = {
        "note": ("Đơn vị ngẫu nhiên hoá là hợp đồng: mỗi hợp đồng lấy lần đầu tiên ở B1 (tháng đang mở, t <= -2), "
                 "cure = về B0 đúng tháng t+1. Lượt hợp đồng-tháng của roll rate không độc lập (một hợp đồng góp "
                 "nhiều lượt) nên không dùng làm đơn vị. Dữ liệu theo tháng nên không đo được tác động của liên hệ "
                 "trong 7 ngày; chỉ tiêu đo được là cure ở tháng sau."),
        "first_b1_cure_baseline": base,
        "contracts_ever_in_b1": int(b1["n"]),
        "old_rel_plus_20pct_equals_pp": rnd(b1row["cure_to_b0"]["rate"] * 0.20 * 100),
        "by_absolute_increase": per_pp,
    }

    # Y7: nhóm (không rõ) trong vintage.
    u = one(con, """
        with firsts as (select sk_id_prev, min(mob) filter (where is_30_plus) as m30 from core.fct_loan_month group by 1)
        select count(*)                                                                      as n_group,
               count(*) filter (where is_partial_history)                                    as n_partial,
               count(*) filter (where end_state = 'never_open')                              as n_never_open,
               count(*) filter (where end_state <> 'never_open' and not is_partial_history)  as n_vintage_base,
               count(*) filter (where end_state <> 'never_open' and not is_partial_history
                                  and end_state = 'unknown' and max_mob < 12)                as n_unknown_excluded_mob12,
               count(*) filter (where end_state <> 'never_open' and not is_partial_history
                                  and end_state = 'unknown' and max_mob < 12 and f.m30 <= 12) as k_unknown_excluded_mob12,
               count(*) filter (where end_state <> 'never_open' and not is_partial_history
                                  and (max_mob >= 12 or end_state in ('closed', 'closed_inferred', 'unknown')))
                                                                                             as n_if_unknown_closed,
               count(*) filter (where end_state <> 'never_open' and not is_partial_history
                                  and (max_mob >= 12 or end_state in ('closed', 'closed_inferred', 'unknown'))
                                  and f.m30 <= 12)                                           as k_if_unknown_closed
        from core.dim_loan d left join firsts f using (sk_id_prev)
        where not d.has_application
    """)
    unk12 = next(r for r in vintage_out["mob12"]["by_product"] if r["contract_type"] == UNKNOWN)
    out["unknown_application_group"] = {
        "n_contracts": int(u["n_group"]),
        "excluded_partial_history": prop(u["n_partial"], u["n_group"]),
        "n_never_open": int(u["n_never_open"]),
        "n_vintage_base_mob0": int(u["n_vintage_base"]),
        "n_unknown_end_state_excluded_at_mob12": int(u["n_unknown_excluded_mob12"]),
        "k_unknown_end_state_excluded_at_mob12": int(u["k_unknown_excluded_mob12"]),
        "mob12_current": unk12["primary"],
        "mob12_if_unknown_end_state_treated_as_closed": prop(u["k_if_unknown_closed"], u["n_if_unknown_closed"]),
        "note": ("closed_inferred cần DAYS_TERMINATION của hồ sơ nên không áp được cho nhóm không có hồ sơ: hợp đồng "
                 "dừng sớm của nhóm giữ nhãn unknown và bị loại khỏi mẫu số MOB 12 nếu max_mob < 12. Nếu đối xử "
                 "như nhóm có hồ sơ (coi là đã đóng), tỷ lệ nhóm là mob12_if_unknown_end_state_treated_as_closed."),
    }

    # Y8: hợp đồng đang mở thiếu dư nợ proxy.
    x = one(con, """
        select count(*) as n, count(*) filter (where f.is_30_plus) as k,
               count(*) filter (where not d.has_application) as n_unknown,
               count(*) filter (where f.is_30_plus and not d.has_application) as k_unknown
        from core.fct_loan_month f join core.dim_loan d using (sk_id_prev)
        where f.is_open and f.months_balance = -1 and f.exposure_proxy is null
    """)
    out["snapshot_exposure_missing"] = {"n_contracts": int(x["n"]), "n_30_plus": int(x["k"]),
                                        "n_contracts_unknown_group": int(x["n_unknown"]),
                                        "n_30_plus_unknown_group": int(x["k_unknown"])}

    # Y9: ca vay tiền mặt đang 30+ trong danh mục mở: MOB hiện tại và MOB lần đầu 30+.
    y = rows(con, """
        with firsts as (select sk_id_prev, min(mob) filter (where is_30_plus) as m30 from core.fct_loan_month group by 1)
        select coalesce(d.channel_type = 'Credit and cash offices', false) as is_cco,
               count(*) as n,
               quantile_disc(f.mob, 0.5) as median_mob_now, min(f.mob) as min_mob_now, max(f.mob) as max_mob_now,
               quantile_disc(fi.m30, 0.5) as median_first_30_plus_mob,
               count(*) filter (where fi.m30 > 12) as n_after12,
               count(*) filter (where d.is_partial_history) as n_partial_history
        from core.fct_loan_month f join core.dim_loan d using (sk_id_prev) left join firsts fi using (sk_id_prev)
        where f.is_open and f.months_balance = -1 and f.is_30_plus and d.has_application
          and d.contract_type = 'Cash loans'
        group by grouping sets ((is_cco), ()) order by 1 nulls first
    """)
    yy = {}
    for r in y:
        if r["is_cco"] is None:
            key = "all_cash_loans"
        elif r["is_cco"]:
            key = "credit_and_cash_offices"
        else:
            continue
        yy[key] = {"n": int(r["n"]), "median_mob_now": int(r["median_mob_now"]),
                   "min_mob_now": int(r["min_mob_now"]), "max_mob_now": int(r["max_mob_now"]),
                   "median_first_30_plus_mob": int(r["median_first_30_plus_mob"]),
                   "first_30_plus_after_mob12": prop(r["n_after12"], r["n"]),
                   "n_partial_history": int(r["n_partial_history"])}
    out["snapshot_cash_loans_30_plus_timing"] = yy

    # Thẻ Stone so với Credit and cash offices: chỉ mô tả.
    stc = next(p for p in channel_out["mob12"]["stone_vs_others"]
               if p["reference_channel"] == "Credit and cash offices")
    rv = stc["by_product"]["Revolving loans"]["primary"]
    out["card_stone_vs_credit_cash_offices_mob12"] = {
        "label": "mô tả, không phải so sánh định trước",
        "primary": rv,
        "n_cases_total": int(rv["numerator"]["k"] + rv["reference"]["k"]),
    }

    # Bonferroni với số so sánh đếm đủ.
    r = seg_out["mob12"]["segment_new_high"]["ratio_vs_rest"]
    k1, n1, k0, n0 = r["numerator"]["k"], r["numerator"]["n"], r["reference"]["k"], r["reference"]["n"]
    se = math.sqrt(1 / k1 - 1 / n1 + 1 / k0 - 1 / n0)
    bonf = {}
    for m in (12, 36, 144):
        zb = NormalDist().inv_cdf(1 - 0.025 / m)
        bonf[str(m)] = [rnd(r["ratio"] * math.exp(-zb * se)), rnd(r["ratio"] * math.exp(zb * se))]
    out["segment_bonferroni_full_count_mob12"] = {
        "note": ("Số so sánh: 12 tổ hợp; 36 = 12 × 3 mốc MOB; 144 = 12 × 3 MOB × 2 định nghĩa × 2 (có, không "
                 "điều kiện kênh)."),
        "ratio": r["ratio"], "ci95_bonferroni_by_n_comparisons": bonf}

    # closed_inferred gồm cả hợp đồng dừng khi đang nợ.
    ci_ = one(con, """
        with firsts as (select sk_id_prev, min(mob) filter (where is_30_plus) as m30 from core.fct_loan_month group by 1),
        lastm as (select sk_id_prev, arg_max(is_30_plus, months_balance) as last_30 from core.fct_loan_month group by 1)
        select count(*) as n_cases, count(*) filter (where l.last_30) as n_last_month_30_plus
        from core.dim_loan d join firsts f using (sk_id_prev) join lastm l using (sk_id_prev)
        where d.end_state = 'closed_inferred' and not d.is_partial_history and d.has_application
          and d.contract_type = 'Consumer loans' and f.m30 <= 12
    """)
    out["closed_inferred_consumer_cases_mob12"] = {
        "n_cases": int(ci_["n_cases"]), "n_30_plus_in_last_observed_month": int(ci_["n_last_month_30_plus"]),
        "note": "closed_inferred là hợp đồng dừng quan sát mà hồ sơ có ngày kết thúc, không nhất thiết là đã trả xong."}

    # Snapshot theo sản phẩm × kênh.
    pc = rows(con, """
        select contract_type, channel_type, sum(n_loans) as n, sum(n_30_plus) as k
        from mart.portfolio_snapshot group by 1, 2 order by 1, 2
    """)
    out["snapshot_by_product_channel"] = [{"contract_type": r["contract_type"], "channel_type": r["channel_type"],
                                           "primary": prop(r["k"], r["n"])} for r in pc]

    # Tổng ma trận roll rate (cho ghi chú trang 4).
    allst = roll_out["primary"]["all"]
    out["roll_totals"] = {
        "n_from_all_states": int(sum(s["n_from"] for s in allst)),
        "cure_b1_plus": prop(sum(s["cure_to_b0"]["k"] for s in allst if s["from_state"] != "B0 Current"),
                             sum(s["n_from"] for s in allst if s["from_state"] != "B0 Current")),
    }
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    con = duckdb.connect(str(DB_PATH), read_only=True)
    con.execute("PRAGMA threads=1")
    try:
        roll_out = roll_cure(con)
        seg_out = segment(con)
        vintage_out = vintage(con)
        channel_out = channel_comparison(con)
        findings = {
            "meta": {
                "script": "scripts/compute_findings.py",
                "primary_definition": "SK_DPD_DEF (DPD có ngưỡng trọng yếu): cột dpd, is_30_plus, n_ever_30_plus, n_30_plus",
                "sensitivity_definition": "SK_DPD (không áp ngưỡng trọng yếu): hậu tố _no_threshold",
                "official_description_SK_DPD_DEF": {
                    "POS_CASH_balance": "DPD during the month with tolerance (debts with low loan amounts are ignored) of the previous credit",
                    "credit_card_balance": "DPD (Days past due) during the month with tolerance (debts with low loan amounts are ignored) of the previous credit",
                },
                "official_description_SK_DPD": {
                    "POS_CASH_balance": "DPD (days past due) during the month of previous credit",
                    "credit_card_balance": "DPD (Days past due) during the month on the previous credit",
                },
                "ci": "95%. Tỷ lệ: Wilson. Tỷ số hai tỷ lệ: log Katz (Haldane +0,5 nếu có ô 0). SMR: Byar. Gộp: Mantel-Haenszel.",
                "z": rnd(Z),
                "min_n_to_interpret": MIN_N,
                "significant_means": "khoảng tin cậy 95% của tỷ số không chứa 1",
            },
            "portfolio": portfolio(con),
            "snapshot": snapshot(con),
            "vintage": vintage_out,
            "channel_comparison": channel_out,
            "origination_cohort": origination_cohort(con),
            "review_checks": review_checks(con, vintage_out, channel_out, roll_out, seg_out),
            "high_risk_segment": seg_out,
            "roll_cure": roll_out,
            "approval": approval(con),
            "fpd30": fpd(con),
            "sample_size": sample_size(con, seg_out, roll_out),
            "unknown_sensitivity": unknown_sensitivity(con),
        }
    finally:
        con.close()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(findings, ensure_ascii=False, indent=1, sort_keys=True, default=str) + "\n",
                        encoding="utf-8")
    print(f"Đã ghi {OUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
