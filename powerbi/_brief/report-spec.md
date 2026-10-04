# Report spec: Credit Portfolio Monitoring (Power BI)

Bản chốt phạm vi và thiết kế trước khi ghi file PBIR. Khung 1280x720, 4 trang,
kể đúng câu chuyện của `dashboard/index.html`.

Phần Markdown dưới đây là để người đọc duyệt. Khối YAML `Design Brief:` ở cuối
file mới là hợp đồng triển khai chính thức; `scripts/build_pbip_report.py` sinh
file PBIR theo đúng khối đó.

## Thuật ngữ dùng trong file này

| Từ | Nghĩa |
|---|---|
| Archetype | Khuôn trang theo mục đích đọc (tổng quan cho lãnh đạo, so sánh, phân tích, vận hành) |
| Layout variant | Một trong 2-3 bố cục A/B/C mà mỗi archetype đưa ra, chọn theo đặc điểm dữ liệu của trang |
| Tone | Tông thị giác chung của cả báo cáo: font, màu nền, mật độ, cách kẻ |
| Signature | Một động tác thị giác lặp lại ở mọi trang, thứ người đọc nhớ sau khi đóng báo cáo |
| PBIR | Power BI Enhanced Report Format, phần JSON mô tả trang và visual |
| VCO | visualContainerObjects, nhóm thuộc tính định dạng cái khung bao quanh visual |
| MOB | Months on book, hợp đồng đã chạy bao nhiêu tháng kể từ tháng mở |
| Trellis / small multiples | Một biểu đồ bị tách thành nhiều ô nhỏ, mỗi ô một nhóm, dùng chung thang đo |
| Hairline rule | Kẻ ngang mảnh (2px) dùng thay viền để chia khối |

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
| `RollRate` | `mart_roll_rate.csv` | nguồn x sản phẩm x kênh x bucket đi x bucket đến |

Hai bảng danh mục dùng chung `Dim Channel[Kênh]` và `Dim Product[Sản phẩm]`
gom giá trị từ cả năm bảng fact, nối 1-nhiều để một slicer lọc đồng thời mọi visual.

Semantic model đóng băng ở bản đã kiểm chứng: 7 bảng, 10 quan hệ, 27 measure.
Bản thiết kế này **không yêu cầu thêm measure nào**.

## Tông và chữ ký

**Tông: Editorial Newsroom.** Đọc như một trang báo kinh tế cuối tuần. Chữ dẫn
dắt, một màu nhấn duy nhất, nhiều khoảng trắng.

| Khía cạnh | Giá trị | Chỗ áp dụng cụ thể |
|---|---|---|
| Font hiển thị | Cambria (serif) 28pt cho tên trang, 13pt cho tiêu đề visual | `textClasses.title`, textbox masthead |
| Font thân | Segoe UI 9-11pt | `textClasses.label`, `header`, trục, nhãn dữ liệu |
| Font chữ số | Segoe UI / Segoe UI Semibold | Segoe UI dùng chữ số tabular (mọi chữ số rộng bằng nhau) sẵn, nên cột số thẳng hàng mà không phải đổi sang font monospace |
| Nền trang | Kem `#FAF7F0` | `page.objects.background` |
| Mực | `#0F172A` | chữ chính, chuỗi dữ liệu mặc định |
| Nhấn | Mustard `#D4A30A`, mỗi visual đúng một phần tử | kicker masthead, gạch chân nút trang đang mở, một cột hoặc đường hoặc bong bóng được làm nổi |
| Thang xám | `#5C5349` `#938A7F` `#C2B9AC` | mọi thứ còn lại trong biểu đồ |
| Mật độ | Perfect Fifth 1.500: 28 / 13 / 9pt | 3 bậc chữ, không quá 4 cỡ trên một trang |
| Gridline | Không có trên biểu đồ. Kẻ ngang mảnh 2px dưới masthead và trên chân trang | shape `rectangle` cao 2px |
| Viền | Không viền, không nền cho mọi visual; nền kem xuyên qua | theme `visualStyles` đặt `border.show=false` và `background.show=false` |

Ghi chú về font hiển thị: bản đầu của spec chọn Georgia, đã bị loại vì file font
Georgia thiếu 19 ký tự tiếng Việt (ấ ầ ẩ ẫ ậ ế ề ể ễ ệ ố ồ ổ ỗ ộ ơ ư ớ ứ), kiểm bằng
bảng mã (cmap) của font. Thiếu glyph thì Windows ghép dấu rời lên ký tự gốc nên
"gấp" hiện thành "gâ´p". Cambria đủ cả 19 ký tự và giữ được chất serif editorial.
Muốn đổi font tiêu đề thì phải kiểm lại 19 ký tự này.

**Chữ ký: S6 Highlight-and-grey**, dựng trên nền S2 (tiêu đề serif) và S10 (kẻ
mảnh thay viền).

Một câu: *mọi biểu đồ chỉ có đúng một phần tử màu mustard, phần còn lại nằm trong
thang mực-xám; mọi khối mở đầu bằng một tiêu đề serif Cambria, mọi con số dùng
chữ số tabular.*

