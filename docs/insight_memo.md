# Memo: chất lượng danh mục theo kênh bán và cửa sổ thu hồi

**Ghi chú:** số liệu lấy từ bộ dữ liệu công khai Home Credit Default Risk trên Kaggle, dùng cho mục đích học tập. Đây không phải số thật của một công ty tài chính tiêu dùng cụ thể nào.

**Gửi:** Giám đốc Rủi ro, Giám đốc Kinh doanh. **Ngày:** 2026-09-20. **Nguồn số:** mục 5.

| Thuật ngữ | Nghĩa dùng trong memo |
|---|---|
| Bucket (nhóm ngày quá hạn) | B0 là 0 ngày, B1 là 1 đến 30 ngày, B2 là 31 đến 60, B3 là 61 đến 90, B4 là trên 90 |
| MOB (month on book) | tuổi hợp đồng tính bằng tháng kể từ tháng bắt đầu mở. MOB 12 là tháng thứ 12 |
| Vintage | cách so các nhóm hợp đồng ở cùng tuổi MOB, để nhóm mới và nhóm cũ không bị so lệch |
| Từng quá hạn 30+ tại MOB 12 | tỷ lệ hợp đồng từng có ít nhất một tháng quá hạn trên 30 ngày tính đến MOB 12 |
| Cure rate (tỷ lệ hồi phục) | tỷ lệ hợp đồng đang quá hạn ở một tháng quay về không quá hạn ngay tháng sau |
| Nhiễu do cơ cấu (confounding) | hai kênh khác nhau về rủi ro chỉ vì bán rổ sản phẩm khác nhau, không phải vì bản thân kênh |

## 1. Kết luận

**Khoảng cách rủi ro giữa các kênh nhỏ hơn nhiều so với con số thô.** Nhìn thô, kênh Stone xấu hơn kênh Credit and cash offices khoảng 8 lần. Nhưng hai kênh bán hai rổ sản phẩm khác hẳn nhau, nên phần lớn khoảng cách đó là do sản phẩm. So trong cùng sản phẩm: ở vay tiêu dùng trả góp, Stone 1,067% (1.445 trên 135.415 hợp đồng) so với Regional / Local 0,530% (365 trên 68.897), gấp 2,0 lần; ở vay tiền mặt, Country-wide 0,437% (78 trên 17.844) so với Credit and cash offices 0,099% (175 trên 175.921), gấp 4,4 lần.

**Rủi ro dồn vào một nhóm nhỏ.** Trong vay tiêu dùng, nhóm hợp đồng của Stone hoặc Country-wide, thuộc khách mới và nhóm lãi suất cao, chiếm 14,0% số hợp đồng (64.462 trên 459.716) nhưng gánh 33,7% số hợp đồng từng quá hạn trên 30 ngày (1.373 trên 4.071). Tỷ lệ của nhóm là 2,130%, gấp 3,1 lần phần vay tiêu dùng còn lại (0,683%, tức 2.698 trên 395.254).

**Cửa sổ thu hồi rất hẹp.** 50,1% lượt hợp đồng quá hạn 1 đến 30 ngày quay về không quá hạn ngay tháng sau (129.922 trên 259.546 lượt), nhưng ở nhóm quá hạn 61 đến 90 ngày chỉ còn 7,0% (505 trên 7.172 lượt).

**Đề xuất:** siết duyệt đúng nhóm 14,0% nói trên, và dồn nhắc nợ vào 30 ngày quá hạn đầu tiên. Cả hai chạy dưới dạng thử nghiệm có nhóm đối chứng, chi tiết ở mục 3.

## 2. Bằng chứng

### 2.1. So kênh phải so trong cùng sản phẩm, nếu không sẽ đọc nhầm

Nhìn thô, Stone duyệt nhiều nhất và xấu nhất, Credit and cash offices duyệt ít nhất và tốt nhất, khoảng cách khoảng 8 lần. Nhưng hai kênh này bán hai rổ sản phẩm gần như không giao nhau, và bản thân sản phẩm đã chênh nhau nhiều lần về rủi ro, nên phần lớn khoảng cách đó là nhiễu do cơ cấu sản phẩm.

