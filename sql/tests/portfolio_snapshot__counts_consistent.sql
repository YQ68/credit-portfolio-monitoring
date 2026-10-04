-- severity: error
-- Các cột đếm phải nhất quán: số hợp đồng dương, số hợp đồng 30+ không âm và không vượt số hợp đồng,
-- dư nợ không âm, dư nợ 30+ không vượt dư nợ (dung sai 0,01 cho sai số dấu phẩy động khi cộng),
-- và cờ 30+ khớp với bucket: B0, B1 không có hợp đồng 30+, từ B2 trở lên thì toàn bộ là 30+
-- (30+ nghĩa là DPD lớn hơn 30).
select *
from mart.portfolio_snapshot
where n_loans <= 0
   or n_30_plus < 0
   or n_30_plus > n_loans
   or coalesce(exposure, 0) < 0
   or coalesce(exposure_30_plus, 0) < 0
   or coalesce(exposure_30_plus, 0) - coalesce(exposure, 0) > 0.01
   or (dpd_bucket_order <= 1 and n_30_plus <> 0)
   or (dpd_bucket_order >= 2 and n_30_plus <> n_loans)
