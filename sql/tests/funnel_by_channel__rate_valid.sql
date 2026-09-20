-- severity: error
-- Tử số không được lớn hơn mẫu số, và mọi tỷ lệ phải nằm trong khoảng 0 đến 1.
select *
from mart.funnel_by_channel
where n_approved + n_unused_offer > n_decided
   or n_approved > n_offered
   or (approval_rate is not null and (approval_rate < 0 or approval_rate > 1))
   or (take_up_rate is not null and (take_up_rate < 0 or take_up_rate > 1))