Vì sao chọn S6:

- Nó là cách sửa gốc cho lỗi "8 đường cùng màu, legend bị cắt": khi chỉ một chuỗi
  được tô màu, legend không còn là thứ phải đọc để hiểu biểu đồ.
- Nó hợp với tông (bảng *Composing tone + signature* trong `signatures.md` khuyên
  Editorial Newsroom dùng S1, S2, S10, không cấm S6; S6 chỉ dùng đúng một màu nên
  không phá kỷ luật "MỘT màu nhấn").
- Nó buộc mỗi biểu đồ phải trả lời câu hỏi "phần tử nào là thông điệp", nên tiêu
  đề visual viết được thành một câu khẳng định.

Phần tử được nhấn ở từng trang: Stone (trang 1 và 2), Consumer loans tức vay tiêu
dùng trả góp (trang 3), nhóm B1 1-30 (trang 4), nhóm B4 90+ (biểu đồ cơ cấu
trang 1).

## Lưới và khung chung

Khung 1280x720 giữ nguyên. Toàn bộ `x`, `y`, `width`, `height` chia hết cho 8.

**Cột.** Lề 24 mỗi bên, bề ngang dùng được 1232, chia 12 cột rãnh 16:
`12 x 88 + 11 x 16 = 1232`. Cột thứ `c` bắt đầu tại `x = 24 + (c-1) x 104`;
một khối trải `n` cột rộng `104n - 16`. Bề rộng hợp lệ: 88, 192, 296, 400, 504,
608, 712, 816, 920, 1024, 1128, 1232.

**Hàng.** Vùng nội dung bắt đầu tại `y = 160`, 8 hàng cao 56:
hàng thứ `r` bắt đầu tại `y = 160 + (r-1) x 56`; một khối trải `n` hàng cao
`56n - 16`. Chiều cao hợp lệ: 40, 96, 152, 208, 264, 320, 376, 432.

**Dải masthead (giống nhau ở cả 4 trang).**

| Phần tử | x | y | w | h |
|---|---|---|---|---|
| Kicker GIÁM SÁT DANH MỤC... | 24 | 16 | 400 | 24 |
| Điều hướng 4 trang (`pageNavigator`) | 648 | 16 | 608 | 32 |
| Tên trang Cambria 28pt + dòng dẫn 11pt | 24 | 48 | 608 | 88 |
| Slicer `Kênh` (dropdown) | 648 | 56 | 296 | 80 |
| Slicer `Sản phẩm` (dropdown) | 960 | 56 | 296 | 80 |
| Kẻ ngang mảnh | 24 | 144 | 1232 | 2 |

**Chân trang (giống nhau ở cả 4 trang).**

| Phần tử | x | y | w | h |
|---|---|---|---|---|
| Kẻ ngang mảnh | 24 | 616 | 1232 | 2 |
| Ghi chú cảnh báo của trang, Segoe UI 9pt | 24 | 632 | 1232 | 48 |

Hai kẻ ngang cao 2px là ngoại lệ duy nhất của quy tắc chia hết cho 8: một kẻ mảnh
cao 8px thì không còn là kẻ mảnh nữa mà thành một thanh. `x`, `y`, `width` của
chúng vẫn nằm trên lưới 8.

## Bốn trang

Mỗi trang đi lại bảng chọn variant trong file archetype của chính nó, bằng đặc
điểm dữ liệu của trang đó.

### Trang 1. Tổng quan danh mục

Archetype **Executive Summary**, variant **A. Hero-Right**.
Tín hiệu: 4 KPI và đúng một thông điệp chủ đạo có biểu đồ chứng minh
("98,65% danh mục sạch nhưng đuôi B4 đáng kể"). Bảng chọn variant xếp trường hợp
"3-4 KPI và một chỉ số chủ đạo có biểu đồ giải thích" vào A.

- Dải KPI 4 thẻ (816x96) bên trái, biểu đồ chủ đạo cơ cấu nhóm quá hạn (400x208)
  bên phải, đúng hình Z của trang tổng quan.
- Hàng phân tích: tỷ lệ 30+ theo kênh (816x320, 7 cột, sắp giảm dần, Stone màu
  mustard) và bảng theo loại sản phẩm (400x208).
- Thẻ KPI không có sparkline vì model không có trục thời gian; bù lại mỗi thẻ có
  một dòng ngữ cảnh ở phụ đề nói rõ mẫu số.

### Trang 2. Kênh bán và rủi ro

Archetype **Comparative Benchmark**, variant **A. Side-by-Side**.
Tín hiệu: so 7 kênh trên cùng một chỉ số rủi ro, và công cụ phân tích thật sự của
trang là trellis tách theo sản phẩm. Variant C (slope graph) bị loại vì nó cần
hai mốc thời gian mà model không có; variant B (stacked pairs) bị loại vì không
có measure baseline để ghép cặp.

