# Tầng mart

Tầng mart là lớp bảng tổng hợp ở cuối pipeline `stg` → `core` → `mart`. Mỗi mart trả lời đúng một câu hỏi kinh doanh và dùng đúng định nghĩa trong [metric dictionary](../../docs/metric_dictionary.md). Có 5 mart, mỗi mart là một file `.sql` trong thư mục này và tạo ra một bảng trong schema `mart`; riêng `mart_roll_rate.sql` tạo thêm bảng độ nhạy `mart.roll_rate_no_threshold` từ cùng một table macro `mart.roll_matrix`.

Viết tắt dùng trong tài liệu này:

- **Grain**: một dòng của bảng đại diện cho cái gì. Ví dụ "1 dòng = 1 hợp đồng trong 1 tháng".
- **DPD** (days past due): số ngày quá hạn. Định nghĩa chính là `SK_DPD_DEF` (DPD có ngưỡng trọng yếu: bỏ qua khoản nợ giá trị thấp). Cột hậu tố `_no_threshold` tính theo `SK_DPD` (không áp ngưỡng trọng yếu), chỉ dùng cho phân tích độ nhạy. **Bucket**: nhóm DPD, B0 = 0 ngày, B1 = 1 đến 30, B2 = 31 đến 60, B3 = 61 đến 90, B4 = trên 90 ngày. **30+** là DPD lớn hơn 30 ngày.
- **MOB** (month on book): số tháng kể từ tháng hợp đồng bắt đầu mở. Tháng mở là MOB 0.
- **FPD30** (first payment default 30): kỳ trả đầu tiên chưa trả đủ sau 30 ngày kể từ ngày đến hạn.
- **Roll rate**: tỷ lệ hợp đồng chuyển từ bucket này sang bucket khác sau một tháng. **Cure rate**: tỷ lệ hợp đồng đang quá hạn quay về B0 ở tháng sau.

## Tổng quan 5 mart (và 1 bảng độ nhạy)

| Bảng | File | Mã chỉ tiêu | Grain | Số dòng |
|---|---|---|---|---|
| `mart.funnel_by_channel` | `mart_funnel_by_channel.sql` | M12 | kênh × loại sản phẩm × loại khách × nhóm lãi suất | 223 |
| `mart.fpd_by_segment` | `mart_fpd_by_segment.sql` | M11 | kênh × loại sản phẩm × loại khách × nhóm lãi suất | 177 |
| `mart.vintage` | `mart_vintage.sql` | M08 | nguồn × loại sản phẩm × kênh × loại khách × nhóm lãi suất × nhóm kỳ hạn × đợt mở × MOB | 66.863 |
| `mart.roll_rate` | `mart_roll_rate.sql` | M09, M10 | nguồn × loại sản phẩm × kênh × bucket đi × bucket đến | 360 |
| `mart.roll_rate_no_threshold` | `mart_roll_rate.sql` | M09, M10 (độ nhạy) | như `mart.roll_rate`, bucket theo `SK_DPD` | 464 |
| `mart.portfolio_snapshot` | `mart_portfolio_snapshot.sql` | M02, M06 | loại sản phẩm × kênh × bucket, tại tháng gần nhất | 58 |

Số dòng là số đếm trên kho dữ liệu hiện tại (2026-10-04). `mart.roll_rate_no_threshold` không được xuất CSV cho Power BI. Thứ tự build nằm trong danh sách `MODELS` của `scripts/build.py`: cả 5 mart đều build sau các bảng `stg` và `core` mà chúng đọc.

## Quy ước chung của cả 5 mart

