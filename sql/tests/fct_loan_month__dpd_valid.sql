-- severity: error
-- DPD không âm, không NULL và luôn được gán bucket, ở cả định nghĩa chính (SK_DPD_DEF) và
-- định nghĩa độ nhạy (SK_DPD, hậu tố _no_threshold).
select sk_id_prev, months_balance, dpd, dpd_bucket, dpd_no_threshold, dpd_bucket_no_threshold
from core.fct_loan_month
where dpd is null or dpd < 0 or dpd_bucket is null
   or dpd_no_threshold is null or dpd_no_threshold < 0 or dpd_bucket_no_threshold is null
