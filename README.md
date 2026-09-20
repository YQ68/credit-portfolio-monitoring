# Credit Portfolio Monitoring

> Muốn hiểu cách làm chứ không chỉ xem kết quả: đọc [docs/walkthrough/00-tong-quan.md](docs/walkthrough/00-tong-quan.md).

Hệ thống giám sát chất lượng danh mục cho vay tiêu dùng, xây trên dữ liệu công khai **Home Credit Default Risk** (Kaggle). Project mô phỏng công việc của một Credit Risk Analyst:

- chuẩn hóa dữ liệu hợp đồng thành bảng snapshot theo tháng,
- định nghĩa metric thống nhất, có tài liệu,
- dùng các metric đó để phân tích delinquency, vintage, roll rate và rủi ro sớm theo kênh, sản phẩm.

## Câu hỏi kinh doanh

1. Kênh, sản phẩm nào có approval rate cao nhưng rủi ro sớm (FPD) cũng cao?
2. Khi so cùng MOB, nhóm hợp đồng nào xấu đi nhanh hơn?
3. Khách quá hạn chuyển bucket ra sao qua từng tháng? Bucket nào có cure rate thấp nhất và cần ưu tiên thu hồi?
4. Phân khúc nào nên siết hoặc nới chính sách?

## Kiến trúc dữ liệu

```
CSV (Kaggle)
 └─ raw    dữ liệu gốc, chỉ đổi tên cột sang chữ thường       scripts/load_raw.py
     └─ stg    đổi tên cột, xử lý giá trị đặc biệt              sql/stg/
         └─ core   bảng dùng chung                              sql/core/
             │     int_loan_month   gộp POS và thẻ, bỏ trùng
             │     dim_loan         1 dòng / hợp đồng: sản phẩm, kênh, mốc vòng đời
             │     fct_loan_month   1 dòng / hợp đồng / tháng: DPD, bucket, MOB, exposure
             └─ mart   bảng tổng hợp cho phân tích, dashboard     sql/mart/
```

Mỗi lần build đều chạy data test trong `sql/tests/`. Test mức `error` làm pipeline dừng, mức `warn` chỉ cảnh báo.

## Cài đặt và chạy

Yêu cầu: Python 3.10 trở lên, khoảng 5 GB ổ trống.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1      # nếu bị chặn: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt

kaggle auth login                 # đăng nhập Kaggle một lần
python scripts/download_data.py   # hoặc tải tay và giải nén CSV vào data/raw/
python scripts/load_raw.py        # CSV vào DuckDB
python scripts/build.py           # build stg, core, mart và chạy data test
python scripts/build_dashboard.py # dựng dashboard/index.html và xuất data/export/*.csv
python scripts/query.py sql/explore/01_profile.sql
```

Nếu đường dẫn thư mục project có dấu tiếng Việt (ví dụ thư mục có dấu), không cần chỉnh gì thêm: `scripts/download_data.py` đã tự ép Kaggle CLI chạy ở mã UTF-8 (biến môi trường `PYTHONUTF8`, `PYTHONIOENCODING`) để không lỗi khi in đường dẫn có dấu, và các script còn lại tự gọi `sys.stdout.reconfigure(encoding="utf-8")` khi in tiếng Việt ra console.

Để tự viết query: tạo file `.sql` và chạy bằng `python scripts/query.py <file>`, hoặc mở `data/warehouse.duckdb` bằng DBeaver.

## Cấu trúc thư mục

```
dashboard/
  index.html              dashboard tĩnh 4 trang, mở thẳng bằng trình duyệt, không cần server
  README.md                cách dựng lại dashboard bằng Power BI từ data/export/
powerbi/                  bản Power BI dạng PBIP: TMDL + PBIR, mở bằng CreditPortfolio.pbip
  README.md                cách mở, 3 lớp kiểm tra, quy tắc khi sửa
  _brief/report-spec.md    bản chốt thiết kế 4 trang
data/
  export/                  CSV xuất từ 4 mart, dùng cho Power BI (không commit, xem .gitignore)
docs/
  metric_dictionary.md    định nghĩa, công thức, edge case của mọi chỉ tiêu
  data_notes.md           cách hiểu dữ liệu, giả định, giới hạn
  insight_memo.md          memo 1 trang gửi ban lãnh đạo: 3 phát hiện chính kèm đề xuất hành động
  walkthrough/              9 file học từng bước cách làm project, đọc từ 00-tong-quan.md
