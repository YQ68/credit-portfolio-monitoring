# Report spec: Credit Portfolio Monitoring (Power BI)

Bản chốt phạm vi và thiết kế trước khi ghi file PBIR. Khung 1280x720, 4 trang,
bám đúng 4 trang của `dashboard/index.html` để hai bản đọc ra cùng một câu chuyện.

## Đối tượng đọc và câu hỏi

Cùng 4 câu hỏi kinh doanh trong `README.md` của project:

1. Kênh, sản phẩm nào duyệt nhiều nhưng rủi ro cũng cao?
2. Khi so cùng MOB, nhóm hợp đồng nào xấu đi nhanh hơn?
3. Khách quá hạn chuyển bucket ra sao? Bucket nào cure rate thấp nhất?
4. Phân khúc nào nên siết hoặc nới?

## Nguồn dữ liệu

5 file CSV trong `data/export/`, sinh bằng `scripts/build_dashboard.py`
(bốn file đầu) và `sql/mart/mart_portfolio_snapshot.sql` (file thứ năm).

| Bảng trong model | File CSV | Grain |
|---|---|---|
| `Snapshot` | `mart_portfolio_snapshot.csv` | sản phẩm x kênh x bucket, tại tháng quan sát gần nhất |
| `Funnel` | `mart_funnel_by_channel.csv` | kênh x sản phẩm x loại khách x nhóm lãi suất |
| `FPD` | `mart_fpd_by_segment.csv` | kênh x sản phẩm x loại khách x nhóm lãi suất |
| `Vintage` | `mart_vintage.csv` | ... x nhóm kỳ hạn x MOB |
| `Roll Rate` | `mart_roll_rate.csv` | nguồn x sản phẩm x kênh x bucket đi x bucket đến |

Hai bảng danh mục dùng chung `Dim Channel[Kênh]` và `Dim Product[Sản phẩm]`
gom giá trị từ cả năm bảng fact, nối 1-nhiều để một slicer lọc đồng thời mọi visual.

## Design identity

Lấy nguyên `PALETTES["light"]` trong `scripts/build_dashboard.py` để bản Power BI
và bản HTML nhìn như một hệ.

- Nền trang `#f9f9f7`, nền visual `#fcfcfb`, viền `#e1e0d9` bo 6px
- Chuỗi dữ liệu: `#2a78d6` xanh, `#eb6834` cam, `#1baf7a` lục
- Chữ chính `#0b0b0b`, chữ phụ `#52514e`, chữ mờ `#898781`
- Cảnh báo `#eda100`
- Font Segoe UI, tiêu đề Segoe UI Semibold 11pt, callout 32pt
- Tắt visual header để trang sạch như bản HTML

## Bố cục dùng chung

| Vùng | y | Cao |
|---|---|---|
| Tiêu đề trang | 16 | 46 |
| Hai slicer (Kênh, Sản phẩm) | 68 | 60 |
| Hàng KPI (chỉ trang 1) | 138 | 104 |
| Vùng biểu đồ | 138 hoặc 258 | 396 hoặc 440 |
| Hàng dưới (bảng + ghi chú) | 544 | 152 |

Lề trái 24, bề ngang dùng được 1232, hai cột 608 cách nhau 16.

## Bốn trang

### Trang 1. Tổng quan danh mục (executive summary)
4 thẻ KPI: `Open Loans`, `Rate 30+ Coincident`, `Exposure`, `Exposure Rate 30+`.
Hai biểu đồ thanh: cơ cấu bucket toàn danh mục, và cơ cấu bucket tách theo sản phẩm.
Thông điệp: phần lớn danh mục sạch (B0 = 98,65%) nhưng vẫn có đuôi B4 đáng kể.

### Trang 2. Kênh bán: tăng trưởng và rủi ro (comparative benchmark)
Scatter `Approval Rate` (trục X) với `Ever 30 Plus MOB12` (trục Y), bong bóng theo số hồ sơ.
Biểu đồ thanh `Ever 30 Plus MOB12` theo kênh, CÓ tách series theo sản phẩm.
Ghi chú cảnh báo: khoảng cách thô 8 lần phần lớn là nhiễu cơ cấu; FPD30 không dùng làm trục rủi ro.

### Trang 3. Vintage (analytical canvas)
Hai line chart `Ever 30 Plus Rate` theo `mob`, một tách theo sản phẩm, một tách theo kênh.
Bảng xếp hạng kênh tại MOB 12 kèm cột mẫu số.
Ghi chú: mẫu số đã loại `is_partial_history`; đuôi MOB cao mỏng dần.

### Trang 4. Chuyển nhóm và thu hồi (operational monitor)
Ma trận `pivotTable` from_state x to_state với measure `Roll Rate`.
Biểu đồ thanh `Cure Rate` theo bucket xuất phát.
Ghi chú: cure rate 50,1% ở B1 xuống 7,0% ở B3; lọc bỏ from_state = B0 khi đọc cure.

## Ràng buộc bắt buộc

1. Mọi tỷ lệ là measure `DIVIDE(SUM(tử), SUM(mẫu))`. Các cột `*_rate` có sẵn
   trong mart đều đã đặt `isHidden` để không ai kéo nhầm vào visual.
2. Mẫu số của roll rate dùng `CALCULATE(..., REMOVEFILTERS('Roll Rate'[to_state]))`,
   KHÔNG cộng cột `n_from`: đó là window sum lặp lại trên từng dòng to_state.
3. `Ever 30 Plus MOB12` cố định `mob = 12` bằng `CALCULATE`, không phụ thuộc slicer.
4. Cột khóa `channel_type` và `contract_type` phía fact đều ẩn, buộc slicer đi qua bảng dim.