1. **Lưu số đếm, không lưu tỷ lệ.** Mỗi mart giữ tử số và mẫu số dạng số đếm (`n_loans`, `n_approved`, `n_ever_30_plus`, ...) rồi mới tính cột tỷ lệ. Khi gom nhóm lớn hơn, chỉ được cộng các cột `n_*` rồi chia lại. Lấy trung bình cột `*_rate` giữa các dòng là sai vì các dòng có mẫu số khác nhau.
2. **Nhãn phân khúc thống nhất.** Hai kênh quá nhỏ là `Car dealer` (452 hồ sơ) và `Channel of corporate sales` (6.117 hồ sơ) được gom thành nhãn `Khác` ở cả 5 mart. Nếu hai mart đặt tên kênh khác nhau thì ghép chúng trên dashboard sẽ khuyết dòng. Ngoài `Khác` còn hai nhãn nữa, và ba nhãn này có nghĩa khác nhau (mart funnel chỉ cần `Unknown` và `Khác` vì nó đọc thẳng bảng hồ sơ, không có hợp đồng nào thiếu hồ sơ):
   - `(không rõ)`: hợp đồng không khớp được hồ sơ trong `stg.previous_application`, mọi thuộc tính phân khúc đều không biết (48.794 hợp đồng).
   - `Unknown`: có hồ sơ nhưng chính cột đó là NULL (ví dụ `yield_group` NULL ở khoảng 30% hồ sơ).
   - `Khác`: hai kênh nhỏ nói ở trên.
3. **Không loại dòng âm thầm.** Dòng bị loại khỏi mẫu số phải được đếm và ghi ở comment đầu file SQL hoặc ở metric dictionary.
4. **Comment đầu mỗi file SQL ghi mã chỉ tiêu, câu hỏi kinh doanh và grain.**

## 1. `mart.funnel_by_channel` (M12)

- **Câu hỏi kinh doanh:** kênh nào duyệt nhiều, khách nhận khoản vay tốt và khoản vay lớn?
- **Grain:** 1 dòng / `channel_type` / `contract_type` / `client_type` / `yield_group`.
- **Bảng nguồn:** `stg.previous_application`, chỉ lấy hồ sơ có `is_last_appl_per_contract` và `is_last_appl_in_day` để bỏ hồ sơ nhập trùng.
- **Cột chính:** số hồ sơ theo từng trạng thái (`n_approved`, `n_unused_offer`, `n_refused`, `n_canceled`), `n_decided` (mẫu số của approval rate), `approval_rate`, `take_up_rate`, tổng và trung vị `credit_amount` của hồ sơ `Approved`.
- **Điểm cần biết:** hồ sơ `Canceled` (khách tự hủy trước khi có quyết định) không nằm trong mẫu số approval rate nhưng vẫn được đếm riêng ở `n_canceled`.
- **Test:** `funnel_by_channel__unique_grain`, `funnel_by_channel__rate_valid`, `funnel_by_channel__reconciles_with_source`.

## 2. `mart.fpd_by_segment` (M11)

- **Câu hỏi kinh doanh:** kênh, sản phẩm nào mang về khách có dấu hiệu rủi ro ngay từ kỳ trả đầu tiên?
- **Grain:** 1 dòng / `channel_type` / `contract_type` / `client_type` / `yield_group`.
- **Bảng nguồn:** `stg.installments_payments` (kỳ 1, `installment_number = 1`, đúng version nhỏ nhất khác 0 của hợp đồng, tức lịch trả gốc), left join `stg.previous_application` để lấy phân khúc. Hai cột `n_approved_*` lấy từ `stg.previous_application` (hồ sơ `Approved`, đã lọc trùng).
- **Cột chính:** `n_loans` (mẫu số), `n_fpd30` và `fpd30_rate`, biến thể theo quy tắc ngày `n_fpd30_late_rule` và `fpd30_late_rule_rate`, `n_approved_not_activated` (duyệt nhưng không có lịch trả, tức không giải ngân hoặc chưa kích hoạt), `n_approved_scheduled_no_installment` (duyệt, có lịch trả nhưng không có dòng kỳ 1).
- **Điểm cần biết:** hồ sơ duyệt không có dòng kỳ 1 (77.885) gần như toàn bộ là không kích hoạt (77.884 không có lịch trả), nên không thuộc mẫu số FPD và không phải hợp đồng xấu biến mất. Cột cũ `n_approved_no_installment` đã bỏ (2026-10-04), thay bằng hai cột trên.
- **Test:** `fpd_by_segment__unique_grain`, `fpd_by_segment__rate_valid`, `fpd_by_segment__reconciles_with_source` (mẫu số và tử số FPD30, đếm độc lập theo version nhỏ nhất), `fpd_by_segment__approved_reconciles`.

## 3. `mart.vintage` (M08)