scripts/
  download_data.py         tải dữ liệu từ Kaggle
  load_raw.py               nạp CSV vào DuckDB
  build.py                  chạy model SQL và data test
  build_dashboard.py        dựng dashboard/index.html và xuất data/export/*.csv
  query.py                   chạy một file SQL, in kết quả
sql/
  00_setup.sql             schema và macro dùng chung
  stg/  core/  mart/
  tests/                    data test, mỗi file trả về các dòng vi phạm
  explore/                   query khám phá dữ liệu
```

## Tiến độ

- [x] Nạp dữ liệu vào DuckDB
- [x] Tầng stg và core (`fct_loan_month`, `dim_loan`)
- [x] Data test cho grain, DPD, MOB, đối chiếu số dòng
- [x] Metric dictionary v0.2
- [x] Profile dữ liệu thật, xác nhận các giả định trong `docs/data_notes.md`
- [x] Mart: funnel và approval rate theo kênh
- [x] Mart: FPD30 theo kênh, sản phẩm
- [x] Mart: vintage ever 30+ theo MOB
- [x] Mart: roll rate và cure rate
- [x] Dashboard HTML tĩnh
- [x] Mart: ảnh chụp danh mục theo bucket (cho trang 1 bản Power BI)
- [x] Bản Power BI dạng PBIP trong `powerbi/`, ảnh từng trang trong `docs/screenshots/`
- [x] Memo insight 1 trang
- [x] Bộ tài liệu học từng bước trong `docs/walkthrough/`

## Kết quả chính

- **Khoảng cách rủi ro giữa các kênh nhỏ hơn nhiều so với con số thô, nhưng vẫn còn thật sau khi so trong cùng sản phẩm.** Trong vay tiêu dùng trả góp, kênh Stone có tỷ lệ hợp đồng từng quá hạn trên 30 ngày tại MOB 12 (month on book, tháng thứ 12 kể từ tháng mở hợp đồng) là 1,067% (1.445/135.415 hợp đồng), gấp 2,0 lần kênh Regional / Local (0,530%, 365/68.897); trong vay tiền mặt, kênh Country-wide 0,437% (78/17.844) gấp 4,4 lần Credit and cash offices (0,099%, 175/175.921).
- **Rủi ro dồn vào một nhóm nhỏ, phát hiện này đứng vững sau khi khử nhiễu cơ cấu sản phẩm.** Trong riêng vay tiêu dùng trả góp, nhóm hợp đồng của kênh Stone hoặc Country-wide, khách mới, nhóm lãi suất cao chiếm 14,0% mẫu số (64.462/459.716 hợp đồng) nhưng gánh 33,7% số hợp đồng từng quá hạn trên 30 ngày (1.373/4.071), tỷ lệ 2,130% gấp 3,1 lần phần vay tiêu dùng còn lại (0,683%).
- **Cửa sổ thu hồi nợ rất hẹp, đóng lại sau khoảng 30 ngày quá hạn đầu tiên.** Cure rate (tỷ lệ hợp đồng quá hạn quay về không quá hạn ngay tháng sau) của nhóm quá hạn 1-30 ngày là 50,1% (129.922/259.546 lượt hợp đồng-tháng), nhưng giảm còn 7,0% ở nhóm quá hạn 61-90 ngày (505/7.172).

Chi tiết đầy đủ, kèm đề xuất hành động và cách kiểm chứng bằng thử nghiệm: [docs/insight_memo.md](docs/insight_memo.md).

## Các quyết định quan trọng

- **Đổi cột DPD (days past due, số ngày quá hạn) chính từ `SK_DPD_DEF` sang `SK_DPD`.** Cột có dung sai làm tử số của mọi chỉ tiêu nợ xấu quá mỏng để cắt theo phân khúc, chỉ còn vài chục hợp đồng. Chi tiết: [docs/metric_dictionary.md](docs/metric_dictionary.md) mục Changelog, [docs/data_notes.md](docs/data_notes.md) mục 7.
- **Không dùng FPD30 (first payment default 30, kỳ trả đầu tiên chưa trả đủ sau 30 ngày) làm trục rủi ro để so sánh kênh.** Dữ liệu trả nợ gần như chỉ ghi kỳ đã trả nên khoảng 7,5% hồ sơ được duyệt biến mất khỏi mẫu số thay vì được tính là vỡ nợ (thiên lệch sống sót); FPD30 đo được chỉ là chặn dưới. Chi tiết: [docs/metric_dictionary.md](docs/metric_dictionary.md) mục M11, [docs/data_notes.md](docs/data_notes.md) mục 11.
- **Mẫu số vintage loại hợp đồng thiếu lịch sử đầu (cờ `is_partial_history`).** Hợp đồng bị cắt trái theo cửa sổ dữ liệu, hoặc đã trả kỳ ngay tại tháng mở đầu tiên, có MOB tính thấp hơn thực tế; giữ lại sẽ làm méo đường cong vintage. Chi tiết: [docs/metric_dictionary.md](docs/metric_dictionary.md) mục M08, [docs/data_notes.md](docs/data_notes.md) mục 6 và mục 11.
- **So sánh rủi ro giữa các kênh phải kiểm soát cơ cấu sản phẩm.** Mỗi kênh bán một rổ sản phẩm khác nhau, và bản thân sản phẩm đã chênh lệch rủi ro nhiều hơn chênh lệch giữa các kênh, nên so gộp sẽ nhầm nhiễu cơ cấu sản phẩm thành hiệu ứng kênh. Chi tiết: [docs/insight_memo.md](docs/insight_memo.md) mục 2.1, [docs/walkthrough/05-mart-vintage.md](docs/walkthrough/05-mart-vintage.md).

## Giới hạn

Dữ liệu dùng thời gian tương đối nên không dựng được vintage theo tháng lịch, và danh mục chỉ gồm các khoản vay trước đây của khách có hồ sơ mới. Chi tiết trong [docs/data_notes.md](docs/data_notes.md).
