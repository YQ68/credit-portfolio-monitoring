-- severity: error
-- Bắt buộc theo metric dictionary (M09): tổng tỷ lệ chuyển trạng thái của mỗi hàng ma trận phải bằng 1.
-- Nếu lệch, nghĩa là có dòng bị loại âm thầm (thường là các dòng không có tháng kế tiếp).
-- Kiểm cả bảng chính và bảng độ nhạy _no_threshold. Dung sai 1e-9 cho sai số dấu phẩy động.
with both_tables as (
    select 'roll_rate' as tbl, * from mart.roll_rate
    union all
    select 'roll_rate_no_threshold' as tbl, * from mart.roll_rate_no_threshold
)
select
    tbl, source, contract_type, channel_type, from_state,
    sum(roll_rate) as total_rate,
    sum(n_loans)   as n_loans_sum,
    max(n_from)    as n_from
from both_tables
group by tbl, source, contract_type, channel_type, from_state
having abs(sum(roll_rate) - 1) > 1e-9
    or sum(n_loans) <> max(n_from)