- **Câu hỏi kinh doanh:** phân khúc nào xấu đi nhanh hơn khi so ở cùng tuổi hợp đồng?
- **Grain:** 1 dòng / `source` / `contract_type` / `channel_type` / `client_type` / `yield_group` / `tenor_group` / `origination_cohort` / `mob`, báo cáo MOB 0 đến 36. `origination_cohort` là đợt mở 12 tháng của `first_open_month` ('-96 đến -85' đến '-12 đến -1'), `origination_cohort_start` là tháng đầu đợt để sắp xếp.
- **Bảng nguồn:** `core.fct_loan_month` (tìm MOB đầu tiên hợp đồng quá hạn 30+) và `core.dim_loan` (thuộc tính phân khúc, `max_mob`, `end_state`, `is_partial_history`).
- **Cột chính:** `n_loans` (mẫu số), `n_observed_full` (số hợp đồng thật sự quan sát đủ đến MOB n), `n_closed_early` (kết thúc trước MOB n), `n_ever_30_plus` (tử số, theo `SK_DPD_DEF`), `ever_30_plus_rate`, và cặp cột độ nhạy `n_ever_30_plus_no_threshold`, `ever_30_plus_rate_no_threshold` tính theo `SK_DPD`, và độ nhạy thứ hai `n_ever_30_plus_due_only` (trả góp: `SK_DPD` trên 30 ở tháng còn kỳ phải trả; thẻ: `SK_DPD_DEF`). Cặp cột `*_tolerant` cũ đã bỏ (2026-10-04) vì nay trùng cột chính.
- **Mẫu số:** hợp đồng đã biết kết quả đến MOB n, tức `max_mob >= n` hoặc `end_state` là `closed` hoặc `closed_inferred` (hợp đồng dừng trước tháng `-1` mà hồ sơ có `DAYS_TERMINATION`, xem comment trong `core/dim_loan.sql`). Loại khỏi mẫu số 95.695 hợp đồng: `is_partial_history` (93.751) và `end_state = 'never_open'` (4.029), trong đó 2.085 hợp đồng thuộc cả hai nhóm. Còn 944.937 trên 1.040.632 hợp đồng.
- **Điểm cần biết:** hai mẫu số `n_loans` và `n_observed_full` phải được in cùng nhau. Tại MOB 24, mẫu số là 763.989 nhưng chỉ 70.635 hợp đồng quan sát đủ (9,2%), nên đoạn MOB cao của đường cong mỏng và bị kéo xuống bởi các hợp đồng kết thúc sớm.
- **Test:** `vintage__unique_grain`, `vintage__counts_consistent`, `vintage__mob0_matches_core`, `vintage__cohort_matches_core` (mẫu số MOB 0 theo từng đợt khớp `core.dim_loan`).

## 4. `mart.roll_rate` (M09 và M10)

- **Câu hỏi kinh doanh:** khách quá hạn chuyển giữa các bucket thế nào, bucket nào khó thu hồi nhất?
- **Grain:** 1 dòng / `source` / `contract_type` / `channel_type` / `from_state` / `to_state`, mỗi dòng là một ô của ma trận chuyển trạng thái từ tháng t sang tháng t + 1.
- **Bảng nguồn:** `core.fct_loan_month`, dùng `lead()` để lấy dòng tháng kế tiếp của cùng một hợp đồng, và `core.dim_loan` (phân khúc).
- **Cột chính:** `n_loans` (số hợp đồng của ô), `n_from` (tổng của cả hàng, tức mẫu số), `roll_rate`, `n_month_gap`, và các cột theo tiền `exposure_from`, `exposure_roll_rate`, `n_exposure_null`.
- **Trạng thái:** bucket đi là B0 đến B4 (chỉ tháng hợp đồng đang mở, loại tháng `-1` vì là cắt phải của cửa sổ dữ liệu). Trạng thái đến là B0 đến B4, `Closed` (`Completed`), `Other` và `Missing` (không có dòng cho đúng tháng t + 1, không được loại âm thầm).
- **Bảng độ nhạy `mart.roll_rate_no_threshold`:** cùng grain, cùng cột, bucket theo `SK_DPD`. Test `roll_rate__definitions_same_months` bảo đảm hai bảng đếm cùng một tập tháng xuất phát.
- **M10 (cure rate)** không có mart riêng. Nó là cột `to_state = 'B0 Current'` của chính bảng này, với bucket đi từ B1 trở lên. Làm mart riêng sẽ tạo ra hai nguồn số có thể lệch nhau.
- **Test:** `roll_rate__unique_grain`, `roll_rate__row_sums_to_one` (mỗi hàng của ma trận cộng lại bằng 1), `roll_rate__counts_consistent`, cả ba kiểm cả bảng chính lẫn bảng độ nhạy; `roll_rate__definitions_same_months`.