| Kênh | Tỷ lệ duyệt | Vay tiêu dùng | Vay tiền mặt | Thẻ quay vòng | Từng quá hạn 30+ tại MOB 12 (số thô) |
|---|---|---|---|---|---|
| Stone | 89,8% (189.948 / 211.409) | 96,9% | 1,2% | 1,9% | 1,068% (1.492 / 139.686) |
| Country-wide | 87,0% (426.961 / 490.936) | 89,7% | 6,3% | 4,0% | 0,868% (2.468 / 284.403) |
| Regional / Local | 89,7% (97.047 / 108.158) | 95,6% | 2,0% | 2,5% | 0,527% (380 / 72.096) |
| Credit and cash offices | 66,4% (289.199 / 435.708) | 0% | 85,2% | 14,8% | 0,132% (272 / 206.463) |

| Sản phẩm | Hợp đồng tại MOB 12 | Từng quá hạn 30+ | Tỷ lệ |
|---|---|---|---|
| Vay tiêu dùng trả góp (Consumer loans) | 459.716 | 4.071 | 0,886% |
| Thẻ quay vòng (Revolving loans) | 60.272 | 412 | 0,684% |
| Vay tiền mặt (Cash loans) | 222.137 | 283 | 0,127% |

So đúng là so các kênh trong cùng một sản phẩm. Khi đó khác biệt giữa kênh vẫn còn thật nhưng nhỏ hơn hẳn: trong vay tiêu dùng, Stone 1,067% (1.445 trên 135.415) cao gấp 2,0 lần Regional / Local 0,530% (365 trên 68.897); trong vay tiền mặt, Country-wide 0,437% (78 trên 17.844) cao gấp 4,4 lần Credit and cash offices 0,099% (175 trên 175.921). Dữ liệu không cho biết nguyên nhân phần chênh lệch còn lại. Giả thuyết cần kiểm chứng bằng thử nghiệm ở mục 3: các kênh bán tại điểm bán hàng tiếp cận nhóm khách khác, chứ không phải bản thân kênh tạo ra rủi ro.

| Sản phẩm | Kênh | Hợp đồng tại MOB 12 | Từng quá hạn 30+ | Tỷ lệ |
|---|---|---|---|---|
| Vay tiêu dùng | Stone | 135.415 | 1.445 | 1,067% |
| Vay tiêu dùng | Country-wide | 255.197 | 2.259 | 0,885% |
| Vay tiêu dùng | Regional / Local | 68.897 | 365 | 0,530% |
| Vay tiền mặt | Country-wide | 17.844 | 78 | 0,437% |
| Vay tiền mặt | AP+ (Cash loan) | 17.415 | 23 | 0,132% |
| Vay tiền mặt | Credit and cash offices | 175.921 | 175 | 0,099% |
| Vay tiền mặt | Contact center | 6.690 | 4 | 0,060% |

Stone và Regional / Local mỗi kênh chỉ có dưới 2.000 hợp đồng vay tiền mặt tại MOB 12 nên không đưa vào bảng so sánh này.

### 2.2. Rủi ro tập trung vào một nhóm nhỏ, kết luận này đứng vững sau khi khử nhiễu

Trong riêng vay tiêu dùng trả góp, nhóm giao của ba điều kiện (kênh Stone hoặc Country-wide, khách mới, nhóm lãi suất cao) chiếm 14,0% (64.462 trên 459.716 hợp đồng) nhưng chứa 33,7% số hợp đồng từng quá hạn 30+ (1.373 trên 4.071). Tỷ lệ 2,130% của nhóm gấp 3,1 lần phần vay tiêu dùng còn lại, vốn ở mức 0,683% (2.698 trên 395.254 hợp đồng). Tính trên toàn danh mục, con số tương ứng là 8,9% và 28,0%, nhưng con số dẫn dắt nên là con số trong cùng sản phẩm. Nhóm đủ nhỏ để can thiệp riêng mà không phải đổi chính sách toàn danh mục.

