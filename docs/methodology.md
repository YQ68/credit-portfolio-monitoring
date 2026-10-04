# Phương pháp phân tích

Tài liệu này tóm tắt cách project được dựng và lý do đằng sau các quyết định phân tích chính: dữ liệu có gì và thiếu gì, pipeline kiểm thử ra sao, mẫu số của từng chỉ tiêu được chọn thế nào, và những gì project chưa làm được.

Ba tài liệu đi kèm giữ chi tiết đầy đủ:

- [`metric_dictionary.md`](metric_dictionary.md): định nghĩa, công thức và edge case của 12 chỉ tiêu, đánh mã M01 đến M12.
- [`data_notes.md`](data_notes.md): giả định về dữ liệu và nhật ký kiểm tra (ngày, kiểm tra gì, kết quả, quyết định).
- [`insight_memo.md`](insight_memo.md): memo gửi ban lãnh đạo, gồm kết luận, bằng chứng và đề xuất thử nghiệm.

Mọi con số dưới đây đo trên kho DuckDB sau khi chạy `scripts/build.py`. Số thập phân viết theo kiểu Việt Nam: dấu phẩy là thập phân, dấu chấm phân cách hàng nghìn.

## Thuật ngữ

| Viết tắt | Nghĩa |
|---|---|
| DPD (days past due) | Số ngày quá hạn của hợp đồng trong tháng quan sát |
| Bucket | Nhóm DPD: B0 = 0 ngày, B1 = 1 đến 30, B2 = 31 đến 60, B3 = 61 đến 90, B4 = trên 90 |
| 30+ | DPD lớn hơn 30 ngày, tức từ B2 trở lên |
| MOB (month on book) | Số tháng kể từ tháng hợp đồng bắt đầu mở. Tháng mở là MOB 0 |
| Vintage, ever 30+@MOBn | Tỷ lệ hợp đồng từng có ít nhất một tháng 30+ tính đến MOB n, so các nhóm ở cùng tuổi hợp đồng |
| FPD30 (first payment default 30) | Kỳ trả đầu tiên chưa trả đủ sau 30 ngày kể từ ngày đến hạn |
| Roll rate | Tỷ lệ hợp đồng chuyển từ bucket này sang bucket khác sau một tháng |
| Cure rate | Tỷ lệ hợp đồng đang quá hạn quay về B0 ở tháng sau |
| Grain | Một dòng của bảng đại diện cho cái gì, ví dụ "1 hợp đồng trong 1 tháng" |
| Exposure | Số tiền còn phải thu của hợp đồng, ở đây là ước lượng (proxy) |
| Confounding (nhiễu do cơ cấu) | Hai nhóm khác nhau về kết quả vì khác nhau ở một yếu tố thứ ba, không phải vì bản thân yếu tố đang so |

## 1. Dữ liệu và giới hạn

### Nguồn và quy mô