## 5. `mart.portfolio_snapshot` (M02 và M06)

- **Câu hỏi kinh doanh:** danh mục đang mở hiện có cơ cấu nhóm quá hạn thế nào, và bao nhiêu phần trăm đang 30+?
- **Grain:** 1 dòng / `contract_type` (sản phẩm) / `channel_type` (kênh) / `dpd_bucket`, chỉ tại tháng gần nhất `months_balance = -1` (tháng tương đối, không phải tháng lịch).
- **Bảng nguồn:** `core.fct_loan_month` (chỉ dòng `is_open` tại tháng `-1`) join `core.dim_loan` (phân khúc).
- **Cột chính:** `n_loans` và `exposure` (số hợp đồng và dư nợ ước lượng của ô), `n_30_plus` và `exposure_30_plus` (phần 30+ của ô, theo `SK_DPD_DEF`). Tỷ lệ 30+ (M06) tính bằng cách cộng `n_30_plus` và `n_loans` rồi chia lại. `n_loans_exposure_known` và `n_30_plus_exposure_known` đếm riêng hợp đồng có `exposure_proxy`: dùng cặp này khi đặt tỷ lệ theo hợp đồng cạnh tỷ lệ theo dư nợ, để hai thẻ KPI tính trên cùng một tập. `n_30_plus_no_threshold` và `exposure_30_plus_no_threshold` là độ nhạy theo `SK_DPD` và không khớp với `dpd_bucket` của dòng.
- **Điểm cần biết:** bảng này sinh ra để trang 1 của báo cáo Power BI bám đúng trang 1 của `dashboard/index.html`, vốn đọc thẳng `core.fct_loan_month`. Tổng `n_loans` toàn bảng là 144.421, bằng số hợp đồng đang mở tại tháng `-1`. Dư nợ (`exposure`) bỏ qua dòng có `exposure_proxy` NULL, nên không tương ứng 1-1 với số hợp đồng.
- **Test:** `portfolio_snapshot__unique_grain`, `portfolio_snapshot__counts_consistent`, `portfolio_snapshot__reconciles_with_core`.

## Quy ước test

Mỗi test là một file `.sql` trong `sql/tests/`, trả về **các dòng vi phạm**: 0 dòng là đạt. Dòng đầu file ghi mức độ: `-- severity: error` (fail thì pipeline dừng) hoặc `-- severity: warn` (chỉ cảnh báo). Tên test theo dạng `<bảng>__<điều được kiểm tra>`. Các loại kiểm tra đang dùng cho mart:

- **`unique_grain`**: grain không bị trùng dòng. Có ở cả 5 mart.
- **`counts_consistent`** hoặc **`rate_valid`**: tử số không lớn hơn mẫu số, tỷ lệ nằm trong khoảng 0 đến 1. Có ở cả 5 mart.
- **`reconciles_with_source`**, **`reconciles_with_core`**, **`mob0_matches_core`**: đếm lại cùng một thứ bằng một đường độc lập (từ `core` hoặc `stg`) rồi so với mart. Có ở funnel, fpd, vintage và snapshot.
- **`roll_rate__row_sums_to_one`**: riêng roll rate, mỗi hàng của ma trận phải cộng lại bằng 1.

Chạy lại toàn bộ pipeline và test: `.venv\Scripts\python.exe scripts\build.py`. Chỉ chạy test: thêm `--tests-only`.

## Thêm một mart mới

1. Viết file `mart_<tên>.sql` với comment đầu file ghi mã chỉ tiêu, câu hỏi kinh doanh và grain.
2. Thêm file vào danh sách `MODELS` trong `scripts/build.py`, đặt sau các model mà nó đọc.
3. Viết ít nhất một test trong `sql/tests/` theo quy ước ở trên.
4. Ghi trạng thái chỉ tiêu trong [metric dictionary](../../docs/metric_dictionary.md) và thêm một dòng vào Changelog của file đó.
