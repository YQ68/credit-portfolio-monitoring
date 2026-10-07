# Dashboard giám sát danh mục tín dụng

## Đầu ra và nguồn số

1. `dashboard/index.html`: dashboard tĩnh 4 trang, sinh bằng `scripts/build_dashboard.py`. Số liệu đã tổng hợp được nhúng thẳng vào HTML (thẻ `<script type="application/json" id="dashboard-data">`), mở bằng trình duyệt là xem được, không cần server, không đọc file ngoài. Câu chữ có số (tiêu đề trang, tiêu đề biểu đồ, ghi chú) sinh từ `data/export/findings.json` qua `scripts/headlines.py`, không gõ cứng trong code.
2. `data/export/*.csv`: `scripts/build_dashboard.py` xuất nguyên cả 5 bảng mart (đầy đủ grain gốc, không phải bản đã tổng hợp cho dashboard), thứ tự dòng cố định (`order by all`) để diff trên git có nghĩa. Bản Power BI trong `powerbi/` đọc 5 file này. Bảng độ nhạy `mart.roll_rate_no_threshold` không được xuất.
3. `data/export/findings.json`: nguồn số duy nhất cho mọi kết luận, sinh bằng `scripts/compute_findings.py`. Không do dashboard sinh ra, nhưng dashboard đọc nó.

Cả 5 CSV và `findings.json` đều được commit (`.gitignore` có ngoại lệ riêng); dữ liệu gốc Kaggle và kho DuckDB thì không.

Chạy lại, theo đúng thứ tự (kho phải được dựng trước bằng `scripts/build.py`):

```
python scripts/compute_findings.py
python scripts/build_dashboard.py
```

Cả hai script mở kho ở chế độ chỉ đọc. Docstring đầu `scripts/build_dashboard.py` ghi chi tiết.