Dữ liệu là bộ [Home Credit Default Risk](https://www.kaggle.com/competitions/home-credit-default-risk/data) công khai trên Kaggle (2018), dùng cho mục đích học tập. Dữ liệu gốc không được commit; chỉ 5 file CSV tổng hợp ở `data/export/` (mỗi dòng là một tổ hợp phân khúc, không phải một hợp đồng) được commit để bản Power BI mở được ngay sau khi clone.

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
- Không dựng được vintage theo tháng giải ngân. Cohort được thay bằng thuộc tính hợp đồng: kênh, sản phẩm, loại khách, nhóm lãi suất, nhóm kỳ hạn.
- "Snapshot hiện tại" là tháng `-1` của mỗi hợp đồng.

### Danh mục là mẫu đã qua một lần sống sót

Danh mục trong project là **các khoản vay trước đây của những khách sau đó đã nộp hồ sơ mới**, không phải toàn bộ danh mục của công ty. Khách quay lại vay đã qua một vòng chọn lọc, nên tỷ lệ tuyệt đối thấp hơn thực tế. Mọi kết luận vì vậy dựa trên **so sánh tương đối giữa các phân khúc**, không dựa trên mức tuyệt đối.

### Cắt trái, cắt phải và hợp đồng thiếu hồ sơ

- **Cắt phải:** lịch sử dừng ở tháng `-1`, hợp đồng còn mở chưa có kết quả cuối. 183.144 hợp đồng (17,60%) có lịch sử dừng sớm hơn `-1` khi vẫn đang `Active`; kiểm tra cho thấy đây cũng là cắt phải, không phải lỗi dữ liệu. Các mart dùng điều kiện `max_mob >= n` thay vì dựa vào nhãn trạng thái kết thúc.
- **Cắt trái:** hợp đồng mở trước cửa sổ dữ liệu có MOB tính ra thấp hơn thực tế. Xử lý ở [quyết định 4.3](#43-vintage-loại-hợp-đồng-có-lịch-sử-không-đầy-đủ).
- **Thiếu hồ sơ:** 48.794 hợp đồng (4,69%) không khớp được hồ sơ nào trong `previous_application`. Chúng không bị loại mà mang nhãn `(không rõ)` ở mọi cột phân khúc.
- **Exposure:** khoản trả góp không có cột dư nợ, nên exposure là proxy `số kỳ còn lại × tiền trả mỗi kỳ` (gồm cả lãi). 3,41% dòng trả góp thiếu giá trị này. Đơn vị tiền không phải VND. Exposure chỉ dùng để so sánh tương đối.

Chi tiết từng giả định và lần kiểm tra: [`data_notes.md`](data_notes.md).

## 2. Kiến trúc pipeline và kiểm thử

### Bốn tầng

```
CSV Kaggle
  raw    nạp nguyên trạng, chỉ đổi tên cột sang chữ thường (scripts/load_raw.py)
  stg    đặt tên cột dễ hiểu, đổi giá trị đặc biệt (365243, XNA, XAP) thành NULL
  core   bảng dùng chung cho mọi phân tích
           int_loan_month   gộp hợp đồng trả góp và thẻ về một cấu trúc
           dim_loan         1 dòng / hợp đồng: phân khúc, mốc vòng đời, cờ cắt trái
           fct_loan_month   1 dòng / hợp đồng / tháng: DPD, bucket, MOB, exposure
  mart   5 bảng tổng hợp, mỗi bảng trả lời một câu hỏi kinh doanh
           funnel_by_channel   approval rate, take-up rate (M12)
           fpd_by_segment      FPD30 (M11)
           vintage             ever 30+ theo MOB (M08)
           roll_rate           ma trận chuyển bucket, cure rate (M09, M10)
           portfolio_snapshot  cơ cấu bucket của danh mục đang mở tại tháng -1 (M02, M06)
```

Toàn bộ chạy trên DuckDB bằng SQL thuần. `scripts/build.py` build các tầng theo thứ tự khai báo trong danh sách `MODELS` rồi chạy test. Mô tả từng mart: [`sql/mart/README.md`](../sql/mart/README.md).

Lý do chia tầng:

- **Một định nghĩa nằm ở một chỗ.** "Hợp đồng đang mở" chỉ được định nghĩa một lần (macro `core.is_open_status` trong `sql/00_setup.sql`). Mọi mart đọc DPD từ `core.fct_loan_month`, nên khi đổi cột DPD chính ([quyết định 4.1](#41-cột-dpd-chính-sk_dpd-thay-vì-sk_dpd_def)) chỉ phải sửa một file.
- **Lần ngược được khi số sai.** Mỗi tầng có test riêng, nên một con số sai ở mart có thể truy về đúng tầng gây ra.

### Data test

Có 27 test trong `sql/tests/`. Mỗi test là một câu SQL trả về **các dòng vi phạm**: 0 dòng là đạt. Dòng đầu file khai báo mức độ:

- `-- severity: error` (21 test): fail thì pipeline dừng. Gồm kiểm grain không trùng, tử số không vượt mẫu số, tỷ lệ trong khoảng 0 đến 1, mỗi hàng ma trận roll rate cộng lại bằng 1, và các test đối chiếu.
- `-- severity: warn` (6 test): chỉ cảnh báo, dùng cho thực tế dữ liệu đã biết và đã chấp nhận, ví dụ 48.794 hợp đồng thiếu hồ sơ (`dim_loan__missing_application`) hay 375 cặp tháng bị hở trên 13,7 triệu dòng (`fct_loan_month__month_gaps`).

Loại test có giá trị nhất là **đối chiếu bằng một đường độc lập**: đếm lại cùng một thứ từ `core` hoặc `stg` rồi so với mart. Ví dụ `vintage__mob0_matches_core` kiểm tra mẫu số vintage tại MOB 0 bằng đúng số hợp đồng đủ điều kiện đếm thẳng từ `core.dim_loan` (944.937). Nếu lệch, điều kiện join với lưới MOB đang loại nhầm hợp đồng.

Hai quy tắc đi cùng test:

- **Không loại dòng âm thầm.** Dòng bị loại khỏi mẫu số phải được đếm và ghi ở comment đầu file SQL hoặc ở metric dictionary. Tháng không có tháng kế tiếp vào trạng thái `Missing` của roll rate, không bị bỏ.
- **Ghi grain ở đầu mỗi file SQL**, kèm mã chỉ tiêu và câu hỏi kinh doanh.

## 3. Nguyên tắc tính tỷ lệ

Mọi mart lưu **số đếm** (tử số và mẫu số, các cột `n_*`) rồi mới tính cột tỷ lệ. Khi gom lên một mức cao hơn, chỉ được **cộng tử số, cộng mẫu số rồi chia**. Không lấy trung bình cột tỷ lệ, vì các dòng có mẫu số khác nhau.

Ví dụ trên `mart.vintage` tại MOB 12, cắt theo 8 kênh:

| Cách tính | Kết quả |
|---|---|
| Trung bình cộng 8 tỷ lệ theo kênh | 1,290% |
| Cộng tử số, cộng mẫu số rồi chia | 0,659% (4.906 / 744.208) |

Chênh gần gấp đôi vì nhóm `(không rõ)` chỉ có 2.083 hợp đồng với tỷ lệ 6,721% nhưng được tính ngang hàng với kênh có 284.403 hợp đồng.

Nguyên tắc này áp dụng xuyên suốt: SQL mẫu trong metric dictionary, dashboard HTML, và mọi measure Power BI (viết dạng `DIVIDE(SUM(tử), SUM(mẫu))`, các cột `*_rate` của mart bị ẩn). Mọi tỷ lệ được trình bày kèm tử số và mẫu số, và ô có mẫu số dưới 1.000 hợp đồng không được diễn giải.

## 4. Các quyết định phân tích

### 4.1 Cột DPD chính: `SK_DPD` thay vì `SK_DPD_DEF`

- **Vấn đề:** dữ liệu có hai cột số ngày quá hạn. `SK_DPD` là DPD thô; `SK_DPD_DEF` có dung sai, bỏ qua các khoản nợ rất nhỏ.
- **Phương án đã cân nhắc:** dùng `SK_DPD_DEF` để khoản nợ lẻ không bị tính là quá hạn (giả định ban đầu), hoặc dùng `SK_DPD`.
- **Lựa chọn:** `SK_DPD` làm cột chính (`dpd`). `SK_DPD_DEF` giữ lại làm chỉ tiêu phụ (`dpd_tolerant`, `is_30_plus_tolerant`), và mart vintage có cặp cột `*_tolerant` để đối chiếu bất cứ lúc nào.
- **Bằng chứng:** theo cột có dung sai, ever 30+@MOB12 chỉ còn 0,053% (395 / 744.208), cắt theo kênh chỉ còn vài chục hợp đồng ở tử số. Theo `SK_DPD` là 0,659% (4.906 / 744.208). Số dòng có DPD trên 30 ngày chênh 22,6 lần ở trả góp (132.058 so với 5.834) và 26,4 lần ở thẻ (54.942 so với 2.079).
- **Hệ quả:** tử số đủ lớn để so sánh phân khúc. Đổi chỉ ở một file của tầng `core`, ghi vào Changelog metric dictionary phiên bản 0.2 kèm số liệu. Điểm còn mở: mô tả gốc của cột chỉ ghi "during the month", chưa rõ là DPD cuối tháng hay cao nhất trong tháng.

### 4.2 FPD30 chỉ là chặn dưới, không dùng làm trục rủi ro

- **Vấn đề:** FPD30 là chỉ tiêu kinh điển để phát hiện kênh kém chất lượng và gian lận, nhưng đo được chỉ 0,011% (99 / 895.744 hợp đồng), thấp bất thường với cho vay tiêu dùng.
- **Nguyên nhân:** bảng `installments_payments` gần như chỉ ghi các kỳ **đã trả**. Hợp đồng bỏ hẳn kỳ đầu không có dòng nào nên rơi khỏi mẫu số thay vì được tính là vỡ nợ. Đây là thiên lệch sống sót (survivorship bias): đúng những hợp đồng xấu nhất lại biến mất. 77.885 hồ sơ được duyệt (7,5%) không có dòng kỳ 1 nào, lớn hơn tử số khoảng 787 lần.
- **Phương án đã cân nhắc:** dùng FPD30 như đo được; bỏ hẳn chỉ tiêu; giữ chỉ tiêu nhưng gắn nhãn và đổi trục xếp hạng.
- **Lựa chọn:** giữ FPD30 trong `mart.fpd_by_segment` với nhãn "chặn dưới" và cột `n_approved_no_installment` đo quy mô vùng mù. Trục xếp hạng rủi ro dùng ever 30+@MOB12. Mart báo cáo song song quy tắc theo số tiền (dung sai 5%) và quy tắc theo ngày (`days_late > 30`, 0,0585%) để thấy độ nhạy của định nghĩa.
- **Hệ quả:** không có chỉ tiêu rủi ro sớm đáng tin. Cảnh báo được gắn vào chính measure `FPD30 Rate` trong Power BI để nó đi theo con số.

### 4.3 Vintage: loại hợp đồng có lịch sử không đầy đủ

- **Vấn đề:** cờ cắt trái `is_left_truncated` (tháng quan sát đầu trùng tháng sớm nhất của bảng) không bắt hết hợp đồng mở trước cửa sổ dữ liệu. Hợp đồng như vậy có MOB thấp hơn thực tế, nên một lần quá hạn ở tuổi 18 tháng bị ghi vào MOB thấp và làm đầu đường cong vống lên.
- **Bằng chứng:** tại MOB 0, 76.197 hợp đồng trả góp (8,17%) đã trả trên 0 kỳ, tức đã chạy trước khi dữ liệu bắt đầu. Cờ cắt trái chỉ bắt được 30.616 trong số đó, bỏ sót 45.581.
- **Phương án đã cân nhắc:** chỉ dùng cờ cắt trái; hoặc thêm cờ thứ hai dựa trên số kỳ đã trả tại MOB 0.
- **Lựa chọn:** thêm `dim_loan.installments_paid_at_open` và cờ `is_partial_history` (cắt trái hoặc đã trả trên 0 kỳ tại MOB 0), gồm 93.751 hợp đồng. Mẫu số vintage loại nhóm này và nhóm `never_open` (4.029, không có MOB 0); hai nhóm giao nhau 2.085, tổng loại 95.695, còn 944.937 trên 1.040.632 hợp đồng.
- **Hệ quả:** ever 30+@MOB12 đổi từ 0,662% trên mẫu số cũ sang 0,659%. Mức thay đổi tổng thể nhỏ, nhưng nhóm bị loại không phân bố đều giữa các kênh nên giữ lại sẽ làm lệch so sánh kênh. Test `dim_loan__partial_history_flag` giữ cờ này đúng định nghĩa.

### 4.4 Vintage: mẫu số theo độ chín

- **Vấn đề:** hợp đồng mới chạy 4 tháng chưa thể biết có quá hạn ở MOB 12 hay không. Hợp đồng tất toán ở tháng thứ 3 thì kết quả đã chốt.
- **Phương án đã cân nhắc** (cùng tử số, khác mẫu số):

  | MOB | A. Đã biết kết quả (chọn) | B. Mẫu số cố định 944.937 | C. Chỉ hợp đồng còn quan sát đủ |
  |---|---|---|---|
  | 12 | 0,659% | 0,568% | 1,227% |
  | 24 | 0,878% | 0,738% | 3,469% |
  | 36 | 0,957% | 0,799% | 7,427% |

- **Lựa chọn:** phương án A, hợp đồng vào mẫu số tại MOB n khi `max_mob >= n` hoặc đã tất toán. B ngầm coi hợp đồng chưa đủ tuổi là tốt nên ép phẳng đường cong; C loại toàn bộ hợp đồng tất toán sớm (nhóm khách tốt) nên thổi phồng đường cong.
- **Hệ quả:** ở MOB cao, phần lớn mẫu số là hợp đồng đã đóng. Tại MOB 24 chỉ 70.635 trên 679.223 hợp đồng (10,4%) còn quan sát đủ. Mart vì vậy lưu thêm `n_observed_full` và `n_closed_early` (có test `n_observed_full + n_closed_early = n_loans`), và đoạn đuôi đường cong không được diễn giải nếu không in kèm hai cột này.

### 4.5 So sánh kênh phải kiểm soát cơ cấu sản phẩm

- **Vấn đề:** xếp hạng thô tại MOB 12 cho thấy Stone 1,068% (1.492 / 139.686) so với Credit and cash offices 0,132% (272 / 206.463), gấp 8,1 lần. Nhưng hai kênh bán hai rổ sản phẩm gần như không giao nhau: Stone 96,9% vay tiêu dùng trả góp, Credit and cash offices 0% vay tiêu dùng và 85,2% vay tiền mặt. Bản thân sản phẩm đã chênh lệch lớn: vay tiêu dùng 0,886%, thẻ quay vòng 0,684%, vay tiền mặt 0,127%.
- **Phương án đã cân nhắc:** báo cáo số thô theo kênh; chuẩn hoá trực tiếp theo cơ cấu sản phẩm; phân tầng (so trong cùng sản phẩm).
- **Lựa chọn:** phân tầng theo sản phẩm. Mart giữ `contract_type` trong grain nên làm được trực tiếp. Số thô chỉ để đối chiếu.
- **Bằng chứng:**

  | Sản phẩm | Kênh cao | Kênh thấp | Chênh |
  |---|---|---|---|
  | Vay tiêu dùng | Stone 1,067% (1.445 / 135.415) | Regional / Local 0,530% (365 / 68.897) | 2,0 lần |
  | Vay tiền mặt | Country-wide 0,437% (78 / 17.844) | Credit and cash offices 0,099% (175 / 175.921) | 4,4 lần |

- **Hệ quả:** khoảng cách 8,1 lần co lại còn 2,0 và 4,4 lần. Phần lớn khoảng cách thô là nhiễu do cơ cấu sản phẩm. Phát hiện chính vẫn đứng vững sau khi phân tầng: trong riêng vay tiêu dùng, nhóm giao (Stone hoặc Country-wide, khách mới, nhóm lãi suất cao) chiếm 14,0% hợp đồng (64.462 / 459.716) nhưng gánh 33,7% số hợp đồng từng 30+ (1.373 / 4.071), tỷ lệ 2,130%, gấp 3,1 lần phần còn lại (0,683%). Dữ liệu không cho biết nguyên nhân phần chênh còn lại giữa kênh; memo đề xuất kiểm chứng bằng thử nghiệm có nhóm đối chứng.

### 4.6 Roll rate: tách cắt phải khỏi mất dữ liệu

- **Vấn đề:** một tháng đang mở không có dòng tháng kế tiếp có thể là do cửa sổ dữ liệu kết thúc, hoặc do dữ liệu thật sự mất.
- **Lựa chọn:** tháng `-1` bị loại khỏi trạng thái xuất phát vì về nguyên tắc không thể quan sát tháng sau (cắt phải). Tháng `t <= -2` mà không có tháng `t + 1` vào trạng thái đích `Missing`, nằm trong mẫu số. Chỉ dùng cặp tháng cách nhau đúng 1 tháng. `Completed` coi là trạng thái hấp thụ (chỉ 18 trên 1.040.632 hợp đồng quay lại trạng thái mở).
- **Hệ quả:** 182.847 dòng (1,44%) vào `Missing` thay vì bị loại âm thầm, kéo tỷ lệ xuống đúng mức. Cure rate (M10) là một cột của chính ma trận này, không có mart riêng, để tránh hai nguồn số lệch nhau. Kết quả nền: cure rate 50,1% ở B1, 17,3% ở B2, 7,0% ở B3, 2,0% ở B4.

## 5. Bản Power BI

Ngoài dashboard HTML tĩnh (`dashboard/index.html`, sinh bằng `scripts/build_dashboard.py`), project có một bản Power BI kể cùng câu chuyện trong 4 trang, nằm ở `powerbi/`. Hướng dẫn mở, cấu trúc và quy tắc sửa: [`powerbi/README.md`](../powerbi/README.md).

**Dựng bằng PBIP sinh từ script.** PBIP (Power BI Project) lưu báo cáo thành thư mục file văn bản thay vì file `.pbix` nhị phân, nên diff và review được trên git. `scripts/build_pbip_model.py` sinh semantic model dạng TMDL (7 bảng: 5 bảng fact từ 5 mart, 2 bảng danh mục kênh và sản phẩm dùng chung; 10 quan hệ; 27 measure). `scripts/build_pbip_report.py` sinh report dạng PBIR (theme, 4 trang). Không sửa tay trong Desktop. ID trang và visual sinh từ hash nên chạy lại cho đúng ID cũ.

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
- **Mẫu số phải ghim cùng ngữ cảnh với tỷ lệ.** Measure `Ever 30 Plus MOB12` ghim `mob = 12`; đặt cạnh nó một measure mẫu số cộng qua mọi MOB cho con số lớn hơn 37 lần. Mỗi tỷ lệ ghim ngữ cảnh cần một measure mẫu số ghim cùng ngữ cảnh.
- **Locale và mã hoá.** Model đặt `culture: en-US` vì CSV dùng dấu chấm thập phân; Power Query ép UTF-8 để giữ dấu tiếng Việt trong nhãn phân khúc.
- **Slicer lấy từ bảng danh mục.** Cột khóa phía fact bị ẩn có chủ đích: slicer lấy từ một bảng fact chỉ lọc bảng đó, các trang khác sai mà vẫn hiện số.

## 6. Những gì project chưa làm được

- **Không có chiều thời gian lịch.** Không dựng được vintage theo tháng giải ngân, không đánh giá được tác động của một thay đổi chính sách theo thời gian, không nói được danh mục đang xấu đi hay tốt lên. Với dữ liệu có ngày thật, chỉ cần đổi cột cohort trong `mart_vintage.sql`.
- **Tỷ lệ tuyệt đối không đại diện.** Danh mục là khoản vay trước đây của khách quay lại, đã qua một lần chọn lọc. Chỉ so sánh tương đối là đáng tin.
- **Không có chỉ tiêu rủi ro sớm đáng tin.** FPD30 chỉ là chặn dưới ([quyết định 4.2](#42-fpd30-chỉ-là-chặn-dưới-không-dùng-làm-trục-rủi-ro)).
- **Phân tầng mới kiểm soát một yếu tố.** So sánh kênh đã kiểm soát sản phẩm, nhưng chưa kiểm soát kỳ hạn, số tiền vay hay đặc điểm khách. Chênh lệch còn lại giữa kênh chưa được giải thích, và dữ liệu quan sát không chứng minh được quan hệ nhân quả.
- **Đoạn đuôi đường cong vintage mỏng.** Tại MOB 24 chỉ 10,4% mẫu số còn quan sát đủ. Hàng B2 và B3 của ma trận roll rate chỉ có 12.315 và 7.172 quan sát toàn danh mục, cắt theo phân khúc thì nhiều ô dưới ngưỡng diễn giải.
- **Ma trận roll rate không tách khách mới và khách vay lại**, nên cure rate là số toàn danh mục.
- **Chưa làm chỉ tiêu 30+ lagged (M07)** và chưa dùng `bureau`, `bureau_balance`.
- **Nghĩa của một số giá trị là suy luận.** File mô tả cột không giải thích từng trạng thái hợp đồng (`Demand`, `Amortized debt`...) và không nói rõ DPD là cuối tháng hay cao nhất trong tháng. Cách hiểu đang dùng ghi ở [`data_notes.md`](data_notes.md#8-trạng-thái-hợp-đồng).
- **Exposure là proxy** gồm cả lãi, không phải dư nợ gốc, đơn vị tiền không phải VND. Không đối chiếu được với số liệu kế toán.
- **Chưa có model dự báo.** Project dừng ở giám sát danh mục mô tả, chưa xây scorecard hay mô hình xác suất vỡ nợ.
