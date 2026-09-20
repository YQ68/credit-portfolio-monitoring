# Bản Power BI của Credit Portfolio Monitoring

Bản PBIP (Power BI Project) của project, kể đúng câu chuyện của
[`dashboard/index.html`](../dashboard/index.html) nhưng trong Power BI.

Muốn hiểu cách dựng và vì sao: đọc
[`docs/walkthrough/09-powerbi-pbip.md`](../docs/walkthrough/09-powerbi-pbip.md).
Bản chốt thiết kế: [`_brief/report-spec.md`](_brief/report-spec.md).

## Mở lần đầu

Cần Power BI Desktop (bản miễn phí là đủ, không cần Pro hay Fabric).

1. Sửa tham số đường dẫn trong
   `CreditPortfolio.SemanticModel/definition/expressions.tmdl` cho đúng máy bạn:

   ```tmdl
   expression DataFolder = "<đường dẫn tuyệt đối tới data/export>" meta [...]
   ```

2. Kiểm tra trước khi mở (tùy chọn nhưng nên làm, xem phần dưới).

3. Mở `CreditPortfolio.pbip`. **Nháy đúp trong File Explorer**, hoặc:

   ```powershell
   Start-Process "CreditPortfolio.pbip"
   ```

   Nếu dùng Power BI Desktop bản Microsoft Store: đừng gọi thẳng `PBIDesktop.exe`
   với đường dẫn file, bản đóng gói MSIX bỏ qua tham số và chỉ mở cửa sổ trắng.

4. Lần mở đầu Desktop hiện banner *"Some of the tables have incomplete or no data"*.
   Bấm **Refresh now** để nạp 5 file CSV. PBIP không lưu dữ liệu, chỉ lưu định nghĩa.

## Nội dung

Semantic model: 7 bảng (5 fact, 2 danh mục), 10 quan hệ, 27 measure.

| Bảng | Nguồn CSV | Trả lời |
|---|---|---|
| `Snapshot` | `mart_portfolio_snapshot.csv` | Danh mục đang mở phân theo bucket quá hạn (M02, M06) |
| `Funnel` | `mart_funnel_by_channel.csv` | Kênh nào duyệt nhiều, chuyển đổi tốt (M12) |
| `FPD` | `mart_fpd_by_segment.csv` | Rủi ro sớm theo phân khúc (M11, có vùng mù) |
| `Vintage` | `mart_vintage.csv` | Nhóm nào xấu đi nhanh hơn theo tuổi hợp đồng (M08) |
| `RollRate` | `mart_roll_rate.csv` | Chuyển nhóm và cure rate (M09, M10) |
| `Dim Channel` | gom từ 5 bảng trên | Danh mục kênh dùng chung |
| `Dim Product` | gom từ 5 bảng trên | Danh mục sản phẩm dùng chung |

Mã chỉ tiêu (M02, M08...) tra trong [`docs/metric_dictionary.md`](../docs/metric_dictionary.md).

Báo cáo: 4 trang, khung 1280x720, bám đúng 4 trang của bản HTML.

## Ba quy tắc khi sửa

1. **Slicer lấy từ `Dim Channel[Kênh]` và `Dim Product[Sản phẩm]`**, không lấy từ
   bảng fact. Cột khóa phía fact đã ẩn có chủ đích: kéo `Funnel[channel_type]` vào
   slicer thì nó chỉ lọc bảng Funnel, bốn bảng còn lại không bị lọc và trang sai
   lặng lẽ mà vẫn hiện số.

2. **Không dùng các cột `*_rate` trong mart.** Chúng đã ẩn. Chúng chỉ đúng ở đúng
   grain gốc từng dòng; gộp nhiều dòng phải dùng measure `DIVIDE(SUM, SUM)`.

3. **Mẫu số roll rate là `[Roll Base Loans]`**, không phải `SUM(RollRate[n_from])`.
   Cột `n_from` là window sum lặp lại trên mỗi dòng `to_state`, cộng thẳng sẽ nhân
   mẫu số lên nhiều lần.

## Dựng lại toàn bộ PBIP từ script

Cả `CreditPortfolio.SemanticModel/` và `CreditPortfolio.Report/` đều sinh ra bằng
script, không sửa tay. Sửa gì thì sửa trong script rồi chạy lại:

```powershell
python scripts/build_pbip_model.py     # TMDL: 7 bảng, 10 quan hệ, 27 measure
python scripts/build_pbip_report.py    # PBIR: theme, 4 trang, 30 visual
```

ID của trang và visual sinh bằng SHA-1 của `trang|khóa` chứ không ngẫu nhiên, nên
chạy lại cho ra đúng ID cũ và `git diff` chỉ hiện phần thật sự đổi.

## Kiểm tra trước khi mở Desktop

Ba lớp, mỗi lớp bắt một loại lỗi khác nhau:

```powershell
# 1. Xung đột tên: measure trùng cột cùng bảng, hoặc trùng tên bảng.
#    Hai CLI dưới KHÔNG bắt được, chỉ lộ ra khi Desktop dựng database.
python scripts/check_model_names.py powerbi/CreditPortfolio.SemanticModel

# 2. Cấu trúc PBIR: schema, ID, thuộc tính formatting, enum, biên bố cục, theme
powerbi-report-author validate powerbi/CreditPortfolio.Report

# 3. Cú pháp TMDL và tính hợp lệ của model (cần Node.js 20+)
#    Gọi Power BI Modeling MCP server với connection_operations / ConnectFolder.
#    Đây là cách duy nhất lấy được thông báo lỗi thật khi Desktop chỉ báo
#    "Issues were found" mà không nói gì thêm.
```

Cài hai CLI một lần:

```powershell
npm install -g @microsoft/powerbi-report-authoring-cli@latest @microsoft/powerbi-desktop-bridge-cli@latest
```

## Lần chuyển đổi đầu tiên của Desktop

Khi Desktop mở một PBIP **vừa sinh ra từ script lần đầu**, nó chuyển đổi rồi ghi
lại file theo dạng chuẩn của nó: thêm `lineageTag` (một GUID định danh nội bộ) cho
mọi bảng, cột và measure trong TMDL, và nâng URL `$schema` của PBIR.

Bản trong repo **đã qua bước đó**, nên mở lên không sinh thêm diff nào. Đã kiểm:
mở Desktop từ trạng thái đã commit, `git status` trả về 0 file thay đổi.

Bạn chỉ gặp lại chuyện này sau khi chạy lại `build_pbip_model.py`, vì generator cố
tình không sinh `lineageTag` (đúng khuyến nghị của Microsoft: để engine tự gán ở
lần lưu đầu). Khi đó mở Desktop một lần rồi commit phần chuẩn hoá là xong.

Riêng URL `$schema`, generator cố tình giữ `visualContainer/2.9.0`, `report/3.3.0`,
`page/2.1.0` thay vì bản mới hơn mà Desktop 2.157 dùng (`2.12.0`, `3.4.0`, `2.3.1`).
Lý do: ba bản mới **chưa được Microsoft publish**, tải về trả HTTP 404, nên
`powerbi-report-author` không lấy được schema và **bỏ qua hẳn lớp kiểm JSON Schema**.
Giữ bản cũ để còn lớp kiểm đó, chính nó đã bắt được lỗi thiếu `reportVersionAtImport`
khi dựng project này.

## Chụp lại ảnh các trang

```powershell
powerbi-desktop status                       # lấy PID
powerbi-desktop reload --pid <pid>
powerbi-desktop screenshot-all --pid <pid> --output-dir docs/screenshots
```

Ảnh nằm trong [`docs/screenshots/`](../docs/screenshots/).
