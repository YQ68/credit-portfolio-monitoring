# Tầng mart: phần việc của bạn

Mỗi mart trả lời một câu hỏi kinh doanh và dùng đúng định nghĩa trong [metric dictionary](../../docs/metric_dictionary.md). Làm theo thứ tự dưới đây. Sau mỗi mart:

1. Thêm file vào danh sách `MODELS` trong `scripts/build.py`.
2. Viết ít nhất một test trong `sql/tests/`, ví dụ: tỷ lệ nằm trong khoảng 0 đến 1, mỗi hàng của ma trận roll rate cộng lại bằng 1.
3. Điền phần SQL và đổi trạng thái metric trong dictionary thành "Có trong mart".

## 1. `mart_funnel_by_channel`

- **Câu hỏi:** kênh nào có approval rate và take-up rate cao?
- **Nguồn:** `stg.previous_application`, định nghĩa M12.
- **Gợi ý:** đếm theo `channel_type` và `application_status`, rồi pivot thành cột. Nhớ lọc hồ sơ trùng.

## 2. `mart_fpd_by_segment`

- **Câu hỏi:** kênh, sản phẩm nào có rủi ro sớm cao?
- **Nguồn:** `stg.installments_payments` join `core.dim_loan`, định nghĩa M11.
- **Gợi ý:** gom tổng tiền trả trong 30 ngày của kỳ 1 cho từng hợp đồng trước, sau đó mới so với số tiền phải trả.
- **Kết hợp với mart 1:** biểu đồ approval rate và FPD30 theo kênh là insight đầu tiên nên có.

## 3. `mart_vintage`

- **Câu hỏi:** cohort nào xấu đi nhanh hơn khi so cùng MOB?
- **Nguồn:** `core.fct_loan_month` join `core.dim_loan`, định nghĩa M08.
- **Gợi ý:**
  - `max(dpd) over (partition by sk_id_prev order by mob)` cho DPD cao nhất tính đến từng MOB.
  - Xử lý mẫu số bằng `end_state` và `max_mob`, loại `is_left_truncated`.
- **Đầu ra:** 1 dòng / cohort / MOB, gồm tử số, mẫu số, tỷ lệ.

## 4. `mart_roll_rate`

- **Câu hỏi:** khách quá hạn chuyển bucket thế nào; bucket nào khó cure nhất?
- **Nguồn:** `core.fct_loan_month`, định nghĩa M09 và M10.
- **Gợi ý:**
  - `lead(dpd_bucket)` và `lead(months_balance)` theo từng hợp đồng, rồi kiểm tra tháng kế tiếp đúng bằng `months_balance + 1`.
  - Thêm trạng thái `Closed` và `Missing`.
- **Đầu ra:** 1 dòng / bucket đầu / bucket sau, gồm số lượng và tỷ lệ.

## Tự kiểm tra trước khi làm dashboard

- Tổng tử số, mẫu số của mart có khớp với query đếm trực tiếp từ `core.fct_loan_month` không?
- Tỷ lệ có hợp lý không? Nếu bất thường, nguyên nhân nằm ở dữ liệu hay ở định nghĩa?
- Mỗi con số trên dashboard có truy ngược được về một mã metric trong dictionary không?