- Scatter `Approval Rate` x `Ever 30 Plus MOB12`, bong bóng theo số hồ sơ, có nhãn
  tên kênh trên từng bong bóng (608x208, cột phải phía trên).
- Bảng phễu duyệt theo kênh (608x208, cột phải phía dưới) ở ô callout của variant A. Theo đúng ghi chú
  trong `comparative-benchmark.md`: khi ô callout chỉ lặp lại con số đã có trong
  biểu đồ bên cạnh thì thay bằng bảng chi tiết gọn. Bảng này thêm `Take-up Rate`,
  thứ scatter không có.
- Trellis 3 ô (608x432, cột trái cao suốt 4 hàng nội dung), mỗi ô một sản phẩm,
  cùng một thang trục giá trị. Đây là luận điểm của trang: so trong cùng sản phẩm
  thì khoảng cách kênh co lại từ 8,1 lần xuống 2,0 lần (Consumer loans) và 4,4 lần
  (Cash loans). Trellis phải cao: Power BI ép mỗi thanh danh mục tối thiểu khoảng
  26px, 7 kênh cần cỡ 182px vùng vẽ. Ô cao 208px chỉ chứa được 3 kênh và hiện thanh
  cuộn dọc, làm hỏng mục đích so sánh, nên bản đầu (trellis nằm ngang dưới đáy) đã
  bị bỏ.

### Trang 3. Vintage theo MOB

Archetype **Analytical Canvas**, variant **C. Small-Multiples-Grid**.
Tín hiệu: câu hỏi của trang chính là so nhiều thực thể cùng một trục (7 kênh trên
cùng trục MOB). Variant B (inline slicers) hợp với số lượng slicer nhưng không
giải quyết được việc 7-8 đường chồng lên nhau; bảng chọn variant xếp trường hợp
"so nhiều thực thể dọc theo các trục giống nhau" vào C.

- Trellis 7 ô (1232x208, lưới 4x2), mỗi ô một kênh, cùng một thang trục giá trị.
  Đây là cách sửa lỗi 8 đường: tách thành 7 ô thì không còn legend để cắt chữ.
- Biểu đồ đường theo sản phẩm (608x208): sau khi bỏ `(không rõ)` còn 3 đường, đọc
  được; Consumer loans màu mustard, hai đường còn lại xám.
- Bảng xếp hạng kênh tại MOB 12 kèm cột mẫu số `Vintage Loans MOB12` (608x208).

### Trang 4. Chuyển nhóm và thu hồi

Archetype **Operational Monitor**, variant **C. Incident-First**.
Tín hiệu: ma trận roll rate là mặt bàn làm việc của người thu hồi nợ, không phải
một ô phụ. Variant A (4-Up Status) cần 4 chỉ số trạng thái mà model không có ở mức
toàn trang; variant B (wallboard) sai ngữ cảnh đọc.

- Ma trận `pivotTable` chiếm trọn bề ngang 1232x208. Ở bản cũ nó nằm trong 608px
  nên bị cuộn ngang; 10 cột giờ hiện hết.
- Cure rate theo nhóm xuất phát (608x208), **đã bỏ dòng `B0 Current`** vì B0 về B0
  không phải là cure. Nhóm B1 1-30 màu mustard.
- Bảng quy mô từng nhóm xuất phát (608x208), giữ cả B0 để thấy mẫu số thật.

Dải trạng thái 4 ô của variant C bị bỏ có chủ đích: không có measure trạng thái
mức trang nào đúng nghĩa (cure rate toàn bộ bị B0 kéo lên 89,6%), và thêm measure
mới nằm ngoài phạm vi được phép sửa.

## Năm lỗi của bản cũ và cách xử lý

| Lỗi | Tên trong `anti-patterns.md` | Cách sửa |
|---|---|---|
| 4 trang dùng chung một khung | `Variant default-bias / uniform-variant pages` | Bốn archetype khác nhau, bốn variant chọn riêng (A, A, C, C), mỗi trang có `variant_rationale` dẫn tín hiệu dữ liệu của chính nó |
| Không có điều hướng | `Multi-page report without navigation` | `pageNavigator` ngang 4 nút ở masthead mọi trang, trang đang mở có gạch chân mustard |
| Line chart 8 đường, legend bị cắt | `In-chart labels vs legend`, `Ignoring small multiples` | Tách thành trellis 7 ô (trang 3) và 3 ô (trang 2); biểu đồ nhiều đường còn lại chỉ 3 chuỗi và dùng S6 |
| Chưa chốt tông và chữ ký | mục *Identity* của `pre-flight-checklist.md` | Tông Editorial Newsroom và chữ ký S6 ghi trong khối YAML, truyền xuống theme, lưới, màu, font, tiêu đề |
| Lưới tự chế 1232 chia đôi 608 | `Pixel drift` | Lưới 12 cột x 8 hàng, bước 104 ngang và 56 dọc, mọi toạ độ chia hết cho 8 |

Hai lỗi phụ sửa kèm: slicer nằm ở góc trên trái (`Slicer in prime real estate`,
nay dời sang phải masthead) và tiêu đề visual mô tả loại biểu đồ thay vì thông
điệp (`Title as chart type`, nay mọi tiêu đề là một câu khẳng định có số).

