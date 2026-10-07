# Ghi chú về dữ liệu

Giấy phép MIT trong [`LICENSE`](LICENSE) chỉ áp dụng cho mã nguồn của repo này, không áp
dụng cho dữ liệu.

Dữ liệu gốc thuộc cuộc thi
[Home Credit Default Risk](https://www.kaggle.com/competitions/home-credit-default-risk)
trên Kaggle và tuân theo điều khoản của cuộc thi đó. Repo không chứa dữ liệu thô. Muốn chạy
lại pipeline, tải dữ liệu từ Kaggle theo hướng dẫn trong [`README.md`](README.md).

Thư mục `data/export/` chỉ chứa các bảng tổng hợp theo phân khúc (kênh, sản phẩm, nhóm
khách, tuổi hợp đồng, nhóm quá hạn), không có cột định danh khách hàng hay hợp đồng. Một số
ô có số hợp đồng rất nhỏ; vì không có định danh nên không thể nối ngược về hợp đồng gốc.

Đây là project portfolio tự làm trên dữ liệu công khai, không phải số liệu của tổ chức nào.
Đơn vị tiền là đơn vị thô của bộ dữ liệu Kaggle, không phải VND.
