-- severity: error
-- Mỗi hợp đồng chỉ có một dòng cho mỗi tháng.
select sk_id_prev, months_balance, count(*) as n_rows
from core.fct_loan_month
group by sk_id_prev, months_balance
having count(*) > 1
