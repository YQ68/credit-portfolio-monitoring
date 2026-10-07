# Bản Power BI của Credit Portfolio Monitoring

Bản PBIP (Power BI Project) của project, kể đúng câu chuyện của
[`dashboard/index.html`](../dashboard/index.html) nhưng trong Power BI.

Muốn hiểu cách dựng và vì sao: đọc mục về bản Power BI trong
[`docs/methodology.md`](../docs/methodology.md).
Bản chốt thiết kế: [`_brief/report-spec.md`](_brief/report-spec.md).

## Mở lần đầu

Cần Power BI Desktop (bản miễn phí là đủ, không cần Pro hay Fabric).

1. Trỏ tham số `DataFolder` về thư mục `data/export` trên máy bạn. Bản trong git
   chứa đường dẫn mẫu `C:\path\to\credit-portfolio-monitoring\data\export`. Cách
   gọn nhất là sinh lại model với đường dẫn thật (không commit bản này):

   ```powershell
   python scripts/build_pbip_model.py --data-folder "D:\...\credit-portfolio-monitoring\data\export"
   # hoặc đặt biến môi trường CPM_DATA_FOLDER rồi chạy không tham số
   ```

   Hoặc sửa tay dòng `expression DataFolder = "..."` trong
   `CreditPortfolio.SemanticModel/definition/expressions.tmdl`.

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

Semantic model: 7 bảng (5 fact, 2 danh mục), 10 quan hệ, 44 measure (4 trong số đó là measure
trình bày `Highlight ...` / `Base ...`, chỉ để tô màu trong small multiples, vì Power BI bỏ qua
selector màu theo danh mục khi visual có Rows). Định nghĩa quá hạn chính là `SK_DPD_DEF`
(DPD có ngưỡng trọng yếu); cột hậu tố `_no_threshold` theo `SK_DPD` chỉ dùng làm độ nhạy.

Tiêu đề viết số kiểu Việt Nam (0,094%), còn nhãn số trong visual hiện theo locale của
Power BI Desktop (thường là 0.094%). Đã thử đặt culture model `vi-VN`: Desktop vẫn hiện
theo locale ứng dụng, nên model giữ `en-US`.

| Bảng | Nguồn CSV | Trả lời |
|---|---|---|
| `Snapshot` | `mart_portfolio_snapshot.csv` | Danh mục đang mở phân theo bucket quá hạn (M02, M06) |
| `Funnel` | `mart_funnel_by_channel.csv` | Kênh nào duyệt nhiều, chuyển đổi tốt (M12) |
| `FPD` | `mart_fpd_by_segment.csv` | Rủi ro sớm theo phân khúc (M11), trên hợp đồng đã kích hoạt |
| `Vintage` | `mart_vintage.csv` | Nhóm nào xấu đi nhanh hơn theo tuổi hợp đồng (M08) |
| `RollRate` | `mart_roll_rate.csv` | Chuyển nhóm và cure rate (M09, M10) |
| `Dim Channel` | gom từ 5 bảng trên | Danh mục kênh dùng chung |
| `Dim Product` | gom từ 5 bảng trên | Danh mục sản phẩm dùng chung |

Mã chỉ tiêu (M02, M08...) tra trong [`docs/metric_dictionary.md`](../docs/metric_dictionary.md).

Báo cáo: 4 trang, khung 1280x720, bám đúng 4 trang của bản HTML. Tổng cộng 48 visual
(đếm file `visual.json` trong các thư mục `visuals/`):

| Trang | Nội dung chính | Số visual |
|---|---|---|
| 1. Tổng quan | 4 thẻ KPI (hai thẻ tỷ lệ cùng một tập), cơ cấu nhóm quá hạn, tỷ lệ 30+ theo kênh, bảng theo loại sản phẩm | 15 |
| 2. Kênh bán | trellis theo sản phẩm, bảng SMR theo kênh (chỉ sản phẩm và sản phẩm × đợt mở, kèm khoảng tin cậy 95%), bảng duyệt chuẩn hoá theo sản phẩm | 11 |
| 3. Vintage | đường vintage theo đợt mở 12 tháng (legend đợt), đường vintage theo sản phẩm, bảng tỷ số so với vay tiền mặt theo bốn cách đo, trellis 7 kênh | 12 |
| 4. Thu hồi | ma trận roll rate, cure rate theo nhóm (bỏ B0), bảng quy mô từng nhóm | 11 |

Mỗi trang gồm 8 visual dùng chung (kicker, tên trang, 2 slicer, thanh điều hướng, ghi chú
chân trang, 2 kẻ ngang) cộng phần nội dung riêng. Trellis là lưới biểu đồ nhỏ, mỗi ô một
nhóm, dùng chung thang đo để so sánh được. MOB (months on book) là số tháng kể từ khi
mở hợp đồng.

## Thiết kế

Tông **Editorial Newsroom**: đọc như một trang báo kinh tế cuối tuần, ít màu, nhiều
khoảng trắng.

