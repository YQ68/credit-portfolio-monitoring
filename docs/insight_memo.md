# Memo: chất lượng danh mục theo đợt mở, sản phẩm, kênh bán và cửa sổ thu hồi

**Ghi chú:** số liệu lấy từ bộ dữ liệu công khai Home Credit Default Risk trên Kaggle, dùng cho mục đích học tập. Đây không phải số thật của một công ty tài chính tiêu dùng cụ thể nào.

**Gửi:** Giám đốc Rủi ro, Giám đốc Kinh doanh. **Ngày:** 2026-10-04, bản thứ ba, thay thế bản sáng cùng ngày và bản ngày 2026-09-20. **Nguồn số:** mục 6.

**Vì sao có bản mới.** Bản ngày 2026-09-20 đo nợ quá hạn bằng một cột tính cả khoản dư lẻ còn treo sau kỳ trả cuối; bản sáng 2026-10-04 chuyển sang cột có ngưỡng trọng yếu của chính bộ dữ liệu ([methodology mục 4](methodology.md#4-quyết-định-đã-đảo-ngược-định-nghĩa-quá-hạn)). Một lần soát độc lập thứ hai sau đó phát hiện một biến gây nhiễu chưa được kiểm soát: **đợt mở hợp đồng**, tức hợp đồng được mở bao nhiêu tháng trước ngày khách nộp hồ sơ hiện tại. Hợp đồng mở càng sớm thì tỷ lệ quá hạn càng cao, và các kênh, sản phẩm có cơ cấu đợt mở rất khác nhau. Bản này kiểm soát cùng lúc sản phẩm và đợt mở; hai kết luận về kênh và một kết luận về sản phẩm của bản sáng không còn đứng vững (mục 3). Chi tiết kỹ thuật: [methodology mục 5.10](methodology.md#510-đợt-mở-hợp-đồng-biến-gây-nhiễu-thứ-hai).

| Thuật ngữ | Nghĩa dùng trong memo |
|---|---|
| Bucket (nhóm ngày quá hạn) | B0 là 0 ngày, B1 là 1 đến 30 ngày, B2 là 31 đến 60, B3 là 61 đến 90, B4 là trên 90 |
| MOB (month on book) | tuổi hợp đồng tính bằng tháng kể từ tháng bắt đầu mở. MOB 12 là tháng thứ 12 |
| Từng quá hạn 30+ tại MOB 12 | tỷ lệ hợp đồng từng có ít nhất một tháng quá hạn trên 30 ngày tính đến MOB 12, chỉ tiêu rủi ro chính của memo |
| Đợt mở (origination cohort) | nhóm hợp đồng mở trong cùng một khoảng 12 tháng, đếm ngược từ ngày khách nộp hồ sơ hiện tại. Ví dụ đợt "-96 đến -85" là hợp đồng mở từ 96 đến 85 tháng trước hồ sơ hiện tại. Đây là thời gian tương đối của từng khách, không phải tháng lịch |
| Biến gây nhiễu | một yếu tố thứ ba vừa liên quan tới nhóm đang so, vừa liên quan tới kết quả, làm hai nhóm trông khác nhau dù khác biệt thật nằm ở yếu tố đó |
| Cure rate (tỷ lệ hồi phục) | tỷ lệ hợp đồng đang quá hạn ở một tháng quay về không quá hạn ngay tháng sau |
| Khoảng tin cậy 95%, viết `[a; b]` | khoảng mà con số thật có khả năng nằm trong, xét theo cỡ mẫu. Hai con số có khoảng không giao nhau thì khác nhau thật |
| Tỷ số | tỷ lệ nhóm này chia tỷ lệ nhóm kia. "Có ý nghĩa" khi khoảng tin cậy của tỷ số không chứa 1 |
| SMR (tỷ số chuẩn hoá) | số ca quá hạn thực tế của một kênh chia số ca kỳ vọng nếu kênh có đúng mức rủi ro trung bình của từng tầng (ở bản này: sản phẩm × đợt mở) mà nó có. Trên 1 là kênh xấu hơn kỳ vọng của chính nó. Mỗi SMR chỉ so một kênh với kỳ vọng của nó; không chia SMR của hai kênh cho nhau |
| Định nghĩa chính, định nghĩa giữa | định nghĩa chính đo quá hạn bằng cột có ngưỡng trọng yếu (`SK_DPD_DEF`). Định nghĩa giữa là phép kiểm độ nhạy: với khoản trả góp, dùng cột không ngưỡng (`SK_DPD`) nhưng chỉ tính ở tháng còn kỳ phải trả; với thẻ giữ định nghĩa chính |

## 1. Kết luận

**Đợt mở là yếu tố mạnh nhất trong dữ liệu: hợp đồng mở càng xa ngày hồ sơ hiện tại thì càng hay quá hạn.** Tính chung ba sản phẩm, 0,192% [0,161; 0,230] hợp đồng của đợt mở -96 đến -85 từng quá hạn 30+ tại MOB 12, so với 0,010% [0,007; 0,015] ở đợt -24 đến -13. Trong cùng một sản phẩm, đợt cũ nhất gấp đợt gần nhất 9,88 [4,52; 21,56] lần ở vay tiền mặt và 62,17 [15,14; 255,35] lần ở vay tiêu dùng. Dữ liệu không cho biết đây là chất lượng giải ngân cải thiện thật hay là hiệu ứng chọn mẫu (khách vừa quá hạn gần đây ít có khả năng xuất hiện với một hồ sơ mới), nên con số này dùng để **kiểm soát so sánh**, không dùng để nói danh mục đang tốt lên.

**Thẻ quay vòng vẫn là sản phẩm rủi ro nhất sau khi kiểm soát đợt mở, nhưng khoảng cách chỉ bằng khoảng một nửa số thô.** Trong cùng đợt mở, thẻ gấp vay tiền mặt 2,29 [1,59; 3,31] lần tại MOB 12, so với 4,85 [3,57; 6,59] lần khi chưa kiểm soát. Kết quả giữ ở MOB 6, MOB 24, ở hai cách cắt đợt khác và khi đo bằng cột không ngưỡng.

**Sau khi kiểm soát cả sản phẩm và đợt mở, chỉ Contact center còn trên kỳ vọng một cách bền vững, và phần vượt nằm ở thẻ mở đã lâu.** Contact center có 48 ca so với 29,1 ca kỳ vọng, SMR 1,65 [1,21; 2,18], giữ ở mọi cách cắt đợt, mọi mốc MOB và cả định nghĩa giữa. Toàn bộ phần vượt nằm ở thẻ (47 ca so với 28,0 kỳ vọng), và 41 trên 47 ca là thẻ mở từ tháng -60 trở về trước. Stone trên kỳ vọng theo định nghĩa chính (1,36 [1,08; 1,69]) nhưng không giữ theo định nghĩa giữa (1,06 [0,95; 1,19]). Credit and cash offices không còn khác kỳ vọng (0,89 [0,68; 1,14]).

**Vay tiêu dùng so với vay tiền mặt: không kết luận được.** Tỷ số đổi chiều theo định nghĩa và theo việc có kiểm soát đợt mở hay không: từ 0,41 [0,30; 0,56] (định nghĩa chính, kiểm soát đợt mở) đến 6,48 [5,75; 7,30] (cột không ngưỡng, không kiểm soát).

**Cửa sổ thu hồi đóng nhanh sau 30 ngày đầu, kể cả trong từng đợt mở.** 57,7% lượt hợp đồng quá hạn 1 đến 30 ngày về không quá hạn ngay tháng sau (111.822 trên 193.814 lượt), ở nhóm 31 đến 60 ngày chỉ còn 27,8% (457 trên 1.642), ở nhóm trên 90 ngày còn 1,2% (68 trên 5.589). Trong cùng đợt mở, cure của B1 vẫn gấp B2 2,09 [1,94; 2,27] lần.

**Quy mô bằng chứng nhỏ, và kiểm soát đợt mở là phân tích hậu nghiệm.** Toàn danh mục chỉ có 425 hợp đồng từng quá hạn 30+ tại MOB 12, trong đó 106 thuộc nhóm hợp đồng không khớp được hồ sơ. Đợt mở được đưa vào sau khi người soát đã nhìn dữ liệu, nên các con số có kiểm soát đợt mở là kiểm tra lại, không phải kiểm định xác nhận độc lập. Đề xuất ở mục 4 vì vậy là điều tra và thử nghiệm có đo lường, không phải đổi chính sách ngay.

## 2. Bằng chứng

### 2.1. Vintage theo đợt mở: đợt cũ xấu hơn hẳn trong mọi sản phẩm

Đây là phân tích vintage theo nghĩa chuẩn: so các đợt mở ở cùng tuổi hợp đồng. Mỗi đợt chỉ được so ở MOB mà toàn bộ hợp đồng của đợt đã có thể quan sát tới (đợt -12 đến -1 chưa đủ 12 tháng nên không có mặt ở MOB 12).

| Đợt mở (tháng trước hồ sơ hiện tại) | Vay tiền mặt | Vay tiêu dùng | Thẻ quay vòng | Ba sản phẩm |
|---|---|---|---|---|
| -96 đến -85 | 0,198% (10 / 5.062) | 0,105% (51 / 48.403) | 0,720% (57 / 7.914) | 0,192% [0,161; 0,230] (118 / 61.379) |
| -84 đến -73 | 0,155% (13 / 8.409) | 0,066% (41 / 61.684) | 0,293% (21 / 7.176) | 0,097% (75 / 77.269) |
| -72 đến -61 | 0,094% (7 / 7.469) | 0,051% (28 / 54.477) | 0,070% (1 / 1.435) | 0,057% (36 / 63.381) |
| -60 đến -49 | 0,062% (8 / 12.929) | 0,019% (12 / 64.846) | 0,192% (2 / 1.039) | 0,028% (22 / 78.814) |
| -48 đến -37 | 0,032% (8 / 25.230) | 0,024% (15 / 63.024) | 0,069% (5 / 7.256) | 0,029% (28 / 95.510) |
| -36 đến -25 | 0,012% (8 / 66.154) | 0,005% (4 / 83.160) | 0,017% (2 / 11.523) | 0,009% (14 / 160.837) |
| -24 đến -13 | 0,020% (17 / 84.990) | 0,002% (2 / 118.005) | 0,018% (4 / 21.708) | 0,010% [0,007; 0,015] (23 / 224.703) |

Đợt cũ nhất so với đợt gần nhất đủ tuổi, trong từng sản phẩm: vay tiền mặt 9,88 [4,52; 21,56], vay tiêu dùng 62,17 [15,14; 255,35], thẻ 39,09 [14,19; 107,69]. Khi cắt đợt thành 3 nhóm (-60 trở về trước, -59 đến -36, -35 trở về sau) các tỷ số là 8,40 [4,96; 14,22], 23,17 [10,21; 52,58] và 38,60 [14,14; 105,37]; khi cắt mỗi 24 tháng là 8,54 [4,56; 15,97], 49,31 [12,15; 200,13] và 28,05 [10,27; 76,60]. Xu hướng giữ ở MOB 6 và MOB 24. Đường không đơn điệu ở từng bậc (các ô giữa của thẻ chỉ có 1 đến 5 ca), nhưng chênh lệch giữa hai đầu lớn hơn nhiều so với độ rộng khoảng tin cậy.

Vì sao điều này quan trọng: các kênh và sản phẩm có cơ cấu đợt mở rất khác nhau. Trong mẫu số MOB 12, 77,2% thẻ của Credit and cash offices mở từ tháng -35 trở về sau, so với 21,1% ở Contact center. So hai kênh này mà không kiểm soát đợt mở là so thẻ mới với thẻ cũ.

### 2.2. Thẻ quay vòng rủi ro nhất, ở mọi cách đo cùng thước

| Cách đo tỷ số thẻ / vay tiền mặt tại MOB 12 | Tỷ số |
|---|---|
| Số thô, định nghĩa chính | 4,85 [3,57; 6,59] |
| Kiểm soát đợt mở (Mantel-Haenszel qua đợt 12 tháng) | 2,29 [1,59; 3,31] |
| Như trên, đợt 3 nhóm / đợt 24 tháng | 2,75 [1,97; 3,86] / 2,50 [1,75; 3,59] |
| Kiểm soát đợt mở, tại MOB 6 / MOB 24 | 2,68 [1,68; 4,26] / 2,97 [2,15; 4,10] |
| Kiểm soát đợt mở, cột không ngưỡng `SK_DPD` cho cả hai sản phẩm | 2,88 [2,48; 3,35] |

Một ngoại lệ cần nêu: theo định nghĩa giữa, khoản trả góp được đo bằng cột không ngưỡng còn thẻ vẫn giữ ngưỡng, tức hai sản phẩm không cùng thước. Khi đó tỷ số sau kiểm soát đợt mở là 0,74 [0,56; 0,97]; nếu thẻ cũng đo bằng cột không ngưỡng thì là 4,05 [3,42; 4,79]. Hai con số này là hai cận của một phép so không cùng thước đo, không phải bằng chứng thẻ an toàn hơn. Ở mọi phép so cùng thước, thẻ rủi ro hơn vay tiền mặt.

Tỷ lệ thô tại MOB 12, để đối chiếu: thẻ 0,155% [0,127; 0,189] (94 trên 60.705), vay tiền mặt 0,032% (72 trên 225.408), vay tiêu dùng 0,029% (153 trên 530.476). Ở MOB 12 chỉ 24,8% mẫu số vay tiêu dùng còn được quan sát thật, so với 95,2% ở thẻ, nên so sánh được kiểm lại ở MOB 6.

### 2.3. Vay tiêu dùng và vay tiền mặt: tỷ số chạy từ 0,41 đến 6,48

| Cách đo tỷ số vay tiêu dùng / vay tiền mặt tại MOB 12 | Số thô | Kiểm soát đợt mở |
|---|---|---|
| Định nghĩa chính (`SK_DPD_DEF`) | 0,90 [0,68; 1,19] | 0,41 [0,30; 0,56] |
| Định nghĩa giữa (`SK_DPD` ở tháng còn kỳ phải trả) | 1,74 [1,49; 2,02] (874 / 530.476 so với 214 / 225.408) | 0,95 [0,82; 1,11] |
| Không áp ngưỡng (`SK_DPD`) | 6,48 [5,75; 7,30] | 2,98 [2,63; 3,37] |

Bản sáng viết hai sản phẩm "ngang nhau" dựa trên dòng đầu. Bảng cho thấy kết luận đó phụ thuộc hoàn toàn vào định nghĩa: theo một cách đo vay tiêu dùng an toàn hơn có ý nghĩa, theo cách khác rủi ro hơn có ý nghĩa. Memo không dùng so sánh này để ra quyết định.

### 2.4. Kênh: so với kỳ vọng theo cả sản phẩm và đợt mở

| Kênh | Quan sát | Kỳ vọng theo sản phẩm × đợt | SMR, định nghĩa chính | SMR, định nghĩa giữa | SMR chỉ theo sản phẩm (bản sáng) |
|---|---|---|---|---|---|
| Contact center | 48 | 29,1 | 1,65 [1,21; 2,18] | 1,65 [1,23; 2,17] | 2,90 [2,14; 3,84] |
| Stone | 82 | 60,1 | 1,36 [1,08; 1,69] | 1,06 [0,95; 1,19] | 1,63 [1,30; 2,02] |
| Credit and cash offices | 61 | 68,9 | 0,89 [0,68; 1,14] | 0,85 [0,72; 1,00] | 0,58 [0,45; 0,75] |
| Country-wide | 110 | 139,8 | 0,79 [0,65; 0,95] | 0,99 [0,91; 1,07] | 1,01 [0,83; 1,21] |
| Regional / Local | 15 | 16,4 | 0,91 [0,51; 1,51] | 0,89 [0,71; 1,11] | 0,60 [0,34; 1,00] |

AP+ (Cash loan) chỉ có 2 ca nên không kết luận được. Các điểm đáng chú ý:

- **Contact center là kết quả bền duy nhất về kênh.** SMR theo sản phẩm × đợt là 1,59 [1,17; 2,10] khi cắt đợt 3 nhóm, 1,56 [1,15; 2,06] khi cắt mỗi 24 tháng, 2,04 [1,39; 2,90] tại MOB 6 và 1,48 [1,16; 1,86] tại MOB 24. Phần vượt nằm ở thẻ: 47 ca thẻ so với 28,0 kỳ vọng. Trong 47 ca đó, 41 là thẻ mở từ tháng -60 trở về trước; thẻ Contact center mở từ tháng -35 trở về sau có 0 ca trên 1.959 hợp đồng. Kênh này cũng duyệt thẻ rộng nhất: 92,6% hồ sơ thẻ có quyết định được duyệt (9.482 trên 10.238), so với 79,9% ở Stone, 78,3% ở Country-wide và 66,4% ở Credit and cash offices. Dữ liệu không cho biết hai việc này có liên quan nhân quả hay không, và tỷ lệ duyệt là của mọi hồ sơ, không riêng thẻ cũ.
- **Stone không đứng vững.** Trên kỳ vọng theo định nghĩa chính tại MOB 12 và MOB 24, nhưng không có ý nghĩa tại MOB 6 (1,38 [0,98; 1,89]) và theo định nghĩa giữa. Cặp Stone so với Country-wide, gộp Mantel-Haenszel qua ba sản phẩm (vay tiêu dùng, vay tiền mặt, thẻ), là 1,80 [1,34; 2,42]; chỉ qua hai sản phẩm vay tiêu dùng và thẻ là 1,88 [1,40; 2,52]; qua sản phẩm × đợt là 1,76 [1,31; 2,37]; theo định nghĩa giữa là 1,09 [0,95; 1,26].
- **Credit and cash offices không còn tốt hơn kỳ vọng.** Mức "dưới kỳ vọng" của bản sáng đến gần như hoàn toàn từ thẻ: chỉ theo sản phẩm, thẻ của kênh có 8 ca so với 47,7 kỳ vọng; khi tính cả đợt mở, kỳ vọng còn 13,9 vì thẻ của kênh phần lớn mới mở. Phần vay tiền mặt của kênh (53 ca so với 55,0 kỳ vọng) chưa bao giờ khác kỳ vọng. Tỷ lệ duyệt thấp của kênh cũng do cơ cấu sản phẩm: chuẩn hoá theo sản phẩm, số hồ sơ duyệt bằng 1,00 lần kỳ vọng.
- **Country-wide dưới kỳ vọng theo định nghĩa chính** (0,79 [0,65; 0,95]) nhưng không theo định nghĩa giữa và không có ý nghĩa tại MOB 6. Đây không phải so sánh định trước nên chỉ ghi để mô tả.

Một ghi chú về cách đọc: SMR là chuẩn hoá gián tiếp, mỗi kênh được so với kỳ vọng tính trên chính cơ cấu của nó. Vì vậy không chia SMR của hai kênh cho nhau để nói kênh này "gấp" kênh kia; so hai kênh trực tiếp phải dùng tỷ số trong cùng tầng (như cặp Stone so với Country-wide ở trên). Trong thẻ, tỷ lệ thô của Stone gấp Credit and cash offices 20,36 [8,55; 48,49] lần, nhưng chỉ dựa trên 22 ca và chưa kiểm soát đợt mở, nên chỉ là mô tả.

### 2.5. Cửa sổ thu hồi đóng nhanh sau 30 ngày đầu

| Nhóm quá hạn tại tháng t | Số lượt | Về không quá hạn ở tháng sau | Cure rate | Rơi tiếp một nhóm |
|---|---|---|---|---|
| B1 (1 đến 30 ngày) | 193.814 | 111.822 | 57,7% [57,5; 57,9] | 0,709% sang B2 |
| B2 (31 đến 60 ngày) | 1.642 | 457 | 27,8% [25,7; 30,0] | 22,8% sang B3 |
| B3 (61 đến 90 ngày) | 403 | 63 | 15,6%, mẫu quá nhỏ để diễn giải | 45,7% sang B4 |
| B4 (trên 90 ngày) | 5.589 | 68 | 1,2% [0,96; 1,54] | 96,9% ở lại B4 |

Hợp đồng ở B1 phần lớn tự quay về hoặc đứng yên; chỉ 0,709% rơi tiếp. Hợp đồng nào đã sang B2 thì khả năng quay về giảm còn khoảng một nửa, sang B4 thì gần như không còn. Kết quả giữ trong từng đợt mở (tỷ số cure B1 / B2 gộp qua đợt 2,09 [1,94; 2,27]). Đơn vị ở đây là lượt hợp đồng-tháng, một hợp đồng góp nhiều lượt, nên khoảng tin cậy hẹp hơn thực tế; mục 4.3 tính lại theo hợp đồng.

### 2.6. Danh mục đang mở: rủi ro hiện tại dồn vào vay tiền mặt quá hạn muộn

Tại tháng gần nhất của dữ liệu, 0,094% [0,079; 0,111] hợp đồng đang mở có quá hạn trên 30 ngày (135 trên 144.311 hợp đồng có số dư ước lượng), tương ứng 0,301% dư nợ ước lượng. Trong 159 hợp đồng đang mở có quá hạn trên 30 ngày, 113 là vay tiền mặt, trong đó 98 thuộc Credit and cash offices (98 trên 100 ca của kênh). Bản sáng nêu giả thuyết "nợ quá hạn của vay tiền mặt xuất hiện muộn, sau MOB 12" mà chưa kiểm chứng. Kiểm lại: 113 ca này có MOB hiện tại trung vị 19 (thấp nhất 7, cao nhất 38), lần đầu quá hạn 30+ ở MOB trung vị 18, và 94 trên 113 ca lần đầu quá hạn 30+ sau MOB 12. Giả thuyết đúng: ca 30+ đang mở của vay tiền mặt chủ yếu là ca muộn mà chỉ tiêu tại MOB 12 không bắt được. Tỷ lệ 30+ hiện tại theo kênh vì vậy phản ánh cơ cấu sản phẩm và tuổi hợp đồng, không dùng để xếp hạng kênh.

## 3. Những kết luận không còn đứng vững

### 3.1. So với bản sáng 2026-10-04 (sau lần soát thứ hai)

| Kết luận bản sáng | Sau khi kiểm soát đợt mở | Trạng thái |
|---|---|---|
| Thẻ quay vòng gấp 4,85 [3,57; 6,59] lần vay tiền mặt | 2,29 [1,59; 3,31] trong cùng đợt mở | Còn, nhỏ hơn khoảng một nửa |
| Vay tiêu dùng và vay tiền mặt ngang nhau, 0,90 [0,68; 1,19] | Từ 0,41 đến 6,48 tuỳ định nghĩa và kiểm soát (mục 2.3) | Không kết luận được |
| Contact center gấp 2,90 [2,14; 3,84] lần kỳ vọng | 1,65 [1,21; 2,18], phần vượt nằm ở thẻ mở đã lâu | Còn, nhỏ hơn, khoanh được nguồn |
| Stone gấp 1,63 [1,30; 2,02] lần kỳ vọng; cao hơn Country-wide 1,80 [1,34; 2,42] lần | 1,36 [1,08; 1,69] và 1,76 [1,31; 2,37] theo định nghĩa chính; 1,06 [0,95; 1,19] và 1,09 [0,95; 1,26] theo định nghĩa giữa | Không bền |
| Credit and cash offices tốt hơn kỳ vọng, 0,58 [0,45; 0,75] | 0,89 [0,68; 1,14] | Không còn |
| "Khoảng cách kênh không do sản phẩm", "kiểm soát sản phẩm làm khoảng cách rõ hơn" | Cơ cấu sản phẩm che bớt chứ không tạo ra khoảng cách, nhưng câu dễ đọc thành "do kênh", và câu thứ hai ngầm chia hai SMR chuẩn hoá gián tiếp cho nhau. Phần khoảng cách còn lại trùng phần lớn với đợt mở | Bỏ cách diễn đạt |
| Ca 30+ đang mở của vay tiền mặt xuất hiện sau MOB 12, chưa kiểm chứng | 94 trên 113 ca lần đầu 30+ sau MOB 12 | Đã kiểm, đúng |
| Thử nghiệm thu hồi cần 273 hợp đồng mỗi nhánh | Con số đó giả định mức tăng tương đối 20%, tức 11,5 điểm phần trăm, và dùng lượt hợp đồng-tháng không độc lập làm đơn vị | Tính lại theo hợp đồng (mục 4.3) |

### 3.2. So với bản 2026-09-20 (sau lần soát thứ nhất)

| Kết luận bản 2026-09-20 | Theo định nghĩa có ngưỡng | Trạng thái |
|---|---|---|
| Rủi ro dồn vào nhóm Stone hoặc Country-wide, khách mới, lãi suất cao: 14,0% hợp đồng vay tiêu dùng gánh 33,7% số ca | Nhóm đó chỉ còn 15,7% hợp đồng, 22,2% số ca. Định nghĩa đơn giản hơn (khách mới × lãi suất cao) cho tỷ số 1,60 [1,11; 2,31] tại MOB 12, không có ý nghĩa tại MOB 6 và MOB 24, và mất ý nghĩa khi tính đến số so sánh đã xem: [0,94; 2,74] cho 12 tổ hợp, [0,82; 3,13] khi đếm đủ 144 phép so | Không còn là phát hiện |
| Khoảng cách giữa kênh phần lớn là do sản phẩm | Theo số thô Stone chỉ gấp 1,73 [1,24; 2,41] lần Credit and cash offices; cơ cấu sản phẩm che bớt chứ không tạo ra khoảng cách, nhưng phần lớn khoảng cách còn lại trùng với đợt mở (mục 3.1) | Đảo chiều, rồi thu hẹp |
| Vay tiêu dùng rủi ro hơn vay tiền mặt nhiều lần | Chỉ đúng khi không áp ngưỡng (mục 2.3) | Không kết luận được |
| Stone là kênh xấu nhất | Contact center là kênh duy nhất trên kỳ vọng một cách bền vững | Không còn |
| Cure rate 50,1% ở B1, 7,0% ở B3 | 57,7% ở B1, 27,8% ở B2; B3 không đủ mẫu | Ý chính còn, số đổi |
| B1 rơi xuống B2 4,302% | 0,709% | B1 hiếm khi rơi tiếp |
| Vay tiền mặt tại Credit and cash offices tốt bất thường (0,099%), nên thử mở rộng | 0,030% (53 trên 178.306), ngang mức chung của vay tiền mặt 0,032% | Đề xuất mở rộng bị rút |
| Thử nghiệm siết duyệt đo bằng tỷ lệ quá hạn 30+ tại MOB 6 và MOB 12 | Cần 843.010 hợp đồng mỗi nhánh cho MOB 12, gấp 18,3 lần quy mô cả nhóm trong dữ liệu | Không khả thi, đổi chỉ tiêu đo (mục 4) |
| Chỉ tiêu nợ kỳ đầu (FPD30) không đo được vì 77.885 hồ sơ duyệt biến mất khỏi mẫu số | 77.884 trong số đó không có lịch trả, tức chưa từng giải ngân; FPD30 đo được 0,011% [0,009; 0,013] trên hợp đồng đã kích hoạt | Lập luận cũ sai |

## 4. Đề xuất hành động

Các đề xuất được cân theo quy mô bằng chứng: tín hiệu bền nhất về kênh dựa trên 47 ca thẻ, phần lớn là thẻ mở đã lâu. Bước đầu là xem hồ sơ và thử nghiệm đo được, không phải đổi chính sách cho toàn kênh.

**4.1. Rà soát thẻ cũ của Contact center, không phải quy trình duyệt thẻ hiện tại.** 41 trên 47 ca thẻ Contact center từng quá hạn 30+ tại MOB 12 là thẻ mở từ tháng -60 trở về trước; thẻ của kênh mở từ tháng -35 trở về sau có 0 ca trên 1.959 hợp đồng. Đề xuất bản sáng là rà soát hồ sơ thẻ của kênh "trước khi đổi chính sách"; nhưng một quy tắc duyệt mới chỉ tác động lên thẻ sắp mở, nơi dữ liệu hiện chưa thấy vấn đề. Việc nên làm là so 41 thẻ cũ quá hạn với thẻ cũ không quá hạn cùng kênh (hạn mức, thu nhập khai báo, kịch bản bán) để hiểu đặc điểm, đồng thời theo dõi thẻ mới của kênh bằng chỉ tiêu sớm ở mục 4.2. Không đề xuất siết duyệt thẻ Contact center lúc này. Với Stone, tín hiệu không đủ bền để rà soát riêng.

**4.2. Nếu thử nghiệm một quy tắc duyệt thẻ, đo bằng chỉ tiêu sớm và tính cỡ mẫu cho đúng thẻ.** Bản sáng nhắm thẻ nhưng lại tính cỡ mẫu cho vay tiêu dùng. Với thẻ Contact center:

| Chỉ tiêu | Tỷ lệ nền | Phát hiện giảm tương đối 20% cần mỗi nhánh | Hai nhánh so với quy mô nhóm (9.276 thẻ) |
|---|---|---|---|
| Từng trễ hạn dù chỉ 1 ngày tính đến MOB 6 (ever 1+@MOB6) | 15,99% [15,26; 16,75] (1.483 / 9.274) | 1.890 | 0,41 lần |
| Từng quá hạn 30+ tính đến MOB 12 | 0,507% (47 / 9.272) | 69.359 | 14,95 lần |

Chỉ tiêu sớm khả thi, chỉ tiêu 30+ thì không. Để tham chiếu, toàn vay tiêu dùng cần 11.173 hợp đồng mỗi nhánh cho ever 1+@MOB6 và 1.224.282 cho ever 30+@MOB12.

Chỉ tiêu sớm có giá trị dự báo thật, nhưng nhỏ hơn con số bản sáng ngụ ý. Bản sáng viết 77,8% ca 30+ tại MOB 12 của vay tiêu dùng đã từng trễ trước MOB 6. Một phần là cơ học: trong 153 ca, 67 ca đã quá hạn 30+ ngay trước MOB 6, tức chắc chắn đã trễ 1+. Phần dự báo thật nằm ở 86 ca lần đầu 30+ ở MOB 7 đến 12: 52 ca (60,5% [49,9; 70,1]) đã từng trễ 1+ trước MOB 6. Trên hợp đồng chưa 30+ đến MOB 6, nhóm đã từng trễ 1+ có 0,310% [0,237; 0,407] lần đầu 30+ ở MOB 7 đến 12, so với 0,0066% ở nhóm chưa từng trễ, tỷ số 46,87 [30,43; 72,19]. Vẫn phải theo dõi kết quả 30+ khi đủ tuổi.

**4.3. Thử liên hệ sớm cho hợp đồng vừa rơi vào B1, ngẫu nhiên hoá theo hợp đồng.** Đơn vị ngẫu nhiên hoá phải là hợp đồng, không phải lượt hợp đồng-tháng, vì một hợp đồng vào B1 nhiều lần và các lượt của nó không độc lập. Tính theo lần đầu mỗi hợp đồng vào B1: cure ở tháng sau là 67,9% [67,5; 68,2] (48.351 trên 71.231 hợp đồng). Cỡ mẫu mỗi nhánh theo mức tăng tuyệt đối muốn phát hiện:

| Mức tăng cure | Cure mục tiêu | Cần mỗi nhánh |
|---|---|---|
| 3 điểm phần trăm | 70,9% | 3.705 |
| 5 điểm phần trăm | 72,9% | 1.308 |
| 10 điểm phần trăm | 77,9% | 310 |

Con số 273 hợp đồng của bản sáng giả định mức tăng tương đối 20%, tức 11,5 điểm phần trăm, một hiệu ứng lớn mà một cuộc gọi sớm khó đạt; nên thiết kế cho mức 3 đến 5 điểm. Dữ liệu ghi theo tháng nên không đo được "liên hệ trong 7 ngày" có tác dụng hay không: chỉ đo được cure ở tháng sau, còn thời điểm liên hệ phải lấy từ hệ thống thu hồi khi chạy thử. Rủi ro: phần lớn B1 tự quay về, nên phải đo chi phí trên mỗi hợp đồng thực sự được cứu.

**4.4. Tìm nguyên nhân nhóm hợp đồng không khớp hồ sơ.** 2.083 hợp đồng (0,25% mẫu số) gánh 106 trên 425 ca quá hạn 30+ tại MOB 12, tỷ lệ 5,089%. Con số này mỏng hơn vẻ ngoài: trong 48.794 hợp đồng của nhóm, 46.178 (94,6%) mang cờ thiếu lịch sử đầu (`is_partial_history`) và bị loại khỏi vintage, nên vintage của nhóm chỉ dựa trên 2.605 hợp đồng. Ngoài ra, quy tắc coi hợp đồng dừng sớm là đã đóng (`closed_inferred`) cần ngày kết thúc trong hồ sơ, nên không áp được cho nhóm này: 512 hợp đồng dừng sớm của nhóm bị loại khỏi mẫu số MOB 12. Nếu đối xử như nhóm có hồ sơ, tỷ lệ của nhóm là 4,35% [3,63; 5,21] (113 trên 2.595) thay vì 5,09%. Đây có thể là nhóm khách thật sự rủi ro hoặc một lỗi ghép dữ liệu. Trong khi chờ, mọi báo cáo nêu kèm tổng không gồm nhóm này: 0,039% [0,035; 0,044] (319 trên 816.589).

## 5. Giới hạn của phân tích

- **Tử số mỏng.** 425 ca trên toàn danh mục tại MOB 12. Nhiều so sánh giữa cặp kênh hay giữa phân khúc không đủ ý nghĩa thống kê và không được nêu ở đây.
- **Kiểm soát đợt mở là hậu nghiệm.** Biến này được đưa vào sau khi người soát nhìn dữ liệu; mốc cắt 3 nhóm do người soát đặt. Memo dùng mốc 12 tháng định sẵn theo năm tương đối và báo thêm hai cách cắt khác để thấy kết luận không phụ thuộc mốc.
- **Đợt mở là thời gian tương đối.** Đợt "-96 đến -85" của hai khách có thể là hai năm lịch khác nhau. Xu hướng theo đợt có thể là chất lượng thật hoặc chọn mẫu, không tách được.
- **Mới kiểm soát hai yếu tố.** So sánh kênh đã tính đến sản phẩm và đợt mở, chưa tính đến kỳ hạn, số tiền vay hay đặc điểm khách. Dữ liệu quan sát không chứng minh được quan hệ nhân quả.
- **Nhóm hợp đồng không khớp hồ sơ** gánh gần một phần tư số ca, chưa giải thích được, và vintage của nhóm chỉ dựa trên 2.605 hợp đồng (mục 4.4).
- **Hai thẻ KPI của danh mục đang mở bỏ 110 hợp đồng thiếu dư nợ ước lượng.** 110 hợp đồng này chứa 24 trên 159 ca 30+ và toàn bộ thuộc nhóm không khớp hồ sơ. Cách diễn đạt sạch hơn là bỏ hẳn nhóm đó: 0,094% [0,080; 0,112] (130 trên 137.611), cùng mức với tập có dư nợ.
- **Một phần mẫu số là suy luận.** 89.414 hợp đồng có lịch sử dừng sớm được coi là đã đóng dựa trên ngày kết thúc trong hồ sơ, một cột mà tài liệu gốc gọi là ngày kết thúc dự kiến. "Đã đóng" ở đây không có nghĩa là đã trả xong: trong 50 ca vay tiêu dùng thuộc nhóm này từng quá hạn 30+ tại MOB 12, 21 ca vẫn đang 30+ ở tháng quan sát cuối. Đổi quy tắc này làm mẫu số MOB 12 đổi khoảng 10% nhưng không đổi kết luận.
- **Danh mục đã qua chọn lọc.** Chỉ gồm khoản vay trước đây của khách sau đó có hồ sơ mới, nên tỷ lệ tuyệt đối thấp hơn thực tế. Chỉ nên đọc so sánh tương đối.
- **Không có tổn thất thật.** Không có số tiền xoá nợ hay thu hồi, nên memo nói về tần suất quá hạn, không nói về tổn thất. Đơn vị tiền không phải VND.
- **Đuôi đường cong mỏng.** Tại MOB 24 chỉ 9,2% mẫu số còn quan sát thật (70.635 trên 763.989).

## 6. Nguồn số

Mọi con số trong memo lấy từ `data/export/findings.json` (sinh bởi `scripts/compute_findings.py`).

| Phần | Khóa trong `findings.json` | Bảng mart | Mã chỉ tiêu |
|---|---|---|---|
| 1, 2.1 Vintage theo đợt mở | `origination_cohort.mob{6,12,24}.cohort_vintage.{cut12,cut3,cut24}`, `origination_cohort.mob12.mix_channel_product_cohort` | `mart.vintage` (cột `origination_cohort`) | M08, M15 |
| 1, 2.2, 2.3 Tỷ số sản phẩm | `vintage.mob{6,12,24}.by_product`, `origination_cohort.mob{6,12,24}.product_ratio_vs_cash` | `mart.vintage` | M08 |
| 1, 2.4 Kênh có kiểm soát sản phẩm và đợt mở | `origination_cohort.mob{6,12,24}.smr_by_channel`, `origination_cohort.mob12.stone_vs_country_wide`, `origination_cohort.mob12.cards_by_channel_cohort` | `mart.vintage` | M08, M14 |
| 2.4 Tỷ lệ duyệt | `approval.within_product`, `approval.channel_standardized` | `mart.funnel_by_channel` | M12 |
| 2.4 Thẻ Stone so với Credit and cash offices | `review_checks.card_stone_vs_credit_cash_offices_mob12` | `mart.vintage` | M08 |
| 1, 2.5 Cure rate và tỷ lệ rơi nhóm | `roll_cure.primary.all`, `origination_cohort.cure_b1_vs_b2_by_cohort` | `mart.roll_rate` | M09, M10 |
| 2.6 Danh mục đang mở | `snapshot.kpi_same_set`, `snapshot.by_channel`, `review_checks.snapshot_by_product_channel`, `review_checks.snapshot_cash_loans_30_plus_timing` | `mart.portfolio_snapshot` | M06 |
| 3 Phân khúc cũ | `high_risk_segment`, `review_checks.segment_bonferroni_full_count_mob12` | `mart.vintage` | M08 |
| 3 FPD30 | `fpd30.total` | `mart.fpd_by_segment` | M11 |
| 4.2 Cỡ mẫu và chỉ tiêu sớm | `review_checks.sample_size_card_contact_center`, `review_checks.early_indicator_decomposition_consumer`, `sample_size` | `mart.vintage` | M13 |
| 4.3 Thử nghiệm thu hồi | `review_checks.collections_sample_size_by_contract` | `core.fct_loan_month` | M10 |
| 4.4, 5 Nhóm không khớp hồ sơ, KPI cùng tập | `review_checks.unknown_application_group`, `review_checks.snapshot_exposure_missing`, `review_checks.closed_inferred_consumer_cases_mob12`, `vintage.mob12.total_excluding_unknown_application` | `mart.vintage`, `mart.portfolio_snapshot` | M06, M08 |

Định nghĩa chỉ tiêu: [`metric_dictionary.md`](metric_dictionary.md). Phương pháp và giới hạn: [`methodology.md`](methodology.md). Giả định về dữ liệu: [`data_notes.md`](data_notes.md).
