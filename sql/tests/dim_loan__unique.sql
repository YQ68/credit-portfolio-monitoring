-- severity: error
-- Mỗi hợp đồng chỉ có một dòng trong dim_loan.
select sk_id_prev, count(*) as n_rows
from core.dim_loan
group by sk_id_prev
having count(*) > 1
