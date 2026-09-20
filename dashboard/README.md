# Dashboard giám sát danh mục tín dụng

## Hai đầu ra

1. `dashboard/index.html`: dashboard tĩnh 4 trang, sinh bằng `scripts/build_dashboard.py`. Số liệu đã tổng hợp được nhúng thẳng vào HTML (thẻ `<script type="application/json" id="dashboard-data">`), mở bằng trình duyệt là xem được, không cần server, không đọc file ngoài.
2. `data/export/*.csv`: xuất nguyên 4 bảng mart (đầy đủ grain gốc, không phải bản đã tổng hợp cho dashboard) để tự dựng lại dashboard bằng Power BI khi luyện công cụ BI. Thư mục này nằm trong `.gitignore` (kế thừa quy tắc `data/`), không commit lên git.

Chạy lại: `.venv/Scripts/python.exe scripts/build_dashboard.py` (xem docstring đầu file để biết chi tiết).

## Dựng lại dashboard bằng Power BI

### Bước 1: nạp dữ liệu

Trong Power BI Desktop: **Get Data → Text/CSV**, nạp cả 4 file trong `data/export/`:

| File CSV | Nguồn mart | Trả lời câu hỏi | Grain (1 dòng = ?) |
|---|---|---|---|
| `mart_funnel_by_channel.csv` | `mart.funnel_by_channel` | Kênh nào duyệt nhiều, chuyển đổi tốt? (M12) | kênh × loại sản phẩm × loại khách × nhóm lãi suất |
| `mart_fpd_by_segment.csv` | `mart.fpd_by_segment` | Kênh/sản phẩm nào rủi ro sớm cao? (M11, có giới hạn dữ liệu, xem trang 2 của dashboard) | kênh × loại sản phẩm × loại khách × nhóm lãi suất |
| `mart_vintage.csv` | `mart.vintage` | Cohort nào xấu đi nhanh hơn theo tuổi hợp đồng? (M08) | kênh × loại sản phẩm × loại khách × nhóm lãi suất × nhóm kỳ hạn × MOB |
| `mart_roll_rate.csv` | `mart.roll_rate` | Khách quá hạn chuyển bucket thế nào? (M09, M10) | kênh × loại sản phẩm × bucket xuất phát × bucket đích |

Mã chỉ tiêu (M08, M09...) tra trong `docs/metric_dictionary.md`.

### Bước 2: quan hệ giữa các bảng

Bốn bảng trên **đã là bảng tổng hợp** (mỗi dòng là một tổ hợp phân khúc, không phải một hợp đồng), nên **không join trực tiếp với nhau theo khóa hợp đồng**. Cả 4 bảng đều có chung 2 cột phân khúc `channel_type` (kênh) và `contract_type` (loại sản phẩm: `Consumer loans` = vay tiêu dùng trả góp, `Cash loans` = vay tiền mặt, `Revolving loans` = thẻ quay vòng).

Cách làm chuẩn kiểu star-schema trong Power BI:

1. Tạo 1 bảng dùng chung `Dim_Channel`: **Get Data → Blank Query**, hoặc trong Power Query dùng `Reference` một trong 4 bảng, chọn cột `channel_type`, **Remove Duplicates**.
2. Tương tự tạo `Dim_Product` từ cột `contract_type`.
3. Ở tab **Model**, kéo quan hệ **1-nhiều** từ `Dim_Channel[channel_type]` sang cột `channel_type` của cả 4 bảng mart (tương tự với `Dim_Product`). Khi đó 1 slicer kênh hoặc sản phẩm sẽ lọc đồng thời cả 4 visual.
4. Không cần quan hệ nào khác: mỗi bảng mart tự đứng độc lập theo đúng câu hỏi nó trả lời, đúng như 4 trang của dashboard HTML.