## Quyết định về nội dung, nói rõ để nghiệm thu

1. **Lọc bỏ `(không rõ)` ở các biểu đồ so sánh kênh và sản phẩm.** Nhãn này nghĩa
   là hợp đồng không khớp `previous_application` nên mọi thuộc tính phân khúc đều
   không biết được. Nhóm này có tỷ lệ 6,72% tại MOB 12, gấp hơn 6 lần kênh xấu
   nhất, nên nếu giữ lại thì trục chung bị nó kéo và 7 kênh thật dồn vào 15%
   chiều dài trục. Bộ lọc đặt ở mức visual, không phải mức trang, nên 4 thẻ KPI
   và ma trận roll rate vẫn tính đủ toàn danh mục. Ghi chú chân trang nói rõ.
2. **Biểu đồ "cơ cấu bucket theo loại sản phẩm" ở trang 1 đổi thành bảng tỷ lệ 30+
   theo loại sản phẩm.** Lý do: B0 chiếm 98,65% nên biểu đồ cột nhóm 4 sản phẩm x
   5 bucket có 20 cột trong đó 16 cột ngắn tới mức không nhìn thấy. Thông điệp
   "phần lớn sạch, có đuôi B4" vẫn do biểu đồ chủ đạo bên phải gánh, còn so sánh
   giữa các sản phẩm chuyển sang dạng bảng đọc được số.
3. **Cure rate trang 4 bỏ dòng `B0 Current`.** Ghi chú cũ đã dặn người đọc tự bỏ
   dòng này; đưa luôn vào bộ lọc thì biểu đồ không còn mời người đọc đọc sai.
4. **Bốn ghi chú cảnh báo được giữ nguyên ý, viết gọn lại** để vừa dải chân trang
   48px: vùng mù FPD30, nhiễu cơ cấu sản phẩm, cure rate dồn vào B1, mẫu số vintage.

## Ràng buộc kỹ thuật bắt buộc

1. Giữ khổ canvas 1280x720 và `displayOption: FitToPage`.
2. Giữ URL `$schema` hiện tại: `visualContainer/2.9.0`, `report/3.3.0`,
   `page/2.1.0`. Ba bản Desktop ghi ra mới hơn chưa được Microsoft publish, tải về
   HTTP 404, nên `powerbi-report-author` sẽ bỏ qua hẳn lớp kiểm JSON Schema.
3. ID trang và visual sinh bằng SHA-1 của `trang|khóa`, không ngẫu nhiên.
4. Mọi tỷ lệ là measure `DIVIDE(SUM(tử), SUM(mẫu))`. Các cột `*_rate` trong mart
   đều `isHidden`.
5. Mẫu số roll rate dùng `[Roll Base Loans]`, không cộng cột `n_from`.
6. `Ever 30 Plus MOB12` cố định `mob = 12` bằng `CALCULATE`.
7. Slicer chỉ lấy từ `Dim Channel[Kênh]` và `Dim Product[Sản phẩm]`.
8. Tên file theme đổi hậu tố mỗi lần sửa nội dung theme, vì Desktop cache theme
   theo tên file.

---

## Canonical design contract