**Định nghĩa quá hạn.** Mọi cột gốc (`n_ever_30_plus`, `n_30_plus`, `dpd_bucket`, `from_state`, `to_state`) theo `SK_DPD_DEF`, tức DPD (days past due, số ngày quá hạn) có ngưỡng trọng yếu. Cột hậu tố `_no_threshold` theo `SK_DPD`, chỉ dùng cho phân tích độ nhạy. Lý do: [methodology mục 4](../docs/methodology.md#4-quyết-định-đã-đảo-ngược-định-nghĩa-quá-hạn).

Bản Power BI hoàn chỉnh dạng PBIP nằm ở `powerbi/`, dựng bằng script chứ không kéo thả. Xem [`powerbi/README.md`](../powerbi/README.md) và mục [Bản Power BI](../docs/methodology.md#6-bản-power-bi) trong `docs/methodology.md`. PBIP **không mở được ngay sau khi clone**: phải đặt tham số `DataFolder` trỏ tới `data/export` trên máy trước. Phần dưới đây giải thích cấu trúc 5 CSV và các measure mẫu, hữu ích khi đọc bản PBIP hoặc tự dựng lại một báo cáo từ cùng dữ liệu.

## Cấu trúc 5 CSV

| File CSV | Nguồn mart | Trả lời câu hỏi | Grain (1 dòng = ?) |
|---|---|---|---|
| `mart_funnel_by_channel.csv` | `mart.funnel_by_channel` | Kênh nào duyệt nhiều, chuyển đổi tốt? (M12) | kênh × loại sản phẩm × loại khách × nhóm lãi suất |
| `mart_fpd_by_segment.csv` | `mart.fpd_by_segment` | Kênh/sản phẩm nào có dấu hiệu rủi ro ngay kỳ đầu? (M11) | kênh × loại sản phẩm × loại khách × nhóm lãi suất |
| `mart_vintage.csv` | `mart.vintage` | Cohort nào xấu đi nhanh hơn theo tuổi hợp đồng? (M08) | nguồn × kênh × loại sản phẩm × loại khách × nhóm lãi suất × nhóm kỳ hạn × MOB |
| `mart_roll_rate.csv` | `mart.roll_rate` | Khách quá hạn chuyển bucket thế nào? (M09, M10) | nguồn × kênh × loại sản phẩm × bucket xuất phát × bucket đích |
| `mart_portfolio_snapshot.csv` | `mart.portfolio_snapshot` | Danh mục đang mở hiện có cơ cấu nhóm quá hạn thế nào? (M02, M06) | loại sản phẩm × kênh × bucket, chỉ tại tháng gần nhất (`months_balance = -1`) |

Mã chỉ tiêu (M08, M09...) tra trong [`docs/metric_dictionary.md`](../docs/metric_dictionary.md). Mô tả đầy đủ từng cột: [`sql/mart/README.md`](../sql/mart/README.md).

Các cột cần chú ý:

- `mart_vintage.csv`: `n_ever_30_plus` và `ever_30_plus_rate` theo `SK_DPD_DEF`; `n_ever_30_plus_no_threshold`, `ever_30_plus_rate_no_threshold` là độ nhạy. `n_observed_full` và `n_closed_early` tách mẫu số `n_loans` thành hợp đồng còn quan sát thật đến MOB đó và hợp đồng đã kết thúc trước. `origination_cohort` là đợt mở 12 tháng (nhãn như `-96 đến -85`, tháng tương đối), `origination_cohort_start` là tháng đầu đợt dùng để sắp xếp; `n_ever_30_plus_due_only` là định nghĩa giữa (SK_DPD 30+ ở tháng còn kỳ phải trả).
- `mart_portfolio_snapshot.csv`: `n_30_plus`, `exposure_30_plus` theo `SK_DPD_DEF`. Khi đặt tỷ lệ 30+ theo hợp đồng cạnh tỷ lệ theo dư nợ, dùng `n_30_plus_exposure_known / n_loans_exposure_known` để hai con số cùng một tập hợp đồng. `n_30_plus_no_threshold`, `exposure_30_plus_no_threshold` là độ nhạy và không khớp `dpd_bucket` của dòng.
- `mart_fpd_by_segment.csv`: `n_approved_not_activated` (hồ sơ duyệt không có lịch trả, tức chưa kích hoạt) và `n_approved_scheduled_no_installment` (có lịch trả nhưng không có dòng kỳ 1) không thuộc mẫu số `n_loans`.
- Cột `source` (nguồn dữ liệu tháng: `pos_cash` là khoản trả góp, `credit_card` là thẻ) chỉ có ở `mart_vintage.csv` và `mart_roll_rate.csv`.

## Quan hệ giữa các bảng

Năm bảng trên **đã là bảng tổng hợp** (mỗi dòng là một tổ hợp phân khúc, không phải một hợp đồng), nên **không join trực tiếp với nhau theo khóa hợp đồng**. Cả 5 bảng đều có chung 2 cột phân khúc `channel_type` (kênh) và `contract_type` (loại sản phẩm: `Consumer loans` = vay tiêu dùng trả góp, `Cash loans` = vay tiền mặt, `Revolving loans` = thẻ quay vòng).

Cách làm kiểu star schema (bản PBIP làm đúng như vậy):

1. Một bảng danh mục kênh dùng chung, lấy giá trị duy nhất của `channel_type`.
2. Tương tự một bảng danh mục sản phẩm từ `contract_type`.
3. Quan hệ **1-nhiều** từ hai bảng danh mục sang cột tương ứng của cả 5 bảng mart. Khi đó một slicer kênh hoặc sản phẩm lọc đồng thời mọi trang. Slicer phải lấy từ bảng danh mục, không lấy từ một bảng fact.
4. Không cần quan hệ nào khác: mỗi bảng mart tự đứng độc lập theo đúng câu hỏi nó trả lời.

**Riêng ma trận roll rate**: `mart_roll_rate.csv` **không có dòng cho ô không có quan sát nào** (ví dụ chuyển từ B1 sang B4 ở một phân khúc nhỏ). Dashboard HTML ghép kết quả với lưới đầy đủ 5 bucket xuất phát × 8 trạng thái đích (hàm `build_roll_grid` trong `scripts/build_dashboard.py`) và hiện ô không có quan sát là trống. Ma trận Power BI cũng hiện trống cho các ô đó. Khi đọc, ô trống nghĩa là 0 lượt, không phải thiếu dữ liệu.

## Measure mẫu

**Nguyên tắc bắt buộc: mọi tỷ lệ phải cộng tử số và cộng mẫu số trước, rồi mới chia.** Các cột `*_rate` sẵn có trong mart (`approval_rate`, `fpd30_rate`, `ever_30_plus_rate`, `roll_rate`...) chỉ đúng ở đúng grain gốc của từng dòng. **Không được `AVERAGE()` các cột `*_rate` này** khi gộp nhiều dòng: các phân khúc có mẫu số rất khác nhau, lấy trung bình cộng sẽ cho một con số không đại diện cho danh mục thật. Luôn viết measure kiểu `DIVIDE(SUM(tử số), SUM(mẫu số))`.

```DAX
// Approval rate (M12), bảng mart_funnel_by_channel
// Tỷ lệ hồ sơ được duyệt (Approved + Unused offer) trên số hồ sơ đã có quyết định.
// So giữa kênh phải trong cùng sản phẩm: tỷ lệ duyệt khác nhau chủ yếu do cơ cấu sản phẩm.
Approval Rate =
DIVIDE(
    SUM(mart_funnel_by_channel[n_approved]) + SUM(mart_funnel_by_channel[n_unused_offer]),
    SUM(mart_funnel_by_channel[n_decided])
)
```

```DAX
// FPD30 (M11), bảng mart_fpd_by_segment
// Đo trên hợp đồng đã kích hoạt. Hồ sơ duyệt chưa kích hoạt đếm riêng ở
// n_approved_not_activated, không thuộc mẫu số. Tử số rất nhỏ, không dùng để xếp hạng kênh.
FPD30 Rate =
DIVIDE(
    SUM(mart_fpd_by_segment[n_fpd30]),
    SUM(mart_fpd_by_segment[n_loans])
)
```

```DAX
// Ever 30+@MOB12 (M08), bảng mart_vintage, định nghĩa chính SK_DPD_DEF
// Cố định đúng 1 giá trị mob = 12 bằng CALCULATE, không lấy trung bình mọi MOB.
Ever 30 Plus MOB12 =
DIVIDE(
    CALCULATE(SUM(mart_vintage[n_ever_30_plus]), mart_vintage[mob] = 12),
    CALCULATE(SUM(mart_vintage[n_loans]), mart_vintage[mob] = 12)
)
```

```DAX
// Tỷ lệ 30+ theo hợp đồng, cùng tập với tỷ lệ theo dư nợ (M06), bảng mart_portfolio_snapshot
DQ30 Rate Same Set =
DIVIDE(
    SUM(mart_portfolio_snapshot[n_30_plus_exposure_known]),
    SUM(mart_portfolio_snapshot[n_loans_exposure_known])
)
```

Cure rate cần **hai measure**, vì mẫu số phải là tổng của cả hàng bucket xuất phát:

```DAX
// Mẫu số của roll rate và cure rate (M09, M10), bảng mart_roll_rate:
// tổng số lượt ở bucket xuất phát, cộng qua MỌI trạng thái đích.
Roll Base Loans =
CALCULATE(
    SUM(mart_roll_rate[n_loans]),
    REMOVEFILTERS(mart_roll_rate[to_state], mart_roll_rate[to_order])
)

// Cure rate (M10): đọc với bucket xuất phát từ B1 trở lên, loại B0
Cure Rate =
DIVIDE(
    CALCULATE(
        SUM(mart_roll_rate[n_loans]),
        REMOVEFILTERS(mart_roll_rate[to_state], mart_roll_rate[to_order]),
        mart_roll_rate[to_state] = "B0 Current"
    ),
    [Roll Base Loans]
)
```

Vì sao không viết mẫu số là `SUM(mart_roll_rate[n_loans])`: khi có bộ lọc `to_state` (một ô của Matrix, hoặc slicer bucket đích), mẫu số cũng bị lọc theo và chỉ còn đúng ô đang xét thay vì cả hàng, nên tỷ lệ sai: ở ô B0 hoặc khi slicer chọn `B0 Current` thì tử số bằng mẫu số và ra 100%. `REMOVEFILTERS` phải bỏ **cả `to_order`**, vì `to_state` sắp xếp theo cột này nên bộ lọc áp lên cả hai. Cũng không dùng cột `n_from` làm mẫu số: nó là tổng của cả hàng nhưng lặp lại trên từng dòng `to_state`, cộng thẳng sẽ nhân mẫu số lên theo số dòng đích.

Hàng B2 và B3 của ma trận roll rate có rất ít lượt (hàng B3 dưới ngưỡng diễn giải 1.000 lượt ngay cả trên toàn danh mục), nên khi cắt theo kênh hay sản phẩm, gần như mọi ô của hai hàng này không đủ mẫu để đọc.

## Đối chiếu số

Sau khi dựng xong, đối chiếu vài số với `data/export/findings.json` (khóa ghi trong mục Nguồn số của [`docs/insight_memo.md`](../docs/insight_memo.md#6-nguồn-số)) hoặc chạy truy vấn SQL mẫu trong `docs/metric_dictionary.md` (mục M06, M08, M09, M11, M12) qua `scripts/query.py`. Nếu số lệch, khả năng cao là đang lấy trung bình cột `*_rate` thay vì `DIVIDE(SUM(...), SUM(...))`, quên lọc đúng `mob = 12` khi gộp `mart_vintage`, hoặc đang dùng nhầm cột `_no_threshold`.
