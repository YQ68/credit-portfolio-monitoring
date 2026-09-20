-- severity: error
-- is_partial_history phải bật cho mọi hợp đồng cắt trái hoặc đã trả kỳ ngay tại tháng mở đầu tiên.
-- Cờ này là bộ lọc của mart vintage, sai cờ là sai toàn bộ đường cong vintage.
select sk_id_prev, is_left_truncated, installments_paid_at_open, is_partial_history
from core.dim_loan
where is_partial_history is distinct from (is_left_truncated or coalesce(installments_paid_at_open, 0) > 0)