| Nhóm | Hợp đồng tại MOB 12 | Tỷ trọng | Từng quá hạn 30+ | Tỷ trọng số hợp đồng từng quá hạn | Tỷ lệ |
|---|---|---|---|---|---|
| Trong vay tiêu dùng: Stone hoặc Country-wide, khách mới, lãi suất cao | 64.462 | 14,0% | 1.373 | 33,7% | 2,130% |
| Vay tiêu dùng còn lại | 395.254 | 86,0% | 2.698 | 66,3% | 0,683% |
| Đối chiếu, cùng nhóm tính trên toàn danh mục | 66.096 | 8,9% | 1.376 | 28,0% | 2,082% |
| Đối chiếu, phần còn lại của toàn danh mục | 678.112 | 91,1% | 3.530 | 72,0% | 0,521% |

### 2.3. Cửa sổ thu hồi rất hẹp, đóng lại sau khoảng 30 ngày

Trong 259.546 lượt hợp đồng tháng ở B1, có 129.922 lượt về không quá hạn ngay tháng sau (50,1%) và 11.166 lượt rơi xuống B2 (4,302%). Cure rate còn 17,3% ở B2 (2.126 trên 12.315 lượt) và 7,0% ở B3 (505 trên 7.172 lượt), tức khả năng thu hồi gần như chỉ còn trong 30 ngày quá hạn đầu tiên. Ma trận chuyển nhóm không tách khách mới và khách vay lại, nên đây là số toàn danh mục.

| Nhóm quá hạn tại tháng t | Số lượt | Về không quá hạn ở tháng sau | Cure rate |
|---|---|---|---|
| B1 (1 đến 30 ngày) | 259.546 | 129.922 | 50,1% |
| B2 (31 đến 60 ngày) | 12.315 | 2.126 | 17,3% |
| B3 (61 đến 90 ngày) | 7.172 | 505 | 7,0% |
| B4 (trên 90 ngày) | 156.716 | 3.072 | 2,0% |

## 3. Đề xuất hành động

**3.1. Siết duyệt đúng nhóm 14,0% của vay tiêu dùng.** Thêm bước xác minh thu nhập bắt buộc hoặc hạ hạn mức cho hồ sơ vay tiêu dùng trả góp thuộc kênh Stone hoặc Country-wide, khách mới, nhóm lãi suất cao. Đo bằng tỷ lệ từng quá hạn 30+ tại MOB 6 và MOB 12 của nhóm, hiện 2,130% (1.373 trên 64.462 hợp đồng), so với phần vay tiêu dùng còn lại 0,683% (2.698 trên 395.254), kèm số hợp đồng giải ngân của nhóm để thấy doanh số phải đánh đổi. Kiểm chứng: chia ngẫu nhiên 50/50 hồ sơ mới của nhóm trong 3 tháng thành nhánh quy tắc mới và nhánh quy tắc cũ, so tại cùng MOB 6. Tính cỡ mẫu trước khi chạy vì tỷ lệ nền chỉ 2,130%.

**3.2. Dồn nhắc nợ vào 30 ngày quá hạn đầu tiên.** Liên hệ trong 7 ngày kể từ ngày quá hạn đầu tiên cho mọi hợp đồng vừa rơi vào B1, ưu tiên nhóm ở mục 3.1. Đo bằng cure rate của B1, hiện 50,1% (129.922 trên 259.546 lượt), và tỷ lệ B1 rơi xuống B2, hiện 4,302% (11.166 trên 259.546 lượt). Kiểm chứng: gán ngẫu nhiên hợp đồng mới rơi vào B1 trong một tháng thành nhóm liên hệ sớm và nhóm theo quy trình hiện tại, so cure rate sau 1 và 2 tháng. Rủi ro: tốn chi phí, phải đo chi phí trên mỗi hợp đồng cứu được.

