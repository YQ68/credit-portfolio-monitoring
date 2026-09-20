-- severity: error
-- Các cột đếm phải nhất quán: tỷ lệ trong khoảng 0 đến 1, tử số không lớn hơn mẫu số,
-- số dòng hở tháng và số dòng thiếu exposure không vượt quá số dòng của ô,
-- và hở tháng chỉ được xuất hiện ở trạng thái đích 'Missing'.
select *
from mart.roll_rate
where roll_rate < 0 or roll_rate > 1
   or n_loans > n_from
   or n_month_gap > n_loans
   or n_exposure_null > n_loans
   or (n_month_gap > 0 and to_state <> 'Missing')
   or coalesce(exposure_roll_rate, 0) < 0
   or coalesce(exposure_roll_rate, 0) > 1
   or exposure_from < 0
