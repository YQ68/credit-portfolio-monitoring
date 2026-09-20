-- severity: error
-- DPD không âm, không NULL và luôn được gán bucket.
select sk_id_prev, months_balance, dpd, dpd_bucket
from core.fct_loan_month
where dpd is null or dpd < 0 or dpd_bucket is null
