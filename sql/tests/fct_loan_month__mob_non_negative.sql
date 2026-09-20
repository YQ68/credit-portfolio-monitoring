-- severity: error
-- MOB bắt đầu từ 0 tại tháng mở và không bao giờ NULL.
select sk_id_prev, months_balance, mob
from core.fct_loan_month
where mob < 0 or mob is null