```yaml
Design Brief:
  generated_by: powerbi-report-cli
  contract_version: 1
  mode: brownfield
  design_identity:
    tone: >-
      Editorial Newsroom. Trang bao kinh te cuoi tuan: chu dan dat, nen kem
      #FAF7F0, dung mot mau nhan mustard #D4A30A tren nen muc #0F172A, ty le
      chu 1.500 (28 / 13 / 9pt), khong gridline tren bieu do, khong vien visual,
      chi ke ngang manh 2px chia khoi.
    signature: >-
      S6 Highlight-and-grey pha S2 va S10: moi bieu do chi co dung mot phan tu
      mau mustard, phan con lai nam trong thang muc-xam; moi khoi mo dau bang
      tieu de serif Cambria; moi con so dung chu so tabular Segoe UI; vien
      visual thay bang ke ngang manh.
    current_tone: >-
      Indistinct. Ban cu muon nguyen PALETTES light cua dashboard HTML: xanh
      #2a78d6, cam #eb6834, luc #1baf7a, nen gan trang #f9f9f7, vien #e1e0d9
      bo 6px, Segoe UI toan bo. Nhin nhu theme mac dinh cua Power BI.
    current_signature: none
  archetype: Multi-archetype (Executive + Comparative + Analytical + Operational)
  color_map:
    - measure: Snapshot[Open Loans]
      color: "#0F172A"
      tint: "#C2B9AC"
    - measure: Snapshot[Rate 30+ Coincident]
      color: "#0F172A"
      tint: "#C2B9AC"
      highlight: "#D4A30A"
    - measure: Snapshot[Open Exposure]
      color: "#0F172A"
      tint: "#C2B9AC"
    - measure: Snapshot[Exposure Rate 30+]
      color: "#0F172A"
      tint: "#C2B9AC"
    - measure: Vintage[Ever 30 Plus MOB12]
      color: "#938A7F"
      tint: "#C2B9AC"
      highlight: "#D4A30A"
    - measure: Vintage[Ever 30 Plus Rate]
      color: "#0F172A"
      tint: "#C2B9AC"
      highlight: "#D4A30A"
    - measure: Vintage[Vintage Loans MOB12]
      color: "#0F172A"
      tint: "#C2B9AC"
    - measure: Funnel[Approval Rate]
      color: "#938A7F"
      tint: "#C2B9AC"
      highlight: "#D4A30A"
    - measure: Funnel[Applications]
      color: "#938A7F"
      tint: "#C2B9AC"
    - measure: Funnel[Take-up Rate]
      color: "#0F172A"
      tint: "#C2B9AC"
    - measure: RollRate[Roll Rate]
      color: "#0F172A"
      tint: "#C2B9AC"
    - measure: RollRate[Cure Rate]
      color: "#938A7F"
      tint: "#C2B9AC"
      highlight: "#D4A30A"
    - measure: RollRate[Roll Base Loans]
      color: "#0F172A"
      tint: "#C2B9AC"
    - measure: RollRate[Exposure From]
      color: "#0F172A"
      tint: "#C2B9AC"
  shared_chrome:
    note: >-
      Bon trang dung chung mot dai masthead va mot dai chan trang. Toa do co
      dinh, khong thuoc layout_contract cua tung trang, va khong tinh vao
      content_cell_count.
    placements:
      - id: kicker
        kind: textbox
        rect_xywh: [24, 16, 400, 24]
        text: "GIAM SAT DANH MUC CHO VAY TIEU DUNG"
      - id: page_nav
        kind: pageNavigator
        rect_xywh: [648, 16, 608, 32]
        purpose: "Sua anti-pattern Multi-page report without navigation."
      - id: page_title
        kind: textbox
        rect_xywh: [24, 48, 608, 88]
        text: "Ten trang Cambria 28pt + dong dan Segoe UI 11pt"
      - id: slicer_channel
        kind: slicer
        rect_xywh: [648, 56, 296, 80]
        field_bindings: Dim Channel[Kênh]
        slicer_type: dropdown
      - id: slicer_product
        kind: slicer
        rect_xywh: [960, 56, 296, 80]
        field_bindings: Dim Product[Sản phẩm]
        slicer_type: dropdown
      - id: rule_header
        kind: shape
        rect_xywh: [24, 144, 1232, 2]
      - id: rule_footer
        kind: shape
        rect_xywh: [24, 616, 1232, 2]
      - id: page_caveat
        kind: textbox
        rect_xywh: [24, 632, 1232, 48]
  pages:
    - name: "1. Tổng quan"
      role: landing
      archetype: Executive
      layout_variant: A
      variant_rationale: >-
        Trang co dung 4 KPI va mot thong diep chu dao duy nhat (co cau nhom qua
        han) co bieu do chung minh, dung o "3-4 KPI va mot chi so chu dao co
        bieu do giai thich" cua bang chon variant trong executive-summary.md.
      page_background: "#FAF7F0"
      layout_summary: >-
        Dai 4 the KPI ben trai, bieu do chu dao ben phai, hang phan tich gom
        xep hang kenh va bang theo san pham.
      layout_contract:
        canvas: { width: 1280, height: 720, margin: 24, gutter: 16, snap: 8 }
        grid:
          columns: 12
          rows: 12
          col_pitch_px: 104
          row_pitch_px: 56
          content_origin_px: [24, 160]
          regions:
            kpis:    [1, 3,  9,  5]
            hero:    [9, 3, 13,  7]
            drivers: [1, 5,  9, 11]
            watch:   [9, 7, 13, 11]
        placements:
          - id: kpi_open_loans
            region: kpis
            kind: cardVisual
            slot: 1
            of: 4
            purpose: "Danh muc dang mo lon co nao?"
            field_bindings: Snapshot[Open Loans]
            color_strategy: measure_match
            insight_basis: "Phu de neu mau so: toan bo hop dong dang mo tai thang quan sat gan nhat."
          - id: kpi_rate30
            region: kpis
            kind: cardVisual
            slot: 2
            of: 4
            purpose: "Bao nhieu phan tram dang qua han tu 30 ngay?"
            field_bindings: Snapshot[Rate 30+ Coincident]
            color_strategy: measure_match
            insight_basis: "Phu de neu day la ty le coincident, khong phai vintage."
          - id: kpi_exposure
            region: kpis
            kind: cardVisual
            slot: 3
            of: 4
            purpose: "Du no proxy dang mo la bao nhieu?"
            field_bindings: Snapshot[Open Exposure]
            color_strategy: measure_match
            insight_basis: "Phu de neu don vi tien te goc cua bo du lieu."
          - id: kpi_exposure_rate
            region: kpis
            kind: cardVisual
            slot: 4
            of: 4
            purpose: "Ty le 30+ tinh theo tien khac theo so hop dong bao nhieu?"
            field_bindings: Snapshot[Exposure Rate 30+]
            color_strategy: measure_match
            insight_basis: "Phu de neu mau so la tong du no, so duoc voi the ben trai."
          - id: bucket_mix
            region: hero
            kind: clusteredBarChart
            purpose: "Danh muc phan bo ra sao giua cac nhom qua han?"
            field_bindings: { Category: "Snapshot[dpd_bucket]", Y: "Snapshot[Open Loans]" }
            sort_policy: natural_order
            color_strategy: semantic
            comparison_basis: "B4 90+ so voi B2 31-60 va B3 61-90 cong lai."
          - id: rate_by_channel
            region: drivers
            kind: clusteredBarChart
            purpose: "Kenh nao dang co ty le 30+ cao nhat ngay luc nay?"
            field_bindings: { Category: "Dim Channel[Kênh]", Y: "Snapshot[Rate 30+ Coincident]" }
            sort_policy: value_desc
            color_strategy: semantic
          - id: product_table
            region: watch
            kind: tableEx
            purpose: "Loai san pham nao dang xau hon, va quy mo bao nhieu?"
            field_bindings: ["Dim Product[Sản phẩm]", "Snapshot[Open Loans]", "Snapshot[Rate 30+ Coincident]"]
            sort_policy: value_desc
            color_strategy: none
        space_audit:
          content_cell_count: 96
          placed_cell_count: 96
          empty_cell_pct: 0
          unplaced_regions: []
          largest_region: { name: drivers, pct_of_content: 50 }
          balance_rationale: >-
            Variant A dat hang phan tich (variance snapshot) cao hon hang KPI,
            nen drivers la vung chu dao hop le cua variant. No can cho that: 7
            cot kenh trong 320px cho moi cot 40px, doc duoc nhan. Dai KPI van
            giu 96px du cho gia tri 32pt kem nhan va phu de, bieu do chu dao
            va bang san pham deu giu 400x208, du cho 5 cot bucket va 4 dong bang.
    - name: "2. Kênh bán"
      role: detail
      archetype: Comparative
      layout_variant: A
      variant_rationale: >-
        So 7 kenh tren mot chi so rui ro duy nhat va cong cu phan tich la trellis
        tach theo san pham, dung hinh variant A. Variant C can hai moc thoi gian
        de ve slope graph ma model khong co truc thoi gian; variant B can measure
        baseline de ghep cap, cung khong co.
      page_background: "#FAF7F0"
      layout_summary: >-
        Trellis 3 o theo san pham o cot trai cao suot 8 hang, scatter duyet-rui
        ro va bang pheu xep chong o cot phai.
      layout_contract:
        canvas: { width: 1280, height: 720, margin: 24, gutter: 16, snap: 8 }
        grid:
          columns: 12
          rows: 12
          col_pitch_px: 104
          row_pitch_px: 56
          content_origin_px: [24, 160]
          regions:
            headline: [7, 3, 13,  7]
            context:  [7, 7, 13, 11]
            mix:      [1, 3,  7, 11]
        placements:
          - id: approval_risk_scatter
            region: headline
            kind: scatterChart
            purpose: "Kenh duyet rong co phai kenh rui ro cao khong?"
            field_bindings:
              { Category: "Dim Channel[Kênh]", X: "Funnel[Approval Rate]", Y: "Vintage[Ever 30 Plus MOB12]", Size: "Funnel[Applications]" }
            color_strategy: semantic
            comparison_basis: "Tung kenh so voi 6 kenh con lai tren cung hai truc."
          - id: funnel_table
            region: context
            kind: tableEx
            purpose: "Moi kenh duyet bao nhieu ho so va giu duoc bao nhieu?"
            field_bindings: ["Dim Channel[Kênh]", "Funnel[Applications]", "Funnel[Approval Rate]", "Funnel[Take-up Rate]"]
            sort_policy: value_desc
            color_strategy: none
            callout_value_basis: >-
              Khong phai callout lap so. Bang nay them Take-up Rate, chi tieu
              scatter khong co, nen no tra loi cau hoi khac: duyet roi khach co
              nhan khong.
          - id: risk_by_product_trellis
            region: mix
            kind: clusteredBarChart
            purpose: "Trong cung mot san pham, khoang cach rui ro giua cac kenh con bao nhieu?"
            field_bindings:
              { Category: "Dim Channel[Kênh]", Y: "Vintage[Ever 30 Plus MOB12]", Rows: "Dim Product[Sản phẩm]" }
            sort_policy: value_desc
            color_strategy: semantic
            comparison_basis: "Stone so voi Regional / Local trong Consumer loans; Country-wide so voi Credit and cash offices trong Cash loans."
        space_audit:
          content_cell_count: 96
          placed_cell_count: 96
          empty_cell_pct: 0
          unplaced_regions: []
          largest_region: { name: mix, pct_of_content: 50 }
          balance_rationale: >-
            Trellis la o small multiples cua variant A va la luan diem cua
            trang, nen no duoc lam vung chu dao (608x432). Ba o rong khoang
            192px, moi o cao du cho 7 thanh kenh; o cao 208px chi chua 3 kenh va
            hien thanh cuon doc. Scatter va bang pheu xep chong o cot phai, moi
            khoi 608x208, du cho 7 bong bong co nhan va 7 dong bang kem tieu de.
    - name: "3. Vintage"
      role: detail
      archetype: Analytical
      layout_variant: C
      variant_rationale: >-
        Cau hoi cua trang chinh la so nhieu thuc the doc theo cung mot truc: 7
        kenh tren cung truc MOB 0-37. Do dung la o "comparing many entities along
        similar axes" cua bang chon variant trong analytical-canvas.md. Variant B
        khop so luong slicer nhung de nguyen 7-8 duong chong nhau trong mot khung.
      page_background: "#FAF7F0"
      layout_summary: >-
        Trellis 7 o theo kenh chay het be ngang, ben duoi la duong vintage theo
        san pham va bang xep hang tai MOB 12 kem mau so.
      layout_contract:
        canvas: { width: 1280, height: 720, margin: 24, gutter: 16, snap: 8 }
        grid:
          columns: 12
          rows: 12
          col_pitch_px: 104
          row_pitch_px: 56
          content_origin_px: [24, 160]
          regions:
            trellis: [1, 3, 13,  7]
            product: [1, 7,  7, 11]
            rank:    [7, 7, 13, 11]
        placements:
          - id: vintage_by_channel_trellis
            region: trellis
            kind: lineChart
            purpose: "Kenh nao dung doc som nhat theo tuoi hop dong?"
            field_bindings:
              { Category: "Vintage[mob]", Y: "Vintage[Ever 30 Plus Rate]", Rows: "Dim Channel[Kênh]" }
            color_strategy: measure_match
            comparison_basis: "Bay kenh tren cung mot thang truc gia tri."
          - id: vintage_by_product
            region: product
            kind: lineChart
            purpose: "Loai san pham nao xau di nhanh hon khi so cung MOB?"
            field_bindings:
              { Category: "Vintage[mob]", Series: "Dim Product[Sản phẩm]", Y: "Vintage[Ever 30 Plus Rate]" }
            color_strategy: semantic
          - id: mob12_rank
            region: rank
            kind: tableEx
            purpose: "Tai MOB 12 kenh nao xau nhat, va mau so bao nhieu hop dong?"
            field_bindings: ["Dim Channel[Kênh]", "Vintage[Ever 30 Plus MOB12]", "Vintage[Vintage Loans MOB12]"]
            sort_policy: value_desc
            color_strategy: none
            insight_basis: >-
              Cot mau so Vintage Loans MOB12 ghim cung mob = 12 voi tu so, dung
              bai hoc cua loi cu: moi ty le ghim ngu canh can mot mau so ghim
              cung ngu canh dat ngay canh.
        space_audit:
          content_cell_count: 96
          placed_cell_count: 96
          empty_cell_pct: 0
          unplaced_regions: []
          largest_region: { name: trellis, pct_of_content: 50 }
          balance_rationale: >-
            Variant C noi thang la trellis tro thanh trang chu khong phai mot o
            phu, nen no duoc nua vung noi dung. Hai visual con lai van giu
            608x208: bieu do duong 3 chuoi va bang 7 dong kem tieu de deu vua
            khung, khong cuon.
    - name: "4. Thu hồi"
      role: detail
      archetype: Operational
      layout_variant: C
      variant_rationale: >-
        Nguoi doc trang nay la nguoi dang xu ly ho so qua han, va ma tran roll
        rate chinh la mat ban lam viec, dung o "exception queue is the working
        surface" cua operational-monitor.md. Variant A doi 4 chi so trang thai
        muc trang ma model khong co; variant B la wallboard, sai ngu canh doc.
      page_background: "#FAF7F0"
      layout_summary: >-
        Ma tran roll rate chay het be ngang, ben duoi la cure rate theo nhom xuat
        phat va bang quy mo tung nhom.
      layout_contract:
        canvas: { width: 1280, height: 720, margin: 24, gutter: 16, snap: 8 }
        grid:
          columns: 12
          rows: 12
          col_pitch_px: 104
          row_pitch_px: 56
          content_origin_px: [24, 160]
          regions:
            queue: [1, 3, 13,  7]
            cure:  [1, 7,  7, 11]
            scale: [7, 7, 13, 11]
        placements:
          - id: roll_matrix
            region: queue
            kind: pivotTable
            purpose: "Hop dong o moi nhom qua han thang nay di ve dau thang sau?"
            field_bindings:
              { Rows: "RollRate[from_state]", Columns: "RollRate[to_state]", Values: "RollRate[Roll Rate]" }
            color_strategy: none
          - id: cure_by_bucket
            region: cure
            kind: clusteredBarChart
            purpose: "Nhom nao con kha nang quay ve khong qua han?"
            field_bindings: { Category: "RollRate[from_state]", Y: "RollRate[Cure Rate]" }
            sort_policy: natural_order
            color_strategy: semantic
            comparison_basis: "B1 1-30 so voi B2, B3, B4; dong B0 Current da loc bo vi B0 ve B0 khong phai cure."
          - id: bucket_scale
            region: scale
            kind: tableEx
            purpose: "Moi nhom xuat phat co bao nhieu luot hop dong-thang va bao nhieu du no?"
            field_bindings: ["RollRate[from_state]", "RollRate[Roll Base Loans]", "RollRate[Cure Rate]", "RollRate[Exposure From]"]
            sort_policy: natural_order
            color_strategy: none
            insight_basis: >-
              Mau so Roll Base Loans dat canh Cure Rate de thay ngay cure 7,0%
              cua B3 chi dua tren 7.172 luot, khac han 259.546 luot cua B1.
        space_audit:
          content_cell_count: 96
          placed_cell_count: 96
          empty_cell_pct: 0
          unplaced_regions: []
          largest_region: { name: queue, pct_of_content: 50 }
          balance_rationale: >-
            Variant C noi thang la exception queue chiem nua vung noi dung. Ma tran
            co 1 cot tieu de + 8 cot dich + 1 cot tong, o ban cu nam trong 608px
            nen bi cuon ngang; 1232px la be ngang toi thieu de 10 cot hien het.
            Hai visual ben duoi van giu 608x208, du 4 cot bucket va 5 dong bang.
  interaction_pattern:
    drill_targets: []
    cross_filter_rules: >-
      Mac dinh Filter cho moi cap. Hai slicer dim loc dong thoi ca 5 bang fact
      qua quan he 1-nhieu. Khong dung bookmark, khong dung drillthrough: 4 trang
      da du chua cau chuyen va drillthrough khong co back button thi roi vao
      anti-pattern Drill without breadcrumb.
    navigation: >-
      pageNavigator ngang 4 nut o masthead moi trang. Trang dang mo co gach chan
      mustard 3px o trang thai selected.
  accessibility:
    alt_text_strategy: headline+trend
    contrast_notes: >-
      Muc #0F172A tren kem #FAF7F0 dat khoang 16:1. Xam #5C5349 dat khoang 7:1,
      dung duoc cho chu. Hai bac xam nhat #938A7F (khoang 3.5:1) va #C2B9AC
      (khoang 2.0:1) chi dung cho mang du lieu nen, khong dung cho chu; day la
      lua chon co chu y cua chu ky S6, phan nen phai lui lai de phan mustard
      noi len. Mustard #D4A30A tren kem dat khoang 2.3:1 nen khong bao gio dung
      lam mau chu, chi lam mau mang, va luon kem kenh thu hai: phan tu duoc nhan
      dong thoi dung dau thu tu sap xep hoac co nhan du lieu.
  theme:
    base: custom, ten file CreditPortfolio-Editorial-<hau to>.json
    name_rule: >-
      Truong name ben trong file theme, themeCollection.customTheme.name va
      resourcePackages items name trong report.json phai trung nhau va deu kem
      duoi .json. Doi hau to moi lan sua noi dung theme vi Desktop cache theme
      theo ten file.
    dataColors: ["#0F172A", "#5C5349", "#938A7F", "#C2B9AC", "#D4A30A", "#78716C", "#A8A29E", "#E0D8C9"]
    textClasses:
      callout: { fontFace: "Segoe UI Semibold", fontSize: 32, color: "#0F172A" }
      title:   { fontFace: "Cambria", fontSize: 13, color: "#0F172A" }
      header:  { fontFace: "Segoe UI Semibold", fontSize: 10, color: "#0F172A" }
      label:   { fontFace: "Segoe UI", fontSize: 9, color: "#5C5349" }
    per_visual_overrides:
      - "visualStyles tat background.show va border.show cho moi visual: nen kem xuyen qua."
      - "visualStyles tat visualHeader.show: bo thanh chrome cua Power BI."
      - "cardVisual: accentBar position Top mau muc rong 2px, label dat tren gia tri, outline tat."
      - "slicer: moi slicer khai bao padding VCO 8/8/8/8 vi khai bao bat ky VCO nao se cat padding ke thua tu theme; height 80 = 60 chrome + 8 + 8."
      - "tableEx va pivotTable: stylePreset None, columnHeaders growToFit + autoSizeColumnWidth, grid chi bat ke ngang mau #E3DACB, nen o trung nen kem."
      - "textbox: padding 0/0/0/0, background va border tat."
      - "shape ke ngang: padding 0, outline tat, cao 2px."
      - "moi bieu do: valueAxis.gridlineShow = false va categoryAxis.gridlineShow = false."
      - "moi visual co title: subTitle.show = false de Power BI khong tu sinh phu de ghep ten field."
    user_overrides: >-
      Khong giu gi tu theme cu. Bang mau cu muon tu dashboard/index.html va
      khong con ap dung cho ban Power BI; hai ban tu nay khac tong co chu y,
      ban HTML giu vai tro ban xem nhanh khong can cai gi.
```
