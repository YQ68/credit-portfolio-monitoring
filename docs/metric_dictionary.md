# Metric Dictionary

Nguồn chuẩn cho định nghĩa và công thức của mọi chỉ tiêu trong project. Dashboard, memo và SQL đều phải dùng đúng các định nghĩa này. Mọi thay đổi định nghĩa ghi vào [Changelog](#changelog).

**Owner:** Lien | **Phiên bản:** 0.3 | **Cập nhật:** 2026-10-03

## Quy ước chung

| Quy ước | Giá trị |
|---|---|
| Cột DPD dùng cho mọi chỉ tiêu | `SK_DPD` (DPD không dung sai), nằm ở cột `dpd`. `SK_DPD_DEF` giữ ở cột `dpd_tolerant` làm chỉ tiêu phụ. Đổi từ phiên bản 0.2, lý do trong [data_notes mục 7](data_notes.md#7-dpd) |
| Bucket | B0 = 0, B1 = 1-30, B2 = 31-60, B3 = 61-90, B4 = trên 90 ngày |
| "30+" | DPD **lớn hơn 30**, tức từ B2 trở lên. Tương tự "90+" là DPD lớn hơn 90 |
| Hợp đồng đang mở (`is_open`) | trạng thái `Active`, `Demand` hoặc `Amortized debt` (macro `core.is_open_status`) |
| MOB 0 | tháng đầu tiên hợp đồng ở trạng thái mở |
| Thời gian | `months_balance` là tháng tương đối so với ngày nộp hồ sơ hiện tại của từng khách, `-1` là tháng gần nhất. Không quy đổi được sang tháng lịch |
| Trình bày tỷ lệ | luôn kèm tử số và mẫu số; mặc định tính theo số hợp đồng, tính theo exposure là chỉ tiêu phụ |

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

---

## Nền tảng

### M01. DPD

- **Định nghĩa:** số ngày quá hạn của hợp đồng trong tháng quan sát.
- **Câu hỏi trả lời:** hợp đồng đang trễ hạn bao lâu?
- **Grain:** hợp đồng × tháng.
- **Nguồn:** `core.fct_loan_month.dpd`, lấy từ `SK_DPD` của `POS_CASH_balance` và `credit_card_balance`. Cột `dpd_tolerant` lấy từ `SK_DPD_DEF`.
- **Công thức:** lấy trực tiếp. Nếu một hợp đồng có nhiều dòng trong cùng tháng, lấy giá trị lớn nhất.
- **Edge case:**
  - Mô tả gốc ghi "DPD during the month", chưa rõ là DPD cuối tháng hay cao nhất trong tháng ([data_notes mục 7](data_notes.md#7-dpd)).
  - Hợp đồng có trong cả hai nguồn: lấy dữ liệu thẻ.
- **Kiểm tra:** `fct_loan_month__dpd_valid`, `fct_loan_month__dpd_tolerant_valid`, `sources__duplicate_months`.

### M02. DPD bucket

- **Định nghĩa:** nhóm DPD thành các khoảng để theo dõi và tính chuyển trạng thái.
- **Grain:** hợp đồng × tháng.
- **Nguồn:** `core.fct_loan_month.dpd_bucket` (nhãn), `dpd_bucket_order` (0 đến 4, dùng để sắp xếp và so sánh). Cơ cấu bucket của danh mục đang mở tại tháng `-1` có sẵn ở `mart.portfolio_snapshot` ([M06](#m06-tỷ-lệ-30-coincident)).
- **Công thức:**

  | Bucket | DPD |
  |---|---|
  | B0 Current | 0 |
  | B1 1-30 | 1 đến 30 |
  | B2 31-60 | 31 đến 60 |
  | B3 61-90 | 61 đến 90 |
  | B4 90+ | trên 90 |

- **Edge case:** ranh giới tính cả hai đầu: DPD = 30 thuộc B1, DPD = 31 thuộc B2.
- **Kiểm tra:** `fct_loan_month__dpd_valid`, `portfolio_snapshot__counts_consistent`.

### M03. Nhóm nợ (proxy)

- **Định nghĩa:** nhóm nợ theo số ngày quá hạn, mô phỏng cách phân loại nợ của TCTD Việt Nam.
- **Grain:** hợp đồng × tháng.
- **Nguồn:** `core.fct_loan_month.debt_group_vn`.
- **Công thức:**

  | Nhóm | DPD |
  |---|---|
  | 1 | dưới 10 |
  | 2 | 10 đến 90 |
  | 3 | 91 đến 180 |
  | 4 | 181 đến 360 |
  | 5 | trên 360 |

  Nợ xấu = nhóm 3 đến 5.
- **Edge case:** chỉ là proxy theo DPD. Phân loại chính thức (Thông tư 31/2024/TT-NHNN) còn xét cơ cấu nợ, yếu tố định tính và điều chỉnh theo thông tin CIC. Trên dashboard luôn ghi rõ "proxy".

### M04. MOB

- **Định nghĩa:** số tháng kể từ tháng hợp đồng bắt đầu mở (month on book).
- **Grain:** hợp đồng × tháng.
- **Nguồn:** `core.fct_loan_month.mob`, `core.dim_loan.first_open_month`.
- **Công thức:** `mob = months_balance - first_open_month`. Tháng mở có MOB = 0.
- **Edge case:**
  - Hợp đồng chưa từng mở (`end_state = 'never_open'`) không có trong `fct_loan_month`.
  - Tháng bị thiếu vẫn làm MOB tăng (MOB tính theo lịch, không theo số dòng).
  - Hợp đồng mở trước cửa sổ dữ liệu (`is_left_truncated`) có MOB thấp hơn thực tế.
- **Kiểm tra:** `fct_loan_month__mob_non_negative`, `fct_loan_month__month_gaps`.

### M05. Exposure proxy

- **Định nghĩa:** ước lượng số tiền còn phải thu của hợp đồng trong tháng.
- **Grain:** hợp đồng × tháng.
- **Nguồn:** `core.fct_loan_month.exposure_proxy`.
- **Công thức:**
  - Khoản trả góp: `installments_remaining × annuity_amount` (gồm cả lãi, không phải dư nợ gốc).
  - Thẻ tín dụng: `balance_amount`, số âm tính là 0.
- **Edge case:** `annuity_amount` NULL thì exposure NULL. Chỉ cộng exposure trên các tháng `is_open`. Chỉ dùng để so sánh tương đối, không đối chiếu với số liệu kế toán.

---

## Chất lượng danh mục

### M06. Tỷ lệ 30+ coincident

- **Định nghĩa:** trong một kỳ quan sát, tỷ lệ hợp đồng đang mở có DPD trên 30.
- **Câu hỏi trả lời:** hiện tại bao nhiêu phần danh mục đang trễ hạn nghiêm trọng?
- **Grain báo cáo:** kỳ quan sát × phân khúc.
- **Nguồn:** `core.fct_loan_month`.
- **Mart:** [`sql/mart/mart_portfolio_snapshot.sql`](../sql/mart/mart_portfolio_snapshot.sql) tạo bảng `mart.portfolio_snapshot`, grain sản phẩm × kênh × bucket, chỉ tại tháng gần nhất `months_balance = -1`. Cột `n_loans`, `n_30_plus`, `exposure`, `exposure_30_plus` là số đếm và số tiền để cộng rồi chia lại. Kỳ khác tháng `-1` vẫn lấy từ `core.fct_loan_month` bằng SQL mẫu bên dưới.
- **Công thức:**
  - Theo số lượng: `count(is_open and is_30_plus) / count(is_open)`
  - Theo exposure: `sum(exposure_proxy where is_open and is_30_plus) / sum(exposure_proxy where is_open)`
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
  - Hợp đồng có `exposure_proxy` NULL bị bỏ qua khi cộng exposure. Báo cáo số lượng nếu đáng kể.
  - Hiệu ứng mẫu số: danh mục tăng nhanh làm tỷ lệ giảm dù chất lượng không đổi. Đọc cùng M07 và M08.
  - Với dữ liệu này, "kỳ quan sát" là tháng tương đối, không phải tháng lịch.
- **Kiểm tra:** `portfolio_snapshot__unique_grain`, `portfolio_snapshot__counts_consistent`, `portfolio_snapshot__reconciles_with_core`.

### M07. Tỷ lệ 30+ lagged

- **Định nghĩa:** số hợp đồng 30+ tại kỳ t chia cho số hợp đồng đang mở tại kỳ t - k.
- **Câu hỏi trả lời:** tỷ lệ nợ trễ hạn còn đẹp không khi loại bỏ tác động của hợp đồng mới giải ngân?
- **Công thức:** `count(is_30_plus tại t) / count(is_open tại t - k)`, mặc định k = 3.
- **Edge case:** chọn k gần với số tháng trung bình để một hợp đồng mới đi đến 30+. Ghi rõ k trên mọi biểu đồ.

### M08. Vintage ever 30+@MOBn

- **Định nghĩa:** trong một cohort hợp đồng, tỷ lệ hợp đồng **từng** có DPD trên 30 tính đến MOB n.
- **Câu hỏi trả lời:** cohort nào xấu đi nhanh hơn khi so cùng tuổi hợp đồng?
- **Cohort:** với dữ liệu này, nhóm theo thuộc tính trong `core.dim_loan` (`source`, `contract_type`, `channel_type`, `client_type`, `yield_group`, nhóm kỳ hạn). Với dữ liệu có ngày thật, cohort là tháng giải ngân.
- **Grain báo cáo:** cohort × MOB, báo cáo MOB 0 đến 36.
- **Nguồn:** `mart.vintage` (file `sql/mart/mart_vintage.sql`), dựng từ `core.fct_loan_month` và `core.dim_loan`.
- **Công thức:**
  - Tử số (`n_ever_30_plus`): hợp đồng có `max(dpd)` trên 30 trong khoảng MOB 0 đến n.
  - Mẫu số (`n_loans`): hợp đồng đã biết kết quả đến MOB n, tức `max_mob >= n` hoặc `end_state = 'closed'`.
  - `ever_30_plus_rate = n_ever_30_plus / n_loans`.
- **Loại khỏi mẫu số:** 95.695 hợp đồng trên 1.040.632, mẫu số gốc còn 944.937 hợp đồng.

  | Lý do loại | Số hợp đồng |
  |---|---|
  | `is_partial_history` (cắt trái theo cửa sổ dữ liệu, hoặc đã trả kỳ ngay tại tháng mở đầu tiên nên MOB thấp hơn thực tế) | 93.751 |
  | `end_state = 'never_open'` (chưa bao giờ ở trạng thái mở nên không có MOB 0) | 4.029 |

  Hai nhóm giao nhau 2.085 hợp đồng (vừa `never_open` vừa `is_partial_history`), nên tổng loại là 95.695 chứ không phải 93.751 + 4.029.

  Không lọc theo nhãn `end_state` cho phần còn lại. Nhãn `unknown` (183.144 hợp đồng) không phải lỗi dữ liệu mà chỉ là lịch sử dừng sớm ở tháng `-2` hoặc `-3`, tức cũng là cắt phải giống `censored`.
- **Hai mẫu số phải in cùng nhau:**
  - `n_loans`: mẫu số của chỉ tiêu, gồm cả hợp đồng tất toán trước MOB n.
  - `n_observed_full`: số hợp đồng thật sự còn quan sát được đến MOB n (`max_mob >= n`), tách khỏi `n_closed_early`.

  | MOB | `n_loans` | `n_observed_full` | `n_ever_30_plus` | tỷ lệ |
  |---|---|---|---|---|
  | 3 | 922.282 | 892.526 | 354 | 0,038% |
  | 6 | 868.559 | 731.065 | 1.268 | 0,146% |
  | 12 | 744.208 | 308.901 | 4.906 | 0,659% |
  | 24 | 679.223 | 70.635 | 5.963 | 0,878% |

- **Edge case:**
  - Hợp đồng tất toán trước MOB n mà chưa từng 30+ được tính là tốt.
  - Tại MOB 24, chỉ 70.635 trên 679.223 hợp đồng của mẫu số còn quan sát đủ (10,4%). Phần lớn mẫu số là hợp đồng đã tất toán sớm, nhóm này gần như không bao giờ 30+, nên đường cong ở MOB cao bị kéo xuống. Không diễn giải đoạn MOB cao nếu không in kèm `n_observed_full`.
  - Không diễn giải ô có `n_loans` dưới 1.000 hợp đồng: tử số theo `dpd` ở nhiều phân khúc chỉ còn một chữ số.
  - 48.794 hợp đồng không khớp `stg.previous_application` mang nhãn `'(không rõ)'` ở mọi cột phân khúc, không loại âm thầm. Nhóm này có tỷ lệ cao bất thường (6,72% tại MOB 12) vì thiếu hồ sơ thường đi kèm dữ liệu tháng bất thường, không nên so trực tiếp với các phân khúc khác.
  - Hai kênh quá nhỏ (`Car dealer` 452 hồ sơ, `Channel of corporate sales` 6.117) gom thành nhóm `Khác`.
  - `yield_group` null ở khoảng 30% hồ sơ, giữ thành nhóm riêng nhãn `Unknown`, không gộp vào nhóm khác.
  - Cột `n_ever_30_plus_tolerant` và `ever_30_plus_rate_tolerant` tính theo `dpd_tolerant` (`SK_DPD_DEF`) chỉ để đối chiếu, không phải chỉ tiêu chính.
  - Biến thể "point 30+@MOBn" (đang 30+ đúng tại MOB n) cho kết quả khác. Chỉ dùng một biến thể trong cùng biểu đồ.
- **Kiểm tra:** `vintage__unique_grain`, `vintage__counts_consistent`, `vintage__mob0_matches_core`.
- **SQL:** `sql/mart/mart_vintage.sql`. Đường cong toàn danh mục:

  ```sql
  select mob,
         sum(n_loans)          as mau_so,
         sum(n_observed_full)  as quan_sat_du,
         sum(n_ever_30_plus)   as tu_so,
         sum(n_ever_30_plus) * 1.0 / sum(n_loans) as ever_30_plus_rate
  from mart.vintage
  group by mob
  order by mob;
  ```

  Cắt theo một phân khúc: thêm cột đó vào `select` và `group by`. Luôn cộng tử số và mẫu số rồi chia lại, không lấy trung bình cột tỷ lệ.

### M09. Roll rate

- **Định nghĩa:** tỷ lệ hợp đồng chuyển từ trạng thái i ở tháng t sang trạng thái j ở tháng t + 1.
- **Câu hỏi trả lời:** khách quá hạn di chuyển giữa các bucket thế nào; bao nhiêu phần trăm tiếp tục xấu đi?
- **Grain báo cáo:** `source` × `contract_type` × `channel_type` × trạng thái đi × trạng thái đến.
- **Nguồn:** `mart.roll_rate` (file `sql/mart/mart_roll_rate.sql`), dựng từ `core.fct_loan_month` và `core.dim_loan`.
- **Trạng thái đi:** B0 đến B4, chỉ lấy các tháng hợp đồng đang mở.
- **Trạng thái đến:** B0 đến B4 (còn mở), `Closed` (`contract_status = 'Completed'`), `Other` (có dòng tháng sau nhưng không mở và không `Completed`), `Missing` (không có dòng cho đúng tháng t + 1).
- **Công thức:** `roll_rate(i, j) = count(i tại t và j tại t + 1) / count(i tại t)`. Mỗi hàng của ma trận cộng lại bằng 100%, có test bắt buộc kiểm tra điều này.
- **Chỉ tiêu dẫn xuất:** forward roll rate = tỷ lệ chuyển sang bucket xấu hơn liền kề (ví dụ B1 sang B2). Cure rate là [M10](#m10-cure-rate).
- **Con số nền (toàn danh mục):** 12.714.200 dòng xuất phát.

  | Trạng thái đi | Số dòng | sang B0 | sang B1 | sang B2 | sang B3 | sang B4 | Closed | Other | Missing |
  |---|---|---|---|---|---|---|---|---|---|
  | B0 Current | 12.278.451 | 91,646% | 1,273% | 0,002% | 0,000% | 0,002% | 5,631% | 0,001% | 1,446% |
  | B1 1-30 | 259.546 | 50,057% | 38,525% | 4,302% | 0,049% | 0,000% | 5,601% | 0,001% | 1,464% |
  | B2 31-60 | 12.315 | 17,263% | 10,361% | 6,179% | 56,370% | 1,941% | 6,423% | 0,008% | 1,454% |
  | B3 61-90 | 7.172 | 7,041% | 1,799% | 0,753% | 0,823% | 85,374% | 3,528% | 0,028% | 0,655% |
  | B4 90+ | 156.716 | 1,960% | 0,025% | 0,006% | 0,008% | 95,635% | 1,515% | 0,004% | 0,846% |

- **Edge case:**
  - Chỉ dùng cặp tháng cách nhau **đúng 1 tháng**. Theo profile, 12.693.134 trên 13.730.112 dòng (92,45%) có tháng kế tiếp hợp lệ.
  - **Phân biệt cắt phải và mất dữ liệu.** Tháng `t = -1` bị loại khỏi trạng thái xuất phát: dữ liệu kết thúc ở `-1` nên về nguyên tắc không thể quan sát tháng sau, đó là cắt phải của cửa sổ dữ liệu. Ngược lại, tháng `t <= -2` lẽ ra phải có tháng sau mà không có thì là mất dữ liệu thật, phải vào trạng thái `Missing` và kéo tỷ lệ xuống, không được loại âm thầm.
  - `Missing` toàn danh mục: 182.847 dòng (1,44%), trong đó chỉ 26 dòng do hở tháng (`n_month_gap`), còn lại là lịch sử hợp đồng dừng hẳn ở tháng `t`. Toàn bảng có 375 cặp hở tháng nhưng phần lớn không xuất phát từ tháng đang mở nên không vào ma trận.
  - `Completed` coi là trạng thái hấp thụ: chỉ 18 hợp đồng trên 1.040.632 (0,0017%) quay lại trạng thái mở sau `Completed`, chấp nhận sai lệch này.
  - **Tỷ lệ theo exposure:** cột `exposure_from`, `exposure_roll_rate` tính trên dư nợ ước lượng tháng t (M05). 286.803 dòng xuất phát có `exposure_proxy` null (2,26% số dòng của ma trận, tương ứng 3,41% dòng POS trên toàn bảng), các dòng này bị bỏ qua khi cộng tiền và đếm riêng ở cột `n_exposure_null`, **không được coi như bằng 0**. Vì vậy mẫu số tiền và mẫu số hợp đồng không tương ứng 1-1.
  - Hàng B2 và B3 chỉ có 12.315 và 7.172 quan sát trên toàn danh mục. Khi cắt theo phân khúc, nhiều ô rơi xuống dưới 1.000 quan sát, không diễn giải.
  - Hợp đồng không khớp `stg.previous_application` mang nhãn `'(không rõ)'` ở cột phân khúc.
- **Kiểm tra:** `roll_rate__unique_grain`, `roll_rate__row_sums_to_one`, `roll_rate__counts_consistent`.
- **SQL:** `sql/mart/mart_roll_rate.sql`. Ma trận toàn danh mục theo số hợp đồng:

  ```sql
  select from_state, to_state,
         sum(n_loans) as n_loans,
         sum(n_loans) * 1.0 / sum(sum(n_loans)) over (partition by from_state) as roll_rate
  from mart.roll_rate
  group by from_state, to_state
  order by from_state, to_state;
  ```

  Theo exposure: thay `n_loans` bằng `exposure_from`, và luôn in kèm `sum(n_exposure_null)`.

---

## Collections

### M10. Cure rate

- **Định nghĩa:** tỷ lệ hợp đồng đang ở bucket B1 trở lên tại tháng t trở về B0 tại tháng t + 1.
- **Câu hỏi trả lời:** bucket nào khó thu hồi nhất và cần ưu tiên nguồn lực?
- **Grain báo cáo:** bucket xuất phát × phân khúc.
- **Nguồn:** không có mart riêng. Lấy trực tiếp từ `mart.roll_rate` ([M09](#m09-roll-rate)), vì cure rate chỉ là một cột của ma trận đó. Làm mart riêng sẽ tạo ra hai nguồn số có thể lệch nhau.
- **Công thức:** `count(bucket >= B1 tại t và B0 tại t + 1) / count(bucket >= B1 tại t)`, tính riêng cho từng bucket xuất phát.
- **Con số nền (toàn danh mục):**

  | Bucket xuất phát | Số dòng | Về B0 | Cure rate | Sang `Closed` |
  |---|---|---|---|---|
  | B1 1-30 | 259.546 | 129.922 | 50,057% | 14.538 (5,601%) |
  | B2 31-60 | 12.315 | 2.126 | 17,263% | 791 (6,423%) |
  | B3 61-90 | 7.172 | 505 | 7,041% | 253 (3,528%) |
  | B4 90+ | 156.716 | 3.072 | 1,960% | 2.374 (1,515%) |
  | Tổng B1 trở lên | 435.749 | 135.625 | 31,125% | 17.956 (4,121%) |

- **Edge case:**
  - Hợp đồng chuyển sang `Closed` từ bucket quá hạn được báo cáo riêng (cột cuối bảng trên), không gộp vào cure. Với dữ liệu này `Closed` nghĩa là `contract_status = 'Completed'`, không phân biệt được tất toán do khách trả hết hay do xóa nợ.
  - Mẫu số và tử số kế thừa mọi quy tắc của M09: chỉ cặp tháng cách nhau đúng 1 tháng, loại tháng `-1` khỏi trạng thái xuất phát, dòng không có tháng sau vào `Missing` (nằm trong mẫu số, không nằm trong tử số).
  - B2 và B3 rất mỏng (12.315 và 7.172 dòng toàn danh mục). Khi cắt theo phân khúc gần như không đủ quan sát, cân nhắc gộp thành một hàng `31-90`.
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
- **Câu hỏi trả lời:** kênh, sản phẩm nào mang về khách có dấu hiệu rủi ro ngay từ kỳ đầu (bao gồm fraud)?
- **Grain báo cáo:** phân khúc (`channel_type` × `contract_type` × `client_type` × `yield_group`).
- **Nguồn:** `stg.installments_payments` (`installment_number = 1`), left join `stg.previous_application` để lấy phân khúc.
- **Công thức:**
  - Kỳ 1: `installment_number = 1`, bỏ `installment_version = 0` (thẻ tín dụng), lấy version nhỏ nhất còn lại.
  - Tử số (`n_fpd30`): hợp đồng có tổng `payment_amount` với `days_late <= 30` nhỏ hơn `installment_amount × (1 - 5%)` (dung sai 5%).
  - Biến thể theo quy tắc ngày (`n_fpd30_late_rule`, `fpd30_late_rule_rate`): kỳ 1 có `days_late > 30` (bất kể đã trả đủ tiền hay chưa), để so sánh với quy tắc theo số tiền.
  - Mẫu số (`n_loans`): hợp đồng có kỳ 1 đến hạn trước thời điểm quan sát ít nhất 30 ngày (`days_due <= -30`) và `installment_amount > 0`.
- **Mart:** [`sql/mart/mart_fpd_by_segment.sql`](../sql/mart/mart_fpd_by_segment.sql) tạo bảng `mart.fpd_by_segment`.
- **SQL mẫu:**

  ```sql
  select
      channel_type,
      sum(n_loans)                                  as n_loans,
      sum(n_fpd30)                                  as n_fpd30,
      sum(n_fpd30) / nullif(sum(n_loans), 0)        as fpd30_rate,
      sum(n_fpd30_late_rule) / nullif(sum(n_loans), 0) as fpd30_late_rule_rate,
      sum(n_approved_no_installment)                as n_approved_no_installment
  from mart.fpd_by_segment
  group by channel_type
  order by fpd30_rate desc;
  ```

- **Edge case:**
  - Một kỳ có thể trả thành nhiều lần: cộng các lần trả trước khi so sánh.
  - Kỳ bị bỏ lỡ có `days_paid` và `payment_amount` NULL, không đáng kể (2.905 dòng, 0,02%).
  - Kỳ 1 có nhiều `installment_version`: bỏ version 0 (thẻ tín dụng), lấy version nhỏ nhất còn lại (lịch trả gốc).
  - Dung sai 5% (thiếu dưới 5% số tiền phải trả không tính là vỡ nợ kỳ đầu).
  - Hợp đồng không khớp được `previous_application` nhận nhãn phân khúc `(không rõ)` ở mọi cột phân khúc, không loại âm thầm.
  - **GIỚI HẠN QUAN TRỌNG (chặn dưới, không phải FPD30 thật):** `stg.installments_payments` gần như chỉ ghi các kỳ ĐÃ TRẢ. Hợp đồng bỏ hẳn kỳ 1 (không trả đồng nào) thì không có dòng nào trong bảng, nên biến mất khỏi mẫu số thay vì được tính là vỡ nợ. Trên dữ liệu thật, `fpd30_rate` toàn danh mục chỉ đo được 0,011% (99 / 895.744 hợp đồng), thấp bất thường so với cảm quan rủi ro tín dụng tiêu dùng. Cột `n_approved_no_installment` đo quy mô vùng mù này: 77.885 hồ sơ `Approved` (khoảng 7,5%) không có bất kỳ dòng kỳ 1 nào được ghi nhận, nên không tham gia mẫu số ở cả tử số lẫn mẫu số của FPD30. Mọi biểu đồ hoặc nhận định dùng `fpd30_rate` phải ghi rõ đây là chặn dưới và nêu kèm `n_approved_no_installment`.
- **Kiểm tra:** `fpd_by_segment__unique_grain`, `fpd_by_segment__rate_valid`, `fpd_by_segment__reconciles_with_source`.

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
- **Mart:** [`sql/mart/mart_funnel_by_channel.sql`](../sql/mart/mart_funnel_by_channel.sql) tạo bảng `mart.funnel_by_channel`.
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
  - Giả định `Unused offer` là hồ sơ được duyệt nhưng khách không dùng. Xác nhận trong file mô tả cột.
  - Kênh `Car dealer` (452 hồ sơ) và `Channel of corporate sales` (6.117 hồ sơ) quá nhỏ để báo cáo riêng, gom chung vào nhãn `Khác` trong mart này.
  - `credit_amount_approved_median` là trung vị theo từng ô phân khúc (`channel_type` × `contract_type` × `client_type` × `yield_group`); không được lấy trung bình các ô này để suy ra trung vị toàn kênh, phải tính lại trực tiếp từ `stg.previous_application` nếu cần trung vị ở mức gộp lớn hơn.
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
| 0.2 | 2026-09-20 | Đổi cột DPD chính từ `SK_DPD_DEF` sang `SK_DPD`. Lý do: theo cột có dung sai, tỷ lệ từng quá hạn trên 30 ngày chỉ 0,053% (395 trên 744.208 hợp đồng tại MOB 12) và tử số khi cắt theo phân khúc chỉ còn vài chục hợp đồng, không phân tích được. `SK_DPD_DEF` chuyển thành chỉ tiêu phụ ở cột `dpd_tolerant` và cờ `is_30_plus_tolerant`. Thêm cờ `dim_loan.is_partial_history` cho mẫu số vintage |
| 0.2 | 2026-09-20 | M08 vintage: chốt mẫu số (`max_mob >= n` hoặc `end_state = 'closed'`), loại `is_partial_history` và `never_open`, thêm cột `n_observed_full` tách hợp đồng quan sát đủ khỏi hợp đồng tất toán sớm. M09 roll rate: dòng không có tháng kế tiếp vào trạng thái `Missing`, loại tháng `-1` khỏi trạng thái xuất phát vì là cắt phải, thêm tỷ lệ theo exposure kèm cột đếm dòng thiếu `exposure_proxy`. M10 cure rate: lấy trực tiếp từ `mart.roll_rate`, không làm mart riêng |
| 0.2 | 2026-09-20 | Thêm 4 mart mới, mỗi mart tương ứng một chỉ tiêu trong bảng danh sách chỉ tiêu ở trên: `mart.funnel_by_channel` (M12, approval rate và take-up rate), `mart.fpd_by_segment` (M11, FPD30), `mart.vintage` (M08, vintage ever 30+@MOBn), `mart.roll_rate` (M09 roll rate, M10 cure rate). Cả 4 mart đã build sạch trên dữ liệu thật, có data test và được dùng trực tiếp trong dashboard (`scripts/build_dashboard.py`) và memo (`docs/insight_memo.md`) |
| 0.3 | 2026-10-03 | Thêm mart thứ 5 `mart.portfolio_snapshot` (M02, M06): cơ cấu bucket quá hạn của danh mục đang mở tại tháng `-1`, theo sản phẩm × kênh × bucket. Mart được đưa vào danh sách `MODELS` của `scripts/build.py` và có 3 data test (`portfolio_snapshot__unique_grain`, `portfolio_snapshot__counts_consistent`, `portfolio_snapshot__reconciles_with_core`). M06 đổi trạng thái từ "Chưa có mart" thành "Có trong `mart.portfolio_snapshot`"; M11, M12 ghi rõ tên bảng mart. Đính chính số liệu của bản 0.2: tỷ lệ ever 30+ tại MOB 12 theo `SK_DPD_DEF` là 0,053% (395 trên 744.208), không phải 0,055% (428 trên 782.119, số đo trước khi loại `is_partial_history`). Ghi rõ hai nhóm loại khỏi mẫu số vintage giao nhau 2.085 hợp đồng. Điền tên Owner |
