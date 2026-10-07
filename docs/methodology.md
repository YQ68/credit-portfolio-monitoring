# Phương pháp phân tích

Tài liệu này tóm tắt cách project được dựng và lý do đằng sau các quyết định phân tích chính: dữ liệu có gì và thiếu gì, pipeline kiểm thử ra sao, mẫu số của từng chỉ tiêu được chọn thế nào, các phép thống kê đi kèm, một quyết định đã phải đảo ngược, và những gì project chưa làm được.

Ba tài liệu đi kèm giữ chi tiết đầy đủ:

- [`metric_dictionary.md`](metric_dictionary.md): định nghĩa, công thức và edge case của từng chỉ tiêu, đánh mã M01 đến M15.
- [`data_notes.md`](data_notes.md): giả định về dữ liệu và nhật ký kiểm tra (ngày, kiểm tra gì, kết quả, quyết định).
- [`insight_memo.md`](insight_memo.md): memo gửi ban lãnh đạo, gồm kết luận, bằng chứng và đề xuất thử nghiệm.

**Nguồn số.** Mọi con số trong tài liệu này lấy từ `data/export/findings.json`, file do `scripts/compute_findings.py` sinh ra từ kho DuckDB sau khi chạy `scripts/build.py` (chạy hai lần cho file giống hệt từng byte), hoặc tính lại được từ 5 file CSV trong `data/export/`. Số thập phân viết theo kiểu Việt Nam: dấu phẩy là thập phân, dấu chấm phân cách hàng nghìn. `[a; b]` là khoảng tin cậy 95%.

## Thuật ngữ

| Viết tắt | Nghĩa |
|---|---|
| DPD (days past due) | Số ngày quá hạn của hợp đồng trong tháng quan sát |
| Ngưỡng trọng yếu | Mức nợ quá hạn tối thiểu để được tính là quá hạn. Cột `SK_DPD_DEF` của dữ liệu bỏ qua khoản nợ giá trị thấp, tức đã áp một ngưỡng như vậy |
| Bucket | Nhóm DPD: B0 = 0 ngày, B1 = 1 đến 30, B2 = 31 đến 60, B3 = 61 đến 90, B4 = trên 90 |
| 30+ | DPD lớn hơn 30 ngày, tức từ B2 trở lên |
| MOB (month on book) | Số tháng kể từ tháng hợp đồng bắt đầu mở. Tháng mở là MOB 0 |
| Vintage, ever 30+@MOBn | Tỷ lệ hợp đồng từng có ít nhất một tháng 30+ tính đến MOB n, so các nhóm ở cùng tuổi hợp đồng |
| Ever 1+@MOBn | Như trên nhưng với ngưỡng DPD lớn hơn 0, dùng làm chỉ tiêu sớm |
| FPD30 (first payment default 30) | Kỳ trả đầu tiên chưa trả đủ sau 30 ngày kể từ ngày đến hạn |
| Roll rate | Tỷ lệ hợp đồng chuyển từ bucket này sang bucket khác sau một tháng |
| Cure rate | Tỷ lệ hợp đồng đang quá hạn quay về B0 ở tháng sau |
| Grain | Một dòng của bảng đại diện cho cái gì, ví dụ "1 hợp đồng trong 1 tháng" |
| Exposure | Số tiền còn phải thu của hợp đồng, ở đây là ước lượng (proxy) |
| Confounding (nhiễu do cơ cấu) | Hai nhóm khác nhau về kết quả vì khác nhau ở một yếu tố thứ ba, không phải vì bản thân yếu tố đang so |
| CI (confidence interval, khoảng tin cậy 95%) | Khoảng giá trị mà tỷ lệ thật có khả năng nằm trong, xét theo cỡ mẫu. Tử số càng nhỏ khoảng càng rộng |
| Tỷ số (rate ratio) | Tỷ lệ của nhóm A chia tỷ lệ của nhóm B. "Có ý nghĩa" nghĩa là khoảng tin cậy 95% của tỷ số không chứa 1 |
| SMR (standardized ratio, tỷ số chuẩn hoá) | Số ca quan sát chia số ca kỳ vọng nếu kênh có đúng tỷ lệ của từng sản phẩm mà nó bán. SMR trên 1 là kênh xấu hơn mức sản phẩm của nó |
| MH (Mantel-Haenszel) | Cách gộp tỷ số của nhiều tầng (ở đây là nhiều sản phẩm) thành một tỷ số chung, trọng số theo cỡ mẫu của từng tầng |
| Đợt mở (origination cohort) | Nhóm 12 tháng của tháng mở hợp đồng (`first_open_month`), tính tương đối so với ngày nộp hồ sơ hiện tại của từng khách, không phải tháng lịch |
| Phân tầng | Chia dữ liệu thành các tầng (ví dụ sản phẩm × đợt mở) rồi so trong từng tầng, để biến tạo tầng không còn gây nhiễu |
| Nghịch lý Simpson | So sánh gộp đổi độ lớn hoặc đổi chiều khi tách theo một biến thứ ba |
| Định nghĩa giữa | Độ nhạy thứ hai: trả góp đo bằng `SK_DPD` trên 30 chỉ ở tháng còn kỳ phải trả, thẻ giữ `SK_DPD_DEF` |
| Bonferroni | Hiệu chỉnh khi xem nhiều so sánh cùng lúc: nới rộng khoảng tin cậy theo số so sánh để giảm khả năng bắt nhầm một kết quả may rủi |

## 1. Dữ liệu và giới hạn

### Nguồn và quy mô

