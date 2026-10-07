-- severity: error
-- Bucket và cờ 30+, 90+ phải khớp đúng cột DPD của định nghĩa tương ứng:
-- cột chính theo dpd (SK_DPD_DEF), cột _no_threshold theo dpd_no_threshold (SK_DPD).
-- Bắt lỗi trộn hai định nghĩa trong cùng một dòng (ví dụ bucket theo cột này, cờ theo cột kia).
select sk_id_prev, months_balance, dpd, dpd_bucket_order, is_30_plus, is_90_plus,
       dpd_no_threshold, dpd_bucket_order_no_threshold, is_30_plus_no_threshold, is_90_plus_no_threshold
from core.fct_loan_month
where is_30_plus is distinct from (dpd > 30)
   or is_90_plus is distinct from (dpd > 90)
   or is_30_plus is distinct from (dpd_bucket_order >= 2)
   or is_90_plus is distinct from (dpd_bucket_order = 4)
   or (dpd_bucket_order = 0) is distinct from (dpd = 0)
   or is_30_plus_no_threshold is distinct from (dpd_no_threshold > 30)
   or is_90_plus_no_threshold is distinct from (dpd_no_threshold > 90)
   or is_30_plus_no_threshold is distinct from (dpd_bucket_order_no_threshold >= 2)
   or is_90_plus_no_threshold is distinct from (dpd_bucket_order_no_threshold = 4)
   or (dpd_bucket_order_no_threshold = 0) is distinct from (dpd_no_threshold = 0)