- Nền kem `#FAF7F0`, chữ mực `#0F172A`.
- Tiêu đề dùng font serif **Cambria**, thân chữ và con số dùng Segoe UI.
- Một màu nhấn duy nhất: mustard `#D4A30A`.
- **Highlight-and-grey**: mỗi biểu đồ chỉ tô mustard đúng một phần tử mang thông điệp
  (ví dụ Contact center và Stone ở trang 2, thẻ quay vòng ở trang 3, nhóm B1 1-30 ở trang 4), phần còn lại
  nằm trong thang xám.
- Tiêu đề visual là câu kết luận có số, không phải tên loại biểu đồ. Ví dụ: "Sau chuẩn
  hoá theo sản phẩm, Contact center gấp 2,90 [2,14; 3,84] lần kỳ vọng, Stone 1,63 [1,30; 2,02]".
- Mọi tên trang, dek, tiêu đề visual có số và ghi chú LƯU Ý sinh từ
  `scripts/headlines.py`, vốn đọc `data/export/findings.json`. Bản HTML dùng chung
  nguồn đó; `python scripts/check_headlines_sync.py` kiểm hai bản khớp nhau và mọi
  con số truy được về `findings.json`.

**Vì sao Cambria mà không phải Georgia.** File font Georgia thiếu 19 ký tự tiếng Việt:
ấ ầ ẩ ẫ ậ ế ề ể ễ ệ ố ồ ổ ỗ ộ ơ ư ớ ứ (đã kiểm bằng bảng mã `cmap` của font). Thiếu glyph
thì Windows ghép dấu rời lên ký tự gốc, nên "gấp" hiện thành "gâ´p". Cambria đủ cả 19
ký tự. Nếu đổi font tiêu đề, phải kiểm lại đúng 19 ký tự này.

Tông, lưới 12 cột, bố cục từng trang và lý do chọn nằm trong
[`_brief/report-spec.md`](_brief/report-spec.md). Ảnh chụp bốn trang:
[`01-tong-quan`](../docs/screenshots/01-tong-quan.png),
[`02-kenh-ban`](../docs/screenshots/02-kenh-ban.png),
[`03-vintage`](../docs/screenshots/03-vintage.png),
[`04-thu-hoi`](../docs/screenshots/04-thu-hoi.png).

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
python scripts/build_pbip_model.py     # TMDL: 7 bảng, 10 quan hệ, 44 measure
python scripts/build_pbip_report.py    # PBIR: theme, 4 trang, 48 visual
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

Bản trong repo là **đầu ra nguyên của hai generator**, chưa qua bước đó (generator cố
tình không sinh `lineageTag`, đúng khuyến nghị của Microsoft: để engine tự gán ở lần
lưu đầu). Vì vậy lần mở đầu tiên Desktop sẽ ghi lại file: thêm `lineageTag`, nâng
`compatibilityLevel`, đổi xuống dòng sang CRLF, thêm thư mục `cultures/` và file
`diagramLayout.json`. Đó là chuyện một lần, không phải mỗi lần mở. Muốn quay về đúng
bản trong git thì chạy lại hai generator, xoá `definition/cultures/` và
`diagramLayout.json` nếu có.

Riêng URL `$schema`, generator cố tình giữ `visualContainer/2.9.0`, `report/3.3.0`,
`page/2.1.0` thay vì bản mới hơn mà Desktop 2.157 dùng (`2.12.0`, `3.4.0`, `2.3.1`).
Lý do: ba bản mới **chưa được Microsoft publish**, tải về trả HTTP 404, nên
`powerbi-report-author` không lấy được schema và **bỏ qua hẳn lớp kiểm JSON Schema**.
Giữ bản cũ để còn lớp kiểm đó, chính nó đã bắt được lỗi thiếu `reportVersionAtImport`
khi dựng project này.

## File cục bộ của Desktop không đưa lên git

Desktop ghi vào thư mục `.pbi/` hai file chỉ có nghĩa trên máy của bạn:
`localSettings.json` (có chuỗi mã hóa `securityBindingsSignature` gắn với tài khoản
Windows) và `cache.abf` (bản nhị phân của dữ liệu đã nạp, đổi sau mỗi lần mở).
`.gitignore` loại cả hai theo khuyến nghị của Microsoft cho PBIP, đừng `git add -f`.
Mở Desktop lần sau thì chúng tự sinh lại. `editorSettings.json` vẫn được theo dõi.

## Chụp lại ảnh các trang

```powershell
powerbi-desktop status                       # lấy PID
powerbi-desktop reload --pid <pid>
powerbi-desktop screenshot-all --pid <pid> --output-dir docs/screenshots
python scripts/rename_screenshots.py         # đổi tên ảnh có dấu về tên ASCII
```

`screenshot-all` luôn đặt tên ảnh theo tên trang hiển thị (ví dụ `1. Tổng quan.png`),
có dấu và dấu cách, dễ làm hỏng link trong Markdown. `rename_screenshots.py` ghép theo
số thứ tự ở đầu tên file rồi đổi thành `01-tong-quan.png`, `02-kenh-ban.png`,
`03-vintage.png`, `04-thu-hoi.png`, ghi đè ảnh cũ cùng tên. Chạy lại nhiều lần không lỗi.

Ảnh nằm trong [`docs/screenshots/`](../docs/screenshots/).
