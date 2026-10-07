# Metric Dictionary

Nguồn chuẩn cho định nghĩa và công thức của mọi chỉ tiêu trong project. Dashboard, memo và SQL đều phải dùng đúng các định nghĩa này. Mọi thay đổi định nghĩa ghi vào [Changelog](#changelog). Con số nền trong file này lấy từ `data/export/findings.json` hoặc tính lại từ CSV trong `data/export/`.

**Owner:** Lien | **Phiên bản:** 0.5 | **Cập nhật:** 2026-10-04

## Quy ước chung

| Quy ước | Giá trị |
|---|---|
| Định nghĩa quá hạn chính | `SK_DPD_DEF` (DPD có ngưỡng trọng yếu: bỏ qua khoản nợ giá trị thấp), nằm ở các cột gốc `dpd`, `dpd_bucket`, `dpd_bucket_order`, `is_30_plus`, `is_90_plus`, `debt_group_vn`, `n_ever_30_plus`, `n_30_plus`. Đổi từ phiên bản 0.4, lý do trong [methodology mục 4](methodology.md#4-quyết-định-đã-đảo-ngược-định-nghĩa-quá-hạn) |
| Định nghĩa độ nhạy | `SK_DPD` (không áp ngưỡng trọng yếu), ở các cột hậu tố `_no_threshold` trên mọi bảng và bảng `mart.roll_rate_no_threshold`. Chỉ dùng để đo độ nhạy, không dùng làm kết luận |
| Bucket | B0 = 0, B1 = 1-30, B2 = 31-60, B3 = 61-90, B4 = trên 90 ngày |
| "30+" | DPD **lớn hơn 30**, tức từ B2 trở lên. Tương tự "90+" là DPD lớn hơn 90, "1+" là DPD lớn hơn 0 |
| Hợp đồng đang mở (`is_open`) | trạng thái `Active`, `Demand` hoặc `Amortized debt` (macro `core.is_open_status`) |
| MOB 0 | tháng đầu tiên hợp đồng ở trạng thái mở |
| Thời gian | `months_balance` là tháng tương đối so với ngày nộp hồ sơ hiện tại của từng khách, `-1` là tháng gần nhất. Không quy đổi được sang tháng lịch |
| Trình bày tỷ lệ | luôn kèm tử số, mẫu số và khoảng tin cậy 95% (Wilson); mặc định tính theo số hợp đồng, tính theo exposure là chỉ tiêu phụ |
| So sánh hai nhóm | tỷ số kèm khoảng tin cậy 95% (log Katz); "có ý nghĩa" khi khoảng không chứa 1. Không tính tỷ số khi một bên có mẫu số dưới 1.000 |

## Danh sách chỉ tiêu

| Mã | Tên | Nhóm | Trạng thái |
|---|---|---|---|
| [M01](#m01-dpd) | DPD | Nền tảng | Có trong `core` |
| [M02](#m02-dpd-bucket) | DPD bucket | Nền tảng | Có trong `core` và `mart.portfolio_snapshot` |
| [M03](#m03-nhóm-nợ-proxy) | Nhóm nợ (proxy theo DPD) | Nền tảng | Có trong `core` |
| [M04](#m04-mob) | MOB | Nền tảng | Có trong `core` |
| [M05](#m05-exposure-proxy) | Exposure proxy | Nền tảng | Có trong `core` |
| [M06](#m06-tỷ-lệ-30-coincident) | Tỷ lệ 30+ coincident | Chất lượng danh mục | Có trong `mart.portfolio_snapshot` (tại tháng `-1`) |
| [M07](#m07-tỷ-lệ-30-lagged) | Tỷ lệ 30+ lagged | Chất lượng danh mục | Chưa có mart |
| [M08](#m08-vintage-ever-30mobn) | Vintage ever 30+@MOBn | Chất lượng danh mục | Có trong `mart.vintage` |
| [M09](#m09-roll-rate) | Roll rate | Chất lượng danh mục | Có trong `mart.roll_rate` |
| [M10](#m10-cure-rate) | Cure rate | Collections | Có trong `mart.roll_rate` |
| [M11](#m11-fpd30) | FPD30 | Rủi ro sớm | Có trong `mart.fpd_by_segment` |
| [M12](#m12-approval-rate-và-take-up-rate) | Approval rate, take-up rate | Funnel | Có trong `mart.funnel_by_channel` |
| [M13](#m13-ever-1mobn-chỉ-tiêu-sớm) | Ever 1+@MOBn (chỉ tiêu sớm) | Rủi ro sớm | Tính trong `scripts/compute_findings.py`, chưa có mart |
| [M14](#m14-smr-theo-kênh) | SMR theo kênh | Chất lượng danh mục | Tính trong `scripts/compute_findings.py` từ cùng dữ liệu với `mart.vintage` |
| [M15](#m15-vintage-theo-đợt-mở) | Vintage theo đợt mở | Chất lượng danh mục | Cột `origination_cohort` của `mart.vintage` |

---

## Nền tảng

### M01. DPD

- **Định nghĩa:** số ngày quá hạn của hợp đồng trong tháng quan sát, sau khi bỏ qua khoản nợ giá trị thấp (ngưỡng trọng yếu do Home Credit đặt).
- **Câu hỏi trả lời:** hợp đồng đang trễ hạn bao lâu?
- **Grain:** hợp đồng × tháng.
- **Nguồn:** `core.fct_loan_month.dpd`, lấy từ `SK_DPD_DEF` của `POS_CASH_balance` và `credit_card_balance` (ở `stg` là cột `dpd_def`). Cột độ nhạy `dpd_no_threshold` lấy từ `SK_DPD` (ở `stg` là `dpd_raw`).
- **Công thức:** lấy trực tiếp. Nếu một hợp đồng có nhiều dòng trong cùng tháng, giữ dòng có `dpd_def` lớn nhất, hòa thì xét `dpd_raw` (quy tắc phòng vệ, trên dữ liệu thật không có cặp trùng).
- **Edge case:**
  - Mô tả chính thức của `SK_DPD_DEF`: "DPD during the month with tolerance (debts with low loan amounts are ignored) of the previous credit" (POS). Ngưỡng "low loan amounts" không được công bố.
  - Mô tả ghi "during the month", chưa rõ là DPD cuối tháng hay cao nhất trong tháng ([data_notes mục 7](data_notes.md#7-dpd)).
  - Không có dòng nào `dpd > dpd_no_threshold`.
  - Hợp đồng có trong cả hai nguồn: lấy dữ liệu thẻ.
- **Kiểm tra:** `fct_loan_month__dpd_valid`, `fct_loan_month__dpd_no_threshold_valid` (warn), `fct_loan_month__flags_match_dpd`, `sources__duplicate_months`.

### M02. DPD bucket

- **Định nghĩa:** nhóm DPD thành các khoảng để theo dõi và tính chuyển trạng thái.
- **Grain:** hợp đồng × tháng.
- **Nguồn:** `core.fct_loan_month.dpd_bucket` (nhãn), `dpd_bucket_order` (0 đến 4, dùng để sắp xếp và so sánh), cả hai theo `dpd`. Cặp độ nhạy `dpd_bucket_no_threshold`, `dpd_bucket_order_no_threshold` theo `dpd_no_threshold`. Cơ cấu bucket của danh mục đang mở tại tháng `-1` có sẵn ở `mart.portfolio_snapshot` ([M06](#m06-tỷ-lệ-30-coincident)).
- **Công thức:**

  | Bucket | DPD |
  |---|---|
  | B0 Current | 0 |
  | B1 1-30 | 1 đến 30 |
  | B2 31-60 | 31 đến 60 |
  | B3 61-90 | 61 đến 90 |
  | B4 90+ | trên 90 |

- **Edge case:** ranh giới tính cả hai đầu: DPD = 30 thuộc B1, DPD = 31 thuộc B2. Không trộn hai định nghĩa trong cùng một dòng: bucket chính đi với `is_30_plus`, bucket `_no_threshold` đi với `is_30_plus_no_threshold`.
- **Kiểm tra:** `fct_loan_month__dpd_valid`, `fct_loan_month__flags_match_dpd`, `portfolio_snapshot__counts_consistent`.

### M03. Nhóm nợ (proxy)

- **Định nghĩa:** nhóm nợ theo số ngày quá hạn, mô phỏng cách phân loại nợ của TCTD (tổ chức tín dụng) Việt Nam.
- **Grain:** hợp đồng × tháng.
- **Nguồn:** `core.fct_loan_month.debt_group_vn`, theo `dpd` (định nghĩa chính).
- **Công thức:**

  | Nhóm | DPD |
  |---|---|
  | 1 | dưới 10 |
  | 2 | 10 đến 90 |
  | 3 | 91 đến 180 |
  | 4 | 181 đến 360 |
  | 5 | trên 360 |

  Nợ xấu = nhóm 3 đến 5.
- **Edge case:** chỉ là proxy theo DPD. Phân loại chính thức (Thông tư 31/2024/TT-NHNN) còn xét cơ cấu nợ, yếu tố định tính và điều chỉnh theo thông tin CIC (Trung tâm Thông tin tín dụng). Trên dashboard luôn ghi rõ "proxy".

### M04. MOB

- **Định nghĩa:** số tháng kể từ tháng hợp đồng bắt đầu mở (month on book).
- **Grain:** hợp đồng × tháng.
- **Nguồn:** `core.fct_loan_month.mob`, `core.dim_loan.first_open_month`.
- **Công thức:** `mob = months_balance - first_open_month`. Tháng mở có MOB = 0.
- **Edge case:**
  - Hợp đồng chưa từng mở (`end_state = 'never_open'`) không có trong `fct_loan_month`.
  - Tháng bị thiếu vẫn làm MOB tăng (MOB tính theo lịch, không theo số dòng).
  - Hợp đồng thiếu lịch sử đầu (`is_partial_history`) có MOB thấp hơn thực tế, bị loại khỏi vintage.
- **Kiểm tra:** `fct_loan_month__mob_non_negative`, `fct_loan_month__month_gaps`.

### M05. Exposure proxy

- **Định nghĩa:** ước lượng số tiền còn phải thu của hợp đồng trong tháng.
- **Grain:** hợp đồng × tháng.
- **Nguồn:** `core.fct_loan_month.exposure_proxy`.
- **Công thức:**
  - Khoản trả góp: `installments_remaining × annuity_amount` (gồm cả lãi, không phải dư nợ gốc).
  - Thẻ tín dụng: `balance_amount`, số âm tính là 0.
- **Edge case:** `annuity_amount` NULL thì exposure NULL (gần như toàn bộ là hợp đồng không khớp hồ sơ). Chỉ cộng exposure trên các tháng `is_open`. Chỉ dùng để so sánh tương đối, không đối chiếu với số liệu kế toán.

---

## Chất lượng danh mục

### M06. Tỷ lệ 30+ coincident

- **Định nghĩa:** trong một kỳ quan sát, tỷ lệ hợp đồng đang mở có DPD trên 30.
- **Câu hỏi trả lời:** hiện tại bao nhiêu phần danh mục đang trễ hạn nghiêm trọng?
- **Grain báo cáo:** kỳ quan sát × phân khúc.
- **Nguồn:** `core.fct_loan_month`.
- **Mart:** [`sql/mart/mart_portfolio_snapshot.sql`](../sql/mart/mart_portfolio_snapshot.sql) tạo bảng `mart.portfolio_snapshot`, grain sản phẩm × kênh × bucket, chỉ tại tháng gần nhất `months_balance = -1`. Cột đếm và tiền: `n_loans`, `exposure`, `n_30_plus`, `exposure_30_plus` (theo `SK_DPD_DEF`); `n_loans_exposure_known`, `n_30_plus_exposure_known` (chỉ hợp đồng có `exposure_proxy`); độ nhạy `n_30_plus_no_threshold`, `exposure_30_plus_no_threshold` (theo `SK_DPD`, không khớp `dpd_bucket` của dòng). Kỳ khác tháng `-1` vẫn lấy từ `core.fct_loan_month` bằng SQL mẫu bên dưới.
- **Công thức:**
  - Theo số lượng: `count(is_open and is_30_plus) / count(is_open)`
  - Theo exposure: `sum(exposure_proxy where is_open and is_30_plus) / sum(exposure_proxy where is_open)`
  - **Khi đặt hai tỷ lệ cạnh nhau** (hai thẻ KPI), tỷ lệ theo số lượng phải tính trên cùng tập với tỷ lệ theo exposure: `sum(n_30_plus_exposure_known) / sum(n_loans_exposure_known)`.
- **Con số nền tại tháng `-1`:** 144.421 hợp đồng đang mở.

  | Tập | 30+ theo hợp đồng | 30+ theo dư nợ |
  |---|---|---|
  | Hợp đồng có exposure (khuyến nghị cho hai thẻ KPI) | 0,094% [0,079; 0,111] (135 / 144.311) | 0,301% |
  | Bỏ hẳn nhóm `(không rõ)` | 0,094% [0,080; 0,112] (130 / 137.611) | 0,301% |
  | Toàn bộ hợp đồng đang mở | 0,110% [0,094; 0,129] (159 / 144.421) | |
  | Độ nhạy `SK_DPD`, toàn bộ hợp đồng đang mở | 0,405% [0,374; 0,439] (585 / 144.421) | 0,312% |

- **SQL mẫu:** snapshot tại tháng gần nhất, theo nguồn

  ```sql
  select
      source,
      count(*) filter (where is_30_plus)            as n_30_plus,
      count(*)                                      as n_open,
      count(*) filter (where is_30_plus) / count(*) as dq30_rate,
      coalesce(sum(exposure_proxy) filter (where is_30_plus), 0)
          / sum(exposure_proxy)                     as dq30_rate_exposure
  from core.fct_loan_month
  where is_open
    and months_balance = -1
  group by source;
  ```

- **Edge case:**
  - Phân khúc không có hợp đồng 30+: `sum(...) filter` trả về NULL, phải `coalesce` về 0.
  - 110 hợp đồng đang mở có `exposure_proxy` NULL, 24 trong số đó đang 30+. Vì vậy tỷ lệ theo hợp đồng trên toàn tập (0,110%) và tỷ lệ theo dư nợ không cùng tập; dùng cặp cột `_exposure_known`.
  - Nhóm `(không rõ)` chiếm 4,72% hợp đồng đang mở nhưng 18,2% số ca 30+ (29 / 159).
  - Hiệu ứng mẫu số: danh mục tăng nhanh làm tỷ lệ giảm dù chất lượng không đổi. Đọc cùng M07 và M08.
  - Với dữ liệu này, "kỳ quan sát" là tháng tương đối, không phải tháng lịch.
- **Kiểm tra:** `portfolio_snapshot__unique_grain`, `portfolio_snapshot__counts_consistent`, `portfolio_snapshot__reconciles_with_core`.

### M07. Tỷ lệ 30+ lagged

- **Định nghĩa:** số hợp đồng 30+ tại kỳ t chia cho số hợp đồng đang mở tại kỳ t - k.
- **Câu hỏi trả lời:** tỷ lệ nợ trễ hạn còn đẹp không khi loại bỏ tác động của hợp đồng mới giải ngân?
- **Công thức:** `count(is_30_plus tại t) / count(is_open tại t - k)`, mặc định k = 3.
- **Edge case:** chọn k gần với số tháng trung bình để một hợp đồng mới đi đến 30+. Ghi rõ k trên mọi biểu đồ. Chỉ tiêu này cần thiết để giải thích vì sao vay tiền mặt chiếm phần lớn 30+ của danh mục đang mở nhưng có ever 30+@MOB12 thấp ([methodology mục 7](methodology.md#7-những-gì-project-chưa-làm-được)).

### M08. Vintage ever 30+@MOBn

- **Định nghĩa:** trong một cohort hợp đồng, tỷ lệ hợp đồng **từng** có DPD (theo `SK_DPD_DEF`) trên 30 tính đến MOB n.
- **Câu hỏi trả lời:** cohort nào xấu đi nhanh hơn khi so cùng tuổi hợp đồng?
- **Cohort:** nhóm theo thuộc tính trong `core.dim_loan` (`source`, `contract_type`, `channel_type`, `client_type`, `yield_group`, nhóm kỳ hạn) và theo đợt mở tương đối `origination_cohort` ([M15](#m15-vintage-theo-đợt-mở)). Với dữ liệu có ngày thật, cohort là tháng giải ngân theo lịch.
- **Grain báo cáo:** cohort × MOB, báo cáo MOB 0 đến 36.
- **Nguồn:** `mart.vintage` (file `sql/mart/mart_vintage.sql`), dựng từ `core.fct_loan_month` và `core.dim_loan`.
- **Công thức:**
  - Tử số (`n_ever_30_plus`): hợp đồng có MOB đầu tiên với `is_30_plus` nằm trong khoảng MOB 0 đến n.
  - Mẫu số (`n_loans`): hợp đồng đã biết kết quả đến MOB n, tức `max_mob >= n` hoặc `end_state` là `closed` hay `closed_inferred`.
  - `ever_30_plus_rate = n_ever_30_plus / n_loans`.
  - Độ nhạy: `n_ever_30_plus_no_threshold`, `ever_30_plus_rate_no_threshold` theo `is_30_plus_no_threshold`, cùng mẫu số.
  - Độ nhạy thứ hai (định nghĩa giữa): `n_ever_30_plus_due_only`. Trả góp: `SK_DPD` trên 30 chỉ ở tháng có `installments_remaining > 0`; thẻ: giữ `SK_DPD_DEF`. Tại MOB 12: vay tiêu dùng 874 / 530.476, vay tiền mặt 214 / 225.408.
- **Loại khỏi mẫu số:** 95.695 hợp đồng trên 1.040.632, mẫu số gốc còn 944.937 hợp đồng.

  | Lý do loại | Số hợp đồng |
  |---|---|
  | `is_partial_history` (cắt trái theo cửa sổ dữ liệu, hoặc đã trả kỳ ngay tại tháng mở đầu tiên nên MOB thấp hơn thực tế) | 93.751 |
  | `end_state = 'never_open'` (chưa bao giờ ở trạng thái mở nên không có MOB 0) | 4.029 |

  Hai nhóm giao nhau 2.085 hợp đồng, nên tổng loại là 95.695 chứ không phải 93.751 + 4.029.

- **Nhãn `end_state`:** `closed` (trạng thái cuối `Completed`, 709.038), `closed_inferred` (lịch sử dừng trước tháng `-1`, trạng thái cuối vẫn mở, hồ sơ có `DAYS_TERMINATION`; 89.414), `censored` (còn mở tại tháng `-1`, 144.421), `unknown` (dừng trước tháng `-1`, không có ngày kết thúc; 93.730), `never_open` (4.029). Hợp đồng `unknown` chỉ vào mẫu số tại MOB n khi `max_mob >= n`. Cách gán `closed_inferred` và độ nhạy của nó: [methodology mục 5.3](methodology.md#53-hợp-đồng-dừng-sớm-closed_inferred-và-unknown).
- **Hai mẫu số phải in cùng nhau:**
  - `n_loans`: mẫu số của chỉ tiêu, gồm cả hợp đồng kết thúc trước MOB n.
  - `n_observed_full`: số hợp đồng thật sự còn quan sát được đến MOB n (`max_mob >= n`), tách khỏi `n_closed_early`.

  | MOB | `n_loans` | `n_observed_full` | `n_ever_30_plus` | tỷ lệ | `n_ever_30_plus_no_threshold` |
  |---|---|---|---|---|---|
  | 3 | 923.488 | 892.526 | 88 | 0,010% | 354 |
  | 6 | 889.874 | 731.065 | 230 | 0,026% | 1.288 |
  | 12 | 818.672 | 308.901 | 425 | 0,052% | 5.215 |
  | 24 | 763.989 | 70.635 | 508 | 0,066% | 6.558 |

- **Edge case:**
  - Hợp đồng kết thúc trước MOB n mà chưa từng 30+ được tính là tốt.
  - Tại MOB 24, chỉ 70.635 trên 763.989 hợp đồng của mẫu số còn quan sát đủ (9,2%). Không diễn giải đoạn MOB cao nếu không in kèm `n_observed_full`.
  - Tỷ lệ quan sát đủ khác nhau giữa sản phẩm (tại MOB 12: thẻ 95,2%, vay tiền mặt 52,8%, vay tiêu dùng 24,8%), nên so sánh sản phẩm phải kiểm lại ở MOB thấp.
  - Không diễn giải ô có `n_loans` dưới 1.000 hợp đồng.
  - 48.794 hợp đồng không khớp `stg.previous_application` mang nhãn `'(không rõ)'` ở mọi cột phân khúc, không loại âm thầm. Tại MOB 12 nhóm có 2.083 hợp đồng nhưng 106 trên 425 ca, tỷ lệ 5,089%. Mọi tổng toàn danh mục phải báo kèm tổng không gồm nhóm này (0,039%, tức 319 / 816.589).
  - Hai kênh quá nhỏ (`Car dealer` 452 hồ sơ, `Channel of corporate sales` 6.117) gom thành nhóm `Khác`.
  - `yield_group` null ở khoảng 30% hồ sơ, giữ thành nhóm riêng nhãn `Unknown`, không gộp vào nhóm khác.
  - Biến thể "point 30+@MOBn" (đang 30+ đúng tại MOB n) cho kết quả khác. Chỉ dùng một biến thể trong cùng biểu đồ.
- **Kiểm tra:** `vintage__unique_grain`, `vintage__counts_consistent`, `vintage__mob0_matches_core`, `vintage__cohort_matches_core`, `dim_loan__end_state_valid`.
- **SQL:** `sql/mart/mart_vintage.sql`. Đường cong toàn danh mục:

  ```sql
  select mob,
         sum(n_loans)          as mau_so,
         sum(n_observed_full)  as quan_sat_du,
         sum(n_ever_30_plus)   as tu_so,
         sum(n_ever_30_plus) * 1.0 / sum(n_loans) as ever_30_plus_rate,
         sum(n_ever_30_plus_no_threshold) * 1.0 / sum(n_loans) as ever_30_plus_rate_no_threshold
  from mart.vintage
  group by mob
  order by mob;
  ```

  Cắt theo một phân khúc: thêm cột đó vào `select` và `group by`. Luôn cộng tử số và mẫu số rồi chia lại, không lấy trung bình cột tỷ lệ.

### M09. Roll rate

- **Định nghĩa:** tỷ lệ hợp đồng chuyển từ trạng thái i ở tháng t sang trạng thái j ở tháng t + 1.
- **Câu hỏi trả lời:** khách quá hạn di chuyển giữa các bucket thế nào; bao nhiêu phần trăm tiếp tục xấu đi?
- **Grain báo cáo:** `source` × `contract_type` × `channel_type` × trạng thái đi × trạng thái đến.
- **Nguồn:** `mart.roll_rate` (file `sql/mart/mart_roll_rate.sql`), dựng từ `core.fct_loan_month` và `core.dim_loan` qua table macro `mart.roll_matrix(no_threshold)`. Bảng độ nhạy `mart.roll_rate_no_threshold` cùng grain, bucket theo `SK_DPD`, không xuất CSV.
- **Trạng thái đi:** B0 đến B4, chỉ lấy các tháng hợp đồng đang mở.
- **Trạng thái đến:** B0 đến B4 (còn mở), `Closed` (`contract_status = 'Completed'`), `Other` (có dòng tháng sau nhưng không mở và không `Completed`), `Missing` (không có dòng cho đúng tháng t + 1).
- **Công thức:** `roll_rate(i, j) = count(i tại t và j tại t + 1) / count(i tại t)`. Mỗi hàng của ma trận cộng lại bằng 100%, có test bắt buộc kiểm tra điều này.
- **Chỉ tiêu dẫn xuất:** forward roll rate = tỷ lệ chuyển sang bucket xấu hơn liền kề (ví dụ B1 sang B2). Cure rate là [M10](#m10-cure-rate).
- **Con số nền (toàn danh mục, định nghĩa chính):** 12.714.200 lượt xuất phát.

  | Trạng thái đi | Số lượt | sang B0 | sang B1 | sang B2 | sang B3 | sang B4 | Closed | Other | Missing |
  |---|---|---|---|---|---|---|---|---|---|
  | B0 Current | 12.512.752 | 91,981% | 0,994% | 0,000% | 0,000% | 0,000% | 5,585% | 0,001% | 1,439% |
  | B1 1-30 | 193.814 | 57,696% | 34,862% | 0,709% | 0,005% | 0,000% | 5,363% | 0,001% | 1,364% |
  | B2 31-60 | 1.642 | 27,832% | 26,675% | 14,312% | 22,777% | 0,244% | 5,542% | 0,000% | 2,619% |
  | B3 61-90 | 403 | 15,633% | 11,911% | 10,174% | 9,926% | 45,658% | 3,722% | 0,000% | 2,978% |
  | B4 90+ | 5.589 | 1,217% | 0,072% | 0,125% | 0,161% | 96,940% | 0,644% | 0,000% | 0,841% |

  Hàng B3 dưới 1.000 lượt, không diễn giải.

- **Edge case:**
  - Chỉ dùng cặp tháng cách nhau **đúng 1 tháng**. Theo profile, 12.693.134 trên 13.730.112 dòng (92,45%) có tháng kế tiếp hợp lệ.
  - **Phân biệt cắt phải và mất dữ liệu.** Tháng `t = -1` bị loại khỏi trạng thái xuất phát: dữ liệu kết thúc ở `-1` nên về nguyên tắc không thể quan sát tháng sau. Ngược lại, tháng `t <= -2` lẽ ra phải có tháng sau mà không có thì là mất dữ liệu thật, phải vào trạng thái `Missing` và kéo tỷ lệ xuống, không được loại âm thầm.
  - `Missing` toàn danh mục: 182.847 lượt (1,44%), trong đó chỉ 26 do hở tháng (`n_month_gap`), còn lại là lịch sử hợp đồng dừng hẳn ở tháng `t`. Tháng cuối của hợp đồng `closed_inferred` cũng vào `Missing` như trước; định nghĩa roll rate không đổi theo nhãn này.
  - `Completed` coi là trạng thái hấp thụ: chỉ 18 hợp đồng trên 1.040.632 (0,0017%) quay lại trạng thái mở sau `Completed`, chấp nhận sai lệch này.
  - **Tỷ lệ theo exposure:** cột `exposure_from`, `exposure_roll_rate` tính trên dư nợ ước lượng tháng t (M05). 286.803 lượt xuất phát có `exposure_proxy` null (2,26% số lượt của ma trận), các lượt này bị bỏ qua khi cộng tiền và đếm riêng ở cột `n_exposure_null`, **không được coi như bằng 0**.
  - Hàng B2 và B3 chỉ có 1.642 và 403 lượt trên toàn danh mục. Khi cắt theo nguồn hay phân khúc, gần như mọi ô B2, B3 dưới 1.000 lượt.
  - Theo `SK_DPD` (bảng độ nhạy), hàng B1 có 259.546 lượt và hàng B4 có 156.716 lượt; phần lớn chênh lệch là khoản dư lẻ ([methodology mục 4](methodology.md#4-quyết-định-đã-đảo-ngược-định-nghĩa-quá-hạn)).
  - Hợp đồng không khớp `stg.previous_application` mang nhãn `'(không rõ)'` ở cột phân khúc.
- **Kiểm tra:** `roll_rate__unique_grain`, `roll_rate__row_sums_to_one`, `roll_rate__counts_consistent` (cả ba kiểm cả bảng chính và bảng độ nhạy), `roll_rate__definitions_same_months`.
- **SQL:** `sql/mart/mart_roll_rate.sql`. Ma trận toàn danh mục theo số hợp đồng:

  ```sql
  select from_state, to_state,
         sum(n_loans) as n_loans,
         sum(n_loans) * 1.0 / sum(sum(n_loans)) over (partition by from_state) as roll_rate
  from mart.roll_rate
  group by from_state, to_state
  order by from_state, to_state;
  ```

  Theo exposure: thay `n_loans` bằng `exposure_from`, và luôn in kèm `sum(n_exposure_null)`. Độ nhạy: thay `mart.roll_rate` bằng `mart.roll_rate_no_threshold`.

### M14. SMR theo kênh

- **Định nghĩa:** số hợp đồng từng 30+ tại MOB n của một kênh chia số kỳ vọng nếu kênh có đúng tỷ lệ của từng sản phẩm mà nó bán (chuẩn hoá gián tiếp).
- **Câu hỏi trả lời:** sau khi tính đến cơ cấu sản phẩm, kênh nào rủi ro hơn mức sản phẩm của nó?
- **Grain báo cáo:** kênh × MOB (6, 12, 24).
- **Nguồn:** cùng dữ liệu với `mart.vintage`, tính trong `scripts/compute_findings.py`, khóa `channel_comparison.mob{6,12,24}.smr_by_channel`.
- **Công thức:** `SMR = O / E`, với `O = sum(n_ever_30_plus)` của kênh và `E = sum over tầng s của n_loans(kênh, s) × rate(s)`, `rate(s)` là tỷ lệ của tầng s trên toàn danh mục có nhãn sản phẩm. Tầng chính (từ phiên bản 0.5) là sản phẩm × đợt mở 12 tháng; bản chỉ theo sản phẩm giữ để đối chiếu. Khoảng tin cậy Byar. Khóa `origination_cohort.mob{6,12,24}.smr_by_channel`.
- **Con số nền tại MOB 12, sản phẩm × đợt mở:** Contact center 1,65 [1,21; 2,18] (48 / 29,1), Stone 1,36 [1,08; 1,69] (82 / 60,1), Credit and cash offices 0,89 [0,68; 1,14] (61 / 68,9), Country-wide 0,79 [0,65; 0,95] (110 / 139,8).
- **Con số nền tại MOB 12, chỉ theo sản phẩm (đối chiếu):** Contact center 2,90 [2,14; 3,84] (48 / 16,6), Stone 1,63 [1,30; 2,02] (82 / 50,3), Country-wide 1,01 [0,83; 1,21] (110 / 109,2), Regional / Local 0,60 [0,34; 1,00] (15 / 24,8), Credit and cash offices 0,58 [0,45; 0,75] (61 / 104,7).
- **Edge case:**
  - Không tính bất định của tỷ lệ tham chiếu.
  - SMR là chuẩn hoá gián tiếp: mỗi kênh so với kỳ vọng trên chính cơ cấu của nó. Không chia SMR hai kênh cho nhau; so hai kênh trực tiếp dùng tỷ số trong cùng tầng.
  - Nhóm `(không rõ)` và sản phẩm `Unknown` không vào tham chiếu.
  - Kênh có O dưới khoảng 10 ghi là không kết luận được (ví dụ AP+ (Cash loan) có O = 2).
  - Đi kèm tỷ số Mantel-Haenszel cho từng cặp kênh (`pairs_within_product`, `stone_vs_others`), chỉ tính khi cả hai ô của một sản phẩm có ít nhất 1.000 hợp đồng.

### M15. Vintage theo đợt mở

- **Định nghĩa:** ever 30+@MOBn ([M08](#m08-vintage-ever-30mobn)) tách theo đợt mở hợp đồng: nhóm 12 tháng của `core.dim_loan.first_open_month`, căn từ tháng -96 (`origination_cohort` '-96 đến -85' đến '-12 đến -1', `origination_cohort_start` là tháng đầu đợt).
- **Câu hỏi trả lời:** hợp đồng mở ở các thời điểm khác nhau có chất lượng khác nhau không, và đợt mở có làm nhiễu so sánh kênh, sản phẩm không?
- **Grain báo cáo:** đợt × sản phẩm × MOB.
- **Nguồn:** `mart.vintage` (cột `origination_cohort`, `origination_cohort_start`); độ nhạy mốc cắt (3 nhóm, 24 tháng) trong `scripts/compute_findings.py`, khóa `origination_cohort`.
- **Công thức:** như M08. Khi so các đợt với nhau tại MOB n, chỉ giữ đợt có tháng cuối `<= -1 - n`.
- **Con số nền tại MOB 12, ba sản phẩm có nhãn:** 0,192% [0,161; 0,230] (118 / 61.379) ở đợt -96 đến -85, 0,010% [0,007; 0,015] (23 / 224.703) ở đợt -24 đến -13.
- **Edge case:**
  - Đây là tháng tương đối so với ngày hồ sơ hiện tại của từng khách, không phải tháng lịch. Xu hướng theo đợt có thể là chọn mẫu, không chỉ là chất lượng giải ngân.
  - Đợt chưa đủ tuổi tới MOB n chỉ có hợp đồng đã đóng sớm trong mẫu số, nên trông tốt giả; không đưa vào so sánh đợt tại MOB đó.
  - Khi dùng làm tầng (SMR, Mantel-Haenszel) thì giữ mọi đợt, vì so sánh trong cùng tầng vẫn công bằng.
  - Cơ cấu sản phẩm đổi theo đợt, nên đọc tỷ lệ gộp ba sản phẩm kèm bảng theo từng sản phẩm.
- **Kiểm tra:** `vintage__cohort_matches_core`, `vintage__unique_grain`.

---

## Collections

### M10. Cure rate

- **Định nghĩa:** tỷ lệ hợp đồng đang ở bucket B1 trở lên tại tháng t trở về B0 tại tháng t + 1.
- **Câu hỏi trả lời:** bucket nào khó thu hồi nhất và cần ưu tiên nguồn lực?
- **Grain báo cáo:** bucket xuất phát × phân khúc.
- **Nguồn:** không có mart riêng. Lấy trực tiếp từ `mart.roll_rate` ([M09](#m09-roll-rate)), vì cure rate chỉ là một cột của ma trận đó. Làm mart riêng sẽ tạo ra hai nguồn số có thể lệch nhau.
- **Công thức:** `count(bucket >= B1 tại t và B0 tại t + 1) / count(bucket >= B1 tại t)`, tính riêng cho từng bucket xuất phát.
- **Con số nền (toàn danh mục):**

  | Bucket xuất phát | Số lượt | Về B0 | Cure rate | Sang `Closed` |
  |---|---|---|---|---|
  | B1 1-30 | 193.814 | 111.822 | 57,7% [57,5; 57,9] | 10.394 (5,363%) |
  | B2 31-60 | 1.642 | 457 | 27,8% [25,7; 30,0] | 91 (5,542%) |
  | B3 61-90 | 403 | 63 | 15,6%, dưới ngưỡng mẫu | 15 (3,722%) |
  | B4 90+ | 5.589 | 68 | 1,2% [0,96; 1,54] | 36 (0,644%) |
  | Tổng B1 trở lên | 201.448 | 112.410 | 55,801% | 10.536 (5,230%) |

  Theo nguồn: B1 của POS 55,3% (59.399 / 107.369), B1 của thẻ 60,6% (52.423 / 86.445). Độ nhạy `SK_DPD`: 50,1% ở B1, 17,3% ở B2, 7,0% ở B3, 2,0% ở B4.

- **Edge case:**
  - Hợp đồng chuyển sang `Closed` từ bucket quá hạn được báo cáo riêng (cột cuối bảng trên), không gộp vào cure. Với dữ liệu này `Closed` nghĩa là `contract_status = 'Completed'`, không phân biệt được tất toán do khách trả hết hay do xóa nợ.
  - Mẫu số và tử số kế thừa mọi quy tắc của M09: chỉ cặp tháng cách nhau đúng 1 tháng, loại tháng `-1` khỏi trạng thái xuất phát, lượt không có tháng sau vào `Missing` (nằm trong mẫu số, không nằm trong tử số).
  - B2 và B3 rất mỏng. Khi cắt theo phân khúc gần như không đủ quan sát, cân nhắc gộp thành một hàng `31-90`.
- **Kiểm tra:** dùng chung test của `mart.roll_rate`.
- **SQL:** truy vấn từ `mart.roll_rate`:

  ```sql
  -- Cure rate theo từng bucket xuất phát, toàn danh mục
  select from_state,
         sum(n_loans)                                          as n_from,
         sum(n_loans) filter (where to_state = 'B0 Current')   as n_cured,
         sum(n_loans) filter (where to_state = 'B0 Current') * 1.0 / sum(n_loans) as cure_rate,
         sum(n_loans) filter (where to_state = 'Closed')       as n_closed
  from mart.roll_rate
  where from_state <> 'B0 Current'
  group by from_state
  order by from_state;
  ```

  Cắt theo phân khúc: thêm `source`, `contract_type` hoặc `channel_type` vào `select` và `group by`.

---

## Rủi ro sớm

### M11. FPD30

- **Định nghĩa:** hợp đồng trả góp mà kỳ trả đầu tiên chưa được trả đủ sau 30 ngày kể từ ngày đến hạn.
- **Câu hỏi trả lời:** kênh, sản phẩm nào mang về khách có dấu hiệu rủi ro ngay từ kỳ đầu (bao gồm gian lận)?
- **Grain báo cáo:** phân khúc (`channel_type` × `contract_type` × `client_type` × `yield_group`).
- **Nguồn:** `stg.installments_payments` (`installment_number = 1`), left join `stg.previous_application` để lấy phân khúc.
- **Công thức:**
  - Kỳ 1: `installment_number = 1`, bỏ `installment_version = 0` (thẻ tín dụng), lấy **đúng** version nhỏ nhất còn lại của hợp đồng (lịch trả gốc); chỉ các dòng của version đó được dùng.
  - Tử số (`n_fpd30`): hợp đồng có tổng `payment_amount` với `days_late <= 30` nhỏ hơn `installment_amount × 95%` (dung sai 5%).
  - Biến thể theo quy tắc ngày (`n_fpd30_late_rule`, `fpd30_late_rule_rate`): kỳ 1 có `days_late > 30` (bất kể đã trả đủ tiền hay chưa).
  - Mẫu số (`n_loans`): hợp đồng có kỳ 1 đến hạn trước thời điểm quan sát ít nhất 30 ngày (`days_due <= -30`) và `installment_amount > 0`.
  - Đếm riêng, không thuộc mẫu số: `n_approved_not_activated` (hồ sơ `Approved`, không có lịch trả, tức `days_first_due` NULL, không có dòng kỳ 1) và `n_approved_scheduled_no_installment` (hồ sơ `Approved` có lịch trả nhưng không có dòng kỳ 1).
- **Con số nền:** 0,011% [0,009; 0,013] (99 / 895.744); quy tắc ngày 0,058% [0,054; 0,064] (523 / 895.744). `n_approved_not_activated` 77.884, `n_approved_scheduled_no_installment` 1.
- **Mart:** [`sql/mart/mart_fpd_by_segment.sql`](../sql/mart/mart_fpd_by_segment.sql) tạo bảng `mart.fpd_by_segment`.
- **SQL mẫu:**

  ```sql
  select
      channel_type,
      sum(n_loans)                                     as n_loans,
      sum(n_fpd30)                                     as n_fpd30,
      sum(n_fpd30) / nullif(sum(n_loans), 0)           as fpd30_rate,
      sum(n_fpd30_late_rule) / nullif(sum(n_loans), 0) as fpd30_late_rule_rate,
      sum(n_approved_not_activated)                    as n_approved_not_activated,
      sum(n_approved_scheduled_no_installment)         as n_approved_scheduled_no_installment
  from mart.fpd_by_segment
  group by channel_type
  order by fpd30_rate desc;
  ```

- **Edge case:**
  - Một kỳ có thể trả thành nhiều lần: cộng các lần trả của version đó trước khi so sánh.
  - Kỳ 1 có nhiều `installment_version`: ở phần lớn trường hợp cùng một lần trả được ghi lặp ở mỗi version còn số tiền phải trả bị tách giữa các version, nên cộng qua version sẽ phồng tiền đã trả. Chỉ dùng version nhỏ nhất.
  - Thẻ tín dụng không có trong mẫu số (lịch trả version 0).
  - Hợp đồng không khớp được `previous_application` nhận nhãn phân khúc `(không rõ)`, không loại âm thầm.
  - Hồ sơ duyệt không có dòng kỳ 1 gần như toàn bộ là chưa kích hoạt; không phải hợp đồng xấu biến khỏi mẫu số. Tử số FPD30 vẫn quá nhỏ để xếp hạng kênh, nên trục rủi ro chính là M08, chỉ tiêu sớm cho thử nghiệm là M13.
- **Kiểm tra:** `fpd_by_segment__unique_grain`, `fpd_by_segment__rate_valid`, `fpd_by_segment__reconciles_with_source` (mẫu số và tử số, đếm độc lập theo version nhỏ nhất), `fpd_by_segment__approved_reconciles`.

### M13. Ever 1+@MOBn (chỉ tiêu sớm)

- **Định nghĩa:** tỷ lệ hợp đồng từng có DPD (theo `SK_DPD_DEF`) lớn hơn 0 tính đến MOB n. Mặc định n = 6.
- **Câu hỏi trả lời:** một thay đổi chính sách duyệt có làm khách xấu đi không, đo được trong vài tháng thay vì phải chờ ca 30+ hiếm hoi?
- **Grain báo cáo:** phân khúc × MOB.
- **Nguồn:** `core.fct_loan_month` và `core.dim_loan`, tính trong `scripts/compute_findings.py` (truy vấn `EARLY_SQL`), kết quả ở `findings.json`, khóa `sample_size`. Chưa có mart.
- **Công thức:** tử số là hợp đồng có MOB đầu tiên với `dpd > 0` nằm trong khoảng 0 đến n; mẫu số giống hệt M08 (đã biết kết quả đến MOB n, loại `is_partial_history` và `never_open`).
- **Con số nền tại MOB 6:** vay tiêu dùng 3,074% [3,029; 3,119] (17.100 / 556.335); phân khúc vay tiêu dùng khách mới × lãi suất cao 4,641% [4,507; 4,779] (4.264 / 91.874).
- **Liên hệ với kết quả xấu về sau** (vay tiêu dùng, đã biết kết quả đến MOB 12): nhóm từng 1+ đến MOB 6 có ever 30+@MOB12 là 0,707% (119 / 16.828), nhóm không có 0,0066% (34 / 513.648), tỷ số 107 [73; 156]; 77,8% ca 30+@MOB12 đã từng 1+ trước MOB 6.
- **Edge case:** một phần liên quan là cơ học (ca đã 30+ trước MOB 6 cũng đã 1+): 67 trên 153 ca. Phần dự báo thật: 52 trên 86 ca lần đầu 30+ ở MOB 7 đến 12 (60,5%) đã từng 1+ trước MOB 6. Theo `SK_DPD` chỉ tiêu này bị khoản dư lẻ thổi phồng nặng, nên luôn tính theo `dpd`.

---

## Funnel

### M12. Approval rate và take-up rate

- **Định nghĩa:**
  - Approval rate: tỷ lệ hồ sơ được duyệt trên các hồ sơ đã có quyết định.
  - Take-up rate: tỷ lệ khách thực sự dùng khoản vay trên các hồ sơ được duyệt.
- **Câu hỏi trả lời:** kênh nào duyệt nhiều, chuyển đổi tốt và mang lại khoản vay lớn?
- **Grain báo cáo:** phân khúc (`channel_type` × `contract_type` × `client_type` × `yield_group`).
- **Nguồn:** `stg.previous_application`, lọc `is_last_appl_per_contract and is_last_appl_in_day`.
- **Công thức:**
  - `approval_rate = (Approved + Unused offer) / (Approved + Unused offer + Refused)`
  - `take_up_rate = Approved / (Approved + Unused offer)`
  - Số tiền: tổng và trung vị `credit_amount` chỉ tính trên hồ sơ `Approved` (khoản vay thực sự giải ngân).
- **Con số nền theo sản phẩm:** vay tiêu dùng 89,7%, thẻ 70,4%, vay tiền mặt 65,3%. Chuẩn hoá theo sản phẩm, tỷ lệ duyệt của các kênh lớn gần như bằng nhau (Credit and cash offices 1,00, Stone 1,01, Country-wide 1,00), nên so tỷ lệ duyệt giữa kênh cũng phải trong cùng sản phẩm.
- **Mart:** [`sql/mart/mart_funnel_by_channel.sql`](../sql/mart/mart_funnel_by_channel.sql) tạo bảng `mart.funnel_by_channel`. Mart này không phụ thuộc định nghĩa DPD.
- **SQL mẫu:**

  ```sql
  select
      channel_type,
      sum(n_decided)                                            as n_decided,
      sum(n_approved + n_unused_offer) / nullif(sum(n_decided), 0) as approval_rate,
      sum(n_approved) / nullif(sum(n_approved + n_unused_offer), 0) as take_up_rate,
      sum(credit_amount_approved_total)                         as credit_amount_approved_total
  from mart.funnel_by_channel
  group by channel_type
  order by approval_rate desc;
  ```

- **Edge case:**
  - `Canceled` (khách hủy trước khi có quyết định) không nằm trong mẫu số, báo cáo riêng ở cột `n_canceled`.
  - Giả định `Unused offer` là hồ sơ được duyệt nhưng khách không dùng. Take-up chỉ có nghĩa ở vay tiêu dùng: `Unused offer` có 25.924 hồ sơ ở vay tiêu dùng, 494 ở vay tiền mặt, 5 ở thẻ.
  - Kênh `Car dealer` (452 hồ sơ) và `Channel of corporate sales` (6.117 hồ sơ) quá nhỏ để báo cáo riêng, gom chung vào nhãn `Khác` trong mart này.
  - `credit_amount_approved_median` là trung vị theo từng ô phân khúc; không được lấy trung bình các ô này để suy ra trung vị toàn kênh, phải tính lại trực tiếp từ `stg.previous_application` nếu cần trung vị ở mức gộp lớn hơn.
- **Kiểm tra:** `funnel_by_channel__unique_grain`, `funnel_by_channel__rate_valid`, `funnel_by_channel__reconciles_with_source`.

---

## Mẫu cho chỉ tiêu mới

```markdown
### Mxx. Tên chỉ tiêu

- **Định nghĩa:**
- **Câu hỏi trả lời:**
- **Grain báo cáo:**
- **Nguồn:**
- **Công thức:**
- **Edge case:**
- **Kiểm tra:**
- **SQL:**
```

## Changelog

| Phiên bản | Ngày | Thay đổi |
|---|---|---|
| 0.1 | 2026-09-13 | Khởi tạo quy ước chung và M01 đến M12 |
| 0.2 | 2026-09-20 | Đổi cột DPD chính từ `SK_DPD_DEF` sang `SK_DPD` vì tử số theo `SK_DPD_DEF` quá mỏng. **Thay đổi này đã bị đảo ngược ở phiên bản 0.4.** Thêm cờ `dim_loan.is_partial_history` cho mẫu số vintage |
| 0.2 | 2026-09-20 | M08 vintage: chốt mẫu số (`max_mob >= n` hoặc đã đóng), loại `is_partial_history` và `never_open`, thêm cột `n_observed_full`. M09 roll rate: dòng không có tháng kế tiếp vào trạng thái `Missing`, loại tháng `-1` khỏi trạng thái xuất phát, thêm tỷ lệ theo exposure kèm cột đếm dòng thiếu `exposure_proxy`. M10 cure rate: lấy trực tiếp từ `mart.roll_rate` |
| 0.2 | 2026-09-20 | Thêm 4 mart: `mart.funnel_by_channel` (M12), `mart.fpd_by_segment` (M11), `mart.vintage` (M08), `mart.roll_rate` (M09, M10) |
| 0.3 | 2026-10-03 | Thêm mart thứ 5 `mart.portfolio_snapshot` (M02, M06) và 3 data test của nó. Ghi rõ hai nhóm loại khỏi mẫu số vintage giao nhau 2.085 hợp đồng. Điền tên Owner |
| 0.4 | 2026-10-04 | **Đổi định nghĩa quá hạn chính về `SK_DPD_DEF`.** Lý do: theo `SK_DPD`, phần lớn tháng 30+ là khoản dư lẻ sau kỳ trả cuối; ở các tháng POS đang mở thuộc B4 theo `SK_DPD`, 95,8% có `SK_DPD_DEF = 0`, 99,8% không còn kỳ nào phải trả, dư nợ trung vị 0. Chi tiết: [methodology mục 4](methodology.md#4-quyết-định-đã-đảo-ngược-định-nghĩa-quá-hạn). Cột gốc giữ tên, đổi nghĩa; thêm bộ cột độ nhạy hậu tố `_no_threshold`; bỏ `dpd_tolerant`, `is_30_plus_tolerant` và cặp cột vintage `*_tolerant`. Thêm bảng `mart.roll_rate_no_threshold` |
| 0.4 | 2026-10-04 | `core.dim_loan.end_state` thêm nhãn `closed_inferred` (89.414 hợp đồng); `unknown` còn 93.730. Sửa mô tả cũ của `unknown` ("dừng sớm 1 đến 3 tháng", sai). M08 mẫu số gồm `closed_inferred`: tại MOB 12 từ 744.208 thành 818.672 |
| 0.4 | 2026-10-04 | M11 FPD30: lấy đúng version nhỏ nhất của kỳ 1 (code cũ cộng qua mọi version). Bỏ `n_approved_no_installment`, thay bằng `n_approved_not_activated` và `n_approved_scheduled_no_installment`. Bỏ nhãn "chặn dưới" vì 77.884 trên 77.885 hồ sơ duyệt không có dòng kỳ 1 là chưa kích hoạt |
| 0.5 | 2026-10-04 | Sau lần soát thứ hai: thêm M15 (vintage theo đợt mở, cột `origination_cohort`, `origination_cohort_start` của `mart.vintage`) và test `vintage__cohort_matches_core`. Thêm cột độ nhạy thứ hai `n_ever_30_plus_due_only` (định nghĩa giữa). M14: tầng chuẩn hoá chính đổi sang sản phẩm × đợt mở. M10: cỡ mẫu thử nghiệm tính theo hợp đồng |
| 0.4 | 2026-10-04 | M06: thêm `n_loans_exposure_known`, `n_30_plus_exposure_known` để hai thẻ KPI tính cùng tập, và cột độ nhạy. Thêm M13 (ever 1+@MOBn, chỉ tiêu sớm) và M14 (SMR theo kênh). Quy ước chung: mọi tỷ lệ kèm khoảng tin cậy 95%, mọi so sánh kèm tỷ số và khoảng tin cậy |
