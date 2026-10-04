# Data Notes

Ghi chép cách hiểu dữ liệu, các giả định đã chọn và giới hạn. Các giả định đã được xác nhận trên dữ liệu thật ngày 2026-09-20 bằng `sql/explore/01_profile.sql` và các kiểm tra bổ sung. Kết quả ghi vào [mục 11](#11-nhật-ký-kiểm-tra).

## 1. Nguồn và điều khoản

- Dữ liệu: [Home Credit Default Risk](https://www.kaggle.com/competitions/home-credit-default-risk/data), Kaggle, 2018.
- Chỉ dùng cho mục đích học tập theo luật của competition. **Không đưa dữ liệu gốc lên GitHub** (`data/raw/` và kho `data/warehouse.duckdb` nằm trong `.gitignore`). Ngoại lệ: 5 file CSV tổng hợp nhỏ ở `data/export/` (mỗi dòng là một tổ hợp phân khúc, không phải một hợp đồng) được commit để bản Power BI mở được ngay sau khi clone.
- `HomeCredit_columns_description.csv` là mô tả cột chính thức. Tra ở đó trước khi đoán nghĩa của một cột.

## 2. Bảng và quan hệ

```
application_train            1 dòng / hồ sơ vay hiện tại (SK_ID_CURR)
└── previous_application     1 dòng / hồ sơ vay trước đây (SK_ID_PREV), gồm cả hồ sơ bị từ chối
    ├── POS_CASH_balance       1 dòng / khoản trả góp / tháng
    ├── credit_card_balance    1 dòng / thẻ tín dụng / tháng
    └── installments_payments  1 dòng / lần trả, hoặc 1 dòng / kỳ bị bỏ lỡ
```

Project chưa dùng `bureau` và `bureau_balance` (lịch sử tín dụng tại tổ chức khác).

## 3. Thời gian tương đối

- Cột `DAYS_*` là số ngày so với ngày nộp hồ sơ hiện tại của khách (số âm là trước ngày đó).
- `MONTHS_BALANCE` là tháng tương đối, `-1` là tháng gần nhất trước ngày nộp hồ sơ hiện tại. Mô tả cột chính thức của `POS_CASH_balance` còn nói `0` nghĩa là thông tin tại ngày nộp hồ sơ, nhưng **dữ liệu thật không có dòng nào `months_balance = 0`**: khoảng giá trị ở cả hai nguồn đều là `-96` đến `-1` (kiểm tra ngày 2026-09-20). Vì vậy `-1` là biên phải duy nhất của cửa sổ dữ liệu.
- Mỗi khách có một mốc riêng: `MONTHS_BALANCE = -5` của hai khách có thể là hai tháng lịch khác nhau.

Hệ quả:

- Không dựng được xu hướng theo tháng lịch, cũng không dựng được vintage theo tháng giải ngân.
- Cách thay thế: phân tích theo MOB, cohort theo thuộc tính hợp đồng (kênh, sản phẩm, nhóm lãi suất), hoặc snapshot tại `months_balance = -1`.

## 4. Giá trị đặc biệt

| Giá trị | Ý nghĩa | Xử lý ở tầng stg |
|---|---|---|
| `365243` trong cột `DAYS_*` | không có giá trị | đổi thành NULL |
| `XNA` | không có thông tin | đổi thành NULL |
| `XAP` | không áp dụng, ví dụ lý do từ chối của hồ sơ được duyệt | đổi thành NULL |

## 5. Thiên lệch mẫu

Danh mục trong project là **các khoản vay trước đây của những khách đã nộp hồ sơ mới** trong mẫu của Kaggle, không phải toàn bộ danh mục của công ty. Khách quay lại vay có thể có hành vi trả nợ khác với khách chỉ vay một lần, nên tỷ lệ tuyệt đối không đại diện cho danh mục thật. Khi trình bày insight, ưu tiên so sánh tương đối giữa các phân khúc.

## 6. Cắt trái và cắt phải

- **Cắt phải (censoring):** lịch sử dừng ở tháng `-1`. Hợp đồng còn mở tại `-1` chưa có kết quả cuối cùng (`dim_loan.end_state = 'censored'`).
- **Cắt trái (truncation):** hợp đồng mở trước cửa sổ dữ liệu có tháng quan sát đầu tiên trùng tháng sớm nhất của bảng, nên MOB tính ra thấp hơn thực tế (`dim_loan.is_left_truncated`). Loại khỏi phân tích vintage.
- **Kết thúc không rõ:** lịch sử dừng trước `-1` mà trạng thái cuối không phải `Completed` (`end_state = 'unknown'`). Đã kiểm tra: 183.144 hợp đồng (17,60% toàn bộ `dim_loan`), trong đó 178.742 không bị cắt trái. Nguyên nhân chính là lịch sử dừng sớm 1 đến 3 tháng chứ không phải hỏng dữ liệu: 93.474 hợp đồng dừng ở tháng `-2`, 9.935 ở `-3`, 3.160 ở `-4`. Trạng thái cuối của nhóm này hầu hết là `Active` (182.739 hợp đồng), trung vị số kỳ còn phải trả là 1. Kết luận: `unknown` về bản chất cũng là cắt phải, chỉ là mốc dừng sớm hơn `-1`. Quyết định: giữ nguyên ba nhãn `closed`, `censored`, `unknown`, và ở tầng mart dùng điều kiện `max_mob >= n` để quyết định hợp đồng có quan sát đủ đến MOB n hay không, thay vì dựa vào nhãn `end_state`.
- **Kiểm tra thêm cho khoản trả góp:** ở MOB 0, 852.464 trên 932.394 hợp đồng POS (91,43%) có số kỳ đã trả (`installments_total - installments_remaining`) bằng 0, đúng như kỳ vọng. 76.197 hợp đồng (8,17%) đã trả trên 0 kỳ ngay tại MOB 0 (`installments_paid_at_open > 0`), tức đã chạy trước cửa sổ dữ liệu. Cờ `is_left_truncated` đã bắt 30.616 trong số đó, còn 45.581 hợp đồng thì cờ cắt trái không bắt được. Riêng nhóm đã trả từ 3 kỳ trở lên (26.249 hợp đồng, 2,82%), cờ cắt trái bắt được 23.166 và bỏ sót 3.083. Phần còn lại của 932.394 hợp đồng gồm 3.732 hợp đồng có số kỳ đã trả âm (số kỳ còn lại lớn hơn tổng số kỳ) và 1 hợp đồng thiếu giá trị. Quyết định: chấp nhận, và khi làm vintage thì loại thêm các hợp đồng có số kỳ đã trả tại MOB 0 lớn hơn 0 (cờ `is_partial_history` trong `dim_loan`: 48.170 hợp đồng cắt trái cộng 45.581 hợp đồng do cờ thứ hai bổ sung, tổng 93.751).

## 7. DPD

- `SK_DPD`: số ngày quá hạn trong tháng.
- `SK_DPD_DEF`: số ngày quá hạn có dung sai, bỏ qua các khoản nợ nhỏ.
- **Giả định ban đầu (đã bị bác bỏ):** dùng `SK_DPD_DEF` làm DPD chính để khoản nợ rất nhỏ không bị tính là quá hạn.
- **Mức chênh giữa hai cột rất lớn, đã đo ngày 2026-09-20.** Số dòng có DPD trên 30 ngày: POS 132.058 theo `dpd_raw` so với 5.834 theo `dpd_def` (chênh 22,6 lần); thẻ tín dụng 54.942 so với 2.079 (chênh 26,4 lần). Tại snapshot `months_balance = -1`, tỷ lệ 30+ của hợp đồng đang mở là 0,17% (POS) và 0,02% (thẻ) theo `dpd_def`, so với 0,41% và 0,40% theo `dpd_raw`. Vintage ever 30+ tại MOB 12 là 0,053% theo `dpd_def` (395 trên 744.208 hợp đồng) so với 0,659% theo `dpd_raw` (4.906 trên 744.208).
- **Quyết định cuối (2026-09-20, người review chốt):** đổi cột DPD chính sang `SK_DPD`, đặt ở cột `dpd`; `SK_DPD_DEF` thành chỉ tiêu phụ ở cột `dpd_tolerant` và cờ `is_30_plus_tolerant`. Lý do: theo cột có dung sai, tử số của hầu hết chỉ tiêu nợ xấu chỉ còn vài trăm hợp đồng trên toàn danh mục, cắt theo kênh thì còn vài chục, không đủ để so sánh phân khúc. Theo `SK_DPD`, tỷ lệ hợp đồng từng quá hạn trên 30 ngày là 1,11% (11.527 trên 1.036.603 hợp đồng). Metric dictionary phiên bản 0.2 đã ghi thay đổi này.
- Mô tả gốc ghi "during the month", chưa rõ là DPD cuối tháng hay cao nhất trong tháng. Nếu là cao nhất, roll rate phản ánh đỉnh trong tháng thay vì trạng thái cuối kỳ.

## 8. Trạng thái hợp đồng

- **Giả định (giữ nguyên sau kiểm tra):** hợp đồng đang mở khi trạng thái là `Active`, `Demand` hoặc `Amortized debt` (macro `core.is_open_status` trong `sql/00_setup.sql`).
- `HomeCredit_columns_description.csv` chỉ ghi `NAME_CONTRACT_STATUS` là "Contract status during the month", **không giải thích từng giá trị**. Vì vậy nghĩa của `Demand`, `Amortized debt`, `Returned to the store`, `Signed`, `Approved`, `Sent proposal` là suy luận, không phải tài liệu chính thức. Cách hiểu đang dùng: `Demand` là khoản đã bị yêu cầu trả toàn bộ trước hạn, `Amortized debt` là khoản đã được cơ cấu lại lịch trả, cả hai vẫn còn nghĩa vụ nợ nên tính là mở; `Signed`, `Approved`, `Sent proposal` là các bước trước khi giải ngân nên chưa mở; `Returned to the store` là hàng đã trả lại nên hợp đồng không còn hiệu lực.
- Phân phối thực tế theo số dòng tháng (2026-09-20). Thẻ tín dụng: `Active` 3.698.436 (96,31%), `Completed` 128.918 (3,36%), `Signed` 11.058 (0,29%), `Demand` 1.365 (0,04%), `Sent proposal` 513, `Refused` 17, `Approved` 5. POS: `Active` 9.151.119 (91,50%), `Completed` 744.883 (7,45%), `Signed` 87.260 (0,87%), `Demand` 7.065 (0,07%), `Returned to the store` 5.461 (0,05%), `Approved` 4.917 (0,05%), `Amortized debt` 636 (0,01%), `Canceled` 15, `XNA` 2.
- **Quyết định:** giữ nguyên macro. `Demand` và `Amortized debt` cộng lại chỉ 9.066 dòng tháng (0,07% toàn bộ), nên giữ hay bỏ gần như không đổi mẫu số, nhưng giữ lại thì không mất nhóm rủi ro nhất. Không thêm `Returned to the store` vào nhóm mở.
- **Quay lại trạng thái mở sau khi `Completed`:** chỉ 18 hợp đồng trên 1.040.632 (0,0017%). Quyết định: coi `Completed` là trạng thái hấp thụ trong roll rate, 18 trường hợp ngoại lệ chấp nhận bỏ qua và ghi lại tại đây.
- Test `int_loan_month__unknown_status` cảnh báo khi xuất hiện trạng thái chưa được phân loại.

## 9. Exposure

- Thẻ tín dụng: `AMT_BALANCE`, số âm tính là 0.
- Khoản trả góp không có cột dư nợ. Proxy: `CNT_INSTALMENT_FUTURE × AMT_ANNUITY`, tức số tiền còn phải trả gồm cả lãi, không phải dư nợ gốc.
- **Độ phủ thực tế (2026-09-20):** `exposure_proxy` null ở 337.877 trên 9.901.621 dòng POS (3,41%), và 0 dòng ở thẻ tín dụng. Nguyên nhân gần như hoàn toàn là hợp đồng không khớp được `previous_application` nên thiếu `annuity_amount` (337.812 trên 337.877 dòng null), chỉ 26 dòng do thiếu `installments_remaining`. Khi báo cáo chỉ tiêu theo exposure phải nêu rõ 3,41% dòng POS bị bỏ qua.
- Chỉ dùng exposure để so sánh tương đối giữa các phân khúc.

## 10. Trùng lặp

- **Hồ sơ trùng:** `previous_application` có thể có nhiều hồ sơ cho cùng một hợp đồng do nhập nhầm. Khi tính funnel, lọc `is_last_appl_per_contract and is_last_appl_in_day`.
- **Hợp đồng ở cả hai bảng tháng:** lấy dữ liệu thẻ, bỏ bản ghi POS (test `sources__loan_in_both`). Trên dữ liệu thật quan sát được **0** hợp đồng như vậy, nên quy tắc này chưa từng loại dòng nào.
- **Nhiều dòng cùng hợp đồng, cùng tháng:** giữ dòng có DPD cao nhất để thận trọng về rủi ro, xếp theo `dpd_raw` (DPD chính) rồi mới đến `dpd_def` (test `sources__duplicate_months`). Trên dữ liệu thật quan sát được **0** cặp (hợp đồng, tháng) trùng: `core.int_loan_month` có 13.841.670 dòng, đúng bằng tổng số dòng của hai bảng nguồn (10.001.358 POS và 3.840.312 thẻ). Cả hai quy tắc khử trùng đều là phòng vệ, không ảnh hưởng số liệu hiện tại.

## 11. Nhật ký kiểm tra

| Ngày | Kiểm tra | Kết quả | Quyết định |
|---|---|---|---|
| 2026-09-20 | Build toàn bộ `stg` và `core` trên dữ liệu thật | 45 giây. 9 test đạt, 2 test mức cảnh báo fail: `dim_loan__missing_application` 48.794 dòng, `fct_loan_month__month_gaps` 375 dòng. Không có test mức lỗi nào fail | Chấp nhận cả hai cảnh báo, xem hai dòng cuối bảng |
| 2026-09-20 | Khoảng giá trị `months_balance` (mục 3) | Cả POS và thẻ đều từ `-96` đến `-1`. Không có dòng nào `months_balance = 0` | Giữ nguyên logic `end_state = 'censored'` khi `last_observed_month = -1`. Không cần xử lý tháng 0 |
| 2026-09-20 | Chênh lệch `SK_DPD` và `SK_DPD_DEF` (mục 7) | Số dòng 30+: POS 132.058 theo raw so với 5.834 theo def; thẻ 54.942 so với 2.079. Vintage ever 30+ tại MOB 12: 0,659% theo raw (4.906 / 744.208) so với 0,053% theo def (395 / 744.208), đo trên mẫu số sau khi loại `is_partial_history` (số đo ban đầu trên mẫu số cũ là 0,662% và 0,055%) | Người review chốt: đổi cột chính sang `SK_DPD`. Cột có dung sai thành chỉ tiêu phụ `dpd_tolerant` |
| 2026-09-20 | Cờ cắt trái thứ hai cho vintage | 76.197 hợp đồng đã trả trên 0 kỳ ngay tại MOB 0 (`installments_paid_at_open > 0`). 30.616 trong số đó đã bị `is_left_truncated` bắt, 45.581 hợp đồng thì không | Thêm cột `dim_loan.installments_paid_at_open` và cờ `is_partial_history` (cắt trái hoặc `installments_paid_at_open > 0`): 48.170 + 45.581 = 93.751 hợp đồng. Mart vintage loại các hợp đồng có cờ này |
| 2026-09-20 | Ý nghĩa và phân phối `contract_status` (mục 8) | File mô tả cột không giải thích từng giá trị. `Demand` 8.430 dòng và `Amortized debt` 636 dòng, cộng lại 0,07% số dòng tháng | Giữ nguyên macro `core.is_open_status`. Không thêm `Returned to the store` (5.461 dòng) vào nhóm mở |
| 2026-09-20 | Hợp đồng `Completed` rồi quay lại trạng thái mở | 18 hợp đồng trên 1.040.632 (0,0017%) | Coi `Completed` là trạng thái hấp thụ trong roll rate, bỏ qua 18 ngoại lệ |
| 2026-09-20 | Trạng thái kết thúc `unknown` (mục 6) | 183.144 hợp đồng (17,60%). 93.474 dừng ở tháng `-2`, 9.935 ở `-3`, 3.160 ở `-4`; 182.739 có trạng thái cuối là `Active`, trung vị số kỳ còn lại là 1 | Coi `unknown` là một dạng cắt phải. Mart vintage lọc theo `max_mob >= n`, không lọc theo nhãn `end_state` |
| 2026-09-20 | Số kỳ đã trả tại MOB 0 của khoản trả góp (mục 6) | 852.464 trên 932.394 hợp đồng (91,43%) đã trả 0 kỳ. 76.197 hợp đồng (8,17%) đã trả trên 0 kỳ, trong đó 26.249 hợp đồng (2,82%) đã trả từ 3 kỳ trở lên. Cờ `is_left_truncated` bắt được 30.616 trên 76.197, và 23.166 trên 26.249 | `first_open_month` dùng được. Vintage loại thêm hợp đồng đã trả trên 0 kỳ tại MOB 0 |
| 2026-09-20 | Cấu trúc `installments_payments` (M11) | 13.605.401 dòng, 997.752 hợp đồng, 965.131 hợp đồng có kỳ 1. 0 dòng trùng hoàn toàn. 2.905 dòng (0,02%) có `days_paid` null. 290 dòng (0,002%) có `installment_amount = 0`. 629.210 kỳ được trả thành 2 lần, 11.000 kỳ trả 3 lần | Cộng các lần trả trong cùng kỳ trước khi so sánh với số tiền phải trả |
| 2026-09-20 | Phiên bản lịch trả của kỳ 1 (M11) | Version 1 ở 879.110 hợp đồng, version 0 (thẻ tín dụng) ở 64.386, version 2 ở 39.091. 18.903 hợp đồng có từ 2 version trở lên cho kỳ 1 | Quy tắc chốt: bỏ `installment_version = 0` vì là thẻ tín dụng, lấy version nhỏ nhất còn lại, tức lịch trả gốc |
| 2026-09-20 | Khả năng đo FPD30 (M11) | Mẫu số 895.744 hợp đồng POS có kỳ 1 đến hạn trước ít nhất 30 ngày. Tử số theo quy tắc số tiền, dung sai 5%: 99 hợp đồng (0,011%). Theo quy tắc `days_late > 30`: 524 hợp đồng (0,0585%) | Chấp nhận dung sai 5%. Cảnh báo lớn: bảng chỉ ghi các kỳ đã trả, 50,35% hợp đồng có số dòng kỳ ít hơn số kỳ theo hợp đồng, nên hợp đồng không trả kỳ 1 hầu như biến mất khỏi mẫu. FPD30 đo được là chặn dưới, phải ghi rõ trên báo cáo |
| 2026-09-20 | Độ phủ `previous_application` so với lịch sử tháng | Sau lọc trùng còn 1.660.953 hồ sơ, trong đó 1.036.044 `Approved`. Trong nhóm `Approved`: 991.128 (95,66%) có lịch sử tháng trong `dim_loan`, 958.159 (92,48%) có kỳ 1 trong `installments_payments`. Ngược lại 48.794 hợp đồng trong `dim_loan` (4,69%) không khớp được hồ sơ nào | Chấp nhận. 48.794 hợp đồng thiếu thuộc tính phân khúc phải gom vào nhóm `(không rõ)` trên mọi mart cắt theo kênh hoặc sản phẩm |
| 2026-09-20 | `exposure_proxy` null (mục 9) | POS 337.877 trên 9.901.621 dòng (3,41%), thẻ 0%. 337.812 dòng null do hợp đồng không có hồ sơ nên thiếu `annuity_amount` | Chấp nhận. Báo cáo theo exposure phải ghi rõ số dòng bị bỏ qua |
| 2026-09-20 | Số hợp đồng dùng được cho vintage | Số đo ban đầu, chỉ loại cắt trái và `never_open` (chưa loại cờ `is_partial_history`): 990.518 hợp đồng. Có kết quả đến MOB 6: 910.311; MOB 12: 782.119; MOB 24: 715.058. Nếu chỉ tính hợp đồng thực sự quan sát đủ số tháng (`max_mob >= n`): 762.551 / 321.788 / 72.721. Sau khi loại thêm `is_partial_history`: 944.937 hợp đồng. Có kết quả đến MOB 6: 868.559; MOB 12: 744.208; MOB 24: 679.223. Quan sát đủ: 731.065 / 308.901 / 70.635 | Dùng mẫu số sau khi loại `is_partial_history`, gồm cả hợp đồng đã tất toán sớm (868.559 / 744.208 / 679.223) theo đúng M08. Báo cáo kèm số hợp đồng quan sát đủ để người đọc thấy độ mỏng ở MOB 24 |
| 2026-09-20 | Phân khúc đủ lớn để báo cáo | `channel_type` 8 giá trị, nhỏ nhất `Car dealer` 452 hồ sơ (0,03%) và `Channel of corporate sales` 6.117 (0,37%). `contract_type` 3 giá trị, nhỏ nhất `Revolving loans` 184.590 (11,11%). `client_type`: `Repeater` 73,63%, `New` 18,13%, `Refreshed` 8,12%. `yield_group`: 30,62% null, `middle` 23,19%, `high` 21,26%, `low_normal` 19,38%, `low_action` 5,54% | Gom `Car dealer` và `Channel of corporate sales` vào nhóm `Khác` khi cắt theo kênh. `yield_group` null giữ thành một nhóm riêng vì chiếm gần một phần ba |
| 2026-09-20 | Cặp tháng liên tiếp cho roll rate (M09) | 13.730.112 dòng, 12.693.134 cặp cách nhau đúng 1 tháng (92,45%), 1.036.603 dòng không có tháng kế tiếp (7,55%, đếm trên toàn bảng, mỗi hợp đồng có đúng một dòng cuối), 375 cặp bị hở tháng. Trong 1.036.603 dòng đó: 144.421 dòng đang mở ở tháng `-1` (cắt phải, bị loại khỏi trạng thái xuất phát), 709.361 dòng không ở trạng thái mở (không phải trạng thái xuất phát) và 182.821 dòng đang mở ở tháng `t <= -2` | Dòng xuất phát hợp lệ mà không có tháng kế tiếp (182.821 dòng, cộng 26 dòng hở tháng thành 182.847) phải vào trạng thái `Missing` trong ma trận roll rate, không được loại âm thầm |
| 2026-09-20 | Cảnh báo `dim_loan__missing_application` | 48.794 dòng | Chấp nhận, là thực tế dữ liệu Kaggle. Xem dòng độ phủ ở trên |
| 2026-09-20 | Cảnh báo `fct_loan_month__month_gaps` | 375 dòng trên 13,7 triệu (0,003%) | Chấp nhận. Roll rate chỉ dùng cặp tháng cách nhau đúng 1 tháng nên các cặp hở tự động bị loại |
