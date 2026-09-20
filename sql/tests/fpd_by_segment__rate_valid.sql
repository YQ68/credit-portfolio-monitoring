-- severity: error
-- Tử số không được lớn hơn mẫu số, và mọi tỷ lệ phải nằm trong khoảng 0 đến 1.
select *
from mart.fpd_by_segment
where n_fpd30 > n_loans
   or n_fpd30_late_rule > n_loans
   or (fpd30_rate is not null and (fpd30_rate < 0 or fpd30_rate > 1))
   or (fpd30_late_rule_rate is not null and (fpd30_late_rule_rate < 0 or fpd30_late_rule_rate > 1))