Dữ liệu là bộ [Home Credit Default Risk](https://www.kaggle.com/competitions/home-credit-default-risk/data) công khai trên Kaggle (2018), dùng cho mục đích học tập. Dữ liệu gốc không được commit; chỉ 5 file CSV tổng hợp và `findings.json` ở `data/export/` được commit (mỗi dòng CSV là một tổ hợp phân khúc, không phải một hợp đồng). Điều khoản dữ liệu: [`DATA_NOTICE.md`](../DATA_NOTICE.md).

| Đối tượng | Quy mô |
|---|---|
| Hồ sơ vay trước đây, sau khi lọc hồ sơ nhập trùng | 1.660.953, trong đó 1.036.044 `Approved` |
| Hợp đồng có lịch sử tháng (`core.dim_loan`) | 1.040.632 (936.325 trả góp, 104.307 thẻ tín dụng) |
| Dòng hợp đồng × tháng (`core.fct_loan_month`) | 13.730.112 |
| Cửa sổ thời gian | tháng tương đối từ `-96` đến `-1` |

Bảng `bureau` và `bureau_balance` (lịch sử tín dụng tại tổ chức khác) chưa được dùng.

### Thời gian là tương đối, không phải tháng lịch

`MONTHS_BALANCE` đếm tháng so với ngày nộp hồ sơ hiện tại của **từng khách**, `-1` là tháng gần nhất. Hai khách có cùng `MONTHS_BALANCE = -5` có thể ở hai tháng lịch khác nhau. Hệ quả:

- Không dựng được xu hướng theo tháng lịch, nên không nói được danh mục đang xấu đi hay tốt lên.
- Không dựng được vintage theo tháng giải ngân theo lịch. Thay vào đó dựng vintage theo đợt mở tương đối (tháng mở so với ngày hồ sơ hiện tại, [mục 5.10](#510-đợt-mở-hợp-đồng-biến-gây-nhiễu-thứ-hai)) cùng các cohort theo thuộc tính hợp đồng: kênh, sản phẩm, loại khách, nhóm lãi suất, nhóm kỳ hạn.
- "Snapshot hiện tại" là tháng `-1` của mỗi hợp đồng.
- Không quy được cỡ mẫu thử nghiệm ra số tháng tuyển ([mục 5.8](#58-cỡ-mẫu-cho-thử-nghiệm)).

### Danh mục là mẫu đã qua một lần sống sót

Danh mục trong project là **các khoản vay trước đây của những khách sau đó đã nộp hồ sơ mới**, không phải toàn bộ danh mục của công ty. Khách quay lại vay đã qua một vòng chọn lọc, nên tỷ lệ tuyệt đối thấp hơn thực tế. Mọi kết luận vì vậy dựa trên **so sánh tương đối giữa các phân khúc**, không dựa trên mức tuyệt đối.

### Cắt trái, cắt phải và hợp đồng thiếu hồ sơ

- **Cắt phải:** lịch sử dừng ở tháng `-1`, hợp đồng còn mở chưa có kết quả cuối (`end_state = 'censored'`, 144.421 hợp đồng). Hợp đồng có lịch sử dừng **trước** tháng `-1` khi trạng thái cuối vẫn là mở được tách thành hai nhãn `closed_inferred` và `unknown`, xem [mục 5.3](#53-hợp-đồng-dừng-sớm-closed_inferred-và-unknown).
- **Cắt trái:** hợp đồng mở trước cửa sổ dữ liệu có MOB tính ra thấp hơn thực tế. Xử lý ở [mục 5.2](#52-vintage-loại-hợp-đồng-có-lịch-sử-không-đầy-đủ).
- **Thiếu hồ sơ:** 48.794 hợp đồng không khớp được hồ sơ nào trong `previous_application`. Chúng không bị loại mà mang nhãn `(không rõ)` ở mọi cột phân khúc. Nhóm này nhỏ nhưng gánh một phần lớn bất thường số ca quá hạn, xem [mục 5.6](#56-nhóm-không-rõ).
- **Exposure:** khoản trả góp không có cột dư nợ, nên exposure là proxy `số kỳ còn lại × tiền trả mỗi kỳ` (gồm cả lãi). 3,41% dòng trả góp thiếu giá trị này. Đơn vị tiền không phải VND. Exposure chỉ dùng để so sánh tương đối.
- **Không có tổn thất thật.** Dữ liệu không có LGD (loss given default, tỷ lệ tổn thất khi vỡ nợ), số tiền xoá nợ hay số tiền thu hồi, nên project chỉ đo tần suất quá hạn, không đo tổn thất.

Chi tiết từng giả định và lần kiểm tra: [`data_notes.md`](data_notes.md).

## 2. Kiến trúc pipeline và kiểm thử

### Bốn tầng và một file kết quả

```
CSV Kaggle
  raw    nạp nguyên trạng, chỉ đổi tên cột sang chữ thường (scripts/load_raw.py)
  stg    đặt tên cột dễ hiểu, đổi giá trị đặc biệt (365243, XNA, XAP) thành NULL
  core   bảng dùng chung cho mọi phân tích
           int_loan_month   gộp hợp đồng trả góp và thẻ về một cấu trúc
           dim_loan         1 dòng / hợp đồng: phân khúc, mốc vòng đời, end_state, cờ cắt trái
           fct_loan_month   1 dòng / hợp đồng / tháng: DPD (chính và độ nhạy), bucket, MOB, exposure
  mart   5 bảng tổng hợp, mỗi bảng trả lời một câu hỏi kinh doanh, cộng 1 bảng độ nhạy
           funnel_by_channel        approval rate, take-up rate (M12)
           fpd_by_segment           FPD30 (M11)
           vintage                  ever 30+ theo MOB và đợt mở (M08, M15)
           roll_rate                ma trận chuyển bucket, cure rate (M09, M10)
           roll_rate_no_threshold   như trên, bucket theo SK_DPD, chỉ để đo độ nhạy
           portfolio_snapshot       cơ cấu bucket của danh mục đang mở tại tháng -1 (M02, M06)
  findings.json   mọi con số dùng cho kết luận, kèm khoảng tin cậy (scripts/compute_findings.py)
```

Toàn bộ chạy trên DuckDB bằng SQL thuần. `scripts/build.py` build các tầng theo thứ tự khai báo trong danh sách `MODELS` rồi chạy test. `scripts/compute_findings.py` đọc kho ở chế độ chỉ đọc, một luồng, và ghi `data/export/findings.json` với khóa sắp xếp cố định, số làm tròn 10 chữ số. README, memo, dashboard và bản Power BI trích số từ file này thay vì chép tay. Mô tả từng mart: [`sql/mart/README.md`](../sql/mart/README.md).

Lý do chia tầng:

- **Một định nghĩa nằm ở một chỗ.** "Hợp đồng đang mở" chỉ được định nghĩa một lần (macro `core.is_open_status` trong `sql/00_setup.sql`). Mọi mart đọc DPD từ `core.fct_loan_month`, nên khi định nghĩa quá hạn đổi ([mục 4](#4-quyết-định-đã-đảo-ngược-định-nghĩa-quá-hạn)) phần logic chính chỉ phải sửa ở một file.
- **Lần ngược được khi số sai.** Mỗi tầng có test riêng, nên một con số sai ở mart có thể truy về đúng tầng gây ra.

### Data test

Có 32 test trong `sql/tests/`. Mỗi test là một câu SQL trả về **các dòng vi phạm**: 0 dòng là đạt. Dòng đầu file khai báo mức độ:

- `-- severity: error` (26 test): fail thì pipeline dừng. Gồm kiểm grain không trùng, tử số không vượt mẫu số, tỷ lệ trong khoảng 0 đến 1, mỗi hàng ma trận roll rate cộng lại bằng 1, cờ 30+ khớp với cột DPD, nhãn `end_state` hợp lệ, bảng roll rate chính và bảng độ nhạy đếm cùng một tập tháng xuất phát, và các test đối chiếu.
- `-- severity: warn` (6 test): chỉ cảnh báo, dùng cho thực tế dữ liệu đã biết và đã chấp nhận, ví dụ 48.794 hợp đồng thiếu hồ sơ (`dim_loan__missing_application`) hay 375 cặp tháng bị hở trên 13,7 triệu dòng (`fct_loan_month__month_gaps`).

Loại test có giá trị nhất là **đối chiếu bằng một đường độc lập**: đếm lại cùng một thứ từ `core` hoặc `stg` rồi so với mart. Ví dụ `vintage__mob0_matches_core` kiểm tra mẫu số vintage tại MOB 0 bằng đúng số hợp đồng đủ điều kiện đếm thẳng từ `core.dim_loan` (944.937); `vintage__cohort_matches_core` làm tương tự cho từng đợt mở, tính đợt bằng một phép chia khác. `fpd_by_segment__reconciles_with_source` đếm lại cả mẫu số lẫn tử số FPD30 theo version nhỏ nhất bằng một truy vấn viết riêng.

Hai quy tắc đi cùng test:

- **Không loại dòng âm thầm.** Dòng bị loại khỏi mẫu số phải được đếm và ghi ở comment đầu file SQL hoặc ở metric dictionary. Tháng không có tháng kế tiếp vào trạng thái `Missing` của roll rate, không bị bỏ.
- **Ghi grain ở đầu mỗi file SQL**, kèm mã chỉ tiêu và câu hỏi kinh doanh.

## 3. Nguyên tắc tính tỷ lệ và thống kê

### Cộng tử, cộng mẫu rồi mới chia

Mọi mart lưu **số đếm** (tử số và mẫu số, các cột `n_*`) rồi mới tính cột tỷ lệ. Khi gom lên một mức cao hơn, chỉ được **cộng tử số, cộng mẫu số rồi chia**. Không lấy trung bình cột tỷ lệ, vì các dòng có mẫu số khác nhau.

Ví dụ trên vintage tại MOB 12, cắt theo 8 nhóm kênh (gồm `(không rõ)` và `Khác`):

| Cách tính | Kết quả |
|---|---|
| Trung bình cộng 8 tỷ lệ theo kênh | 0,698% |
| Cộng tử số, cộng mẫu số rồi chia | 0,052% (425 / 818.672) |

Chênh hơn 13 lần vì nhóm `(không rõ)` chỉ có 2.083 hợp đồng với tỷ lệ 5,089% nhưng được tính ngang hàng với kênh có 326.652 hợp đồng.

Nguyên tắc này áp dụng xuyên suốt: SQL mẫu trong metric dictionary, dashboard HTML, và mọi measure Power BI (viết dạng `DIVIDE(SUM(tử), SUM(mẫu))`, các cột `*_rate` của mart bị ẩn). Mọi tỷ lệ được trình bày kèm tử số và mẫu số.

### Khoảng tin cậy và so sánh

Tử số của project mỏng: toàn danh mục chỉ có 425 hợp đồng từng 30+ tại MOB 12. Vì vậy mọi tỷ lệ dẫn trong kết luận đi kèm khoảng tin cậy 95%, và mọi so sánh hai nhóm đi kèm khoảng tin cậy của tỷ số. Các phép tính nằm trong `scripts/compute_findings.py`, chỉ dùng thư viện chuẩn của Python.

| Đại lượng | Phương pháp | Ghi chú |
|---|---|---|
| Tỷ lệ | Khoảng Wilson | Đúng hơn công thức gần đúng chuẩn khi tỷ lệ gần 0, đúng tình huống của project |
| Tỷ số hai tỷ lệ | Khoảng log theo Katz | Nếu một tử số bằng 0, cộng 0,5 vào mọi ô (hiệu chỉnh Haldane) và gắn cờ `haldane` |
| So kênh có kiểm soát sản phẩm | SMR (chuẩn hoá gián tiếp), khoảng Byar | Kỳ vọng tính bằng tỷ lệ của từng tầng sản phẩm × đợt mở trên toàn danh mục có nhãn (bản chỉ theo sản phẩm giữ để đối chiếu); không tính bất định của tỷ lệ tham chiếu. Không chia SMR của hai kênh cho nhau |
| Gộp tỷ số qua sản phẩm | Mantel-Haenszel, phương sai Greenland-Robins | Cặp kênh chỉ qua tầng có ít nhất 1.000 hợp đồng mỗi bên; tỷ số sản phẩm gộp qua mọi đợt mở |
| Nhiều tổ hợp phân khúc | Khoảng Bonferroni | Nới khoảng theo số tổ hợp đủ mẫu đã xem |
| Cỡ mẫu thử nghiệm | Hai tỷ lệ độc lập, hai phía, alpha 0,05, power 0,8, chia 1:1 | Duyệt: thay đổi tương đối 20%. Thu hồi: tăng tuyệt đối 3, 5, 10 điểm phần trăm, đơn vị là hợp đồng |

Ba quy ước đi kèm:

- **Ngưỡng diễn giải 1.000.** Ô có mẫu số dưới 1.000 không được diễn giải, và script không tính tỷ số khi một bên dưới ngưỡng.
- **Tử số dưới khoảng 10 thì ghi "không kết luận được"** thay vì dẫn tỷ số, vì khoảng Byar và hiệu chỉnh Haldane chỉ là xấp xỉ ở vùng đó.
- **Chỉ so sánh định trước mới được làm tiêu đề.** Script tính mọi cặp kênh và mọi tổ hợp phân khúc để không giấu gì, nhưng tiêu đề chỉ dùng các so sánh đã định trước: tỷ số sản phẩm, SMR theo kênh, cặp Stone so với Country-wide, và phân khúc khách mới × lãi suất cao. Phần còn lại là mô tả. Kiểm soát đợt mở là hậu nghiệm: nó kiểm tra lại các so sánh định trước, không thêm so sánh mới làm tiêu đề.

## 4. Quyết định đã đảo ngược: định nghĩa quá hạn

Dữ liệu có hai cột số ngày quá hạn cho cả khoản trả góp và thẻ: `SK_DPD` và `SK_DPD_DEF`. Phiên bản đầu của project dùng `SK_DPD`. Một lần soát độc lập cho thấy cột này đo phần lớn là khoản dư lẻ còn treo sau kỳ trả cuối, không phải nợ quá hạn theo nghĩa rủi ro tín dụng. Định nghĩa chính đã được chuyển sang `SK_DPD_DEF` ngày 2026-10-04 và mọi kết luận được tính lại. Mục này ghi lại quyết định ban đầu, bằng chứng, định nghĩa mới và những kết luận đã đổi.

### 4.1 Định nghĩa ban đầu và lý do khi đó

Ngày 2026-09-20, project chọn `SK_DPD` làm cột DPD chính và để `SK_DPD_DEF` làm chỉ tiêu phụ. Lý do khi đó là độ dày tử số: theo `SK_DPD_DEF`, ever 30+@MOB12 chỉ 0,053% (395 / 744.208), cắt theo kênh còn vài chục ca; theo `SK_DPD` là 0,659% (4.906 / 744.208), đủ dày để so phân khúc. Tiêu chí chọn vì vậy là lượng tín hiệu thống kê, chưa phải nội dung mà mỗi cột đo.

### 4.2 Bằng chứng định nghĩa ban đầu đo sai

Đo trên các tháng hợp đồng trả góp (POS) đang mở, xếp bucket theo `SK_DPD`:

| Bucket theo `SK_DPD` | Số tháng | Tỷ lệ có `SK_DPD_DEF = 0` | Tỷ lệ không còn kỳ nào phải trả | Trung vị dư nợ ước lượng |
|---|---|---|---|---|
| B2 31-60 | 7.942 | 66,8% | 72,2% | 0 |
| B3 61-90 | 4.993 | 93,5% | 94,6% | 0 |
| B4 90+ | 108.970 | 95,8% | 99,8% | 0 |

Ở bucket B4, 99,8% tháng không còn kỳ nào phải trả và dư nợ trung vị bằng 0: hợp đồng đã trả hết lịch nhưng chưa được đóng, và bộ đếm `SK_DPD` tiếp tục chạy trên một khoản dư rất nhỏ. Cùng những tháng đó, 95,8% có `SK_DPD_DEF = 0`. Ở thẻ tín dụng, tháng B4 theo `SK_DPD` có 97,7% `SK_DPD_DEF = 0`, dư nợ trung vị 209 đơn vị tiền. Không có dòng nào `SK_DPD_DEF` lớn hơn `SK_DPD`, đúng với việc cột thứ hai là cột thứ nhất sau khi bỏ khoản nợ nhỏ.

Hệ quả trực tiếp: đuôi B4 dày của danh mục và phần lớn khác biệt giữa sản phẩm theo `SK_DPD` là sản phẩm của khoản dư lẻ. Vay tiêu dùng trả góp có nhiều hợp đồng kỳ hạn ngắn trả hết lịch nên chịu ảnh hưởng nặng nhất.

### 4.3 Định nghĩa mới và căn cứ

Mô tả cột chính thức, trích nguyên văn từ `data/raw/HomeCredit_columns_description.csv`:

| Bảng | Cột | Mô tả chính thức |
|---|---|---|
| `POS_CASH_balance` | `SK_DPD` | "DPD (days past due) during the month of previous credit" |
| `POS_CASH_balance` | `SK_DPD_DEF` | "DPD during the month with tolerance (debts with low loan amounts are ignored) of the previous credit" |
| `credit_card_balance` | `SK_DPD` | "DPD (Days past due) during the month on the previous credit" |
| `credit_card_balance` | `SK_DPD_DEF` | "DPD (Days past due) during the month with tolerance (debts with low loan amounts are ignored) of the previous credit" |

`SK_DPD_DEF` là DPD sau khi bỏ qua khoản nợ giá trị thấp, tức đúng khái niệm ngưỡng trọng yếu mà bộ phận rủi ro dùng để không gọi một khoản dư vài đơn vị tiền là nợ quá hạn. Ngưỡng do Home Credit đặt, không được công bố, và không biết là ngưỡng tuyệt đối hay tương đối.

Quyết định:

- **Định nghĩa chính là `SK_DPD_DEF`**, nằm ở các cột gốc `dpd`, `dpd_bucket`, `is_30_plus`, `is_90_plus`, `n_ever_30_plus`, `n_30_plus`. Dashboard và Power BI đọc tên cột gốc nên tự chuyển sang định nghĩa mới.
- **`SK_DPD` chỉ còn là phân tích độ nhạy**, gọi là "không áp ngưỡng trọng yếu", ở các cột hậu tố `_no_threshold` trên mọi bảng, và bảng `mart.roll_rate_no_threshold`.
- Cặp cột `*_tolerant` cũ bị bỏ vì nay trùng cột chính.

### 4.4 Kết luận đã đổi ra sao

Số cũ đo trên mẫu số cũ (trước khi có nhãn `closed_inferred`, [mục 5.3](#53-hợp-đồng-dừng-sớm-closed_inferred-và-unknown)); số mới đo trên mẫu số hiện tại.

| Kết luận | Số cũ, theo `SK_DPD` | Số mới, theo `SK_DPD_DEF` | Trạng thái |
|---|---|---|---|
| Ever 30+@MOB12 toàn danh mục | 0,659% (4.906 / 744.208) | 0,052% [0,047; 0,057] (425 / 818.672) | Thấp hơn khoảng 12 lần; trên cùng mẫu số mới, `SK_DPD` cho 0,637% (5.215 / 818.672) |
| Vay tiêu dùng so với vay tiền mặt | 0,886% so với 0,127%, "gấp bảy lần" | 0,029% so với 0,032%, tỷ số 0,90 [0,68; 1,19] | Không còn khác biệt; sau lần soát thứ hai là không kết luận được ([mục 5.10](#510-đợt-mở-hợp-đồng-biến-gây-nhiễu-thứ-hai)) |
| Sản phẩm rủi ro nhất | Vay tiêu dùng | Thẻ quay vòng, gấp 4,85 [3,57; 6,59] lần vay tiền mặt; 2,29 [1,59; 3,31] trong cùng đợt mở | Đổi |
| Khoảng cách kênh Stone so với Credit and cash offices | 8,1 lần thô, co lại còn 2,0 và 4,4 lần trong cùng sản phẩm, "phần lớn do sản phẩm" | Thô 1,73 [1,24; 2,41]; trong thẻ 20,36 [8,55; 48,49], chỉ 22 ca, mô tả | Cơ cấu sản phẩm che bớt chứ không tạo ra khoảng cách; phần còn lại trùng phần lớn với đợt mở ([mục 5.10](#510-đợt-mở-hợp-đồng-biến-gây-nhiễu-thứ-hai)) |
| Phân khúc tập trung rủi ro trong vay tiêu dùng | 14,0% hợp đồng gánh 33,7% số ca, gấp 3,1 lần | Tỷ số 1,60 [1,11; 2,31], mất ý nghĩa sau Bonferroni [0,94; 2,74] | Không còn |
| Cure rate B1 / B2 / B3 / B4 | 50,1% / 17,3% / 7,0% / 2,0% | 57,7% / 27,8% / 15,6% (dưới ngưỡng mẫu) / 1,2% | Ý chính còn, số đổi |
| B1 rơi tiếp sang B2 | 4,302% (11.166 / 259.546) | 0,709% (1.375 / 193.814) | B1 hiếm khi rơi tiếp |
| 30+ của danh mục đang mở | 0,405% (585 / 144.421) | 0,110% (159 / 144.421) | Mức giảm, thứ hạng kênh đổi |
| Đuôi B4 của danh mục đang mở | 438 hợp đồng, gần gấp ba B2 + B3 gộp | 56 hợp đồng, bằng 0,54 lần B2 + B3 (103) | Không còn |
| FPD30 là chặn dưới vì 77.885 hồ sơ duyệt không có dòng kỳ 1 | | 77.884 trên 77.885 hồ sơ đó không có lịch trả, tức không kích hoạt | Lập luận bị bác ([mục 5.1](#51-fpd30-đo-trên-hợp-đồng-đã-kích-hoạt)) |

Theo `SK_DPD`, nhóm cũ (Stone hoặc Country-wide × khách mới × lãi suất cao) gánh 33,7% số ca với tỷ số 2,72 [2,55; 2,89]; theo `SK_DPD_DEF` cùng nhóm đó chỉ còn 22,2% số ca và tỷ số 1,53 [1,05; 2,24]. Phần chênh là khoản dư lẻ: nhóm lãi suất cao trong vay tiêu dùng có nhiều hợp đồng ngắn hạn trả hết lịch.

Cột độ nhạy vẫn có giá trị như một phép kiểm: dư nợ 30+ của danh mục đang mở gần như không đổi giữa hai định nghĩa (0,301% so với 0,312% dư nợ), đúng với việc phần 30+ chỉ có theo `SK_DPD` là khoản rất nhỏ. Kết luận nào chỉ đứng được theo `SK_DPD` thì không được dùng.

### 4.5 Lần soát thứ hai: biến gây nhiễu đợt mở

Sau khi đổi định nghĩa, một lần soát độc lập thứ hai tiếp tục phát hiện một lỗi cùng loại: một biến chưa được kiểm soát làm sai so sánh. Tháng mở hợp đồng tương đối (`first_open_month`) liên quan mạnh tới quá hạn (thẻ đợt cũ nhất gấp đợt gần nhất đủ tuổi 39,09 [14,19; 107,69] lần) và phân bố rất khác giữa các kênh. Cách kiểm soát: thêm cột `origination_cohort` vào `mart.vintage`, dựng vintage theo đợt, phân tầng sản phẩm × đợt cho SMR và Mantel-Haenszel, thử ba cách cắt đợt, và thêm định nghĩa giữa làm độ nhạy thứ hai. Hệ quả: Credit and cash offices không còn tốt hơn kỳ vọng, Stone trên kỳ vọng không còn bền, vay tiêu dùng so với vay tiền mặt không kết luận được; thẻ rủi ro nhất, Contact center trên kỳ vọng và cure B1 so với B2 vẫn đứng. Chi tiết: [mục 5.10](#510-đợt-mở-hợp-đồng-biến-gây-nhiễu-thứ-hai).

## 5. Các quyết định phân tích

### 5.1 FPD30 đo trên hợp đồng đã kích hoạt

- **Định nghĩa:** kỳ 1 theo lịch trả gốc (`installment_number = 1`, version nhỏ nhất khác 0, vì version 0 là thẻ tín dụng), trả chưa đủ 95% số tiền trong 30 ngày sau hạn. Mẫu số là hợp đồng có kỳ 1 đến hạn trước thời điểm quan sát ít nhất 30 ngày.
- **Kết quả:** 0,011% [0,009; 0,013] (99 / 895.744). Biến thể theo ngày (có lần trả kỳ 1 trễ quá 30 ngày): 0,058% [0,054; 0,064] (523 / 895.744). Theo sản phẩm: vay tiền mặt 0,013% (38 / 287.914), vay tiêu dùng 0,010% (58 / 603.511). Thẻ không có trong mẫu số.
- **Lập luận cũ bị bác.** Phiên bản trước gọi 0,011% là "chặn dưới", với giả định 77.885 hồ sơ được duyệt mà không có dòng kỳ 1 là hợp đồng xấu bỏ hẳn kỳ đầu và biến khỏi mẫu số. Kiểm tra lại cho thấy 77.884 trên 77.885 hồ sơ đó không có lịch trả (`DAYS_FIRST_DUE` là 365243 hoặc trống): được duyệt nhưng không giải ngân hoặc chưa kích hoạt (vay tiền mặt 24.116, vay tiêu dùng 18.445, thẻ 35.323). Chỉ 1 hồ sơ có lịch trả mà không có dòng kỳ 1. Mart nay đếm hai nhóm ở hai cột riêng `n_approved_not_activated` và `n_approved_scheduled_no_installment`.
- **Sửa lỗi version.** Code cũ cộng tiền trả qua mọi version của kỳ 1, ngược với tài liệu. 18.903 hợp đồng có từ 2 version kỳ 1; ở 18.595 hợp đồng, cùng một lần trả được ghi lặp ở mỗi version còn số tiền phải trả bị tách giữa các version, nên code cũ phồng tiền đã trả. Sửa xong, tử số theo số tiền vẫn là 99, theo ngày từ 524 thành 523.
- **Hệ quả:** FPD30 là số đo hợp lệ trên hợp đồng đã kích hoạt, nhưng tử số quá nhỏ để xếp hạng kênh. Trục rủi ro chính vẫn là ever 30+@MOB12; chỉ tiêu sớm cho thử nghiệm là ever 1+@MOB6 ([mục 5.8](#58-cỡ-mẫu-cho-thử-nghiệm)).

### 5.2 Vintage: loại hợp đồng có lịch sử không đầy đủ

- **Vấn đề:** cờ cắt trái `is_left_truncated` (tháng quan sát đầu trùng tháng sớm nhất của bảng) không bắt hết hợp đồng mở trước cửa sổ dữ liệu. Hợp đồng như vậy có MOB thấp hơn thực tế, nên một lần quá hạn ở tuổi 18 tháng bị ghi vào MOB thấp và làm đầu đường cong vống lên.
- **Bằng chứng:** tại MOB 0, 76.197 hợp đồng trả góp (8,17%) đã trả trên 0 kỳ, tức đã chạy trước khi dữ liệu bắt đầu. Cờ cắt trái chỉ bắt được 30.616 trong số đó, bỏ sót 45.581.
- **Lựa chọn:** thêm `dim_loan.installments_paid_at_open` và cờ `is_partial_history` (cắt trái hoặc đã trả trên 0 kỳ tại MOB 0), gồm 93.751 hợp đồng. Mẫu số vintage loại nhóm này và nhóm `never_open` (4.029, không có MOB 0); hai nhóm giao nhau 2.085, tổng loại 95.695, còn 944.937 trên 1.040.632 hợp đồng.
- **Hệ quả:** nhóm bị loại không phân bố đều giữa các kênh, nên giữ lại sẽ làm lệch so sánh kênh. Test `dim_loan__partial_history_flag` giữ cờ này đúng định nghĩa.

### 5.3 Hợp đồng dừng sớm: `closed_inferred` và `unknown`

- **Vấn đề:** 183.144 hợp đồng có lịch sử dừng trước tháng `-1` khi trạng thái cuối vẫn là mở. Phiên bản trước gọi cả nhóm là `unknown` và mô tả là "dừng sớm 1 đến 3 tháng", tức một dạng cắt phải. Mô tả đó sai: nhóm tách làm hai và không hợp đồng nào dừng ở tháng `-5` đến `-16`.

  | Nhóm | Hợp đồng | Đặc điểm |
  |---|---|---|
  | Dừng ở tháng `-17` hoặc sớm hơn, toàn POS | 76.575 | 74.270 có `DAYS_TERMINATION`, trung vị còn 1 kỳ; 2.305 còn lại không có |
  | Dừng ở tháng `-2` đến `-4`, POS và thẻ | 106.569 | POS: 13.767 có `DAYS_TERMINATION`, 58.719 không có (trung vị còn 9 kỳ). Thẻ: 1.377 có, 32.706 không có |

- **Bằng chứng:** ở hợp đồng POS có hồ sơ, `DAYS_TERMINATION` đã qua ở 99,96% hợp đồng `closed` và trùng tháng `Completed` (trung vị lệch 0,0 tháng); ở hợp đồng `censored`, 92,2% là 365243 (chưa kết thúc), ở thẻ là 99,1%. Ở nhóm dừng từ tháng `-17` trở về trước, 74.270 trên 74.294 hợp đồng có hồ sơ có ngày kết thúc, trung vị 0,9 tháng sau dòng cuối. Tháng ngay trước `Completed` của hợp đồng `closed` cũng có trung vị còn 1 kỳ, giống hệt nhóm này.
- **Quy tắc:** hợp đồng dừng trước tháng `-1`, trạng thái cuối vẫn mở, hồ sơ có `DAYS_TERMINATION` thì nhận nhãn `closed_inferred` (89.414 hợp đồng) và vào mẫu số vintage như hợp đồng đã đóng. Phần còn lại giữ nhãn `unknown` (93.730) và chỉ vào mẫu số tại MOB n khi `max_mob >= n`. Chọn trường khách quan `DAYS_TERMINATION` thay vì quy tắc "còn 0 kỳ thì coi là đóng", vì quy tắc 0 kỳ bỏ sót phần lớn nhóm dừng từ tháng `-17` (trung vị còn 1 kỳ) và lại gắn nhãn đóng cho hợp đồng dừng ở `-2` đến `-4` chưa có ngày kết thúc.
- **"Đã đóng" không có nghĩa là đã trả xong.** `closed_inferred` là hợp đồng dừng quan sát mà hồ sơ có ngày kết thúc. Trong 50 ca vay tiêu dùng thuộc nhãn này từng 30+ tại MOB 12, 21 ca vẫn đang 30+ ở tháng quan sát cuối.
- **Suy luận, không phải xác nhận.** Mô tả chính thức của `DAYS_TERMINATION` là "expected termination", không phải ngày kết thúc thực. Hành vi dữ liệu cho thấy nó hoạt động như ngày kết thúc thực, nhưng đây là suy luận.
- **Độ nhạy:** lựa chọn quy tắc làm mẫu số MOB 12 đổi tới khoảng 10% nhưng không đổi tỷ lệ quá khoảng tin cậy và không đổi thứ hạng sản phẩm.

  | Quy tắc mẫu số | Ever 30+@MOB12 toàn danh mục | Vay tiêu dùng | Thẻ | Độ nhạy `SK_DPD`, toàn danh mục |
  |---|---|---|---|---|
  | Đang dùng: `closed_inferred` coi như đóng | 0,052% (425 / 818.672) | 0,029% (153 / 530.476) | 0,155% | 0,637% |
  | Quy tắc cũ, chỉ `Completed` là đóng | 0,053% (395 / 744.208) | 0,027% (124 / 459.716) | 0,156% | 0,659% |
  | Quy tắc cũ cộng mọi hợp đồng dừng sớm còn 0 kỳ | 0,055% (423 / 764.266) | 0,030% (144 / 478.698) | 0,156% | 0,673% |

### 5.4 Vintage: mẫu số theo độ chín

- **Vấn đề:** hợp đồng mới chạy 4 tháng chưa thể biết có quá hạn ở MOB 12 hay không. Hợp đồng tất toán ở tháng thứ 3 thì kết quả đã chốt.
- **Phương án đã cân nhắc** (cùng định nghĩa tử số, khác mẫu số): (A) hợp đồng đã biết kết quả đến MOB n; (B) mẫu số cố định là toàn bộ 944.937 hợp đồng; (C) chỉ hợp đồng còn quan sát đủ đến MOB n.
- **Lựa chọn:** phương án A, hợp đồng vào mẫu số tại MOB n khi `max_mob >= n` hoặc `end_state` là `closed` hay `closed_inferred`. B ngầm coi hợp đồng chưa đủ tuổi là tốt nên ép phẳng đường cong; C loại toàn bộ hợp đồng tất toán sớm (nhóm khách tốt) nên thổi phồng đường cong.
- **Hệ quả:** ở MOB cao, phần lớn mẫu số là hợp đồng đã đóng. Tại MOB 12 có 308.901 trên 818.672 hợp đồng (37,7%) còn quan sát đủ; tại MOB 24 chỉ 70.635 trên 763.989 (9,2%). Mart lưu thêm `n_observed_full` và `n_closed_early` (có test `n_observed_full + n_closed_early = n_loans`), và đoạn đuôi đường cong không được diễn giải nếu không in kèm hai cột này.
- **Ảnh hưởng tới so sánh sản phẩm.** Tỷ lệ quan sát đủ khác hẳn giữa sản phẩm: tại MOB 12, thẻ 95,2% (57.821 / 60.705), vay tiền mặt 52,8% (118.966 / 225.408), vay tiêu dùng 24,8% (131.347 / 530.476). Vì vậy so sánh sản phẩm ở MOB 12 pha lẫn khác biệt rủi ro với mức pha loãng bởi hợp đồng đóng sớm. Phép kiểm: tại MOB 6, nơi tỷ lệ quan sát đủ gần nhau hơn (thẻ 99,0%, tiền mặt 84,0%, tiêu dùng 78,8%), thẻ vẫn 0,073% [0,057; 0,094] so với vay tiền mặt 0,014% [0,010; 0,020] và vay tiêu dùng 0,012% [0,010; 0,015]. Khoảng cách sản phẩm vì vậy không chỉ do pha loãng.

### 5.5 So sánh kênh phải kiểm soát cơ cấu sản phẩm

- **Vấn đề:** mỗi kênh bán một rổ sản phẩm khác nhau. Stone bán 97,3% vay tiêu dùng, Credit and cash offices bán 85,3% vay tiền mặt và 14,7% thẻ, Contact center bán 57,2% thẻ (cơ cấu tại MOB 12). Trong khi đó rủi ro sản phẩm chênh nhau tới gần 5 lần. So số thô sẽ nhầm cơ cấu sản phẩm thành hiệu ứng kênh.
- **Phương án đã cân nhắc:** báo cáo số thô; phân tầng (so trong từng sản phẩm); chuẩn hoá gián tiếp (SMR); gộp các tầng bằng Mantel-Haenszel.
- **Lựa chọn:** dẫn dắt bằng SMR theo kênh (một con số mỗi kênh, so với chính mức sản phẩm của kênh đó), kèm cặp Stone so với Country-wide gộp Mantel-Haenszel (cặp duy nhất có hai sản phẩm có tử số dày). Phân tầng từng sản phẩm để kiểm tra hướng. Số thô chỉ để đối chiếu.
- **Kết quả, MOB 12:**

    Bảng dưới là bước một (chỉ chuẩn hoá theo sản phẩm). Sau lần soát thứ hai, kết quả chính là chuẩn hoá theo sản phẩm × đợt mở ở [mục 5.10](#510-đợt-mở-hợp-đồng-biến-gây-nhiễu-thứ-hai).

  | Kênh | Quan sát | Kỳ vọng | SMR | Độ nhạy `SK_DPD` | Định nghĩa giữa |
  |---|---|---|---|---|---|
  | Contact center | 48 | 16,6 | 2,90 [2,14; 3,84] | 1,59 [1,31; 1,91] | 2,44 [1,81; 3,20] |
  | Stone | 82 | 50,3 | 1,63 [1,30; 2,02] | 1,22 [1,16; 1,28] | 1,16 [1,03; 1,29] |
  | Country-wide | 110 | 109,2 | 1,01 [0,83; 1,21], không có ý nghĩa | 1,04 [1,00; 1,08] | 1,10 [1,01; 1,19] |
  | Regional / Local | 15 | 24,8 | 0,60 [0,34; 1,00], sát biên | 0,62 [0,56; 0,69] | 0,64 [0,50; 0,79] |
  | Credit and cash offices | 61 | 104,7 | 0,58 [0,45; 0,75] | 0,63 [0,56; 0,71] | 0,69 [0,58; 0,81] |
  | AP+ (Cash loan) | 2 | 12,5 | tử số 2, không kết luận được | 0,72 [0,51; 0,99] | 0,68 [0,39; 1,10] |

  Ổn định qua MOB: Contact center 3,88 [2,63; 5,50] tại MOB 6 và 2,08 [1,63; 2,61] tại MOB 24; Stone 1,69 [1,20; 2,32] và 1,56 [1,26; 1,91]; Credit and cash offices 0,51 [0,34; 0,73] và 0,51 [0,40; 0,65].

  Stone so với Country-wide trong cùng sản phẩm: vay tiêu dùng 1,72 [1,24; 2,40], thẻ 2,88 [1,47; 5,66], vay tiền mặt không kết luận được (0 / 1.668 so với 15 / 18.159); gộp Mantel-Haenszel qua cả ba tầng sản phẩm (gồm tầng vay tiền mặt) 1,80 [1,34; 2,42], chỉ qua hai tầng vay tiêu dùng và thẻ 1,88 [1,40; 2,52], ổn định tại MOB 6 (1,83 [1,20; 2,79]) và MOB 24 (1,57 [1,20; 2,06]).

- **Hệ quả (bước một, đã được thay bởi mục 5.10):** kết luận cũ "phần lớn khoảng cách kênh là do sản phẩm" không còn: cơ cấu sản phẩm che bớt chứ không tạo ra khoảng cách. Không được đọc bảng trên như "khoảng cách rõ hơn sau chuẩn hoá", vì hai SMR chuẩn hoá gián tiếp không chia cho nhau được. Theo định nghĩa mới, số thô chỉ chênh 1,73 [1,24; 2,41] lần giữa Stone và Credit and cash offices, nhưng sau khi kiểm soát sản phẩm, Stone vẫn cao hơn mức sản phẩm của nó và Contact center lệch xa nhất, chủ yếu do thẻ của kênh này (0,507% [0,381; 0,673], 47 / 9.272). Credit and cash offices không bán vay tiêu dùng nên không thể so cùng cặp với nó ở cả ba sản phẩm. Dữ liệu quan sát không cho biết nguyên nhân; kỳ hạn, số tiền vay và đặc điểm khách chưa được kiểm soát.

### 5.6 Nhóm "(không rõ)"

- **Quy mô:** 48.794 hợp đồng không khớp hồ sơ. Tại MOB 12 chỉ 2.083 hợp đồng vào mẫu số (0,25%) nhưng gánh 106 trên 425 ca từng 30+ (24,9%), tỷ lệ 5,089% [4,225; 6,118], gấp hơn 100 lần tỷ lệ của phần còn lại (0,039%). Trong danh mục đang mở, nhóm chiếm 4,72% hợp đồng (6.810) nhưng 18,2% số ca 30+ (29 / 159).
- **Chưa giải thích được.** Có thể là đặc điểm thật của nhóm khách này, cũng có thể là lỗi ghép dữ liệu ở nguồn Kaggle. Dữ liệu hiện có không đủ để phân biệt.
- **Mỏng hơn vẻ ngoài.** 46.178 trên 48.794 hợp đồng của nhóm (94,6%) mang cờ `is_partial_history` nên bị loại khỏi vintage; mẫu số MOB 0 của nhóm chỉ còn 2.605. Quy tắc `closed_inferred` cần `DAYS_TERMINATION` của hồ sơ nên không áp được cho nhóm: 512 hợp đồng dừng sớm của nhóm mang nhãn `unknown` và bị loại khỏi mẫu số MOB 12. Đối xử như nhóm có hồ sơ (coi là đã đóng) thì tỷ lệ là 4,35% [3,63; 5,21] (113 / 2.595) thay vì 5,09%.
- **KPI danh mục đang mở.** 110 hợp đồng đang mở thiếu dư nợ ước lượng, chứa 24 trên 159 ca 30+, toàn bộ thuộc nhóm này. Bỏ hẳn nhóm cho 0,094% [0,080; 0,112] (130 / 137.611), cùng mức với tập có dư nợ.
- **Cách xử lý:** không loại âm thầm. Nhóm mang nhãn `(không rõ)` ở mọi cột phân khúc, không vào SMR hay so sánh cặp kênh. Mọi tổng toàn danh mục được báo kèm **tổng không gồm nhóm này**: ever 30+@MOB12 là 0,039% [0,035; 0,044] (319 / 816.589), so với 0,052% khi gồm cả nhóm.

### 5.7 Roll rate: tách cắt phải khỏi mất dữ liệu

- **Vấn đề:** một tháng đang mở không có dòng tháng kế tiếp có thể là do cửa sổ dữ liệu kết thúc, hoặc do dữ liệu thật sự mất.
- **Lựa chọn:** tháng `-1` bị loại khỏi trạng thái xuất phát vì về nguyên tắc không thể quan sát tháng sau (cắt phải). Tháng `t <= -2` mà không có tháng `t + 1` vào trạng thái đích `Missing`, nằm trong mẫu số. Chỉ dùng cặp tháng cách nhau đúng 1 tháng. `Completed` coi là trạng thái hấp thụ (chỉ 18 trên 1.040.632 hợp đồng quay lại trạng thái mở).
- **Hệ quả:** 182.847 dòng (1,44% số lượt xuất phát) vào `Missing` thay vì bị loại âm thầm. Cure rate (M10) là một cột của chính ma trận này, không có mart riêng. Bảng độ nhạy `mart.roll_rate_no_threshold` sinh từ cùng một table macro, có test bảo đảm cùng tập tháng xuất phát.
- **Kết quả:** cure rate 57,7% [57,5; 57,9] ở B1 (111.822 / 193.814), 27,8% [25,7; 30,0] ở B2 (457 / 1.642), 1,2% [0,96; 1,54] ở B4 (68 / 5.589). B3 chỉ có 403 lượt, dưới ngưỡng diễn giải. B1 hiếm khi rơi tiếp: 0,709% [0,673; 0,748] sang B2. Tách theo nguồn: cure B1 của POS 55,3% (59.399 / 107.369), của thẻ 60,6% (52.423 / 86.445); các hàng B2, B3 của từng nguồn đều dưới 1.000 lượt.

### 5.8 Cỡ mẫu cho thử nghiệm

- **Vấn đề:** đề xuất chính sách phải kiểm chứng bằng thử nghiệm có nhóm đối chứng, nhưng tử số của project rất mỏng. Trước khi đề xuất một thử nghiệm phải biết nó có đo được không.
- **Phép tính:** hai tỷ lệ độc lập, hai phía, alpha 0,05, power 0,8, chia 1:1, phát hiện giảm tương đối 20%. So với quy mô của nhóm trong toàn bộ dữ liệu (MOB 0), vì không có thời gian lịch để quy ra số tháng tuyển.

  | Nhóm | Chỉ tiêu | Tỷ lệ nền | Cần mỗi nhánh | Hai nhánh so với quy mô nhóm |
  |---|---|---|---|---|
  | Vay tiêu dùng, khách mới × lãi suất cao (92.297) | ever 30+@MOB12 | 0,042% | 843.010 | 18,3 lần |
  | như trên | ever 30+@MOB6 | 0,019% | 1.908.497 | 41,4 lần |
  | như trên | ever 1+@MOB6 | 4,641% [4,507; 4,779] | 7.292 | 0,16 lần |
  | Toàn vay tiêu dùng (587.477) | ever 30+@MOB12 | 0,029% | 1.224.282 | 4,2 lần |
  | như trên | ever 1+@MOB6 | 3,074% | 11.173 | 0,04 lần |

- **Kết luận:** đo tác động bằng ever 30+ là không khả thi. Chỉ tiêu sớm đề xuất là **ever 1+@MOB6** (`SK_DPD_DEF > 0` lần nào đó tính đến MOB 6). Kiểm tra liên quan trong vay tiêu dùng: nhóm từng 1+ đến MOB 6 có ever 30+@MOB12 là 0,707% [0,591; 0,845] (119 / 16.828), so với 0,0066% (34 / 513.648) ở nhóm không, tỷ số 107 [73; 156]; 77,8% số ca 30+@MOB12 đã từng 1+ trước MOB 6. Một phần liên quan này là cơ học, vì ca đã 30+ trước MOB 6 thì cũng đã 1+.
- **Phần cơ học và phần dự báo thật của chỉ tiêu sớm.** Trong 153 ca vay tiêu dùng 30+ tại MOB 12, 67 ca đã 30+ trước MOB 6 (chắc chắn đã 1+, phần cơ học). Trong 86 ca lần đầu 30+ ở MOB 7 đến 12, 52 ca (60,5% [49,9; 70,1]) đã từng 1+ trước MOB 6. Trên hợp đồng chưa 30+ đến MOB 6: 0,310% [0,237; 0,407] ở nhóm từng 1+ so với 0,0066% ở nhóm chưa, tỷ số 46,87 [30,43; 72,19].
- **Cỡ mẫu cho đúng nhóm thẻ Contact center** (9.276 hợp đồng): ever 1+@MOB6 nền 15,99% [15,26; 16,75] (1.483 / 9.274), cần 1.890 mỗi nhánh (0,41 lần quy mô); ever 30+@MOB12 nền 0,507%, cần 69.359 mỗi nhánh (14,95 lần quy mô).
- **Thử nghiệm thu hồi, đơn vị là hợp đồng.** Bản trước tính cure B1 nền 57,7% trên lượt hợp đồng-tháng, vốn không độc lập, và giả định tăng tương đối 20% (11,5 điểm phần trăm, hiệu ứng lớn): 273 mỗi nhánh. Tính lại theo lần đầu mỗi hợp đồng vào B1: nền 67,9% [67,5; 68,2] (48.351 / 71.231); tăng 3 điểm cần 3.705, 5 điểm cần 1.308, 10 điểm cần 310 hợp đồng mỗi nhánh. Phát hiện giảm 20% tỷ lệ B1 rơi sang B2 (nền 0,709%) cần 49.467 mỗi nhánh. "Liên hệ trong 7 ngày" không đo được bằng dữ liệu theo tháng; chỉ đo được cure tháng sau.

### 5.9 Phân khúc rủi ro cao: đã xét, không còn đứng vững

- **Định nghĩa đã xét:** trong vay tiêu dùng, `client_type = 'New'` và `yield_group = 'high'`. Bỏ điều kiện kênh của phiên bản cũ vì 92% phân khúc vốn đã thuộc Stone hoặc Country-wide và trong phân khúc, hai kênh này không khác kênh còn lại (0,041% so với 0,055%, tỷ số 0,74 [0,26; 2,08]).
- **Số tổ hợp đã xét:** 16 (loại khách × nhóm lãi suất), 12 tổ hợp có ít nhất 1.000 hợp đồng. Tổ hợp này được nêu từ phân tích cũ, tức đã nhìn dữ liệu trước, nên kết quả dưới đây không phải kiểm định xác nhận độc lập.

  | | MOB 6 | MOB 12 | MOB 24 |
  |---|---|---|---|
  | Tỷ lệ phân khúc | 0,019% [0,012; 0,030] (17 / 91.874) | 0,042% [0,031; 0,057] (38 / 90.732) | 0,043% [0,031; 0,059] (39 / 90.586) |
  | Tỷ trọng hợp đồng / tỷ trọng ca | 16,5% / 25,0% | 17,1% / 24,8% | 17,5% / 23,1% |
  | Tỷ số so với phần vay tiêu dùng còn lại | 1,69 [0,97; 2,92] | 1,60 [1,11; 2,31] | 1,42 [0,99; 2,03] |
  | Khoảng Bonferroni cho 12 tổ hợp | [0,76; 3,76] | [0,94; 2,74] | [0,84; 2,39] |
  | Độ nhạy `SK_DPD`, tỷ số | 2,07 [1,79; 2,40] | 2,79 [2,63; 2,97] | 2,75 [2,60; 2,91] |

- **Đếm đủ số phép so.** Đã xem 12 tổ hợp × 3 mốc MOB × 2 định nghĩa × 2 (có, không điều kiện kênh) = 144 phép so. Khoảng Bonferroni tại MOB 12: [0,94; 2,74] cho 12, [0,88; 2,91] cho 36, [0,82; 3,13] cho 144.
- **Kết luận:** tỷ số chỉ có ý nghĩa ở MOB 12 và mất ý nghĩa sau hiệu chỉnh Bonferroni; ở MOB 6 và MOB 24 không có ý nghĩa. Phân khúc không còn là phát hiện chính. Không chọn một phân khúc khác để thay, vì làm vậy là chọn sau khi nhìn dữ liệu.
- **Ghi chú khám phá, không dùng làm kết luận:** trong bảng 16 tổ hợp, `Repeater × high` cao hơn (tỷ số 2,45 [1,75; 3,43]); gộp theo riêng nhóm lãi suất, `yield_group = 'high'` chiếm 36,5% hợp đồng vay tiêu dùng và 58,8% số ca, tỷ số 2,49 [1,80; 3,43] tại MOB 12, ổn định ở MOB 6 và MOB 24. Đây là giả thuyết thêm vào sau khi nhìn bảng, cần dữ liệu khác để kiểm chứng, và nhóm 36,5% quá rộng để gọi là phân khúc nhỏ.

### 5.10 Đợt mở hợp đồng: biến gây nhiễu thứ hai

- **Vấn đề.** Lần soát độc lập thứ hai chỉ ra `dim_loan.first_open_month` (tháng tương đối của MOB 0) là biến gây nhiễu mạnh chưa được kiểm soát. Nó liên quan tới kết quả (hợp đồng mở càng xa ngày hồ sơ hiện tại càng hay quá hạn) và tới nhóm đang so (kênh, sản phẩm có cơ cấu đợt mở rất khác nhau). Trong mẫu số MOB 12, 77,2% thẻ của Credit and cash offices mở từ tháng -35 trở về sau, so với 21,1% ở Contact center. Chuẩn hoá chỉ theo sản phẩm vì vậy so thẻ mới của một kênh với thẻ cũ của kênh khác. Đây là dạng nghịch lý Simpson: một so sánh gộp đổi độ lớn, thậm chí đổi chiều, khi tách theo một biến thứ ba.
- **Phương án đã cân nhắc.** (A) Hồi quy với đợt mở là biến liên tục: phải giả định dạng hàm, khó giải thích với tử số vài chục ca. (B) Phân tầng theo đợt rời rạc rồi chuẩn hoá và gộp Mantel-Haenszel: cùng công cụ đã dùng cho sản phẩm, minh bạch, đọc được từng tầng. Chọn B.
- **Mốc cắt.** Chính: mỗi 12 tháng của `first_open_month`, căn từ tháng -96 (tháng sớm nhất của dữ liệu) nên đợt cuối kết thúc đúng tháng -1: 8 đợt "-96 đến -85" đến "-12 đến -1". Lý do: một năm tương đối là mốc tự nhiên, định trước, không chọn theo dữ liệu; đủ mịn để thấy xu hướng; đủ dày để hầu hết ô sản phẩm × đợt có trên 1.000 hợp đồng. Mốc 12 tháng còn khớp với các mốc MOB 12 và MOB 24, nên mỗi đợt hoặc đủ tuổi trọn vẹn tới MOB đó hoặc không. Độ nhạy: (1) 3 nhóm do người soát đặt (-60 trở về trước, -59 đến -36, -35 trở về sau); (2) mỗi 24 tháng (4 đợt). Cột `mart.vintage.origination_cohort` theo mốc chính; hai mốc độ nhạy tính trong `scripts/compute_findings.py` từ một truy vấn đếm lại độc lập trên `core`, và script dừng nếu cách cắt chính của truy vấn đó lệch `mart.vintage`.

  | Đợt mở | -96 đến -85 | -84 đến -73 | -72 đến -61 | -60 đến -49 | -48 đến -37 | -36 đến -25 | -24 đến -13 | -12 đến -1 |
  |---|---|---|---|---|---|---|---|---|
  | Hợp đồng tại MOB 0 | 62.056 | 77.857 | 63.776 | 79.124 | 95.805 | 161.052 | 227.756 | 177.511 |

- **Hai cách dùng, hai quy tắc mẫu số.**
  - *Vintage theo đợt mở* (so các đợt với nhau): mỗi đợt chỉ được so ở MOB n mà toàn bộ hợp đồng của đợt đã có thể quan sát tới, tức `first_open_month <= -1 - n`. Đợt chưa đủ tuổi chỉ có hợp đồng đã đóng sớm trong mẫu số tại MOB n, nên trông tốt giả. Tại MOB 12 đợt "-12 đến -1" bị loại; tại MOB 24 đợt "-24 đến -13" cũng bị loại.
  - *Phân tầng* (so kênh, sản phẩm trong cùng đợt): giữ nguyên mẫu số của vintage chính, đợt chỉ là tầng. So sánh trong một tầng vẫn công bằng dù tầng đó chưa đủ tuổi, và kết quả so được trực tiếp với bản chỉ chuẩn hoá theo sản phẩm vì cùng một tập hợp đồng.
- **Kết quả 1: đợt cũ xấu hơn hẳn trong mọi sản phẩm (MOB 12).** Ba sản phẩm gộp: 0,192% [0,161; 0,230] (118 / 61.379) ở đợt -96 đến -85, 0,010% [0,007; 0,015] (23 / 224.703) ở đợt -24 đến -13. Đợt cũ nhất so với đợt gần nhất đủ tuổi trong từng sản phẩm:

  | Cách cắt | Vay tiền mặt | Vay tiêu dùng | Thẻ quay vòng |
  |---|---|---|---|
  | 12 tháng (-96 đến -85 so với -24 đến -13) | 9,88 [4,52; 21,56] | 62,17 [15,14; 255,35] | 39,09 [14,19; 107,69] |
  | 3 nhóm (-60 trở về trước so với -35 trở về sau) | 8,40 [4,96; 14,22] | 23,17 [10,21; 52,58] | 38,60 [14,14; 105,37] |
  | 24 tháng (-96 đến -73 so với -24 đến -1) | 8,54 [4,56; 15,97] | 49,31 [12,15; 200,13] | 28,05 [10,27; 76,60] |

  Đường không đơn điệu từng bậc (các ô giữa của thẻ chỉ 1 đến 5 ca), nhưng khoảng cách giữa hai đầu vượt xa độ rộng khoảng tin cậy. Bảng đầy đủ theo sản phẩm × đợt: [insight memo mục 2.1](insight_memo.md#21-vintage-theo-đợt-mở-đợt-cũ-xấu-hơn-hẳn-trong-mọi-sản-phẩm).
- **Diễn giải, không phải kết luận.** Đợt mở là tháng tương đối so với ngày nộp hồ sơ hiện tại, nên xu hướng này có ít nhất ba cách giải thích mà dữ liệu không tách được: (a) chọn mẫu: khách vừa quá hạn gần đây ít có khả năng xuất hiện với một hồ sơ mới, còn khách quá hạn từ 7, 8 năm trước đã có thời gian phục hồi; (b) chất lượng giải ngân cải thiện thật; (c) cách ghi nhận DPD hoặc ngưỡng của `SK_DPD_DEF` thay đổi theo thời gian. Vì vậy đợt mở chỉ được dùng làm biến kiểm soát, không dùng để nói danh mục đang tốt lên.
- **Kết quả 2: so sánh sau khi kiểm soát đợt mở, MOB 12, ba cách cắt, hai định nghĩa.** Định nghĩa giữa: khoản trả góp đo bằng `SK_DPD` lớn hơn 30 nhưng chỉ ở tháng còn kỳ phải trả (`installments_remaining > 0`), tức bỏ khoản dư lẻ sau kỳ trả cuối mà không dùng ngưỡng không công bố; thẻ giữ `SK_DPD_DEF`. Cột `mart.vintage.n_ever_30_plus_due_only`.

  | Phép so | 12 tháng | 3 nhóm | 24 tháng | Định nghĩa giữa, 12 tháng | Chưa kiểm soát đợt |
  |---|---|---|---|---|---|
  | Thẻ / vay tiền mặt (MH qua đợt) | 2,29 [1,59; 3,31] | 2,75 [1,97; 3,86] | 2,50 [1,75; 3,59] | 0,74 [0,56; 0,97], xem dưới | 4,85 [3,57; 6,59] |
  | Vay tiêu dùng / vay tiền mặt (MH qua đợt) | 0,41 [0,30; 0,56] | 0,42 [0,30; 0,57] | 0,44 [0,33; 0,60] | 0,95 [0,82; 1,11] | 0,90 [0,68; 1,19] |
  | SMR Contact center (sản phẩm × đợt) | 1,65 [1,21; 2,18] | 1,59 [1,17; 2,10] | 1,56 [1,15; 2,06] | 1,65 [1,23; 2,17] | 2,90 [2,14; 3,84] |
  | SMR Stone | 1,36 [1,08; 1,69] | 1,40 [1,12; 1,74] | 1,38 [1,10; 1,71] | 1,06 [0,95; 1,19] | 1,63 [1,30; 2,02] |
  | SMR Credit and cash offices | 0,89 [0,68; 1,14] | 0,86 [0,66; 1,10] | 0,88 [0,67; 1,13] | 0,85 [0,72; 1,00] | 0,58 [0,45; 0,75] |
  | SMR Country-wide | 0,79 [0,65; 0,95] | 0,80 [0,66; 0,97] | 0,80 [0,66; 0,97] | 0,99 [0,91; 1,07] | 1,01 [0,83; 1,21] |
  | Stone / Country-wide (MH qua sản phẩm × đợt) | 1,76 [1,31; 2,37] | 1,81 [1,35; 2,43] | 1,77 [1,31; 2,38] | 1,09 [0,95; 1,26] | 1,80 [1,34; 2,42] |

  Theo mốc MOB (cắt 12 tháng, định nghĩa chính): SMR Contact center 2,04 [1,39; 2,90] tại MOB 6 và 1,48 [1,16; 1,86] tại MOB 24; Stone 1,38 [0,98; 1,89] và 1,28 [1,04; 1,58]; Credit and cash offices 0,76 [0,51; 1,08] và 0,85 [0,66; 1,07]; thẻ / vay tiền mặt 2,68 [1,68; 4,26] và 2,97 [2,15; 4,10]. Theo cột không ngưỡng `SK_DPD` cho cả hai sản phẩm, thẻ / vay tiền mặt là 2,88 [2,48; 3,35] và vay tiêu dùng / vay tiền mặt là 2,98 [2,63; 3,37].

  Về dòng thẻ dưới định nghĩa giữa: định nghĩa giữa không có bản tương đương cho thẻ, nên trả góp được đo không ngưỡng còn thẻ vẫn có ngưỡng, tức hai sản phẩm không cùng thước. Nếu thẻ cũng đo bằng `SK_DPD` thì tỷ số là 4,05 [3,42; 4,79] (3 nhóm 4,45 [3,76; 5,27], 24 tháng 4,28 [3,62; 5,06]). Hai giá trị 0,74 và 4,05 là cận của một phép so không cùng thước, không được dùng làm kết luận. Ở mọi phép so cùng thước (định nghĩa chính cho cả hai, hoặc không ngưỡng cho cả hai), thẻ rủi ro hơn vay tiền mặt.
- **Nguồn của phần vượt kỳ vọng.** Contact center: thẻ có 47 ca so với 28,0 kỳ vọng, vay tiền mặt 1 so với 1,1. Trong 47 ca thẻ, 41 là thẻ mở từ tháng -60 trở về trước; thẻ mở từ tháng -35 trở về sau có 0 ca trên 1.959. Credit and cash offices: chỉ theo sản phẩm, thẻ có 8 ca so với 47,7 kỳ vọng, vay tiền mặt 53 so với 57,0; theo sản phẩm × đợt, thẻ 8 so với 13,9, vay tiền mặt 53 so với 55,0. Mức "dưới kỳ vọng" cũ của kênh này và mức "trên kỳ vọng" cũ của Contact center vì vậy đến gần như hoàn toàn từ thẻ, và phần thẻ trùng với đợt mở.
- **Cure rate.** Trong cùng đợt mở, cure B1 vẫn gấp B2: tỷ số gộp Mantel-Haenszel qua 8 đợt là 2,09 [1,94; 2,27], so với tỷ số thô 57,7% / 27,8%.
- **Kết luận rút ra.** Bền qua mọi cách cắt, mọi mốc MOB và cả định nghĩa giữa: thẻ rủi ro hơn vay tiền mặt (ở mọi phép so cùng thước), Contact center trên kỳ vọng, cure B1 gấp B2. Không bền: Stone trên kỳ vọng và Stone cao hơn Country-wide (mất khi đổi định nghĩa, Stone mất cả ở MOB 6). Không còn: Credit and cash offices tốt hơn kỳ vọng. Không kết luận được: vay tiêu dùng so với vay tiền mặt (từ 0,41 đến 6,48 tuỳ cách đo). Country-wide dưới kỳ vọng theo định nghĩa chính nhưng không theo định nghĩa giữa và không là so sánh định trước, nên chỉ để mô tả.
- **Hậu nghiệm.** Đợt mở được đưa vào sau khi người soát nhìn dữ liệu, và mốc 3 nhóm do người soát đặt sau khi nhìn. Các con số trong mục này là kiểm tra lại các so sánh định trước, không phải kiểm định xác nhận độc lập. Mốc 12 tháng định trước theo năm tương đối giảm phần lựa chọn sau khi nhìn, nhưng không xoá được nó.
- **Khóa trong `findings.json`:** `origination_cohort.mob{6,12,24}` (`cohort_vintage`, `smr_by_channel`, `product_ratio_vs_cash`, `stone_vs_country_wide`, `cards_by_channel_cohort`, `mix_channel_product_cohort`), `origination_cohort.curve_by_cohort_labeled_products`, `origination_cohort.cure_b1_vs_b2_by_cohort`. Định nghĩa chỉ tiêu: [M15](metric_dictionary.md#m15-vintage-theo-đợt-mở).

## 6. Bản Power BI

Ngoài dashboard HTML tĩnh (`dashboard/index.html`, sinh bằng `scripts/build_dashboard.py`), project có một bản Power BI kể cùng câu chuyện trong 4 trang, nằm ở `powerbi/`. Hướng dẫn mở, cấu trúc và quy tắc sửa: [`powerbi/README.md`](../powerbi/README.md).

**Dựng bằng PBIP sinh từ script.** PBIP (Power BI Project) lưu báo cáo thành thư mục file văn bản thay vì file `.pbix` nhị phân, nên diff và review được trên git. `scripts/build_pbip_model.py` sinh semantic model dạng TMDL (7 bảng: 5 bảng fact từ 5 mart, 2 bảng danh mục kênh và sản phẩm dùng chung; 10 quan hệ; 27 measure). `scripts/build_pbip_report.py` sinh report dạng PBIR (theme, 4 trang). Không sửa tay trong Desktop. ID trang và visual sinh từ hash nên chạy lại cho đúng ID cũ. Measure đọc các cột gốc của mart (`n_ever_30_plus`, `n_30_plus`, `dpd_bucket`), nên theo định nghĩa chính `SK_DPD_DEF`; cột `_no_threshold` chỉ dùng cho độ nhạy. Sau khi clone phải đặt tham số `DataFolder` trỏ tới `data/export` trên máy.

**Ba lớp kiểm tra trước khi mở Desktop**, mỗi lớp bắt một loại lỗi khác:

1. `scripts/check_model_names.py`: xung đột tên trong model mà hai lớp sau không bắt được.
2. `powerbi-report-author validate`: cấu trúc PBIR (schema, thuộc tính, bố cục, theme).
3. Power BI Modeling MCP server (`ConnectFolder`): cú pháp TMDL và tính hợp lệ của model, cũng là cách duy nhất lấy được thông báo lỗi thật khi Desktop chỉ báo "Issues were found".

Sau ba lớp vẫn còn loại lỗi cho số sai mà file mở bình thường, nên vòng reload và chụp ảnh từng trang là bước bắt buộc cuối cùng.

**Các bẫy kỹ thuật đáng kể:**

- **`REMOVEFILTERS` phải bỏ cả cột sort.** Mẫu số roll rate là `CALCULATE(SUM(n_loans), REMOVEFILTERS(to_state, to_order))`. Cột `to_state` sắp xếp theo `to_order`, và bộ lọc trong ma trận áp lên cả hai cột. Bỏ mỗi `to_state` thì mẫu số vẫn bị ghim về đúng ô và mọi ô ra 100%. Lỗi này qua được cả ba lớp kiểm tra, chỉ ảnh chụp mới lộ.
- **Không dùng `SUM(n_from)` làm mẫu số.** `n_from` là tổng cửa sổ lặp lại trên mỗi dòng trạng thái đích, cộng thẳng sẽ nhân mẫu số lên nhiều lần.
- **Tên trong tabular model không phân biệt hoa thường.** Measure `Exposure` trùng cột `exposure` cùng bảng làm Desktop từ chối mở file; measure trùng tên bảng cũng vậy. Đây là lý do có lớp kiểm tra thứ nhất.
- **Font phải đủ glyph tiếng Việt.** Georgia thiếu 19 ký tự thường gặp (ví dụ ấ, ầ, ế, ồ, ư, ớ), Windows ghép dấu rời nên "gấp" hiện thành "gâ´p". Font tiêu đề được đổi sang Cambria sau khi kiểm bảng mã của từng font.
- **Mẫu số phải ghim cùng ngữ cảnh với tỷ lệ.** Measure `Ever 30 Plus MOB12` ghim `mob = 12`; đặt cạnh nó một measure mẫu số cộng qua mọi MOB cho con số lớn hơn nhiều lần. Mỗi tỷ lệ ghim ngữ cảnh cần một measure mẫu số ghim cùng ngữ cảnh.
- **Hai thẻ KPI phải cùng một tập.** Tỷ lệ 30+ theo hợp đồng và theo dư nợ chỉ đặt cạnh nhau được khi cùng tính trên hợp đồng có exposure (cột `n_loans_exposure_known`, `n_30_plus_exposure_known` của snapshot).
- **Locale và mã hoá.** Model đặt `culture: en-US` vì CSV dùng dấu chấm thập phân; Power Query ép UTF-8 để giữ dấu tiếng Việt trong nhãn phân khúc.
- **Slicer lấy từ bảng danh mục.** Cột khóa phía fact bị ẩn có chủ đích: slicer lấy từ một bảng fact chỉ lọc bảng đó, các trang khác sai mà vẫn hiện số.

## 7. Những gì project chưa làm được

- **Không có chiều thời gian lịch.** Vintage theo đợt mở dùng tháng mở tương đối, không tách được chất lượng thật với chọn mẫu. Không dựng được vintage theo tháng giải ngân theo lịch, không đánh giá được tác động của một thay đổi chính sách theo thời gian, không quy được cỡ mẫu thử nghiệm ra số tháng tuyển. Với dữ liệu có ngày thật, chỉ cần đổi cột cohort trong `mart_vintage.sql`.
- **Tỷ lệ tuyệt đối không đại diện.** Danh mục là khoản vay trước đây của khách quay lại, đã qua một lần chọn lọc. Chỉ so sánh tương đối là đáng tin.
- **Tử số mỏng.** 425 ca từng 30+ tại MOB 12 trên toàn danh mục. Nhiều so sánh phân khúc, cặp kênh, hay hàng B2, B3 của ma trận roll rate không đủ ý nghĩa thống kê, và được ghi là không kết luận được thay vì dẫn số.
- **Nhóm "(không rõ)" chưa được giải thích** ([mục 5.6](#56-nhóm-không-rõ)), trong khi gánh gần một phần tư số ca vintage.
- **`closed_inferred` là suy luận** từ hành vi của `DAYS_TERMINATION`, một cột mà mô tả chính thức gọi là ngày kết thúc dự kiến.
- **Ngưỡng của `SK_DPD_DEF` không được công bố.** Không kiểm được ngưỡng có hợp lý với một chính sách trọng yếu cụ thể nào không.
- **Kiểm soát nhiễu mới hai yếu tố, yếu tố thứ hai là hậu nghiệm.** So sánh kênh đã kiểm soát sản phẩm và đợt mở, nhưng chưa kiểm soát kỳ hạn, số tiền vay hay đặc điểm khách. Dữ liệu quan sát không chứng minh được quan hệ nhân quả.
- **Mâu thuẫn giữa snapshot và vintage ở vay tiền mặt đã được giải thích, nhưng M07 chưa làm.** 113 ca vay tiền mặt đang 30+ có MOB hiện tại trung vị 19 (7 đến 38), lần đầu 30+ ở MOB trung vị 18, và 94 trên 113 ca lần đầu 30+ sau MOB 12: ca muộn mà chỉ tiêu tại MOB 12 không bắt được. Chỉ tiêu 30+ lagged (M07) vẫn chưa có.
- **Ma trận roll rate không tách khách mới và khách vay lại**, nên cure rate là số toàn danh mục.
- **Không có LGD hay tổn thất thật**, exposure là proxy gồm cả lãi, đơn vị tiền không phải VND. Không đối chiếu được với số liệu kế toán.
- **Chưa dùng `bureau`, `bureau_balance`, chưa làm M07, chưa có model dự báo.** Project dừng ở giám sát danh mục mô tả, chưa xây scorecard hay mô hình xác suất vỡ nợ.
- **Nghĩa của một số giá trị là suy luận.** File mô tả cột không giải thích từng trạng thái hợp đồng (`Demand`, `Amortized debt`...) và không nói rõ DPD là cuối tháng hay cao nhất trong tháng. Cách hiểu đang dùng ghi ở [`data_notes.md`](data_notes.md#8-trạng-thái-hợp-đồng).
