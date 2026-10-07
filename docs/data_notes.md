# Data Notes

Ghi chép cách hiểu dữ liệu, các giả định đã chọn và giới hạn. Các giả định được xác nhận trên dữ liệu thật bằng `sql/explore/01_profile.sql` và các kiểm tra bổ sung, lần đầu ngày 2026-09-20 và soát lại ngày 2026-10-04 sau khi đổi định nghĩa quá hạn. Kết quả ghi vào [mục 11](#11-nhật-ký-kiểm-tra). Số liệu kết luận lấy từ `data/export/findings.json`.

## 1. Nguồn và điều khoản

- Dữ liệu: [Home Credit Default Risk](https://www.kaggle.com/competitions/home-credit-default-risk/data), Kaggle, 2018.
- Chỉ dùng cho mục đích học tập theo luật của competition. **Không đưa dữ liệu gốc lên GitHub** (`data/raw/` và kho `data/warehouse.duckdb` nằm trong `.gitignore`). Ngoại lệ: 5 file CSV tổng hợp nhỏ và `findings.json` ở `data/export/` (mỗi dòng CSV là một tổ hợp phân khúc, không phải một hợp đồng) được commit. Điều khoản: [`DATA_NOTICE.md`](../DATA_NOTICE.md).
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
- `MONTHS_BALANCE` là tháng tương đối, `-1` là tháng gần nhất trước ngày nộp hồ sơ hiện tại. Mô tả cột chính thức của `POS_CASH_balance` còn nói `0` nghĩa là thông tin tại ngày nộp hồ sơ, nhưng **dữ liệu thật không có dòng nào `months_balance = 0`**: khoảng giá trị ở cả hai nguồn đều là `-96` đến `-1`. Vì vậy `-1` là biên phải duy nhất của cửa sổ dữ liệu.
- Mỗi khách có một mốc riêng: `MONTHS_BALANCE = -5` của hai khách có thể là hai tháng lịch khác nhau.

Hệ quả:

- Không dựng được xu hướng theo tháng lịch, cũng không dựng được vintage theo tháng giải ngân theo lịch. Vintage theo đợt mở tương đối (`origination_cohort`) thì dựng được, nhưng chỉ đọc như một biến kiểm soát ([methodology mục 5.10](methodology.md#510-đợt-mở-hợp-đồng-biến-gây-nhiễu-thứ-hai)).
- Cách thay thế: phân tích theo MOB, cohort theo thuộc tính hợp đồng (kênh, sản phẩm, nhóm lãi suất), hoặc snapshot tại `months_balance = -1`.

## 4. Giá trị đặc biệt

| Giá trị | Ý nghĩa | Xử lý ở tầng stg |
|---|---|---|
| `365243` trong cột `DAYS_*` | không có giá trị (với `DAYS_TERMINATION`: chưa kết thúc; với `DAYS_FIRST_DUE`: không có lịch trả) | đổi thành NULL |
| `XNA` | không có thông tin | đổi thành NULL |
| `XAP` | không áp dụng, ví dụ lý do từ chối của hồ sơ được duyệt | đổi thành NULL |

## 5. Thiên lệch mẫu

Danh mục trong project là **các khoản vay trước đây của những khách đã nộp hồ sơ mới** trong mẫu của Kaggle, không phải toàn bộ danh mục của công ty. Khách quay lại vay có thể có hành vi trả nợ khác với khách chỉ vay một lần, nên tỷ lệ tuyệt đối không đại diện cho danh mục thật. Khi trình bày insight, ưu tiên so sánh tương đối giữa các phân khúc.

## 6. Cắt trái, cắt phải và trạng thái kết thúc

- **Cắt phải (censoring):** lịch sử dừng ở tháng `-1`. Hợp đồng còn mở tại `-1` chưa có kết quả cuối cùng (`dim_loan.end_state = 'censored'`, 144.421 hợp đồng).
- **Cắt trái (truncation):** hợp đồng mở trước cửa sổ dữ liệu có tháng quan sát đầu tiên trùng tháng sớm nhất của bảng, nên MOB tính ra thấp hơn thực tế (`dim_loan.is_left_truncated`). Loại khỏi phân tích vintage.
- **Dừng trước tháng `-1` khi trạng thái cuối vẫn mở.** 183.144 hợp đồng. Phiên bản trước gọi cả nhóm là `unknown` và mô tả là "dừng sớm 1 đến 3 tháng", tức cắt phải. Kiểm tra lại ngày 2026-10-04 cho thấy mô tả đó sai: không hợp đồng nào dừng ở tháng `-5` đến `-16`, và nhóm tách làm hai.
  - Dừng ở tháng `-17` hoặc sớm hơn: 76.575 hợp đồng, toàn POS. 74.270 có `DAYS_TERMINATION`, trung vị còn 1 kỳ phải trả; 2.305 còn lại (hầu hết thiếu hồ sơ) không có.
  - Dừng ở tháng `-2` đến `-4`: 106.569 hợp đồng. POS 72.486 (13.767 có `DAYS_TERMINATION`; 58.719 không có, trung vị còn 9 kỳ), thẻ 34.083 (1.377 có).
  - Bằng chứng `DAYS_TERMINATION` hoạt động như ngày kết thúc thực: ở hợp đồng POS có hồ sơ, giá trị này đã qua ở 99,96% hợp đồng `closed` và trùng tháng `Completed` (trung vị lệch 0,0 tháng); ở hợp đồng `censored`, 92,2% là `365243` (ở thẻ là 99,1%); ở nhóm dừng từ tháng `-17` trở về trước, 74.270 trên 74.294 hợp đồng có hồ sơ có ngày kết thúc, trung vị 0,9 tháng sau dòng cuối.
  - **Quyết định:** hợp đồng trong nhóm này có `DAYS_TERMINATION` nhận nhãn `closed_inferred` (89.414 hợp đồng) và vào mẫu số vintage như hợp đồng đã đóng; phần còn lại giữ nhãn `unknown` (93.730) và chỉ vào mẫu số tại MOB n khi `max_mob >= n`. Mô tả chính thức của cột là "expected termination", nên đây là suy luận. Độ nhạy của quy tắc: [methodology mục 5.3](methodology.md#53-hợp-đồng-dừng-sớm-closed_inferred-và-unknown).
- **Phân bố `end_state` hiện tại:** `closed` 709.038, `closed_inferred` 89.414, `unknown` 93.730, `censored` 144.421, `never_open` 4.029.
- **Kiểm tra thêm cho khoản trả góp:** ở MOB 0, 852.464 trên 932.394 hợp đồng POS (91,43%) có số kỳ đã trả (`installments_total - installments_remaining`) bằng 0, đúng như kỳ vọng. 76.197 hợp đồng (8,17%) đã trả trên 0 kỳ ngay tại MOB 0 (`installments_paid_at_open > 0`), tức đã chạy trước cửa sổ dữ liệu. Cờ `is_left_truncated` đã bắt 30.616 trong số đó, còn 45.581 hợp đồng thì cờ cắt trái không bắt được. Quyết định: khi làm vintage loại thêm các hợp đồng có số kỳ đã trả tại MOB 0 lớn hơn 0 (cờ `is_partial_history` trong `dim_loan`: 48.170 hợp đồng cắt trái cộng 45.581 hợp đồng do cờ thứ hai bổ sung, tổng 93.751).

## 7. DPD

- `SK_DPD` (POS): "DPD (days past due) during the month of previous credit". Thẻ: "DPD (Days past due) during the month on the previous credit".
- `SK_DPD_DEF` (POS): "DPD during the month with tolerance (debts with low loan amounts are ignored) of the previous credit". Thẻ: "DPD (Days past due) during the month with tolerance (debts with low loan amounts are ignored) of the previous credit".
- **Định nghĩa chính từ 2026-10-04: `SK_DPD_DEF`** (DPD có ngưỡng trọng yếu), ở cột `dpd` và các cột gốc. `SK_DPD` chỉ còn là độ nhạy, ở cột `dpd_no_threshold` và các cột hậu tố `_no_threshold`.
- **Lịch sử quyết định.** Giả định ban đầu (2026-09-13) là dùng `SK_DPD_DEF`. Ngày 2026-09-20 đổi sang `SK_DPD` vì theo `SK_DPD_DEF` tử số quá mỏng: ever 30+@MOB12 chỉ 0,053% (395 trên 744.208) so với 0,659% (4.906 trên 744.208). Ngày 2026-10-04 đổi lại về `SK_DPD_DEF` sau khi phát hiện `SK_DPD` đo phần lớn là khoản dư lẻ ([methodology mục 4](methodology.md#4-quyết-định-đã-đảo-ngược-định-nghĩa-quá-hạn)).
- **Bằng chứng (2026-10-04).** Ở các tháng POS đang mở thuộc bucket theo `SK_DPD`: B2 có 7.942 tháng, 66,8% có `SK_DPD_DEF = 0`, 72,2% không còn kỳ nào phải trả; B3 có 4.993 tháng, 93,5% và 94,6%; B4 có 108.970 tháng, 95,8% và 99,8%. Trung vị dư nợ ước lượng của cả ba nhóm là 0. Ở thẻ, tháng B4 theo `SK_DPD` có 97,7% `SK_DPD_DEF = 0`, trung vị dư nợ 209 đơn vị tiền. Không có dòng nào `SK_DPD_DEF > SK_DPD`.
- **Mức chênh hiện tại.** Ever 30+@MOB12: 0,052% theo `SK_DPD_DEF` (425 trên 818.672) so với 0,637% theo `SK_DPD` (5.215 trên 818.672). Danh mục đang mở tại tháng `-1`: 159 hợp đồng 30+ theo `SK_DPD_DEF`, 585 theo `SK_DPD`, trên 144.421.
- Ngưỡng "low loan amounts" không được công bố; không biết là tuyệt đối hay tương đối.
- Mô tả gốc ghi "during the month", chưa rõ là DPD cuối tháng hay cao nhất trong tháng. Nếu là cao nhất, roll rate phản ánh đỉnh trong tháng thay vì trạng thái cuối kỳ.

## 8. Trạng thái hợp đồng

- **Giả định (giữ nguyên sau kiểm tra):** hợp đồng đang mở khi trạng thái là `Active`, `Demand` hoặc `Amortized debt` (macro `core.is_open_status` trong `sql/00_setup.sql`).
- `HomeCredit_columns_description.csv` chỉ ghi `NAME_CONTRACT_STATUS` là "Contract status during the month", **không giải thích từng giá trị**. Vì vậy nghĩa của `Demand`, `Amortized debt`, `Returned to the store`, `Signed`, `Approved`, `Sent proposal` là suy luận, không phải tài liệu chính thức. Cách hiểu đang dùng: `Demand` là khoản đã bị yêu cầu trả toàn bộ trước hạn, `Amortized debt` là khoản đã được cơ cấu lại lịch trả, cả hai vẫn còn nghĩa vụ nợ nên tính là mở; `Signed`, `Approved`, `Sent proposal` là các bước trước khi giải ngân nên chưa mở; `Returned to the store` là hàng đã trả lại nên hợp đồng không còn hiệu lực.
- **Quyết định:** giữ nguyên macro. `Demand` và `Amortized debt` cộng lại chỉ khoảng 0,07% số dòng tháng, nên giữ hay bỏ gần như không đổi mẫu số, nhưng giữ lại thì không mất nhóm rủi ro nhất. Không thêm `Returned to the store` vào nhóm mở.
- **Quay lại trạng thái mở sau khi `Completed`:** chỉ 18 hợp đồng trên 1.040.632 (0,0017%). Quyết định: coi `Completed` là trạng thái hấp thụ trong roll rate.
- Test `int_loan_month__unknown_status` cảnh báo khi xuất hiện trạng thái chưa được phân loại.

## 9. Exposure

- Thẻ tín dụng: `AMT_BALANCE`, số âm tính là 0.
- Khoản trả góp không có cột dư nợ. Proxy: `CNT_INSTALMENT_FUTURE × AMT_ANNUITY`, tức số tiền còn phải trả gồm cả lãi, không phải dư nợ gốc.
- **Độ phủ:** `exposure_proxy` null ở 3,41% dòng POS và 0 dòng ở thẻ tín dụng. Nguyên nhân gần như hoàn toàn là hợp đồng không khớp được `previous_application` nên thiếu `annuity_amount`. Trong danh mục đang mở tại tháng `-1`, 110 hợp đồng không có exposure, 24 trong số đó đang 30+; vì vậy tỷ lệ 30+ theo hợp đồng và theo dư nợ chỉ đặt cạnh nhau khi cùng tính trên tập có exposure (cột `n_loans_exposure_known`, `n_30_plus_exposure_known` của `mart.portfolio_snapshot`).
- Chỉ dùng exposure để so sánh tương đối giữa các phân khúc. Dữ liệu không có LGD, số tiền xoá nợ hay số tiền thu hồi.

## 10. Trùng lặp

- **Hồ sơ trùng:** `previous_application` có thể có nhiều hồ sơ cho cùng một hợp đồng do nhập nhầm. Khi tính funnel và đếm hồ sơ duyệt cho FPD, lọc `is_last_appl_per_contract and is_last_appl_in_day`.
- **Hợp đồng ở cả hai bảng tháng:** lấy dữ liệu thẻ, bỏ bản ghi POS (test `sources__loan_in_both`). Trên dữ liệu thật quan sát được **0** hợp đồng như vậy.
- **Nhiều dòng cùng hợp đồng, cùng tháng:** giữ dòng có DPD cao nhất để thận trọng về rủi ro, xếp theo `dpd_def` (định nghĩa chính) rồi mới đến `dpd_raw` (test `sources__duplicate_months`). Trên dữ liệu thật quan sát được **0** cặp (hợp đồng, tháng) trùng. Cả hai quy tắc khử trùng đều là phòng vệ, không ảnh hưởng số liệu hiện tại.

## 11. Nhật ký kiểm tra

Các dòng ngày 2026-09-20 ghi lại kiểm tra ban đầu; dòng nào bị thay thế có ghi chú "thay bởi" và trỏ tới dòng 2026-10-04 tương ứng.

| Ngày | Kiểm tra | Kết quả | Quyết định |
|---|---|---|---|
| 2026-09-20 | Build toàn bộ `stg` và `core` trên dữ liệu thật | Không có test mức lỗi nào fail; 2 test mức cảnh báo: `dim_loan__missing_application` 48.794 dòng, `fct_loan_month__month_gaps` 375 dòng | Chấp nhận cả hai cảnh báo |
| 2026-09-20 | Khoảng giá trị `months_balance` (mục 3) | Cả POS và thẻ đều từ `-96` đến `-1`. Không có dòng nào `months_balance = 0` | Giữ logic `end_state = 'censored'` khi `last_observed_month = -1` |
| 2026-09-20 | Chênh lệch `SK_DPD` và `SK_DPD_DEF` (mục 7) | Ever 30+@MOB12: 0,659% theo `SK_DPD` (4.906 / 744.208) so với 0,053% theo `SK_DPD_DEF` (395 / 744.208) | Đổi cột chính sang `SK_DPD`. **Thay bởi** dòng 2026-10-04 về định nghĩa quá hạn |
| 2026-09-20 | Cờ cắt trái thứ hai cho vintage | 76.197 hợp đồng đã trả trên 0 kỳ ngay tại MOB 0. 30.616 trong số đó đã bị `is_left_truncated` bắt, 45.581 thì không | Thêm `dim_loan.installments_paid_at_open` và cờ `is_partial_history`: 48.170 + 45.581 = 93.751 hợp đồng. Mart vintage loại các hợp đồng có cờ này |
| 2026-09-20 | Ý nghĩa và phân phối `contract_status` (mục 8) | File mô tả cột không giải thích từng giá trị. `Demand` và `Amortized debt` cộng lại khoảng 0,07% số dòng tháng | Giữ nguyên macro `core.is_open_status` |
| 2026-09-20 | Hợp đồng `Completed` rồi quay lại trạng thái mở | 18 hợp đồng trên 1.040.632 (0,0017%) | Coi `Completed` là trạng thái hấp thụ trong roll rate |
| 2026-09-20 | Trạng thái kết thúc `unknown` (mục 6) | 183.144 hợp đồng, mô tả là "dừng sớm 1 đến 3 tháng" | Coi là cắt phải. **Thay bởi** dòng 2026-10-04 về `closed_inferred` |
| 2026-09-20 | Số kỳ đã trả tại MOB 0 của khoản trả góp (mục 6) | 852.464 trên 932.394 hợp đồng (91,43%) đã trả 0 kỳ; 76.197 (8,17%) đã trả trên 0 kỳ | `first_open_month` dùng được. Vintage loại thêm hợp đồng đã trả trên 0 kỳ tại MOB 0 |
| 2026-09-20 | Phiên bản lịch trả của kỳ 1 (M11) | 18.903 hợp đồng có từ 2 version trở lên cho kỳ 1 (không tính version 0 của thẻ) | Quy tắc chốt trên giấy: bỏ version 0, lấy version nhỏ nhất còn lại. Code khi đó chưa làm đúng, **sửa** ở dòng 2026-10-04 về FPD30 |
| 2026-09-20 | Khả năng đo FPD30 (M11) | 77.885 hồ sơ duyệt không có dòng kỳ 1, khi đó được hiểu là hợp đồng xấu biến khỏi mẫu số | Gọi FPD30 là chặn dưới. **Thay bởi** dòng 2026-10-04 về FPD30 |
| 2026-09-20 | Độ phủ `previous_application` so với lịch sử tháng | Sau lọc trùng còn 1.660.953 hồ sơ, trong đó 1.036.044 `Approved`. 48.794 hợp đồng trong `dim_loan` không khớp được hồ sơ nào | Gom 48.794 hợp đồng vào nhóm `(không rõ)` trên mọi mart cắt theo kênh hoặc sản phẩm |
| 2026-09-20 | `exposure_proxy` null (mục 9) | 3,41% dòng POS, 0% dòng thẻ, gần như toàn bộ do thiếu hồ sơ | Báo cáo theo exposure phải ghi rõ số dòng bị bỏ qua |
| 2026-09-20 | Phân khúc đủ lớn để báo cáo | `Car dealer` 452 hồ sơ, `Channel of corporate sales` 6.117; `yield_group` null ở khoảng 30% hồ sơ | Gom hai kênh nhỏ vào `Khác`; `yield_group` null giữ thành nhóm `Unknown` |
| 2026-09-20 | Cặp tháng liên tiếp cho roll rate (M09) | 12.693.134 trên 13.730.112 dòng (92,45%) có tháng kế tiếp cách đúng 1 tháng; 375 cặp hở tháng | Dòng xuất phát hợp lệ mà không có tháng kế tiếp vào trạng thái `Missing` (182.847 lượt), không loại âm thầm |
| 2026-10-04 | Định nghĩa quá hạn (mục 7) | Ở tháng POS đang mở thuộc B4 theo `SK_DPD`: 95,8% có `SK_DPD_DEF = 0`, 99,8% không còn kỳ phải trả, dư nợ trung vị 0 (108.970 tháng) | Định nghĩa chính đổi về `SK_DPD_DEF`; `SK_DPD` thành độ nhạy `_no_threshold`; bỏ cột `*_tolerant` |
| 2026-10-04 | Nhóm dừng trước tháng `-1` (mục 6) | 76.575 dừng ở `-17` hoặc sớm hơn, 106.569 dừng ở `-2` đến `-4`, 0 ở `-5` đến `-16`. `DAYS_TERMINATION` trùng tháng `Completed` ở hợp đồng đóng, là `365243` ở 92,2% hợp đồng `censored` POS | Thêm nhãn `closed_inferred` (89.414); `unknown` còn 93.730. Mẫu số vintage tại MOB 12 từ 744.208 thành 818.672, tại MOB 24 từ 679.223 thành 763.989 |
| 2026-10-04 | FPD30 (M11) | 77.884 trên 77.885 hồ sơ duyệt không có dòng kỳ 1 cũng không có lịch trả (`DAYS_FIRST_DUE` trống hoặc `365243`); 1 hồ sơ có lịch trả. Code cũ cộng tiền trả qua mọi version của kỳ 1; ở 18.595 trên 18.903 hợp đồng nhiều version, cùng một lần trả bị ghi lặp ở mỗi version | Bỏ nhãn chặn dưới. Tách `n_approved_not_activated` và `n_approved_scheduled_no_installment`. Lấy đúng version nhỏ nhất: FPD30 0,011% (99 / 895.744), quy tắc ngày 0,058% (523 / 895.744) |
| 2026-10-04 | Nhóm `(không rõ)` | Tại MOB 12: 2.083 hợp đồng, 106 trên 425 ca 30+ (5,089%). Danh mục đang mở: 4,72% hợp đồng, 18,2% ca 30+ | Chưa giải thích được. Mọi tổng toàn danh mục báo kèm tổng không gồm nhóm này (0,039%, tức 319 / 816.589) |
| 2026-10-04 | Quan sát đủ đến MOB n | MOB 12: 308.901 trên 818.672 (37,7%); MOB 24: 70.635 trên 763.989 (9,2%). Tại MOB 12: thẻ 95,2%, vay tiền mặt 52,8%, vay tiêu dùng 24,8% | So sánh sản phẩm kiểm lại ở MOB 6; không diễn giải đuôi đường cong nếu không in kèm `n_observed_full` |
| 2026-10-04 | Đợt mở hợp đồng (lần soát thứ hai) | Ever 30+@MOB12 ba sản phẩm: 0,192% ở đợt -96 đến -85, 0,010% ở đợt -24 đến -13; 77,2% thẻ của Credit and cash offices mở từ tháng -35 trở về sau, Contact center 21,1% | Thêm `origination_cohort` vào `mart.vintage`; phân tầng sản phẩm × đợt cho mọi so sánh kênh, sản phẩm |
| 2026-10-04 | Định nghĩa giữa | Trả góp `SK_DPD` trên 30 ở tháng còn kỳ phải trả: vay tiêu dùng 874 / 530.476, vay tiền mặt 214 / 225.408 tại MOB 12 | Thêm cột độ nhạy `n_ever_30_plus_due_only` |
| 2026-10-04 | Nhóm `(không rõ)` trong vintage | 46.178 trên 48.794 hợp đồng mang cờ `is_partial_history`; mẫu số MOB 0 còn 2.605; 512 hợp đồng `unknown` bị loại tại MOB 12 vì `closed_inferred` cần hồ sơ | Ghi ở methodology mục 5.6; tỷ lệ nếu coi là đã đóng 4,35% |
| 2026-10-04 | Data test sau lần soát thứ hai | 32 test (26 error, 6 warn), 0 test error hỏng | Thêm `vintage__cohort_matches_core` |
| 2026-10-04 | Data test sau khi làm lại pipeline | 31 test (25 error, 6 warn). 29 đạt, 2 cảnh báo đã biết (`dim_loan__missing_application` 48.794 dòng, `fct_loan_month__month_gaps` 375 dòng), 0 test error hỏng | Chấp nhận hai cảnh báo |
| 2026-10-04 | Tính tất định | Dựng lại kho từ đầu lần hai cho 5 CSV và `findings.json` giống hệt từng byte | `PRAGMA threads=1` ở `build.py` và `compute_findings.py`; CSV xuất có `order by all` |
| 2026-10-04 | Cảnh báo `dim_loan__missing_application` | 48.794 dòng | Chấp nhận, là thực tế dữ liệu Kaggle |
| 2026-10-04 | Cảnh báo `fct_loan_month__month_gaps` | 375 dòng trên 13,7 triệu (0,003%) | Chấp nhận. Roll rate chỉ dùng cặp tháng cách nhau đúng 1 tháng nên các cặp hở tự động bị loại |
