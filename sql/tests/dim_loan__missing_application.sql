-- severity: warn
-- Hợp đồng có lịch sử tháng nhưng không tìm thấy trong previous_application,
-- nên thiếu thuộc tính kênh, sản phẩm khi phân khúc.
select sk_id_prev, sk_id_curr, source
from core.dim_loan
where not has_application
