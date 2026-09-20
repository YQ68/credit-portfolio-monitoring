-- severity: error
-- Các cột đếm phải nhất quán: tử số không lớn hơn mẫu số, tỷ lệ nằm trong khoảng 0 đến 1,
-- số hợp đồng quan sát đủ cộng số tất toán sớm phải bằng mẫu số.
select *
from mart.vintage
where n_ever_30_plus > n_loans
   or n_ever_30_plus_tolerant > n_loans
   or n_observed_full > n_loans
   or n_observed_full + n_closed_early <> n_loans
   or ever_30_plus_rate < 0 or ever_30_plus_rate > 1
   or ever_30_plus_rate_tolerant < 0 or ever_30_plus_rate_tolerant > 1
   or n_loans <= 0
