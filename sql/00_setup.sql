-- Tạo schema theo tầng dữ liệu và các macro dùng chung.
--   raw  : dữ liệu gốc nạp từ CSV, không sửa
--   stg  : đổi tên cột, chuẩn hóa giá trị đặc biệt; mỗi bảng raw có một bảng stg
--   core : bảng dùng chung cho mọi phân tích (int, dim, fct)
--   mart : bảng tổng hợp cho từng câu hỏi phân tích và dashboard

create schema if not exists raw;
create schema if not exists stg;
create schema if not exists core;
create schema if not exists mart;

-- Trạng thái được coi là hợp đồng đang mở (còn nghĩa vụ trả nợ).
-- Định nghĩa gốc: docs/metric_dictionary.md, mục Quy ước chung.
create or replace macro core.is_open_status(status) as
    status in ('Active', 'Demand', 'Amortized debt');
