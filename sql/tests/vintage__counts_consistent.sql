-- severity: error
-- Các cột đếm phải nhất quán: tử số không lớn hơn mẫu số, tỷ lệ nằm trong khoảng 0 đến 1,
-- số hợp đồng quan sát đủ cộng số tất toán sớm phải bằng mẫu số.
-- Định nghĩa chính (SK_DPD_DEF) bỏ qua khoản nợ nhỏ nên từng 30+ theo định nghĩa chính không thể
-- nhiều hơn từng 30+ theo SK_DPD (_no_threshold).
-- Độ nhạy thứ hai (_due_only): với thẻ phải trùng định nghĩa chính; với trả góp là tập con của
-- SK_DPD (_no_threshold) vì chỉ giữ tháng còn kỳ phải trả.
select *
from mart.vintage
where n_ever_30_plus > n_loans
   or n_ever_30_plus_no_threshold > n_loans
   or n_ever_30_plus > n_ever_30_plus_no_threshold
   or n_observed_full > n_loans
   or n_observed_full + n_closed_early <> n_loans
   or ever_30_plus_rate < 0 or ever_30_plus_rate > 1
   or ever_30_plus_rate_no_threshold < 0 or ever_30_plus_rate_no_threshold > 1
   or n_ever_30_plus_due_only > n_loans
   or (source = 'credit_card' and n_ever_30_plus_due_only <> n_ever_30_plus)
   or (source = 'pos_cash' and n_ever_30_plus_due_only > n_ever_30_plus_no_threshold)
   or n_loans <= 0
