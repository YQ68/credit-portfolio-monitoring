-- severity: warn
-- Trạng thái hợp đồng chưa được phân loại mở hoặc đóng.
-- Nếu xuất hiện: cập nhật macro core.is_open_status (sql/00_setup.sql) và docs/metric_dictionary.md.
select source, contract_status, count(*) as n_rows
from core.int_loan_month
where contract_status is null
   or contract_status not in (
        'Active', 'Demand', 'Amortized debt',                       -- mở
        'Completed', 'Signed', 'Approved', 'Sent proposal',         -- đóng hoặc chưa mở
        'Refused', 'Canceled', 'Returned to the store', 'XNA'
   )
group by source, contract_status
