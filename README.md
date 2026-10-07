# Credit Portfolio Monitoring

Giám sát chất lượng danh mục cho vay tiêu dùng trên dữ liệu công khai **Home Credit Default Risk** (Kaggle): 1.040.632 hợp đồng, 13,73 triệu dòng hợp đồng-tháng, từ dữ liệu thô đến bộ chỉ tiêu có tài liệu, khoảng tin cậy cho mọi kết luận, dashboard và memo đề xuất hành động.

**Stack:** Python, DuckDB, SQL (pipeline raw, stg, core, mart kèm 32 data test), Power BI dạng PBIP (Power BI Project: model TMDL, report PBIR, sinh bằng script), dashboard HTML/SVG tĩnh.

**Xem nhanh:** [Kết quả chính](#kết-quả-chính) · [Hai lần soát, hai lần đảo ngược](#hai-lần-soát-hai-lần-đảo-ngược) · [Memo gửi lãnh đạo](docs/insight_memo.md) · [Phương pháp](docs/methodology.md) · [Dashboard trực tiếp](https://yq68.github.io/credit-portfolio-monitoring/dashboard/) · [Bản Power BI](powerbi/README.md)

![Trang Tổng quan danh mục của bản Power BI](docs/screenshots/01-tong-quan.png)

**Xem dashboard trực tiếp:** https://yq68.github.io/credit-portfolio-monitoring/dashboard/

Nguồn là file [`dashboard/index.html`](dashboard/index.html), tự chứa (biểu đồ vẽ sẵn bằng SVG, số liệu nhúng trong file), tải về mở bằng trình duyệt cũng xem được không cần mạng.

## Kết quả chính

Chỉ tiêu rủi ro chính là **tỷ lệ từng quá hạn trên 30 ngày tại MOB 12** (ever 30+@MOB12; MOB là month on book, số tháng kể từ tháng mở hợp đồng): tỷ lệ hợp đồng có ít nhất một tháng quá hạn trên 30 ngày tính đến tháng thứ 12. So các nhóm ở cùng tuổi hợp đồng như vậy gọi là phân tích vintage. Quá hạn đo bằng `SK_DPD_DEF`, cột DPD (days past due, số ngày quá hạn) có ngưỡng trọng yếu của chính bộ dữ liệu. Mọi tỷ lệ đi kèm tử số, mẫu số và khoảng tin cậy 95% viết dạng `[a; b]`.

Mức toàn danh mục: 0,052% [0,047; 0,057] (425 / 818.672). Không gồm nhóm hợp đồng không khớp được hồ sơ, vốn gánh 106 trong 425 ca và chưa giải thích được: 0,039% [0,035; 0,044] (319 / 816.589).

**1. Đợt mở hợp đồng là biến gây nhiễu mạnh nhất: hợp đồng mở càng xa ngày hồ sơ hiện tại càng hay quá hạn.**
Đợt mở (origination cohort) là nhóm 12 tháng của tháng mở hợp đồng, đếm ngược từ ngày khách nộp hồ sơ hiện tại. Tính chung ba sản phẩm, đợt -96 đến -85 có 0,192% [0,161; 0,230] (118 / 61.379), đợt -24 đến -13 có 0,010% [0,007; 0,015] (23 / 224.703). Trong cùng sản phẩm, đợt cũ nhất gấp đợt gần nhất đủ tuổi 9,88 [4,52; 21,56] lần ở vay tiền mặt và 62,17 [15,14; 255,35] lần ở vay tiêu dùng; giữ ở ba cách cắt đợt. Vì kênh và sản phẩm có cơ cấu đợt mở rất khác nhau, các so sánh dưới đây kiểm soát cùng lúc sản phẩm và đợt mở. Không tách được chất lượng giải ngân thật với hiệu ứng chọn mẫu, nên đây là biến cần kiểm soát chứ không phải bằng chứng danh mục đang tốt lên.

**2. Thẻ quay vòng là sản phẩm rủi ro nhất, nhưng khoảng cách chỉ bằng khoảng một nửa số thô.**
Trong cùng đợt mở, thẻ gấp vay tiền mặt 2,29 [1,59; 3,31] lần (gộp Mantel-Haenszel qua đợt), so với 4,85 [3,57; 6,59] lần khi so thô. Giữ ở MOB 6 và MOB 24, ở hai cách cắt đợt khác (2,50 [1,75; 3,59] và 2,75 [1,97; 3,86]) và khi đo cả hai sản phẩm bằng cột không ngưỡng (2,88 [2,48; 3,35]). Vay tiêu dùng so với vay tiền mặt thì không kết luận được: tỷ số chạy từ 0,41 [0,30; 0,56] đến 6,48 [5,75; 7,30] tuỳ định nghĩa và việc có kiểm soát đợt mở.

**3. Sau khi kiểm soát sản phẩm và đợt mở, chỉ Contact center còn trên kỳ vọng một cách bền vững, và nguồn là thẻ mở đã lâu.**
SMR (standardized ratio, tỷ số chuẩn hoá gián tiếp: số ca thực tế chia số ca kỳ vọng nếu kênh có đúng tỷ lệ của từng tầng sản phẩm × đợt mở trên toàn danh mục có nhãn) tại MOB 12: Contact center 1,65 [1,21; 2,18] (48 ca / 29,1 kỳ vọng), giữ ở mọi cách cắt đợt, mọi mốc MOB và theo định nghĩa giữa (`SK_DPD` trên 30 ngày ở tháng còn kỳ phải trả). 41 trên 47 ca thẻ của kênh là thẻ mở từ tháng -60 trở về trước; thẻ mở từ tháng -35 trở về sau có 0 ca trên 1.959. Stone 1,36 [1,08; 1,69] theo định nghĩa chính nhưng 1,06 [0,95; 1,19] theo định nghĩa giữa: không bền. Credit and cash offices 0,89 [0,68; 1,14]: không còn khác kỳ vọng. Mỗi SMR so một kênh với kỳ vọng của chính nó, không chia SMR hai kênh cho nhau.

**4. Cửa sổ thu hồi đóng nhanh sau 30 ngày quá hạn đầu tiên.**
Cure rate (tỷ lệ hợp đồng đang quá hạn quay về không quá hạn ngay tháng sau) là 57,7% [57,5; 57,9] ở nhóm quá hạn 1 đến 30 ngày (B1, 111.822 / 193.814 lượt hợp đồng-tháng), còn 27,8% [25,7; 30,0] ở B2 (31 đến 60 ngày, 457 / 1.642) và 1,2% [0,96; 1,54] ở B4 (trên 90 ngày, 68 / 5.589). Trong cùng đợt mở, cure B1 vẫn gấp B2 2,09 [1,94; 2,27] lần.

**Đề xuất**, cân theo quy mô bằng chứng (tử số chỉ vài chục đến vài trăm ca): rà soát thẻ cũ của Contact center thay vì siết duyệt thẻ mới; nếu thử nghiệm một quy tắc duyệt thẻ thì đo bằng chỉ tiêu sớm ever 1+@MOB6 (thẻ Contact center: nền 15,99%, cần 1.890 hợp đồng mỗi nhánh), vì đo bằng ever 30+@MOB12 cần 69.359 hợp đồng mỗi nhánh, gấp 14,95 lần quy mô nhóm; thử liên hệ sớm cho hợp đồng vừa rơi vào B1, ngẫu nhiên hoá theo hợp đồng (phát hiện cure tăng 5 điểm phần trăm từ nền 67,9% cần 1.308 hợp đồng mỗi nhánh). Chi tiết: [docs/insight_memo.md](docs/insight_memo.md#4-đề-xuất-hành-động).

## Hai lần soát, hai lần đảo ngược

**Lần một: định nghĩa quá hạn.** Bản đầu của project đo quá hạn bằng `SK_DPD` vì cột này cho tử số dày hơn. Một lần soát độc lập cho thấy cột đó đo phần lớn là khoản dư lẻ còn treo sau kỳ trả cuối: ở các tháng trả góp đang mở thuộc nhóm quá hạn trên 90 ngày theo `SK_DPD`, 95,8% có `SK_DPD_DEF = 0`, 99,8% không còn kỳ nào phải trả và dư nợ trung vị bằng 0. Định nghĩa chính được chuyển sang `SK_DPD_DEF`, mọi kết luận được tính lại, và ba kết luận của bản đầu không còn đứng vững: vay tiêu dùng rủi ro hơn vay tiền mặt nhiều lần, khoảng cách kênh phần lớn do sản phẩm, và một phân khúc nhỏ gánh phần lớn số ca. `SK_DPD` được giữ làm phân tích độ nhạy. Chi tiết: [docs/methodology.md](docs/methodology.md#4-quyết-định-đã-đảo-ngược-định-nghĩa-quá-hạn).

**Lần hai: biến gây nhiễu đợt mở.** Lần soát độc lập thứ hai phát hiện tháng mở hợp đồng (`dim_loan.first_open_month`) là biến gây nhiễu mạnh chưa được kiểm soát: thẻ đợt cũ nhất quá hạn gấp 39,09 [14,19; 107,69] lần thẻ đợt gần nhất đủ tuổi, và 77,2% thẻ của Credit and cash offices mở từ tháng -35 trở về sau, so với 21,1% ở Contact center. So kênh chỉ theo sản phẩm là so thẻ mới với thẻ cũ. Cách kiểm soát: thêm cột `origination_cohort` (nhóm 12 tháng) vào `mart.vintage`, dựng vintage theo đợt mở, chuẩn hoá SMR theo sản phẩm × đợt mở, gộp tỷ số sản phẩm bằng Mantel-Haenszel qua đợt, thử hai cách cắt đợt khác và thêm định nghĩa giữa làm độ nhạy thứ hai. Ba kết luận của bản trước không còn đứng vững: Credit and cash offices tốt hơn kỳ vọng, Stone trên kỳ vọng, vay tiêu dùng ngang vay tiền mặt. Chi tiết: [docs/methodology.md](docs/methodology.md#510-đợt-mở-hợp-đồng-biến-gây-nhiễu-thứ-hai).

## Bản Power BI

Bốn trang, mỗi trang mở bằng một câu kết luận có số.

| | |
|---|---|
| ![Tổng quan danh mục](docs/screenshots/01-tong-quan.png) | ![Kênh bán và rủi ro](docs/screenshots/02-kenh-ban.png) |
| **1. Tổng quan:** cơ cấu nhóm quá hạn của danh mục đang mở, tỷ lệ 30+ theo hợp đồng và theo dư nợ trên cùng một tập hợp đồng. | **2. Kênh bán:** tỷ lệ duyệt và rủi ro theo kênh, đọc trong cùng sản phẩm. |
| ![Vintage theo MOB](docs/screenshots/03-vintage.png) | ![Chuyển nhóm và thu hồi](docs/screenshots/04-thu-hoi.png) |
| **3. Vintage:** đường cong ever 30+ theo tuổi hợp đồng, theo đợt mở, sản phẩm và kênh. | **4. Thu hồi:** ma trận chuyển nhóm quá hạn và cure rate theo từng nhóm. |

Model sinh hoàn toàn bằng script nên diff và review được trên git. Cách mở, cấu trúc và quy tắc sửa: [powerbi/README.md](powerbi/README.md). Lý do thiết kế và các bẫy kỹ thuật: [docs/methodology.md](docs/methodology.md#6-bản-power-bi).

## Câu hỏi kinh doanh

1. Kênh, sản phẩm nào có approval rate (tỷ lệ duyệt hồ sơ) cao nhưng rủi ro sớm cũng cao?
2. Khi so cùng MOB, nhóm hợp đồng nào xấu đi nhanh hơn?
3. Khách quá hạn chuyển bucket (nhóm số ngày quá hạn: B0 là 0 ngày, B1 1 đến 30, B2 31 đến 60, B3 61 đến 90, B4 trên 90) ra sao qua từng tháng? Bucket nào có cure rate thấp nhất và cần ưu tiên thu hồi?
4. Phân khúc nào nên siết hoặc nới chính sách, và thử nghiệm nào đủ cỡ mẫu để kiểm chứng?

## Các quyết định phân tích quan trọng

- **Định nghĩa quá hạn chính là `SK_DPD_DEF`, `SK_DPD` chỉ là độ nhạy.** Cột độ nhạy mang hậu tố `_no_threshold` trên mọi bảng. [Chi tiết](docs/methodology.md#4-quyết-định-đã-đảo-ngược-định-nghĩa-quá-hạn)
- **So sánh kênh và sản phẩm phải kiểm soát cùng lúc cơ cấu sản phẩm và đợt mở.** Mỗi kênh bán một rổ sản phẩm khác nhau và có cơ cấu đợt mở khác nhau, nên so gộp sẽ nhầm cơ cấu thành hiệu ứng kênh. Dẫn dắt bằng SMR theo sản phẩm × đợt mở, kiểm tra bằng tỷ số trong từng tầng và Mantel-Haenszel. Cặp Stone so với Country-wide được gộp qua ba tầng sản phẩm (vay tiêu dùng, vay tiền mặt, thẻ): 1,80 [1,34; 2,42]; chỉ qua vay tiêu dùng và thẻ là 1,88 [1,40; 2,52]. [Chi tiết](docs/methodology.md#55-so-sánh-kênh-phải-kiểm-soát-cơ-cấu-sản-phẩm), [đợt mở](docs/methodology.md#510-đợt-mở-hợp-đồng-biến-gây-nhiễu-thứ-hai)
- **Đợt mở cắt mỗi 12 tháng, kiểm bằng hai cách cắt khác.** Mốc 12 tháng là một năm tương đối, định trước, không chọn theo dữ liệu; cách cắt 3 nhóm của người soát và cách cắt 24 tháng cho cùng kết luận. [Chi tiết](docs/methodology.md#510-đợt-mở-hợp-đồng-biến-gây-nhiễu-thứ-hai)
- **Mẫu số vintage loại hợp đồng thiếu lịch sử đầu (cờ `is_partial_history`, 93.751 hợp đồng)** vì MOB của chúng thấp hơn thực tế; cờ cắt trái có sẵn bỏ sót 45.581 trường hợp như vậy. [Chi tiết](docs/methodology.md#52-vintage-loại-hợp-đồng-có-lịch-sử-không-đầy-đủ)
- **Hợp đồng dừng sớm có ngày kết thúc trong hồ sơ được coi là đã đóng (`closed_inferred`, 89.414 hợp đồng).** "Đã đóng" là đã dừng quan sát, không nhất thiết đã trả xong: 21 trên 50 ca vay tiêu dùng của nhóm này từng 30+ tại MOB 12 vẫn đang 30+ ở tháng cuối. Quy tắc là suy luận; đổi quy tắc làm mẫu số MOB 12 đổi khoảng 10% nhưng không đổi kết luận. [Chi tiết](docs/methodology.md#53-hợp-đồng-dừng-sớm-closed_inferred-và-unknown)
- **FPD30 (first payment default 30, kỳ trả đầu tiên chưa trả đủ sau 30 ngày) đo trên hợp đồng đã kích hoạt: 0,011% [0,009; 0,013] (99 / 895.744).** 77.884 trên 77.885 hồ sơ duyệt không có dòng kỳ 1 là hồ sơ không có lịch trả, tức chưa giải ngân, nên không thuộc mẫu số. Tử số quá nhỏ để xếp hạng kênh. [Chi tiết](docs/methodology.md#51-fpd30-đo-trên-hợp-đồng-đã-kích-hoạt)
- **Một phân khúc đã xét kỹ và bị loại khỏi kết luận.** Khách mới × lãi suất cao trong vay tiêu dùng chỉ có ý nghĩa ở MOB 12 (1,60 [1,11; 2,31]) và mất ý nghĩa sau hiệu chỉnh Bonferroni, dù đếm 12 tổ hợp ([0,94; 2,74]) hay đếm đủ 144 phép so đã xem qua 3 mốc MOB, 2 định nghĩa và có hoặc không điều kiện kênh ([0,82; 3,13]). [Chi tiết](docs/methodology.md#59-phân-khúc-rủi-ro-cao-đã-xét-không-còn-đứng-vững)

Ngoài ra: mẫu số theo độ chín của hợp đồng ([5.4](docs/methodology.md#54-vintage-mẫu-số-theo-độ-chín)), cách tách cắt phải khỏi mất dữ liệu trong roll rate ([5.7](docs/methodology.md#57-roll-rate-tách-cắt-phải-khỏi-mất-dữ-liệu)) và cỡ mẫu thử nghiệm ([5.8](docs/methodology.md#58-cỡ-mẫu-cho-thử-nghiệm)).

## Cách đảm bảo số đúng

- **Một nguồn số duy nhất.** `scripts/compute_findings.py` đọc kho ở chế độ chỉ đọc và ghi [`data/export/findings.json`](data/export/findings.json) (xuống dòng LF trên mọi hệ điều hành): mọi tỷ lệ kèm tử số, mẫu số và khoảng tin cậy (Wilson cho tỷ lệ, log Katz cho tỷ số, Byar cho SMR, Greenland-Robins cho Mantel-Haenszel). README, memo, dashboard và Power BI trích số từ file này. Phần đợt mở được đếm lại bằng một truy vấn độc lập từ `core` và script dừng nếu lệch `mart.vintage`. Chạy lại cho 5 CSV và `findings.json` giống hệt từng byte.
- **Câu chữ có số sinh từ `findings.json` và được kiểm.** `scripts/headlines.py` sinh mọi tiêu đề, dòng phụ và ghi chú của 4 trang, mỗi con số kèm đường dẫn khóa nguồn. `scripts/check_headlines_sync.py` tính lại từng con số từ `findings.json`, báo lỗi nếu câu còn chữ số không rõ nguồn, và so câu chữ trong `dashboard/index.html` và PBIR với đầu ra của `headlines.py`.
- **32 data test** trong `sql/tests/`, chạy sau mỗi lần build: 26 test mức `error` (fail thì pipeline dừng: grain không trùng, tử số không vượt mẫu số, mỗi hàng ma trận roll rate cộng bằng 1, cờ 30+ khớp cột DPD của đúng định nghĩa, bảng chính và bảng độ nhạy đếm cùng một tập tháng, đối chiếu mart với `core`/`stg` bằng một đường đếm độc lập, kể cả theo từng đợt mở) và 6 test mức `warn` cho thực tế dữ liệu đã biết và chấp nhận. [Chi tiết](docs/methodology.md#data-test)
- **Cộng tử số, cộng mẫu số rồi mới chia**, không lấy trung bình các tỷ lệ. Ví dụ tại MOB 12, trung bình 8 tỷ lệ theo kênh cho 0,698%, cách đúng cho 0,052%. Nguyên tắc áp dụng cho cả SQL, dashboard và mọi measure Power BI (`DIVIDE(SUM(tử), SUM(mẫu))`). [Chi tiết](docs/methodology.md#3-nguyên-tắc-tính-tỷ-lệ-và-thống-kê)
- **Ba lớp kiểm tra bản Power BI** trước khi mở Desktop: script bắt xung đột tên trong model, `powerbi-report-author validate` cho cấu trúc PBIR, Power BI Modeling MCP server cho cú pháp TMDL; sau đó reload và chụp từng trang để bắt lỗi số sai mà file vẫn mở bình thường.

## Giới hạn

- **Tử số mỏng.** 425 ca từng 30+ tại MOB 12 trên toàn danh mục. Nhiều so sánh giữa cặp kênh hay phân khúc không đủ ý nghĩa thống kê; chúng được ghi là không kết luận được thay vì dẫn số.
- **Nhóm "(không rõ)" chưa giải thích được.** 48.794 hợp đồng không khớp được hồ sơ; tại MOB 12 nhóm chỉ là 0,25% mẫu số (2.083 hợp đồng) nhưng gánh 106 trên 425 ca. Con số mỏng hơn vẻ ngoài: 46.178 hợp đồng của nhóm (94,6%) bị loại khỏi vintage vì thiếu lịch sử đầu, vintage của nhóm chỉ dựa trên 2.605 hợp đồng, và quy tắc `closed_inferred` không áp được cho nhóm (cần ngày kết thúc trong hồ sơ); đối xử như nhóm có hồ sơ thì tỷ lệ là 4,35% thay vì 5,09%. Mọi tổng toàn danh mục được báo kèm tổng không gồm nhóm này. Hai thẻ KPI của danh mục đang mở bỏ 110 hợp đồng thiếu dư nợ ước lượng, chứa 24 trên 159 ca 30+ và toàn bộ thuộc nhóm này; bỏ hẳn nhóm cũng ra 0,094% (130 / 137.611).
- **`closed_inferred` là suy luận** từ cột `DAYS_TERMINATION`, mà mô tả chính thức gọi là ngày kết thúc dự kiến.
- **Không có LGD (loss given default, tỷ lệ tổn thất khi vỡ nợ) hay tổn thất thật.** Project đo tần suất quá hạn, không đo tiền mất. Exposure (dư nợ) là ước lượng gồm cả lãi, đơn vị tiền không phải VND.
- **Không có thời gian lịch.** `MONTHS_BALANCE` là tháng tương đối so với ngày nộp hồ sơ của từng khách. Vintage theo đợt mở vì vậy dùng tháng mở tương đối, không phải tháng giải ngân theo lịch: hai hợp đồng cùng đợt có thể giải ngân ở hai năm lịch khác nhau. Không nói được danh mục đang xấu đi hay tốt lên, không tách được xu hướng theo đợt thành chất lượng thật hay chọn mẫu, và không quy được cỡ mẫu thử nghiệm ra số tháng.
- **Tỷ lệ tuyệt đối không đại diện.** Danh mục chỉ gồm các khoản vay trước đây của khách sau đó có hồ sơ mới, tức đã qua một lần chọn lọc. Chỉ so sánh tương đối giữa phân khúc là đáng tin.
- **Mẫu số vintage phần lớn là hợp đồng đã kết thúc.** Tại MOB 12 chỉ 37,7% mẫu số (308.901 / 818.672) còn quan sát thật; tỷ lệ này là 95,2% ở thẻ, 52,8% ở vay tiền mặt, 24,8% ở vay tiêu dùng, nên so sánh sản phẩm được kiểm lại ở MOB 6. Tại MOB 24 chỉ còn 9,2% (70.635 / 763.989), nên đoạn đuôi đường cong không được diễn giải.
- **Kiểm soát nhiễu mới hai yếu tố, và yếu tố thứ hai là hậu nghiệm.** So sánh kênh đã kiểm soát sản phẩm và đợt mở nhưng chưa kiểm soát kỳ hạn, số tiền vay hay đặc điểm khách. Đợt mở được đưa vào sau khi người soát đã nhìn dữ liệu, nên các con số có kiểm soát đợt mở là kiểm tra lại, không phải kiểm định xác nhận. Dữ liệu quan sát không chứng minh được quan hệ nhân quả, nên đề xuất đều đi kèm thử nghiệm.

Danh sách đầy đủ: [docs/methodology.md](docs/methodology.md#7-những-gì-project-chưa-làm-được) và [docs/data_notes.md](docs/data_notes.md).

## Kiến trúc dữ liệu

```
CSV (Kaggle)
 └─ raw    dữ liệu gốc, chỉ đổi tên cột sang chữ thường          scripts/load_raw.py
     └─ stg    đặt tên cột dễ hiểu, giá trị đặc biệt thành NULL    sql/stg/
         └─ core   bảng dùng chung                                 sql/core/
             │     int_loan_month   gộp hợp đồng trả góp và thẻ về một cấu trúc
             │     dim_loan         1 dòng / hợp đồng: sản phẩm, kênh, mốc vòng đời, end_state, cờ cắt trái
             │     fct_loan_month   1 dòng / hợp đồng / tháng: DPD chính và độ nhạy, bucket, MOB, exposure
             └─ mart   5 bảng tổng hợp, mỗi bảng trả lời một câu hỏi   sql/mart/
                   funnel_by_channel    approval rate, take-up rate
                   fpd_by_segment       FPD30, hồ sơ duyệt chưa kích hoạt
                   vintage              ever 30+ theo MOB và đợt mở hợp đồng
                   roll_rate            ma trận chuyển bucket, cure rate (kèm bảng độ nhạy, không xuất CSV)
                   portfolio_snapshot   cơ cấu bucket của danh mục đang mở tại tháng gần nhất
                 └─ findings.json   mọi con số kết luận kèm khoảng tin cậy    scripts/compute_findings.py
```

Định nghĩa 15 chỉ tiêu (M01 đến M15): [docs/metric_dictionary.md](docs/metric_dictionary.md). Mô tả từng mart: [sql/mart/README.md](sql/mart/README.md).

## Cài đặt và chạy

Yêu cầu: Python 3.11 trở lên (gói `kaggle` 2.2.4 yêu cầu từ 3.11), khoảng 5,8 GB ổ trống (file zip 0,72 GB, CSV giải nén 2,11 GB, kho DuckDB 3,00 GB), tài khoản Kaggle đã chấp nhận điều khoản cuộc thi. Bản Power BI cần Power BI Desktop, chỉ chạy trên Windows; pipeline và dashboard HTML chạy trên mọi hệ điều hành.

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

kaggle auth login                     # đăng nhập Kaggle một lần
python scripts/download_data.py       # hoặc tải tay và giải nén CSV vào data/raw/
python scripts/load_raw.py            # nạp CSV vào data/warehouse.duckdb
python scripts/build.py               # build stg, core, 5 mart và chạy 32 data test
python scripts/compute_findings.py    # tính mọi con số kết luận, ghi data/export/findings.json
python scripts/build_dashboard.py     # dựng dashboard/index.html, xuất 5 CSV vào data/export/
python scripts/check_headlines_sync.py  # kiểm câu chữ có số của HTML và PBIR khớp findings.json
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

kaggle auth login
python scripts/download_data.py
python scripts/load_raw.py
python scripts/build.py
python scripts/compute_findings.py
python scripts/build_dashboard.py
python scripts/check_headlines_sync.py
```

`compute_findings.py` và `build_dashboard.py` chỉ đọc kho (`read_only`), không ghi vào kho. Thứ tự là bắt buộc: `build.py` dựng kho, `compute_findings.py` ghi `findings.json`, rồi `build_dashboard.py` đọc cả kho lẫn `findings.json` (câu chữ có số trên dashboard sinh từ file này qua `scripts/headlines.py`).

Bản Power BI: 5 CSV đã có sẵn trong repo, nhưng PBIP **chưa mở được ngay sau khi clone**: trước khi mở `powerbi/CreditPortfolio.pbip`, sửa tham số `DataFolder` trong `powerbi/CreditPortfolio.SemanticModel/definition/expressions.tmdl` thành đường dẫn tuyệt đối tới `data/export` trên máy. Dựng lại model và report (tùy chọn): `python scripts/build_pbip_model.py`, `python scripts/build_pbip_report.py`, rồi kiểm bằng `python scripts/check_model_names.py powerbi/CreditPortfolio.SemanticModel`. Chi tiết: [powerbi/README.md](powerbi/README.md).

Tự viết query: `python scripts/query.py <file.sql>`, ví dụ `python scripts/query.py sql/explore/01_profile.sql`.

Ghi chú Windows: nếu PowerShell chặn kích hoạt venv, chạy `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. Đường dẫn thư mục có dấu tiếng Việt không cần chỉnh gì, các script đã tự ép UTF-8 khi in ra màn hình.

## Cấu trúc thư mục

```
dashboard/
  index.html                 dashboard tĩnh 4 trang, mở thẳng bằng trình duyệt
  README.md                  nguồn dữ liệu của dashboard, cách dựng lại bằng Power BI từ data/export/
data/
  export/                    được commit; dữ liệu gốc và kho DuckDB thì không
    findings.json            nguồn số duy nhất cho mọi kết luận
    mart_*.csv               5 CSV tổng hợp từ 5 mart (Power BI đọc)
docs/
  insight_memo.md            memo gửi lãnh đạo: kết luận, bằng chứng, đề xuất, giới hạn
  methodology.md             phương pháp, quyết định đã đảo ngược, thống kê, giới hạn
  metric_dictionary.md       định nghĩa, công thức, edge case của 15 chỉ tiêu
  data_notes.md              giả định về dữ liệu và nhật ký kiểm tra
  screenshots/               ảnh 4 trang Power BI
powerbi/
  CreditPortfolio.pbip       file mở bằng Power BI Desktop
  CreditPortfolio.SemanticModel/   model dạng TMDL
  CreditPortfolio.Report/          report dạng PBIR
  _brief/report-spec.md      bản chốt thiết kế 4 trang
  README.md                  cách mở, 3 lớp kiểm tra, quy tắc khi sửa
scripts/
  download_data.py           tải dữ liệu từ Kaggle
  load_raw.py                nạp CSV vào DuckDB
  build.py                   build stg, core, mart và chạy data test
  compute_findings.py        tính mọi con số kết luận kèm khoảng tin cậy, ghi findings.json
  headlines.py               câu chữ có số của dashboard và Power BI, sinh từ findings.json
  build_dashboard.py         dựng dashboard/index.html, xuất 5 CSV
  check_headlines_sync.py    kiểm mọi số trong câu chữ truy được về findings.json, HTML và PBIR khớp nhau
  build_pbip_model.py        sinh semantic model TMDL
  build_pbip_report.py       sinh report PBIR
  check_model_names.py       bắt xung đột tên trong model trước khi mở Desktop
  rename_screenshots.py      đổi tên ảnh chụp trang về tên ASCII cố định
  query.py                   chạy một file SQL, in kết quả
sql/
  00_setup.sql               schema và macro dùng chung
  stg/  core/  mart/         các tầng model
  tests/                     32 data test, mỗi file trả về các dòng vi phạm
  explore/                   query khám phá dữ liệu
DATA_NOTICE.md               điều khoản dữ liệu
LICENSE                      giấy phép MIT cho mã nguồn
requirements.txt             duckdb, kaggle
```

## Nguồn dữ liệu và giấy phép

- Mã nguồn phát hành theo giấy phép MIT: [LICENSE](LICENSE). Giấy phép không áp dụng cho dữ liệu.
- Dữ liệu: [Home Credit Default Risk](https://www.kaggle.com/competitions/home-credit-default-risk), Kaggle, 2018, sử dụng theo điều khoản của cuộc thi. Repo không chứa dữ liệu gốc, chỉ chứa các bảng tổng hợp ở `data/export/` (mỗi dòng là một tổ hợp phân khúc, không phải một hợp đồng). Chi tiết: [DATA_NOTICE.md](DATA_NOTICE.md).
- Đây là project portfolio cá nhân tự làm trên dữ liệu công khai, không phải số liệu của tổ chức nào. Đơn vị tiền là đơn vị thô của bộ dữ liệu Kaggle, không phải VND.