**3.3. Thử lấy thêm khối lượng vay tiền mặt ở Credit and cash offices.** Nới ngưỡng duyệt trong biên hẹp cho hồ sơ vay tiền mặt bị từ chối sát ngưỡng ở kênh này, kênh đang duyệt 66,4% (289.199 trên 435.708 hồ sơ). Lưu ý mức 0,099% (175 trên 175.921 hợp đồng) là của **vay tiền mặt tại kênh này**, không phải mức chung của kênh và không so được với vay tiêu dùng, vì bản thân vay tiền mặt toàn danh mục chỉ 0,127% (283 trên 222.137) so với vay tiêu dùng 0,886% (4.071 trên 459.716). Đo bằng tỷ lệ từng quá hạn 30+ tại MOB 6 của riêng nhóm duyệt thêm, so với chính vay tiền mặt của kênh, kèm số hợp đồng tăng thêm. Kiểm chứng: duyệt ngẫu nhiên một nửa số hồ sơ biên, nửa còn lại giữ quyết định từ chối, theo dõi tới MOB 6. Rủi ro: hồ sơ biên xấu hơn hồ sơ đang được duyệt nên 0,099% không phải mức dự kiến cho nhóm mở thêm.

## 4. Giới hạn của phân tích

- So sánh giữa các kênh phải kiểm soát cơ cấu sản phẩm, vì mỗi kênh bán một rổ sản phẩm khác nhau và chênh lệch rủi ro giữa sản phẩm lớn hơn chênh lệch giữa kênh. Mọi so sánh kênh trong memo đã được tính lại trong cùng sản phẩm; con số thô chỉ để đối chiếu. Các yếu tố khác như kỳ hạn hay số tiền vay chưa được kiểm soát.
- Thời gian là tháng tương đối so với ngày nộp hồ sơ của từng khách, không phải tháng lịch, nên không dựng được vintage theo tháng giải ngân và không nói được danh mục đang xấu đi hay tốt lên.
- Danh mục chỉ gồm khoản vay trước đây của khách sau đó có hồ sơ mới, tức đã lọc qua một lần sống sót. Tỷ lệ tuyệt đối vì vậy thấp hơn thực tế, chỉ nên đọc theo so sánh tương đối giữa các phân khúc.
- FPD30 (first payment default 30, kỳ trả đầu tiên chưa trả đủ sau 30 ngày kể từ ngày đến hạn) không đo được đáng tin vì dữ liệu chỉ ghi các kỳ đã trả: 77.885 trên 1.036.044 hồ sơ được duyệt (7,5%) không có dòng kỳ 1 nào. Mức 0,011% (99 trên 895.744 hợp đồng) chỉ là chặn dưới.
- Tại MOB 24, chỉ 70.635 trên 679.223 hợp đồng của mẫu số còn quan sát đủ (10,4%), phần còn lại đã tất toán sớm, nên không diễn giải đoạn đuôi đường cong.
- Đơn vị tiền trong dữ liệu không phải VND, chỉ dùng so sánh tương đối. Ngoài ra 48.794 hợp đồng không khớp được hồ sơ nên mang nhãn "(không rõ)" ở mọi cột phân khúc, không so trực tiếp với nhóm khác.

## 5. Nguồn số

| Phát hiện | Bảng số liệu | Mã chỉ tiêu |
|---|---|---|
| 2.1 Tỷ lệ duyệt theo kênh | `mart.funnel_by_channel` | M12 (approval rate) |
| 2.1 Cơ cấu sản phẩm, rủi ro theo sản phẩm, kênh trong cùng sản phẩm | `mart.vintage` | M08 (vintage ever 30+@MOBn) |
| 2.2 Nhóm rủi ro tập trung trong vay tiêu dùng | `mart.vintage` | M08 |
| 2.3 Cure rate và tỷ lệ rơi nhóm | `mart.roll_rate` | M09 (roll rate), M10 (cure rate) |
| Mục 4, FPD30 | `mart.fpd_by_segment` | M11 (FPD30) |

Định nghĩa chỉ tiêu: `docs/metric_dictionary.md`. Giả định và giới hạn dữ liệu: `docs/data_notes.md`.
