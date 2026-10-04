-- severity: error
-- Bắt buộc theo metric dictionary (M09): tổng tỷ lệ chuyển trạng thái của mỗi hàng ma trận phải bằng 1.
-- Nếu lệch, nghĩa là có dòng bị loại âm thầm (thường là các dòng không có tháng kế tiếp).
-- Dung sai 1e-9 cho sai số dấu phẩy động.
select
    source, contract_type, channel_type, from_state,
    sum(roll_rate) as total_rate,
    sum(n_loans)   as n_loans_sum,
    max(n_from)    as n_from
from mart.roll_rate
group by source, contract_type, channel_type, from_state
having abs(sum(roll_rate) - 1) > 1e-9
    or sum(n_loans) <> max(n_from)