**Riêng ma trận roll rate**: `mart_roll_rate.csv` **không có dòng cho ô không có quan sát nào** (ví dụ chuyển từ B1 sang B4 ở một phân khúc nhỏ). Nếu dựng Matrix visual trực tiếp từ bảng này, ô đó sẽ hiện **trống (blank)** chứ không phải **0**, dễ đọc nhầm là "chưa có dữ liệu" thay vì "0 hợp đồng, đã khớp lưới đầy đủ". Muốn hiện đúng số 0 như trong `dashboard/index.html`, cần tạo bảng lưới đầy đủ (5 bucket xuất phát × 8 trạng thái đích) trong Power Query rồi `Merge Query` (Left Outer) với `mart_roll_rate`, điền 0 cho `n_loans` ở các dòng không khớp, đúng logic mà `scripts/build_dashboard.py` (hàm `build_full_rollrate_grid`) đã làm khi vẽ trang 4.

### Bước 3: đo lường (measure)

**Nguyên tắc bắt buộc: mọi tỷ lệ phải cộng tử số và cộng mẫu số trước, rồi mới chia.** Các cột `*_rate` sẵn có trong mart (`approval_rate`, `fpd30_rate`, `ever_30_plus_rate`, `roll_rate`...) chỉ đúng ở đúng grain gốc của từng dòng. **Không được `AVERAGE()` các cột `*_rate` này** khi gộp nhiều dòng (nhiều kênh, nhiều sản phẩm...): các phân khúc có mẫu số rất khác nhau (ví dụ một kênh có 435.708 hồ sơ, kênh khác chỉ 6.389), lấy trung bình cộng đơn giản sẽ cho một con số không đại diện cho danh mục thật. Luôn viết measure kiểu `DIVIDE(SUM(tử số), SUM(mẫu số))`.

Ba measure mẫu (viết bằng DAX, tạo trong bảng tương ứng hoặc một bảng Measure riêng):

```DAX
// 1. Approval rate (M12), bảng mart_funnel_by_channel
// Tỷ lệ hồ sơ được duyệt (Approved + Unused offer) trên số hồ sơ đã có quyết định.
Approval Rate =
DIVIDE(
    SUM(mart_funnel_by_channel[n_approved]) + SUM(mart_funnel_by_channel[n_unused_offer]),
    SUM(mart_funnel_by_channel[n_decided])
)
```

```DAX
// 2. FPD30 (M11), bảng mart_fpd_by_segment
// CHẶN DƯỚI, không phải số cuối cùng: xem cảnh báo vùng mù dữ liệu trên trang 2
// của dashboard (dashboard/index.html) và docs/metric_dictionary.md mục M11
// trước khi dùng số này để xếp hạng kênh hay sản phẩm.
FPD30 Rate =
DIVIDE(
    SUM(mart_fpd_by_segment[n_fpd30]),
    SUM(mart_fpd_by_segment[n_loans])
)
```

```DAX
// 3. Ever 30+@MOB12 (M08), bảng mart_vintage
// Tỷ lệ hợp đồng TỪNG quá hạn trên 30 ngày tính đến MOB 12, cố định đúng 1 giá
// trị mob = 12 bằng CALCULATE, không lấy trung bình mọi MOB.
Ever 30 Plus MOB12 =
DIVIDE(
    CALCULATE(SUM(mart_vintage[n_ever_30_plus]), mart_vintage[mob] = 12),
    CALCULATE(SUM(mart_vintage[n_loans]), mart_vintage[mob] = 12)
)
```

Measure phụ hay dùng kèm (không bắt buộc nhưng hữu ích khi dựng lại trang 4):

```DAX
// Cure rate (M10), bảng mart_roll_rate, loại bucket xuất phát B0
Cure Rate =
DIVIDE(
    CALCULATE(SUM(mart_roll_rate[n_loans]), mart_roll_rate[to_state] = "B0 Current"),
    SUM(mart_roll_rate[n_loans])
)
```

### Bước 4: đối chiếu số

Sau khi dựng xong, đối chiếu vài số với `docs/metric_dictionary.md` hoặc chạy lại truy vấn SQL mẫu trong đó (mục M08, M09, M11, M12) qua `scripts/query.py`. Nếu số lệch, khả năng cao là đang lấy trung bình cột `*_rate` thay vì `DIVIDE(SUM(...), SUM(...))`, hoặc quên lọc đúng `mob = 12` khi gộp `mart_vintage`.
